"""Password hashing and verification via Argon2id (argon2-cffi).

Approved algorithm only; no custom cryptography. Hashes are never logged
and never returned by any API.
"""

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

# Established-library parameters (defaults); not custom crypto.
_hasher = PasswordHasher()

# Constant dummy hash used for unknown-email verification work so that
# authentication failures do not reveal account existence through an
# obvious fast-path timing difference. (Not claimed to be perfect timing
# equality.) Generated at import time — never a real credential.
DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(24))


def hash_password(plaintext: str) -> str:
    """Hash a plaintext password with Argon2id."""
    return _hasher.hash(plaintext)


def verify_password(plaintext: str, password_hash: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    try:
        return _hasher.verify(password_hash, plaintext)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def verify_dummy_for_unknown_email(plaintext: str) -> None:
    """Perform equivalent Argon2id verification work for unknown emails.

    Uses a constant dummy hash so the outward behavior of 'unknown email'
    matches 'wrong password' (generic 401) without an obvious fast-path
    difference. Perfect timing equality is NOT claimed.
    """
    verify_password(plaintext, DUMMY_HASH)
