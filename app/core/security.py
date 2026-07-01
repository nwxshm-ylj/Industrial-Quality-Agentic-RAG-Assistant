import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt import InvalidTokenError

from app.core.config import settings


PASSWORD_SCHEME = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600_000


def _encode_bytes(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_bytes(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("密码不能为空")

    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return "$".join([
        PASSWORD_SCHEME,
        str(PBKDF2_ITERATIONS),
        _encode_bytes(salt),
        _encode_bytes(digest),
    ])


def verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, iterations, encoded_salt, encoded_digest = password_hash.split(
            "$",
            3,
        )
        if scheme != PASSWORD_SCHEME:
            return False

        expected_digest = _decode_bytes(encoded_digest)
        actual_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            _decode_bytes(encoded_salt),
            int(iterations),
        )
        return hmac.compare_digest(actual_digest, expected_digest)
    except (TypeError, ValueError):
        return False


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
) -> str:
    payload: dict[str, Any] = data.copy()
    now = datetime.now(timezone.utc)
    expires_at = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload.update({
        "iat": now,
        "exp": expires_at,
    })
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except InvalidTokenError as exc:
        raise ValueError("访问令牌无效或已过期") from exc
