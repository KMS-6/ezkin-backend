from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.scan import SkinScan
from app.modules.reports.aggregator import aggregate_scans, check_eligibility


@pytest.fixture()
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


_DEFAULT_SCORES = {"flushing": 0.5, "oiliness": 0.3, "moisture": 0.6, "sensitivity": 0.2}
_UNSET = object()


def _make_scan(
    persona_id: str,
    created_at: datetime,
    scores: object = _UNSET,
) -> SkinScan:
    resolved = _DEFAULT_SCORES if scores is _UNSET else scores
    return SkinScan(
        persona_id=persona_id,
        capture_method="camera",
        status="completed",
        captured_at=created_at,
        created_at=created_at,
        scores=resolved,  # type: ignore[arg-type]
    )


def _dt(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 12, 0, 0, tzinfo=UTC)


class TestCheckEligibility:
    async def test_eligible_with_enough_scans(self, db_session: AsyncSession):
        today = date(2026, 8, 16)
        for i in range(14):
            d = date(2026, 8, 3 + i)
            db_session.add(_make_scan("persona_a1_seoyeon", _dt(d)))
        await db_session.commit()

        result = await check_eligibility(
            db_session, "persona_a1_seoyeon", period_days=14, as_of=today
        )
        assert result["eligible"] is True
        assert result["available_days"] >= 14
        assert result["required_days"] == 14

    async def test_not_eligible_insufficient_scans(self, db_session: AsyncSession):
        today = date(2026, 8, 16)
        for i in range(5):
            d = date(2026, 8, 11 + i)
            db_session.add(_make_scan("persona_a1_seoyeon", _dt(d)))
        await db_session.commit()

        result = await check_eligibility(
            db_session, "persona_a1_seoyeon", period_days=14, as_of=today
        )
        assert result["eligible"] is False
        assert result["available_days"] < 14

    async def test_missing_inputs_empty_when_eligible(self, db_session: AsyncSession):
        today = date(2026, 8, 16)
        for i in range(14):
            d = date(2026, 8, 3 + i)
            db_session.add(_make_scan("persona_a1_seoyeon", _dt(d)))
        await db_session.commit()

        result = await check_eligibility(
            db_session, "persona_a1_seoyeon", period_days=14, as_of=today
        )
        assert result["missing_inputs"] == []

    async def test_30day_requires_30_scans(self, db_session: AsyncSession):
        today = date(2026, 8, 16)
        # 14일치만 있음
        for i in range(14):
            d = date(2026, 8, 3 + i)
            db_session.add(_make_scan("persona_b1_eunji", _dt(d)))
        await db_session.commit()

        result = await check_eligibility(
            db_session, "persona_b1_eunji", period_days=30, as_of=today
        )
        assert result["eligible"] is False
        assert result["required_days"] == 30


class TestAggregateScans:
    async def test_returns_scores_per_day(self, db_session: AsyncSession):
        today = date(2026, 8, 16)
        for i in range(3):
            d = date(2026, 8, 14 + i)
            db_session.add(
                _make_scan("persona_a1_seoyeon", _dt(d), scores={"flushing": 0.4 + i * 0.1})
            )
        await db_session.commit()

        rows = await aggregate_scans(db_session, "persona_a1_seoyeon", period_days=14, as_of=today)
        assert len(rows) == 3
        assert all("metric_date" in r for r in rows)
        assert all("avg_scores" in r for r in rows)

    async def test_null_scores_scans_excluded(self, db_session: AsyncSession):
        today = date(2026, 8, 16)
        db_session.add(_make_scan("persona_a2_haneul", _dt(date(2026, 8, 15)), scores=None))
        db_session.add(
            _make_scan("persona_a2_haneul", _dt(date(2026, 8, 14)), scores={"flushing": 0.3})
        )
        await db_session.commit()

        rows = await aggregate_scans(db_session, "persona_a2_haneul", period_days=14, as_of=today)
        # null scores 스캔이 있는 날은 avg_scores가 없거나 해당 날짜만 건너뜀
        valid_rows = [r for r in rows if r["avg_scores"] is not None]
        assert len(valid_rows) == 1
