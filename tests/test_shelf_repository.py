from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.shelf import Cosmetic
from app.models.user import User


@pytest.mark.asyncio
async def test_shelf_product_can_be_created_and_soft_deleted() -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid4()
    async with session_factory() as session:
        session.add(User(id=user_id, email="test@example.com", nickname="테스터"))
        product = Cosmetic(
            user_id=user_id,
            brand="AAC",
            product_name="보습 크림",
            product_type="moisturizer",
            registration_source="manual",
            user_verified_at=datetime.now(UTC),
        )
        session.add(product)
        await session.commit()

        product.deleted_at = datetime.now(UTC)
        product.is_active = False
        await session.commit()

        active_products = await session.scalars(
            select(Cosmetic).where(
                Cosmetic.user_id == user_id,
                Cosmetic.deleted_at.is_(None),
            )
        )
        assert list(active_products) == []

    await engine.dispose()
