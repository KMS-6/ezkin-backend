import base64
import binascii
import hashlib
import hmac
import time
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode(value: str) -> bytes:
    decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if _encode(decoded) != value:
        # base64's trailing padding bits are ignored by the decoder, so a tampered
        # string can decode to the same bytes as a valid one unless we require the
        # canonical re-encoding to round-trip exactly.
        raise ValueError("non-canonical base64 encoding")
    return decoded


def create_access_token(user_id: UUID, issued_at: int | None = None) -> str:
    timestamp = int(time.time()) if issued_at is None else issued_at
    payload = f"{user_id}:{timestamp}".encode()
    signature = hmac.new(
        settings.auth_secret.get_secret_value().encode(), payload, hashlib.sha256
    ).digest()
    return f"{_encode(payload)}.{_encode(signature)}"


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="유효한 인증 정보가 필요합니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> UUID:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    try:
        payload_text, signature_text = credentials.credentials.split(".", 1)
        payload = _decode(payload_text)
        signature = _decode(signature_text)
        expected = hmac.new(
            settings.auth_secret.get_secret_value().encode(), payload, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        user_id_text, issued_at_text = payload.decode().split(":", 1)
        if int(time.time()) - int(issued_at_text) > settings.access_token_ttl_seconds:
            raise ValueError
        return UUID(user_id_text)
    except (binascii.Error, ValueError, UnicodeDecodeError):
        raise _unauthorized() from None
