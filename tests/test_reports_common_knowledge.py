"""기간 Report(14/30일)의 공통 지식 Claim 연동(system_architecture.md 5.5/5.7/7.3절) 검증.

Report(pattern-analysis)·Briefing과 동일한 Claim Card 예시(claim_sleep_barrier_001)를
시드 데이터로 써서, 기간 Report도 동일한 근거 매칭 정책(feature="report")을 공유하는지
확인한다.
"""

from datetime import UTC, date, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metrics import DailyMetric
from app.models.scan import SkinScan
from tests.conftest import TEST_PERSONA_ID
from tests.test_briefing_common_knowledge import SLEEP_SENTENCE, _seed_claim


def _dt(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 12, 0, 0, tzinfo=UTC)


async def _seed_scans(db: AsyncSession, count: int, base: date) -> None:
    for i in range(count):
        d = base - timedelta(days=i)
        db.add(
            SkinScan(
                persona_id=TEST_PERSONA_ID,
                capture_method="camera",
                status="completed",
                captured_at=_dt(d),
                created_at=_dt(d),
                scores={"redness": 0.3, "dryness": 0.3, "oiliness": 0.3},
            )
        )
    await db.commit()


async def test_report_includes_common_knowledge_when_sleep_claim_matches(
    client: AsyncClient, persona_headers: dict[str, str], db_session: AsyncSession
) -> None:
    today = datetime.now(UTC).date()
    await _seed_scans(db_session, 14, today)
    db_session.add(DailyMetric(persona_id=TEST_PERSONA_ID, metric_date=today, sleep_hours=4.0))
    await db_session.commit()
    await _seed_claim(
        db_session,
        claim_id="claim_sleep_barrier_001",
        topic="sleep",
        required_user_facts=[
            "sleep_hours_available",
            "sleep_below_personal_baseline_or_threshold",
        ],
        sentence=SLEEP_SENTENCE,
    )

    create_resp = await client.post(
        "/api/v1/reports", json={"period_days": 14}, headers=persona_headers
    )
    report_id = create_resp.json()["report_id"]

    resp = await client.get(f"/api/v1/reports/{report_id}", headers=persona_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["common_knowledge"] == [
        {
            "claim_id": "claim_sleep_barrier_001",
            "version": 1,
            "sentence": SLEEP_SENTENCE,
            "topic": "sleep",
        }
    ]


async def test_report_common_knowledge_is_empty_without_matching_conditions(
    client: AsyncClient, persona_headers: dict[str, str], db_session: AsyncSession
) -> None:
    today = datetime.now(UTC).date()
    await _seed_scans(db_session, 14, today)

    create_resp = await client.post(
        "/api/v1/reports", json={"period_days": 14}, headers=persona_headers
    )
    report_id = create_resp.json()["report_id"]

    resp = await client.get(f"/api/v1/reports/{report_id}", headers=persona_headers)
    assert resp.status_code == 200
    assert resp.json()["common_knowledge"] == []
