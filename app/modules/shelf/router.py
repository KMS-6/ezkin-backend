from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.db.session import get_db
from app.models.shelf import Cosmetic
from app.modules.shelf.schemas import (
    RegistrationSource,
    ShelfProductCreate,
    ShelfProductListResponse,
    ShelfProductResponse,
    ShelfProductUpdate,
)

router = APIRouter(prefix="/shelf/products", tags=["my-shelf"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]


async def _owned_product(db: AsyncSession, product_id: UUID, user_id: UUID) -> Cosmetic:
    result = await db.execute(
        select(Cosmetic).where(
            Cosmetic.id == product_id,
            Cosmetic.user_id == user_id,
            Cosmetic.deleted_at.is_(None),
        )
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="제품을 찾을 수 없습니다.")
    return product


@router.post("", response_model=ShelfProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ShelfProductCreate,
    db: DbSession,
    user_id: CurrentUserId,
) -> Cosmetic:
    product = Cosmetic(user_id=user_id, **payload.model_dump())
    if payload.registration_source == RegistrationSource.MANUAL:
        product.user_verified_at = datetime.now(UTC)
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


@router.get("", response_model=ShelfProductListResponse)
async def list_products(
    db: DbSession,
    user_id: CurrentUserId,
) -> ShelfProductListResponse:
    result = await db.execute(
        select(Cosmetic)
        .where(Cosmetic.user_id == user_id, Cosmetic.deleted_at.is_(None))
        .order_by(Cosmetic.created_at.desc())
    )
    return ShelfProductListResponse(items=list(result.scalars()))


@router.get("/{product_id}", response_model=ShelfProductResponse)
async def get_product(
    product_id: UUID,
    db: DbSession,
    user_id: CurrentUserId,
) -> Cosmetic:
    return await _owned_product(db, product_id, user_id)


@router.patch("/{product_id}", response_model=ShelfProductResponse)
async def update_product(
    product_id: UUID,
    payload: ShelfProductUpdate,
    db: DbSession,
    user_id: CurrentUserId,
) -> Cosmetic:
    product = await _owned_product(db, product_id, user_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    await db.commit()
    await db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    db: DbSession,
    user_id: CurrentUserId,
) -> Response:
    product = await _owned_product(db, product_id, user_id)
    product.deleted_at = datetime.now(UTC)
    product.is_active = False
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
