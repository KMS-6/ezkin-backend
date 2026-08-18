from datetime import UTC, date, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.persona import Persona
from app.models.scan import SkinScan

PERSONA = "persona_a1_seoyeon"
HEADERS = {"X-Mock-Persona-Id": PERSONA}


@pytest.fixture()
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        s.add(Persona(id=PERSONA, label="테스트 페르소나", summary_traits={}))
        s.add(Persona(id="persona_b1_eunji", label="테스트 페르소나2", summary_traits={}))
        await s.commit()
        yield s
    await engine.dispose()


@pytest.fixture()
async def client(db_session: AsyncSession):
    async def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _dt(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 12, 0, 0, tzinfo=UTC)


async def _seed_scans(db: AsyncSession, persona_id: str, count: int, base: date | None = None):
    if base is None:
        base = date.today()
    for i in range(count):
        d = base - __import__("datetime").timedelta(days=i)
        db.add(
            SkinScan(
                persona_id=persona_id,
                capture_method="camera",
                status="completed",
                captured_at=_dt(d),
                created_at=_dt(d),
                scores={"flushing": 0.4, "oiliness": 0.3, "moisture": 0.6, "sensitivity": 0.2},
            )
        )
    await db.commit()


class TestEligibility:
    async def test_eligible_true_with_enough_scans(self, client, db_session):
        await _seed_scans(db_session, PERSONA, 14)
        resp = await client.get("/api/v1/analysis/eligibility", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["eligible"] is True
        assert body["required_days"] == 14

    async def test_eligible_false_insufficient(self, client, db_session):
        await _seed_scans(db_session, PERSONA, 5)
        resp = await client.get("/api/v1/analysis/eligibility", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["eligible"] is False

    async def test_period_days_param(self, client, db_session):
        await _seed_scans(db_session, PERSONA, 14)
        resp = await client.get("/api/v1/analysis/eligibility?period_days=30", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["required_days"] == 30
        assert body["eligible"] is False  # 14일치만 있음


class TestCreateReport:
    async def test_returns_202_when_eligible(self, client, db_session):
        await _seed_scans(db_session, PERSONA, 14)
        resp = await client.post(
            "/api/v1/reports",
            json={"period_days": 14},
            headers=HEADERS,
        )
        assert resp.status_code == 202
        body = resp.json()
        assert "report_id" in body
        assert body["status"] in ("processing", "completed")

    async def test_returns_409_when_insufficient(self, client, db_session):
        await _seed_scans(db_session, PERSONA, 3)
        resp = await client.post(
            "/api/v1/reports",
            json={"period_days": 14},
            headers=HEADERS,
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "insufficient_data_history"

    async def test_status_url_in_response(self, client, db_session):
        await _seed_scans(db_session, PERSONA, 14)
        resp = await client.post(
            "/api/v1/reports",
            json={"period_days": 14},
            headers=HEADERS,
        )
        body = resp.json()
        assert body["status_url"].startswith("/api/v1/reports/")


class TestGetReport:
    async def test_get_completed_report(self, client, db_session):
        await _seed_scans(db_session, PERSONA, 14)
        create_resp = await client.post(
            "/api/v1/reports",
            json={"period_days": 14},
            headers=HEADERS,
        )
        report_id = create_resp.json()["report_id"]

        resp = await client.get(f"/api/v1/reports/{report_id}", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["report_id"] == report_id
        assert body["status"] == "completed"
        assert "summary" in body
        assert "observations" in body
        assert body["safety_status"] == "wellness_only"

    async def test_get_report_not_found(self, client):
        resp = await client.get(
            "/api/v1/reports/00000000-0000-0000-0000-000000000000",
            headers=HEADERS,
        )
        assert resp.status_code == 404

    async def test_other_persona_cannot_access_report(self, client, db_session):
        await _seed_scans(db_session, PERSONA, 14)
        create_resp = await client.post(
            "/api/v1/reports",
            json={"period_days": 14},
            headers=HEADERS,
        )
        report_id = create_resp.json()["report_id"]

        # 다른 페르소나로 조회 시 404
        resp = await client.get(
            f"/api/v1/reports/{report_id}",
            headers={"X-Mock-Persona-Id": "persona_b1_eunji"},
        )
        assert resp.status_code == 404


class TestPatternAnalysis:
    async def test_scan_not_found_returns_404(self, client):
        resp = await client.get(
            "/api/v1/pattern-analysis?scan_id=00000000-0000-0000-0000-000000000000",
            headers=HEADERS,
        )
        assert resp.status_code == 404

    async def test_scan_with_null_scores_returns_409(self, client, db_session):
        scan = SkinScan(
            persona_id=PERSONA,
            capture_method="camera",
            status="completed",
            captured_at=_dt(date(2026, 8, 15)),
            created_at=_dt(date(2026, 8, 15)),
            scores=None,
        )
        db_session.add(scan)
        await db_session.commit()
        await db_session.refresh(scan)

        resp = await client.get(
            f"/api/v1/pattern-analysis?scan_id={scan.id}",
            headers=HEADERS,
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "scan_has_no_scores"

    async def test_pattern_analysis_returns_schema(self, client, db_session):
        scan = SkinScan(
            persona_id=PERSONA,
            capture_method="camera",
            status="completed",
            captured_at=_dt(date(2026, 8, 15)),
            created_at=_dt(date(2026, 8, 15)),
            scores={"flushing": 0.6},
        )
        db_session.add(scan)
        await db_session.commit()
        await db_session.refresh(scan)

        resp = await client.get(
            f"/api/v1/pattern-analysis?scan_id={scan.id}",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["window"] == "72h"
        assert "raw_facts" in body
        assert "observed_pattern" in body
        assert body["common_knowledge"] is None
        assert "disclaimer" in body
