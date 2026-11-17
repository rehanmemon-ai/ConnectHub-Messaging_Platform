from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
)
_dummy_hash = _hasher.hash("connecthub-dummy-password-never-valid")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    target = password_hash or _dummy_hash
    try:
        valid = _hasher.verify(target, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False
    return bool(valid and password_hash is not None)


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)
