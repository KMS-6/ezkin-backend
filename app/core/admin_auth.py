import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import settings


def get_admin(
    x_admin_key: Annotated[str | None, Header(alias="X-Admin-Key")] = None,
) -> None:
    if x_admin_key is None or not secrets.compare_digest(x_admin_key, settings.admin_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "forbidden"})
