from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_auth import require_admin
from app.core.audit_log import write_audit_log
from app.core.idempotency import check_idempotency, store_idempotency
from app.core.mock_persona import get_persona_id
from app.db.session import get_db
from app.models.recommendation import Product
from app.modules.recommendations.logic import build_recommendations
from app.modules.recommendations.schemas import (
    ProductCreateIn,
    ProductListResponse,
    ProductOut,
    RecommendationListResponse,
    RecommendationOut,
)

router = APIRouter(tags=["recommendations"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
PersonaId = Annotated[str, Depends(get_persona_id)]


def _to_product_out(product: Product) -> ProductOut:
    return ProductOut(
        product_id=str(product.id),
        name=product.name,
        brand=product.brand,
        category=product.category,
        external_url=product.external_url,
        safety_policy_note=product.safety_policy_note,
    )


@router.get("/recommendations", response_model=RecommendationListResponse)
async def get_recommendations(db: DbSession, persona_id: PersonaId) -> RecommendationListResponse:
    items = await build_recommendations(db, persona_id)
    return RecommendationListResponse(recommendations=[RecommendationOut(**item) for item in items])


@router.post(
    "/admin/products",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_product(
    payload: ProductCreateIn,
    db: DbSession,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> ProductOut:
    idempotency_payload = payload.model_dump()
    cached = await check_idempotency(
        db,
        scope="admin:products:create",
        subject="admin",
        key=idempotency_key,
        payload=idempotency_payload,
    )
    if cached is not None:
        return ProductOut(**cached)

    result = await db.execute(
        select(Product).where(
            Product.brand == payload.brand.strip(), Product.name == payload.name.strip()
        )
    )
    if result.scalar_one_or_none() is not None:
        await write_audit_log(
            db,
            actor="admin",
            action="admin.products.create",
            resource_type="product",
            resource_id=None,
            result="conflict",
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="product_already_exists: 이미 등록된 제품입니다.",
        )
    product = Product(**payload.model_dump())
    db.add(product)
    await db.flush()

    await write_audit_log(
        db,
        actor="admin",
        action="admin.products.create",
        resource_type="product",
        resource_id=str(product.id),
        result="success",
    )

    response = _to_product_out(product)
    cached = await store_idempotency(
        db,
        scope="admin:products:create",
        subject="admin",
        key=idempotency_key,
        payload=idempotency_payload,
        response_status=status.HTTP_201_CREATED,
        response_body=response.model_dump(),
    )
    if cached is not None:
        return ProductOut(**cached)

    await db.commit()
    return response


@router.get(
    "/admin/products",
    response_model=ProductListResponse,
    dependencies=[Depends(require_admin)],
)
async def list_products(db: DbSession) -> ProductListResponse:
    result = await db.execute(select(Product))
    return ProductListResponse(items=[_to_product_out(product) for product in result.scalars()])
