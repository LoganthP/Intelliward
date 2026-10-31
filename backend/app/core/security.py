import hashlib
import hmac
import os
import struct
from datetime import timedelta

import jwt
from cryptography.fernet import Fernet

from .config import settings
from .timeutil import utcnow

_ITER = 200_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITER)
    return f"pbkdf2_sha256${_ITER}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, digest = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(dk.hex(), digest)
    except Exception:
        return False


def create_token(user_id: int, role: str) -> str:
    payload = {"sub": str(user_id), "role": role, "exp": utcnow() + timedelta(minutes=settings.jwt_expire_minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


_fernet: Fernet | None = None


def fernet() -> Fernet:
    """Fernet cipher used to encrypt face embeddings at rest."""
    global _fernet
    if _fernet is None:
        key = settings.embedding_key.strip()
        if not key:
            key_file = settings.data_path / "secret.key"
            if key_file.exists():
                key = key_file.read_text().strip()
            else:
                key = Fernet.generate_key().decode()
                key_file.write_text(key)
        _fernet = Fernet(key.encode())
    return _fernet


def encrypt_vector(vec: list[float]) -> str:
    return fernet().encrypt(struct.pack(f"<{len(vec)}f", *vec)).decode()


def decrypt_vector(token: str) -> list[float]:
    raw = fernet().decrypt(token.encode())
    return list(struct.unpack(f"<{len(raw) // 4}f", raw))
