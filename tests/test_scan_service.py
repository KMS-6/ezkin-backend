from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.modules.scans.schemas import CaptureMethod, QuestionnaireAnswers, SkinScanCreate
from app.modules.scans.service import create_scan, get_scan, list_scans


@pytest.fixture()
async def db() -> AsyncIterator[AsyncSession]:
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


async def test_camera_scan_creates_failed_status(db: AsyncSession) -> None:
    payload = SkinScanCreate(capture_method=CaptureMethod.CAMERA, image_key="uploads/a.jpg")
    scan, is_new = await create_scan(db, "persona_a1_seoyeon", payload, "key-001")

    assert is_new is True
    assert scan.status == "failed"
    assert scan.failure["code"] == "model_not_implemented"
    assert scan.failure["retryable"] is False
    assert scan.lower_accuracy is False
    assert scan.scores is None


async def test_questionnaire_scan_creates_completed_with_scores(db: AsyncSession) -> None:
    answers = QuestionnaireAnswers(
        redness="mild", tightness="moderate", oiliness="none", new_lesions=False
    )
    payload = SkinScanCreate(capture_method=CaptureMethod.QUESTIONNAIRE, answers=answers)
    scan, is_new = await create_scan(db, "persona_b1_eunji", payload, "key-002")

    assert is_new is True
    assert scan.status == "completed"
    assert scan.lower_accuracy is True
    assert scan.scores["redness"] == 0.3  # mild
    assert scan.scores["dryness"] == 0.6  # tightness → dryness, moderate
    assert scan.scores["oiliness"] == 0.0  # none


async def test_idempotency_same_key_same_payload_returns_same_scan(db: AsyncSession) -> None:
    payload = SkinScanCreate(capture_method=CaptureMethod.CAMERA, image_key="uploads/b.jpg")
    scan1, is_new1 = await create_scan(db, "persona_a1_seoyeon", payload, "key-idem")
    scan2, is_new2 = await create_scan(db, "persona_a1_seoyeon", payload, "key-idem")

    assert is_new1 is True
    assert is_new2 is False
    assert scan1.id == scan2.id


async def test_idempotency_same_key_different_payload_raises(db: AsyncSession) -> None:
    payload1 = SkinScanCreate(capture_method=CaptureMethod.CAMERA, image_key="uploads/c.jpg")
    payload2 = SkinScanCreate(capture_method=CaptureMethod.CAMERA, image_key="uploads/d.jpg")

    await create_scan(db, "persona_a1_seoyeon", payload1, "key-conflict")
    with pytest.raises(ValueError, match="idempotency_conflict"):
        await create_scan(db, "persona_a1_seoyeon", payload2, "key-conflict")


async def test_get_scan_returns_none_for_other_persona(db: AsyncSession) -> None:
    payload = SkinScanCreate(capture_method=CaptureMethod.CAMERA, image_key="uploads/e.jpg")
    scan, _ = await create_scan(db, "persona_a1_seoyeon", payload, "key-003")

    result = await get_scan(db, scan.id, "persona_b1_eunji")
    assert result is None


async def test_list_scans_pagination(db: AsyncSession) -> None:
    for i in range(5):
        payload = SkinScanCreate(capture_method=CaptureMethod.CAMERA, image_key=f"uploads/{i}.jpg")
        await create_scan(db, "persona_c1_minjun", payload, f"key-list-{i}")

    items, next_cursor = await list_scans(db, "persona_c1_minjun", limit=3)
    assert len(items) == 3
    assert next_cursor is not None

    items2, next_cursor2 = await list_scans(db, "persona_c1_minjun", limit=3, cursor=next_cursor)
    assert len(items2) == 2
    assert next_cursor2 is None


async def test_create_scan_integrity_error_recovery(db: AsyncSession) -> None:
    # 최초 생성
    payload = SkinScanCreate(capture_method=CaptureMethod.CAMERA, image_key="uploads/race.jpg")
    scan1, is_new1 = await create_scan(db, "persona_race", payload, "key-race")
    assert is_new1 is True

    # commit 시점에 IntegrityError가 발생하도록 mock
    from unittest.mock import patch

    from sqlalchemy.exc import IntegrityError

    with patch.object(db, "commit", side_effect=IntegrityError("duplicate", None, None)):
        scan2, is_new2 = await create_scan(db, "persona_race", payload, "key-race")
        assert is_new2 is False
        assert scan2.id == scan1.id


async def test_list_scans_invalid_cursor_ignored(db: AsyncSession) -> None:
    for i in range(2):
        payload = SkinScanCreate(capture_method=CaptureMethod.CAMERA, image_key=f"uploads/{i}.jpg")
        await create_scan(db, "persona_invalid_cursor", payload, f"key-inv-{i}")

    items, _ = await list_scans(
        db, "persona_invalid_cursor", limit=10, cursor="invalid-not-base64?!"
    )
    assert len(items) == 2
