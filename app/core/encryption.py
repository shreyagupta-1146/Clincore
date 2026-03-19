"""
app/core/encryption.py
───────────────────────
Application-layer AES-256-GCM encryption for sensitive data.

Why application-layer encryption in addition to DB encryption?
- Provides defense-in-depth: even if the DB encryption key is compromised,
  the message content is still protected by this layer.
- The encryption key is derived from the user's credentials, meaning
  the application server cannot read messages without the user's input.

For the competition MVP, we use a server-side key (DB_ENCRYPTION_KEY).
In production, this would use a hardware security module (HSM) or
AWS KMS / GCP Cloud KMS for key management.
"""

import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import settings


def _get_key() -> bytes:
    """Derive a 32-byte AES key from the configured encryption key."""
    key_material = settings.DB_ENCRYPTION_KEY.encode()
    # Use PBKDF2 to derive a proper 256-bit key
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"clinicore_static_salt_v1",  # In prod: use a per-user random salt
        iterations=100_000,
    )
    return kdf.derive(key_material)


def encrypt(plaintext: str) -> bytes:
    """
    Encrypt a string using AES-256-GCM.
    Returns: nonce (12 bytes) + ciphertext + tag (16 bytes), base64 encoded.
    """
    if not plaintext:
        return b""

    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit random nonce

    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

    # Prepend nonce to ciphertext for storage
    return base64.b64encode(nonce + ciphertext)


def decrypt(encrypted: bytes) -> str:
    """
    Decrypt AES-256-GCM encrypted bytes.
    Returns the original plaintext string.
    """
    if not encrypted:
        return ""

    key = _get_key()
    aesgcm = AESGCM(key)

    raw = base64.b64decode(encrypted)
    nonce = raw[:12]
    ciphertext = raw[12:]

    plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext_bytes.decode("utf-8")


def encrypt_for_storage(text: str) -> bytes:
    """Alias for encrypt — used when saving messages to DB."""
    return encrypt(text)


def decrypt_from_storage(data: bytes) -> str:
    """Alias for decrypt — used when reading messages from DB."""
    return decrypt(data)
