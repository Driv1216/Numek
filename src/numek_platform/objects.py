"""Immutable object storage.

Objects are written once and never modified. Integrity is established by
hashing the exact bytes that a reader consumes: :meth:`read_verified` loads the
object into memory, hashes that buffer and only then returns it for parsing.
There is no metadata-based trust and no window between check and use.

Physical keys are ``objects/<org>/<sha[:2]>/<sha>.<generation>``. Deduplication
reuses only *active* objects; any other state gets a new generation, so
reclaiming one generation can never delete bytes another generation needs.
"""
import hashlib
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from .errors import IntegrityFailure, PlatformError
from .fsutil import fsync_directory, open_private, private_directory

MAX_OBJECT_BYTES = 256 * 1024**2
CHUNK = 1024**2


@dataclass(frozen=True)
class Staged:
    path: Path
    sha256: str
    bytes: int


class LocalObjectStore:
    """Owner-only local filesystem implementation of the object-store contract."""

    def __init__(self, root, *, max_object_bytes=MAX_OBJECT_BYTES):
        self.root = private_directory(root)
        self.max_object_bytes = max_object_bytes
        private_directory(self.root / 'objects')
        private_directory(self.root / 'staging')

    # Keys --------------------------------------------------------------
    @staticmethod
    def physical_key(org_id, sha256, generation):
        if len(sha256) != 64 or any(c not in '0123456789abcdef' for c in sha256):
            raise PlatformError('Invalid object identity.', 'unknown_object')
        return f'objects/{uuid.UUID(str(org_id)).hex}/{sha256[:2]}/{sha256}.{int(generation)}'

    def _path(self, physical_key):
        parts = physical_key.split('/')
        if (len(parts) != 4 or parts[0] != 'objects' or any(not p or p in ('.', '..') for p in parts)):
            raise PlatformError('Invalid object location.', 'unknown_object')
        return self.root.joinpath(*parts)

    def staging_dir(self, job_id, fence):
        return self.root / 'staging' / f'{uuid.UUID(str(job_id)).hex}.{int(fence)}'

    # Writes ------------------------------------------------------------
    def write_staged(self, job_id, fence, chunks):
        """W1: stream bytes into this attempt's staging area; fsync; hash."""
        folder = private_directory(self.staging_dir(job_id, fence))
        path = folder / uuid.uuid4().hex
        digest, size = hashlib.sha256(), 0
        if isinstance(chunks, (bytes, bytearray, memoryview)):
            chunks = [bytes(chunks)]
        with open_private(path, 'xb') as stream:
            for chunk in chunks:
                size += len(chunk)
                if size > self.max_object_bytes:
                    stream.close()
                    path.unlink()
                    raise PlatformError('Object exceeds the configured size limit.', 'object_too_large')
                digest.update(chunk)
                stream.write(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        fsync_directory(folder)
        return Staged(path, digest.hexdigest(), size)

    def promote(self, staged, physical_key):
        """W3: move a staged file into its permanent key (after its row exists)."""
        target = self._path(physical_key)
        private_directory(target.parent)
        if target.exists():
            raise PlatformError('Object location is already occupied.', 'object_conflict')
        os.link(staged.path, target)  # never replaces an existing name
        staged.path.unlink()
        fsync_directory(target.parent)
        fsync_directory(staged.path.parent)

    # Reads -------------------------------------------------------------
    def read_verified(self, physical_key, sha256, size):
        """Return the object's bytes only if their SHA-256 and size match."""
        if size > self.max_object_bytes:
            raise PlatformError('Object exceeds the configured size limit.', 'object_too_large')
        try:
            with open_private(self._path(physical_key), 'rb') as stream:
                data = stream.read(size + 1)
        except FileNotFoundError as exc:
            raise IntegrityFailure('Stored evidence is missing.') from exc
        if len(data) != size or hashlib.sha256(data).hexdigest() != sha256:
            raise IntegrityFailure()
        return data

    def hash_existing(self, physical_key):
        """Rehash an object in chunks (scrubbing); returns (sha256, size)."""
        digest, size = hashlib.sha256(), 0
        with open_private(self._path(physical_key), 'rb') as stream:
            for block in iter(lambda: stream.read(CHUNK), b''):
                digest.update(block)
                size += len(block)
        return digest.hexdigest(), size

    def exists(self, physical_key):
        return self._path(physical_key).is_file()

    # Removal -----------------------------------------------------------
    def unlink(self, physical_key):
        """Idempotent removal of a reclaimed object."""
        path = self._path(physical_key)
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        fsync_directory(path.parent)
        return True

    def staging_attempts(self):
        """Yield (job_id, fence, path) for every staging directory."""
        for entry in (self.root / 'staging').iterdir():
            name = entry.name
            try:
                job_hex, fence = name.split('.')
                yield uuid.UUID(job_hex), int(fence), entry
            except ValueError:
                yield None, None, entry

    def remove_staging(self, path):
        if path.is_symlink():
            raise PlatformError('Unsafe staging entry.', 'unsafe_path')
        shutil.rmtree(path, ignore_errors=True)
