"""Optional encryption for sanitization_map.json (CLAUDE.md section 14):
the map contains original sensitive values in plain text, so --encrypt-map
lets the user protect it at rest with a password.
"""
from __future__ import annotations

import base64
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_KDF_ITERATIONS = 390_000
_SALT_SIZE = 16


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=_KDF_ITERATIONS)
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def encrypt_map_bytes(data: bytes, password: str) -> bytes:
    salt = os.urandom(_SALT_SIZE)
    key = _derive_key(password, salt)
    token = Fernet(key).encrypt(data)
    return salt + token


def decrypt_map_bytes(blob: bytes, password: str) -> bytes:
    salt, token = blob[:_SALT_SIZE], blob[_SALT_SIZE:]
    key = _derive_key(password, salt)
    try:
        return Fernet(key).decrypt(token)
    except InvalidToken as exc:
        raise ValueError("Incorrect password or corrupted mapping file") from exc
