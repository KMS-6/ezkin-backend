import json
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_auth import require_admin
from app.core.mock_persona import get_persona_id
from app.core.storage import save_upload
from app.db.session import get_db
from app.models.cosmetic_catalog import Ingredient, PersonaCosmetic
from app.modules.cosmetics_catalog.matching import load_ingredient_catalog, match_ingredient_risks
from app.modules.cosmetics_catalog.schemas import (
    CosmeticCreateResult,
    CosmeticListResponse,
    CosmeticOut,
    CosmeticUpdateIn,
    IngredientCreateIn,
    IngredientListResponse,
    IngredientOut,
)

router = APIRouter(tags=["cosmetics"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
PersonaId = Annotated[str, Depends(get_persona_id)]


def _to_out(cosmetic: PersonaCosmetic) -> CosmeticOut:
    return CosmeticOut(
        cosmetic_id=str(cosmetic.id),
        brand=cosmetic.brand,
        product_name=cosmetic.product_name,
        product_type=cosmetic.product_type,
        ingredients_raw=cosmetic.ingredients_raw,
        updated_at=cosmetic.updated_at,
    )


async def _owned_cosmetic(
    db: AsyncSession, cosmetic_id: uuid.UUID, persona_id: str
) -> PersonaCosmetic:
    cosmetic = await db.get(PersonaCosmetic, cosmetic_id)
    if cosmetic is None or cosmetic.persona_id != persona_id or cosmetic.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="화장품을 찾을 수 없습니다."
        )
    return cosmetic


@router.post("/cosmetics", response_model=CosmeticCreateResult, status_code=status.HTTP_201_CREATED)
async def create_cosmetic(
    db: DbSession,
    persona_id: PersonaId,
    brand: Annotated[str, Form()],
    product_name: Annotated[str, Form()],
    product_type: Annotated[str | None, Form()] = None,
    ingredients_raw: Annotated[str | None, Form()] = None,
    image: Annotated[UploadFile | None, File()] = None,
) -> CosmeticCreateResult:
    try:
        parsed_ingredients = json.loads(ingredients_raw) if ingredients_raw else None
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ingredients_raw는 JSON 배열이어야 합니다.",
        ) from exc

    image_key = await save_upload(image, "cosmetics") if image is not None else None

    cosmetic = PersonaCosmetic(
        persona_id=persona_id,
        brand=brand,
        product_name=product_name,
        product_type=product_type,
        ingredients_raw=parsed_ingredients,
        image_key=image_key,
    )
    db.add(cosmetic)
    await db.flush()

    catalog = await load_ingredient_catalog(db)
    matched_ids, risk_alerts = match_ingredient_risks(parsed_ingredients, catalog)
    await db.commit()

    return CosmeticCreateResult(
        cosmetic_id=str(cosmetic.id), matched_ingredients=matched_ids, risk_alerts=risk_alerts
    )


@router.get("/cosmetics", response_model=CosmeticListResponse)
async def list_cosmetics(db: DbSession, persona_id: PersonaId) -> CosmeticListResponse:
    result = await db.execute(
        select(PersonaCosmetic).where(
            PersonaCosmetic.persona_id == persona_id, PersonaCosmetic.deleted_at.is_(None)
        )
    )
    return CosmeticListResponse(items=[_to_out(item) for item in result.scalars()])


@router.patch("/cosmetics/{cosmetic_id}", response_model=CosmeticOut)
async def update_cosmetic(
    cosmetic_id: uuid.UUID, payload: CosmeticUpdateIn, db: DbSession, persona_id: PersonaId
) -> CosmeticOut:
    cosmetic = await _owned_cosmetic(db, cosmetic_id, persona_id)
    provided = payload.model_dump(exclude_unset=True)

    if "brand" in provided and provided["brand"] is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="brand는 null일 수 없습니다."
        )
    if "product_name" in provided and provided["product_name"] is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="product_name은 null일 수 없습니다.",
        )

    for field in ("brand", "product_name", "product_type", "ingredients_raw"):
        if field in provided:
            setattr(cosmetic, field, provided[field])

    await db.commit()
    await db.refresh(cosmetic)
    return _to_out(cosmetic)


@router.delete("/cosmetics/{cosmetic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cosmetic(cosmetic_id: uuid.UUID, db: DbSession, persona_id: PersonaId) -> None:
    cosmetic = await _owned_cosmetic(db, cosmetic_id, persona_id)
    cosmetic.deleted_at = datetime.now(UTC)
    await db.commit()


@router.get("/ingredients", response_model=IngredientListResponse)
async def list_ingredients(
    db: DbSession,
    persona_id: PersonaId,
    risk_level: Annotated[str | None, Query()] = None,
    target_concern: Annotated[str | None, Query()] = None,
) -> IngredientListResponse:
    stmt = select(Ingredient)
    if risk_level:
        stmt = stmt.where(Ingredient.risk_level == risk_level)
    if target_concern:
        stmt = stmt.where(Ingredient.target_concern.contains(target_concern))
    result = await db.execute(stmt)
    return IngredientListResponse(
        ingredients=[
            IngredientOut(
                id=i.id,
                name=i.name,
                risk_level=i.risk_level,
                target_concern=i.target_concern,
                description=i.description,
            )
            for i in result.scalars()
        ]
    )


@router.post(
    "/admin/ingredients",
    response_model=IngredientOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_ingredient(payload: IngredientCreateIn, db: DbSession) -> IngredientOut:
    result = await db.execute(select(Ingredient).where(Ingredient.name == payload.name.strip()))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="ingredient_already_exists: 이미 등록된 성분입니다.",
        )

    ingredient = Ingredient(
        id=f"ing_{uuid.uuid4().hex[:12]}",
        name=payload.name.strip(),
        risk_level=payload.risk_level,
        target_concern=payload.target_concern,
        description=payload.description,
    )
    db.add(ingredient)
    await db.commit()
    return IngredientOut(
        id=ingredient.id,
        name=ingredient.name,
        risk_level=ingredient.risk_level,
        target_concern=ingredient.target_concern,
        description=ingredient.description,
    )
