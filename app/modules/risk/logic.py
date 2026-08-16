from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metrics import DailyMetric
from app.models.skin_scan import SkinScan

RISK_LEVELS = ["low", "moderate", "high", "very_high"]
IRRITATING_DIET_FLAGS = {"spicy", "late_night_meal", "alcohol"}
HIGH_SCORE_THRESHOLD = 0.66


def compute_risk(
    sleep_hours: float | None,
    diet_flag: str | None,
    latest_scores: dict[str, float] | None,
) -> tuple[str, list[str]]:
    """Rule-based risk level from the day's inputs — mirrors app.modules.care.rules."""
    factors: list[str] = []
    if sleep_hours is not None and sleep_hours < 6:
        factors.append(f"수면 {sleep_hours}시간 미만")
    if diet_flag in IRRITATING_DIET_FLAGS:
        factors.append(f"자극 유발 가능 식습관 기록 ({diet_flag})")
    if latest_scores:
        high = [metric for metric, value in latest_scores.items() if value >= HIGH_SCORE_THRESHOLD]
        if high:
            factors.append(f"최근 스캔에서 높은 수치 관찰: {', '.join(sorted(high))}")

    level = RISK_LEVELS[min(len(factors), len(RISK_LEVELS) - 1)]
    return level, factors


async def count_observation_days(db: AsyncSession, persona_id: str, window_days: int) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=window_days)
    result = await db.execute(
        select(func.count(func.distinct(func.date(SkinScan.captured_at)))).where(
            SkinScan.persona_id == persona_id,
            SkinScan.status == "completed",
            SkinScan.captured_at >= cutoff,
        )
    )
    return result.scalar_one() or 0


async def build_report_content(db: AsyncSession, persona_id: str, period_days: int) -> dict:
    cutoff = datetime.now(UTC) - timedelta(days=period_days)
    scans_result = await db.execute(
        select(SkinScan)
        .where(
            SkinScan.persona_id == persona_id,
            SkinScan.status == "completed",
            SkinScan.captured_at >= cutoff,
        )
        .order_by(SkinScan.captured_at)
    )
    scans = list(scans_result.scalars())

    metrics_result = await db.execute(
        select(DailyMetric).where(
            DailyMetric.persona_id == persona_id, DailyMetric.metric_date >= cutoff.date()
        )
    )
    metrics = list(metrics_result.scalars())

    observations: list[dict] = []
    patterns: list[dict] = []
    recommendations: list[dict] = []

    if scans:
        scores_by_metric: dict[str, list[float]] = {}
        for scan in scans:
            for metric, value in (scan.scores or {}).items():
                scores_by_metric.setdefault(metric, []).append(value)
        averages = {
            metric: round(sum(values) / len(values), 2)
            for metric, values in scores_by_metric.items()
        }
        observations.append(
            {
                "text": f"{period_days}일간 평균 지표: "
                + ", ".join(f"{metric} {value}" for metric, value in sorted(averages.items())),
                "evidence_ids": [str(scan.id) for scan in scans],
            }
        )

        if len(scans) >= 2:
            midpoint = len(scans) // 2
            for metric in averages:
                first_half = [
                    s.scores[metric] for s in scans[:midpoint] if s.scores and metric in s.scores
                ]
                second_half = [
                    s.scores[metric] for s in scans[midpoint:] if s.scores and metric in s.scores
                ]
                if first_half and second_half:
                    delta = round(
                        (sum(second_half) / len(second_half)) - (sum(first_half) / len(first_half)),
                        2,
                    )
                    if abs(delta) >= 0.15:
                        direction = "증가" if delta > 0 else "감소"
                        patterns.append(
                            {
                                "text": f"{metric} 지표가 후반부로 갈수록 {direction} 추세예요.",
                                "evidence_ids": [str(s.id) for s in scans],
                            }
                        )

        elevated = [metric for metric, value in averages.items() if value >= HIGH_SCORE_THRESHOLD]
        if elevated:
            elevated_text = ", ".join(sorted(elevated))
            recommendations.append(
                {
                    "text": f"{elevated_text} 지표 상승, 순한 성분 루틴을 참고해 보세요.",
                    "evidence_ids": [str(scan.id) for scan in scans],
                }
            )

    irritating_days = [m for m in metrics if m.diet_flag in IRRITATING_DIET_FLAGS]
    if irritating_days:
        patterns.append(
            {
                "text": f"자극 유발 가능 식습관이 {len(irritating_days)}일 기록됐어요.",
                "evidence_ids": [str(m.id) for m in irritating_days],
            }
        )

    summary = (
        f"최근 {period_days}일간 {len(scans)}회의 관찰 데이터를 분석했어요."
        if scans
        else f"최근 {period_days}일간 분석 가능한 관찰 데이터가 없었어요."
    )

    return {
        "period": {"days": period_days},
        "summary": summary,
        "observations": observations,
        "patterns": patterns,
        "recommendations": recommendations,
        "limitations": "의료적 진단이 아닌 참고 정보이며, 공통 지식(RAG) 근거는 미연동입니다.",
        "safety_status": "ok",
    }
