import hmac
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import settings


async def require_partner_key(x_partner_key: Annotated[str | None, Header()] = None) -> None:
    expected = settings.partner_api_key.get_secret_value()
    if not x_partner_key or not hmac.compare_digest(x_partner_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효한 X-Partner-Key가 필요합니다.",
            headers={"WWW-Authenticate": 'ApiKey realm="partner"'},
        )
