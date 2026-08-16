from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.scan import SkinScan


@pytest.fixture()
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def test_skin_scan_camera_defaults(db_session: AsyncSession) -> None:
    scan = SkinScan(
        persona_id="persona_a1_seoyeon",
        capture_method="camera",
        image_key="uploads/test.jpg",
        failure={"code": "model_not_implemented", "message": "...", "retryable": False},
        status="failed",
        idempotency_key="key-001",
        idempotency_payload_hash="abc123",
    )
    db_session.add(scan)
    await db_session.commit()
    await db_session.refresh(scan)

    assert scan.id is not None
    assert scan.persona_id == "persona_a1_seoyeon"
    assert scan.capture_method == "camera"
    assert scan.status == "failed"
    assert scan.lower_accuracy is False
    assert scan.scores is None
    assert scan.failure["code"] == "model_not_implemented"
    assert scan.created_at is not None


async def test_skin_scan_questionnaire(db_session: AsyncSession) -> None:
    answers = {"redness": "mild", "tightness": "moderate", "oiliness": "none", "new_lesions": False}
    scan = SkinScan(
        persona_id="persona_b1_eunji",
        capture_method="questionnaire",
        questionnaire_answers=answers,
        scores={"redness": 0.3, "dryness": 0.6, "oiliness": 0.0},
        status="completed",
        lower_accuracy=True,
    )
    db_session.add(scan)
    await db_session.commit()
    await db_session.refresh(scan)

    assert scan.status == "completed"
    assert scan.lower_accuracy is True
    assert scan.scores["redness"] == 0.3
    assert scan.questionnaire_answers["redness"] == "mild"


async def test_skin_scan_unique_constraint(db_session: AsyncSession) -> None:
    from sqlalchemy.exc import IntegrityError

    scan1 = SkinScan(
        persona_id="persona_uq",
        capture_method="camera",
        idempotency_key="key-same",
    )
    db_session.add(scan1)
    await db_session.commit()

    scan2 = SkinScan(
        persona_id="persona_uq",
        capture_method="camera",
        idempotency_key="key-same",
    )
    db_session.add(scan2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
