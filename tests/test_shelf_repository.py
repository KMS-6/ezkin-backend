from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shelf import Cosmetic
from app.models.user import User


async def test_shelf_product_can_be_created_and_soft_deleted(
    db_session: AsyncSession,
) -> None:
    user = User(email="test@example.com", nickname="테스터")
    db_session.add(user)
    await db_session.flush()

    product = Cosmetic(
        user_id=user.id,
        brand="AAC",
        product_name="보습 크림",
        product_type="moisturizer",
        registration_source="manual",
        user_verified_at=datetime.now(UTC),
    )
    db_session.add(product)
    await db_session.commit()

    product.deleted_at = datetime.now(UTC)
    product.is_active = False
    await db_session.commit()

    active_products = await db_session.scalars(
        select(Cosmetic).where(
            Cosmetic.user_id == user.id,
            Cosmetic.deleted_at.is_(None),
        )
    )
    assert list(active_products) == []
