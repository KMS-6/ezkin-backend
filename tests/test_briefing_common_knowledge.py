"""Briefing의 common_knowledge RAG 연동(통합_기능_명세서.md Morning Briefing 8.3절) 검증.

`AAC 공통 지식 RAG 근거와 응답 규칙 v1` 4.1/4.2절의 실제 예시 Claim Card
(claim_sleep_barrier_001, claim_humidity_dryness_001)을 그대로 시드 데이터로 써서
근거 매칭이 스펙 예시와 일치하는지 확인한다.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeDocument, KnowledgeIndex
from app.models.weather import WeatherSnapshot
from app.modules.briefings.logic import select_common_knowledge
from app.modules.knowledge.matching import find_claim
from tests.conftest import TEST_PERSONA_ID
from tests.test_briefings import _freeze_briefing_clock  # noqa: F401 (autouse clock freeze)

KST = ZoneInfo("Asia/Seoul")
AFTER_READY_TIME = datetime(2026, 8, 16, 9, 0, tzinfo=KST)


async def _seed_claim(
    db: AsyncSession,
    *,
    claim_id: str,
    topic: str,
    required_user_facts: list[str],
    sentence: str,
    version: int = 1,
    allowed_features: list[str] | None = None,
    population: str = "성인",
) -> None:
    doc = KnowledgeDocument(
        source_url="https://pubmed.ncbi.nlm.nih.gov/40432361/",
        title="테스트 근거 문서",
        collected_at=datetime.now(UTC),
        review_status="approved",
        claim_id=claim_id,
        claim_version=version,
        topic=topic,
        population=population,
        allowed_features=allowed_features or ["briefing", "report"],
        required_user_facts=required_user_facts,
        allowed_expressions=sentence,
    )
    db.add(doc)
    await db.flush()
    db.add(
        KnowledgeIndex(
            version=f"idx-{claim_id}",
            is_active=True,
            claim_ids=[claim_id],
            claim_versions={claim_id: version},
        )
    )
    await db.commit()


SLEEP_SENTENCE = "최근 수면이 짧아 오늘은 피부 자극을 줄여보세요."
HUMIDITY_SENTENCE = "낮은 습도는 각질층 수분과 피부 건조 지표에 영향을 줄 수 있어요."


class TestFindClaim:
    async def test_no_match_without_any_document(self, db_session: AsyncSession) -> None:
        result = await find_claim(db_session, feature="briefing", topic="sleep", facts={"x"})
        assert result is None

    async def test_matches_when_required_facts_are_satisfied(
        self, db_session: AsyncSession
    ) -> None:
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

        result = await find_claim(
            db_session,
            feature="briefing",
            topic="sleep",
            facts={"sleep_hours_available", "sleep_below_personal_baseline_or_threshold"},
        )

        assert result is not None
        assert result.claim_id == "claim_sleep_barrier_001"
        assert result.version == 1
        assert result.sentence == SLEEP_SENTENCE

    async def test_no_match_when_a_required_fact_is_missing(self, db_session: AsyncSession) -> None:
        # 스펙 4.1절의 recent_sleep_below_baseline은 이 코드베이스에 baseline
        # 산출 로직이 없어 fact bundle에 절대 나타나지 않는다 — 그런 fact를
        # 요구하는 claim은 항상 제외돼야 한다.
        await _seed_claim(
            db_session,
            claim_id="claim_sleep_barrier_001",
            topic="sleep",
            required_user_facts=["recent_sleep_below_baseline"],
            sentence=SLEEP_SENTENCE,
        )

        result = await find_claim(
            db_session,
            feature="briefing",
            topic="sleep",
            facts={"sleep_hours_available", "sleep_below_personal_baseline_or_threshold"},
        )

        assert result is None

    async def test_no_match_when_feature_not_allowed(self, db_session: AsyncSession) -> None:
        await _seed_claim(
            db_session,
            claim_id="claim_sleep_barrier_001",
            topic="sleep",
            required_user_facts=["sleep_hours_available"],
            sentence=SLEEP_SENTENCE,
            allowed_features=["report"],  # briefing 없음
        )

        result = await find_claim(
            db_session, feature="briefing", topic="sleep", facts={"sleep_hours_available"}
        )

        assert result is None

    async def test_no_match_for_non_general_population(self, db_session: AsyncSession) -> None:
        await _seed_claim(
            db_session,
            claim_id="claim_sleep_barrier_001",
            topic="sleep",
            required_user_facts=["sleep_hours_available"],
            sentence=SLEEP_SENTENCE,
            population="청소년",
        )

        result = await find_claim(
            db_session, feature="briefing", topic="sleep", facts={"sleep_hours_available"}
        )

        assert result is None

    async def test_active_index_pins_claim_version(self, db_session: AsyncSession) -> None:
        await _seed_claim(
            db_session,
            claim_id="claim_sleep_barrier_001",
            topic="sleep",
            required_user_facts=["sleep_hours_available"],
            sentence="인덱스 생성 당시 문장",
            version=1,
        )
        db_session.add(
            KnowledgeDocument(
                source_url="https://example.com/v2",
                title="새 버전",
                collected_at=datetime.now(UTC),
                review_status="approved",
                claim_id="claim_sleep_barrier_001",
                claim_version=2,
                topic="sleep",
                population="성인",
                allowed_features=["briefing"],
                required_user_facts=["sleep_hours_available"],
                allowed_expressions="인덱스 생성 후 승인된 문장",
            )
        )
        await db_session.commit()

        result = await find_claim(
            db_session, feature="briefing", topic="sleep", facts={"sleep_hours_available"}
        )

        assert result is not None
        assert result.version == 1
        assert result.sentence == "인덱스 생성 당시 문장"

    async def test_no_match_when_not_approved(self, db_session: AsyncSession) -> None:
        doc = KnowledgeDocument(
            source_url="https://example.com",
            title="검수 전",
            collected_at=datetime.now(UTC),
            review_status="draft",
            claim_id="claim_sleep_barrier_001",
            claim_version=1,
            topic="sleep",
            allowed_features=["briefing"],
            required_user_facts=["sleep_hours_available"],
            allowed_expressions=SLEEP_SENTENCE,
        )
        db_session.add(doc)
        await db_session.flush()
        db_session.add(
            KnowledgeIndex(version="idx", is_active=True, claim_ids=["claim_sleep_barrier_001"])
        )
        await db_session.commit()

        result = await find_claim(
            db_session, feature="briefing", topic="sleep", facts={"sleep_hours_available"}
        )

        assert result is None


class TestSelectCommonKnowledgeForBriefing:
    async def test_picks_sleep_claim_when_sleep_is_the_only_factor(
        self, db_session: AsyncSession
    ) -> None:
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
        context = {
            "factors": [("sleep", "수면 4.5시간 미만")],
            "metric": type("M", (), {"sleep_hours": 4.5})(),
            "weather": None,
            "weather_consented": False,
        }

        result = await select_common_knowledge(db_session, context)

        assert result == {
            "claim_id": "claim_sleep_barrier_001",
            "version": 1,
            "sentence": SLEEP_SENTENCE,
        }

    async def test_picks_higher_weight_sleep_over_humidity(self, db_session: AsyncSession) -> None:
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
        await _seed_claim(
            db_session,
            claim_id="claim_humidity_dryness_001",
            topic="humidity",
            required_user_facts=[
                "weather_consent",
                "fresh_humidity_data",
                "humidity_below_rule_threshold",
            ],
            sentence=HUMIDITY_SENTENCE,
        )
        weather = type("W", (), {"humidity_percent": 20.0})()
        context = {
            # sleep(가중치 2)이 weather(가중치 1)보다 먼저 나오고 더 무겁다.
            "factors": [("sleep", "수면 부족"), ("weather", "습도 20%")],
            "metric": type("M", (), {"sleep_hours": 4.5})(),
            "weather": weather,
            "weather_consented": True,
        }

        result = await select_common_knowledge(db_session, context)

        assert result is not None
        assert result["claim_id"] == "claim_sleep_barrier_001"

    async def test_no_claim_when_no_factors_triggered(self, db_session: AsyncSession) -> None:
        context = {
            "factors": [],
            "metric": None,
            "weather": None,
            "weather_consented": False,
        }

        result = await select_common_knowledge(db_session, context)

        assert result is None

    async def test_unmapped_factor_type_never_looks_up_a_claim(
        self, db_session: AsyncSession
    ) -> None:
        # scan/diet/hrv는 아직 대응하는 Claim Card 매핑이 없다(RAG 문서에 예시
        # 없음) — 항상 None이어야 하고, 이건 DB에 근거가 없어서가 아니라
        # 애초에 조회조차 시도하지 않아서다.
        context = {
            "factors": [("hrv", "HRV 저하")],
            "metric": None,
            "weather": None,
            "weather_consented": False,
        }

        result = await select_common_knowledge(db_session, context)

        assert result is None


@pytest.mark.usefixtures("_freeze_briefing_clock")
async def test_briefing_endpoint_includes_matched_humidity_claim(
    client: AsyncClient, persona_headers: dict[str, str], db_session: AsyncSession
) -> None:
    await _seed_claim(
        db_session,
        claim_id="claim_humidity_dryness_001",
        topic="humidity",
        required_user_facts=[
            "weather_consent",
            "fresh_humidity_data",
            "humidity_below_rule_threshold",
        ],
        sentence=HUMIDITY_SENTENCE,
    )

    weather_consent = await client.put(
        "/api/v1/consents/weather_location", headers=persona_headers, json={"consented": True}
    )
    assert weather_consent.status_code == 200

    db_session.add(
        WeatherSnapshot(
            persona_id=TEST_PERSONA_ID,
            observed_at=AFTER_READY_TIME - timedelta(hours=1),
            humidity_percent=20.0,
            source="mock",
        )
    )
    await db_session.commit()

    response = await client.get("/api/v1/briefings/today", headers=persona_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["common_knowledge"] == {
        "claim_id": "claim_humidity_dryness_001",
        "version": 1,
        "sentence": HUMIDITY_SENTENCE,
    }


@pytest.mark.usefixtures("_freeze_briefing_clock")
async def test_briefing_endpoint_omits_common_knowledge_without_matching_claim(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    # 아무 Claim Card도 없으므로(기본 상태) 근거 없이 정상 응답한다 — 8.3절: "조건에
    # 맞는 승인된 claim이 없으면 common_knowledge는 null이며 나머지는 정상 반환".
    response = await client.get("/api/v1/briefings/today", headers=persona_headers)

    assert response.status_code == 200
    assert response.json()["common_knowledge"] is None
