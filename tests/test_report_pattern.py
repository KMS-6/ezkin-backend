from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.scan import SkinScan
from app.modules.reports.pattern import analyze_pattern


@pytest.fixture()
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _dt(d: date, hour: int = 12) -> datetime:
    return datetime(d.year, d.month, d.day, hour, 0, 0, tzinfo=UTC)


async def _add_scan(
    db: AsyncSession,
    persona_id: str,
    created_at: datetime,
    status: str = "completed",
    scores: dict | None = None,
) -> SkinScan:
    scan = SkinScan(
        persona_id=persona_id,
        capture_method="camera",
        status=status,
        created_at=created_at,
        scores=scores,
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)
    return scan


class TestAnalyzePattern:
    async def test_scan_not_found_raises_404(self, db_session: AsyncSession):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await analyze_pattern(db_session, "persona_a1_seoyeon", uuid4())
        assert exc_info.value.status_code == 404

    async def test_scan_with_null_scores_raises_409(self, db_session: AsyncSession):
        from fastapi import HTTPException

        scan = await _add_scan(
            db_session,
            "persona_a1_seoyeon",
            _dt(date(2026, 8, 15)),
            status="completed",
            scores=None,
        )

        with pytest.raises(HTTPException) as exc_info:
            await analyze_pattern(db_session, "persona_a1_seoyeon", scan.id)
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "scan_has_no_scores"

    async def test_raw_facts_returned(self, db_session: AsyncSession):
        center = date(2026, 8, 15)
        scan = await _add_scan(
            db_session,
            "persona_a1_seoyeon",
            _dt(center),
            scores={"flushing": 0.7},
        )
        # 주변 스캔 추가 (72시간 내)
        for i in range(3):
            await _add_scan(
                db_session,
                "persona_a1_seoyeon",
                _dt(center) - timedelta(hours=24 * (i + 1)),
                scores={"flushing": 0.3 + i * 0.1},
            )

        result = await analyze_pattern(db_session, "persona_a1_seoyeon", scan.id)
        assert "raw_facts" in result
        assert isinstance(result["raw_facts"], list)
        assert result["disclaimer"] is not None

    async def test_observed_pattern_null_when_below_threshold(self, db_session: AsyncSession):
        """동시발생 3회 미만이면 observed_pattern: null (center 1개 + 주변 1개 = 총 2회)"""
        center = date(2026, 8, 15)
        scan = await _add_scan(
            db_session,
            "persona_b1_eunji",
            _dt(center),
            scores={"flushing": 0.7},
        )
        # 72시간 내 스캔 1개만 추가 → center 포함 총 2회 (임계값 3 미만)
        await _add_scan(
            db_session,
            "persona_b1_eunji",
            _dt(center) - timedelta(hours=20),
            scores={"flushing": 0.6},
        )

        result = await analyze_pattern(db_session, "persona_b1_eunji", scan.id)
        assert result["observed_pattern"] is None

    async def test_observed_pattern_detected_when_threshold_met(self, db_session: AsyncSession):
        """동시발생 3회 이상이면 observed_pattern 문자열 반환"""
        center = date(2026, 8, 15)
        scan = await _add_scan(
            db_session,
            "persona_b1_eunji",
            _dt(center),
            scores={"flushing": 0.7},
        )
        for i in range(2):
            await _add_scan(
                db_session,
                "persona_b1_eunji",
                _dt(center) - timedelta(hours=10 * (i + 1)),
                scores={"flushing": 0.6},
            )

        result = await analyze_pattern(db_session, "persona_b1_eunji", scan.id)
        assert result["observed_pattern"] is not None
        assert "3회 관찰" in result["observed_pattern"]

    async def test_common_knowledge_is_null(self, db_session: AsyncSession):
        center = date(2026, 8, 15)
        scan = await _add_scan(
            db_session,
            "persona_a2_haneul",
            _dt(center),
            scores={"flushing": 0.7},
        )

        result = await analyze_pattern(db_session, "persona_a2_haneul", scan.id)
        assert result["common_knowledge"] is None

    async def test_window_is_72h(self, db_session: AsyncSession):
        center = date(2026, 8, 15)
        scan = await _add_scan(
            db_session,
            "persona_c1_minjun",
            _dt(center),
            scores={"flushing": 0.5},
        )

        result = await analyze_pattern(db_session, "persona_c1_minjun", scan.id)
        assert result["window"] == "72h"
