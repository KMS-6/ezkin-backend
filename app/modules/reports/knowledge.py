"""기간 Report(14/30일)의 공통 지식 Claim 검색 — system_architecture.md 5.5/5.7/7.3절.

briefings/logic.py::select_common_knowledge, triggers/logic.py::_select_pattern_common_knowledge와
동일하게 feature="report"로 승인된 Claim만 조회한다. 트리거 분석·Briefing은 최우선 조건
1개만 찾지만, 기간 Report는 기간 내 나타난 조건마다 후보를 모아 최대
MAX_REPORT_CLAIMS(5)개까지 Evidence Bundle로 구성한다(5.5절 "검색 후보를 최대 5개로
구성").
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metrics import DailyMetric
from app.modules.knowledge.matching import find_claim
from app.modules.risk.logic import IRRITATING_DIET_FLAGS, SLEEP_LOW_THRESHOLD_HOURS

MAX_REPORT_CLAIMS = 5

# sleep > diet 우선순위는 briefings/triggers 모듈과 동일하게 유지한다.
_TOPIC_ORDER = ("sleep", "diet")


async def select_report_common_knowledge(
    db: AsyncSession, persona_id: str, start_date: date, end_date: date
) -> list[dict]:
    metrics_result = await db.execute(
        select(DailyMetric).where(
            DailyMetric.persona_id == persona_id,
            DailyMetric.metric_date >= start_date,
            DailyMetric.metric_date <= end_date,
        )
    )
    metrics = list(metrics_result.scalars())

    facts_by_topic: dict[str, set[str]] = {}
    if any(
        m.sleep_hours is not None and m.sleep_hours < SLEEP_LOW_THRESHOLD_HOURS for m in metrics
    ):
        facts_by_topic["sleep"] = {
            "sleep_hours_available",
            "sleep_below_personal_baseline_or_threshold",
        }
    if any(m.diet_flag in IRRITATING_DIET_FLAGS for m in metrics):
        facts_by_topic["diet"] = {"irritating_diet_flag_present"}

    claims: list[dict] = []
    for topic in _TOPIC_ORDER:
        if len(claims) >= MAX_REPORT_CLAIMS:
            break
        facts = facts_by_topic.get(topic)
        if facts is None:
            continue
        claim = await find_claim(db, feature="report", topic=topic, facts=facts)
        if claim is not None:
            claims.append(
                {
                    "claim_id": claim.claim_id,
                    "version": claim.version,
                    "sentence": claim.sentence,
                    "topic": topic,
                }
            )
    return claims
