import hmac
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import settings


async def require_admin(x_admin_key: Annotated[str | None, Header()] = None) -> None:
    expected = settings.admin_api_key.get_secret_value()
    if not x_admin_key or not hmac.compare_digest(x_admin_key, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다.",
        )
