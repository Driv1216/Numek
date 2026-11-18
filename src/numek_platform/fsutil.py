"""Owner-only filesystem helpers (the same rules as the v2 catalog)."""
import os
import stat
from pathlib import Path

from .errors import PlatformError


def fsync_directory(path):
    if os.name != 'nt':
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def private_directory(path):
    """Create or validate a 0700 directory owned by this user, with no symlinks."""
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink():
            raise PlatformError('Platform paths must not contain symbolic links.', 'unsafe_path')
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    if not path.is_dir() or (hasattr(os, 'getuid') and path.stat().st_uid != os.getuid()):
        raise PlatformError('Platform directory ownership differs.', 'unsafe_path')
    os.chmod(path, 0o700)
    return path


def open_private(path, mode='rb'):
    """Open an owner-only regular file without following links.

    ``mode`` is ``'rb'`` or ``'xb'`` (exclusive create with 0600).
    """
    flags = getattr(os, 'O_NOFOLLOW', 0)
    if mode == 'xb':
        flags |= os.O_WRONLY | os.O_CREAT | os.O_EXCL
    elif mode == 'rb':
        flags |= os.O_RDONLY
    else:
        raise ValueError(mode)
    try:
        fd = os.open(path, flags, 0o600)
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise PlatformError('Protected file could not be opened safely.', 'unsafe_path') from exc
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o077
            or (hasattr(os, 'getuid') and info.st_uid != os.getuid())):
        os.close(fd)
        raise PlatformError('Protected file ownership or permissions differ.', 'unsafe_path')
    return os.fdopen(fd, mode)


def write_atomic(path, data):
    """Durably replace ``path`` with ``data`` (0600), via fsync + rename."""
    path = Path(path)
    tmp = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    try:
        tmp.unlink()
    except FileNotFoundError:
        pass
    with open_private(tmp, 'xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
    fsync_directory(path.parent)
