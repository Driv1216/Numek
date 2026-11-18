"""Secrets, data keys and backup keyrings.

* :class:`FileSecretStore` keeps operator secrets in an owner-only directory.
  Secrets are never stored in the database or returned by the API.
* :class:`DataKeys` manages AES-256-GCM data keys (for example for raw
  ingestion batches). ``destroy_live`` removes the live key only; data is
  *deleted* only once every backup keyring containing the key has also been
  destroyed or expired, and status reporting says so.
* Keyrings wrap selected data keys with a key derived (scrypt) from an operator
  backup passphrase.
"""
import json
import re
import secrets as _secrets
import uuid

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .errors import PlatformError
from .fsutil import open_private, private_directory, write_atomic

NAME = re.compile(r'^[a-z0-9][a-z0-9._/-]{0,200}$')
ENVELOPE_MAGIC = b'NMKE1'
KEYRING_MAGIC = b'NMKR1'


class FileSecretStore:
    def __init__(self, root):
        self.root = private_directory(root)

    def _path(self, name):
        if not NAME.match(name) or '..' in name.split('/'):
            raise PlatformError('Invalid secret name.', 'invalid_secret')
        return self.root.joinpath(*name.split('/'))

    def put(self, name, data):
        path = self._path(name)
        private_directory(path.parent)
        write_atomic(path, data)

    def get(self, name):
        try:
            with open_private(self._path(name), 'rb') as stream:
                return stream.read()
        except FileNotFoundError:
            raise PlatformError('Required secret is missing.', 'secret_missing') from None

    def exists(self, name):
        return self._path(name).is_file()

    def delete(self, name):
        try:
            self._path(name).unlink()
            return True
        except FileNotFoundError:
            return False


def _key_name(org_id, key_id):
    return f'datakeys/{uuid.UUID(str(org_id)).hex}/{uuid.UUID(str(key_id)).hex}'


class DataKeys:
    def __init__(self, secret_store):
        self.secrets = secret_store

    def create(self, conn, scope, purpose):
        key_id = uuid.uuid4()
        self.secrets.put(_key_name(scope.org_id, key_id), AESGCM.generate_key(bit_length=256))
        conn.execute("INSERT INTO key_records(org_id, key_id, purpose, state) VALUES (%s, %s, %s, 'active')",
                     (scope.org_id, key_id, purpose))
        return key_id

    def encrypt(self, scope, key_id, plaintext, aad=b''):
        key = self.secrets.get(_key_name(scope.org_id, key_id))
        nonce = _secrets.token_bytes(12)
        return ENVELOPE_MAGIC + uuid.UUID(str(key_id)).bytes + nonce + AESGCM(key).encrypt(nonce, plaintext, aad)

    def decrypt(self, scope, envelope, aad=b''):
        if envelope[:5] != ENVELOPE_MAGIC:
            raise PlatformError('Unrecognised encrypted object.', 'evidence_corrupt')
        key_id = uuid.UUID(bytes=envelope[5:21])
        key = self.secrets.get(_key_name(scope.org_id, key_id))
        try:
            return AESGCM(key).decrypt(envelope[21:33], envelope[33:], aad)
        except Exception as exc:
            raise PlatformError('Encrypted object failed authentication.', 'evidence_corrupt') from exc

    def destroy_live(self, conn, scope, key_id):
        """Destroy the live key. Backups that contain it can still decrypt until they expire."""
        self.secrets.delete(_key_name(scope.org_id, key_id))
        conn.execute("UPDATE key_records SET state = 'destroyed_live', destroyed_at = now() WHERE org_id = %s AND key_id = %s",
                     (scope.org_id, key_id))

    def available(self, scope, key_id):
        return self.secrets.exists(_key_name(scope.org_id, key_id))


def _kdf(passphrase, salt):
    if len(passphrase) < 12:
        raise PlatformError('Backup passphrases must have at least 12 characters.', 'weak_password')
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(passphrase.encode())


def export_keyring(secret_store, entries, passphrase):
    """Wrap {(org_id, key_id)} keys for a backup. Refuses if any key is missing."""
    keys = {}
    for org_id, key_id in entries:
        name = _key_name(org_id, key_id)
        if not secret_store.exists(name):
            raise PlatformError('A key required by the backup is missing or destroyed.', 'backup_key_missing')
        keys[name] = secret_store.get(name).hex()
    salt, nonce = _secrets.token_bytes(16), _secrets.token_bytes(12)
    body = json.dumps({'keys': keys}, sort_keys=True).encode()
    return KEYRING_MAGIC + salt + nonce + AESGCM(_kdf(passphrase, salt)).encrypt(nonce, body, KEYRING_MAGIC)


def import_keyring(secret_store, blob, passphrase):
    if blob[:5] != KEYRING_MAGIC:
        raise PlatformError('Unrecognised keyring.', 'backup_invalid')
    salt, nonce = blob[5:21], blob[21:33]
    try:
        body = AESGCM(_kdf(passphrase, salt)).decrypt(nonce, blob[33:], KEYRING_MAGIC)
    except Exception as exc:
        raise PlatformError('The backup passphrase is wrong or the keyring is damaged.', 'backup_invalid') from exc
    keys = json.loads(body)['keys']
    for name, value in keys.items():
        secret_store.put(name, bytes.fromhex(value))
    return len(keys)
