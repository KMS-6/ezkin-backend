from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metrics import DailyMetric
from app.models.onboarding import Consent
from app.models.scan import SkinScan
from app.models.weather import WeatherSnapshot

RISK_LEVELS = ["low", "moderate", "high", "very_high"]
IRRITATING_DIET_FLAGS = {"spicy", "late_night_meal"}
HIGH_SCORE_THRESHOLD = 0.66

# 기능명세서_briefing.md 6.1절 가중치(초기값, Mock Data·QA로 조정 예정).
SCAN_DELTA_THRESHOLD = 0.15
SLEEP_LOW_THRESHOLD_HOURS = 5.0
UV_HIGH_THRESHOLD = 8.0
LOW_HUMIDITY_THRESHOLD = 30.0
HRV_DROP_THRESHOLD_PERCENT = 20.0
HRV_BASELINE_MIN_DAYS = 14
# 6.2절 합산 구간: 점수가 이 상한 이하면 해당 등급, 모두 초과하면 very_high.
RISK_SCORE_BANDS = [(1, "low"), (3, "moderate"), (5, "high")]


def _risk_level_from_score(score: int) -> str:
    for max_score, level in RISK_SCORE_BANDS:
        if score <= max_score:
            return level
    return "very_high"


def _elevated_scan_metrics(
    latest_scores: dict[str, float] | None, previous_scores: dict[str, float] | None
) -> list[str]:
    """절대 고수치(>=0.66) 또는 직전 스캔 대비 유의미한 상승(6.1절)이 있는 지표를 찾는다.

    직전 스캔이 없어도(첫 스캔) 절대 고수치는 여전히 유의미한 관찰로 본다.
    """
    if not latest_scores:
        return []
    risen: set[str] = set()
    for metric, value in latest_scores.items():
        if value >= HIGH_SCORE_THRESHOLD:
            risen.add(metric)
        elif previous_scores and metric in previous_scores:
            if value - previous_scores[metric] >= SCAN_DELTA_THRESHOLD:
                risen.add(metric)
    return sorted(risen)


def compute_risk(
    sleep_hours: float | None,
    diet_flag: str | None,
    latest_scores: dict[str, float] | None,
    previous_scores: dict[str, float] | None = None,
    uv_index: float | None = None,
    humidity_percent: float | None = None,
    hrv_deviation_percent: float | None = None,
) -> tuple[str, list[tuple[str, str]]]:
    """기능명세서_briefing.md 6.1/6.2절 가중치 합산 위험도.

    `/risk-assessments/today`, Briefing, SOS 챗봇이 공유하는 단일 규칙 엔진이다.
    반환 factors는 (type, text) 튜플 목록이며 실제 사용된 데이터만 포함한다(6.4절
    "단일 요인만으로 원인을 확정하지 않는다").
    """
    factors: list[tuple[str, str]] = []
    score = 0

    if sleep_hours is not None and sleep_hours < SLEEP_LOW_THRESHOLD_HOURS:
        score += 2
        factors.append(("sleep", f"수면 {sleep_hours}시간 미만"))

    if hrv_deviation_percent is not None and hrv_deviation_percent <= -HRV_DROP_THRESHOLD_PERCENT:
        score += 2
        factors.append(
            ("hrv", f"HRV가 평소보다 {abs(round(hrv_deviation_percent))}% 낮게 관찰돼요")
        )

    if uv_index is not None and uv_index >= UV_HIGH_THRESHOLD:
        score += 1
        factors.append(("weather", f"자외선지수 {uv_index} (매우 높음)"))

    if humidity_percent is not None and humidity_percent < LOW_HUMIDITY_THRESHOLD:
        score += 1
        factors.append(("weather", f"습도 {humidity_percent}%"))

    risen_metrics = _elevated_scan_metrics(latest_scores, previous_scores)
    if risen_metrics:
        score += 2
        factors.append(("scan", f"최근 스캔에서 상승 관찰: {', '.join(risen_metrics)}"))

    if diet_flag in IRRITATING_DIET_FLAGS:
        score += 1
        factors.append(("diet", f"자극 유발 가능 식습관 기록 ({diet_flag})"))

    return _risk_level_from_score(score), factors


async def compute_hrv_baseline_deviation(
    db: AsyncSession, persona_id: str, today: date
) -> tuple[float | None, bool]:
    """6.3절: 최근 HRV_BASELINE_MIN_DAYS일의 유효 HRV 평균을 baseline으로 삼는다.

    유효 일수가 모자라면 (None, False)를 반환해 위험도 계산에서 HRV를 제외하고
    `data_coverage.baseline_established=false`로 표시할 수 있게 한다.
    """
    window_start = today - timedelta(days=HRV_BASELINE_MIN_DAYS)
    baseline_result = await db.execute(
        select(DailyMetric.hrv_ms).where(
            DailyMetric.persona_id == persona_id,
            DailyMetric.metric_date >= window_start,
            DailyMetric.metric_date < today,
            DailyMetric.hrv_ms.is_not(None),
        )
    )
    baseline_values = [value for (value,) in baseline_result.all()]
    if len(baseline_values) < HRV_BASELINE_MIN_DAYS:
        return None, False

    today_result = await db.execute(
        select(DailyMetric.hrv_ms).where(
            DailyMetric.persona_id == persona_id, DailyMetric.metric_date == today
        )
    )
    today_hrv = today_result.scalar_one_or_none()
    baseline_avg = sum(baseline_values) / len(baseline_values)
    if today_hrv is None or baseline_avg == 0:
        return None, True

    deviation_percent = ((today_hrv - baseline_avg) / baseline_avg) * 100
    return deviation_percent, True


def _as_naive_utc(value: datetime) -> datetime:
    """SQLite는 DateTime(timezone=True)를 offset 없이 round-trip한다 — 비교 전에
    naive UTC로 정규화해 aware/naive 혼합 뺄셈 오류를 피한다."""
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


async def load_latest_weather(
    db: AsyncSession, persona_id: str, now: datetime, max_age_hours: int = 6
) -> WeatherSnapshot | None:
    """4.1/5절: 생성 시점 기준 max_age_hours 이내 관측만 사용하고, 오래됐으면 제외한다."""
    result = await db.execute(
        select(WeatherSnapshot)
        .where(WeatherSnapshot.persona_id == persona_id)
        .order_by(WeatherSnapshot.observed_at.desc())
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        return None
    if _as_naive_utc(now) - _as_naive_utc(snapshot.observed_at) > timedelta(hours=max_age_hours):
        return None
    return snapshot


async def load_today_risk_context(
    db: AsyncSession, persona_id: str, today: date, now: datetime
) -> dict:
    """`/risk-assessments/today`·Briefing·SOS 챗봇이 공유하는 단일 진입점.

    `today`·`now`는 호출자가 각자의 시계로 계산해 넘긴다 — 이 함수가 자체적으로
    datetime.now()를 호출하면 Briefing 테스트의 시계 freeze(monkeypatch)가 적용되지
    않기 때문이다.
    """
    metric_result = await db.execute(
        select(DailyMetric).where(
            DailyMetric.persona_id == persona_id, DailyMetric.metric_date == today
        )
    )
    metric = metric_result.scalar_one_or_none()

    scans_result = await db.execute(
        select(SkinScan)
        .where(SkinScan.persona_id == persona_id, SkinScan.status == "completed")
        .order_by(SkinScan.captured_at.desc())
        .limit(2)
    )
    recent_scans = list(scans_result.scalars())
    latest_scan = recent_scans[0] if recent_scans else None
    previous_scan = recent_scans[1] if len(recent_scans) > 1 else None

    consents_result = await db.execute(select(Consent).where(Consent.persona_id == persona_id))
    consent_map = {c.type: c.consented for c in consents_result.scalars()}
    weather_consented = consent_map.get("weather_location", False)
    health_consented = consent_map.get("apple_health", False)

    weather = await load_latest_weather(db, persona_id, now) if weather_consented else None
    hrv_deviation_percent, baseline_established = (
        await compute_hrv_baseline_deviation(db, persona_id, today)
        if health_consented
        else (None, False)
    )

    risk_level, factors = compute_risk(
        sleep_hours=metric.sleep_hours if metric else None,
        diet_flag=metric.diet_flag if metric else None,
        latest_scores=latest_scan.scores if latest_scan else None,
        previous_scores=previous_scan.scores if previous_scan else None,
        uv_index=weather.uv_index if weather else None,
        humidity_percent=weather.humidity_percent if weather else None,
        hrv_deviation_percent=hrv_deviation_percent,
    )

    return {
        "risk_level": risk_level,
        "factors": factors,
        "metric": metric,
        "latest_scan": latest_scan,
        "weather": weather,
        "weather_consented": weather_consented,
        "health_consented": health_consented,
        "baseline_established": baseline_established,
    }


async def build_report_content(
    db: AsyncSession, persona_id: str, period_days: int, end_date: date
) -> dict:
    start_date = end_date - timedelta(days=period_days - 1)
    window_start = datetime.combine(start_date, time.min, tzinfo=UTC)
    window_end = datetime.combine(end_date, time.max, tzinfo=UTC)
    scans_result = await db.execute(
        select(SkinScan)
        .where(
            SkinScan.persona_id == persona_id,
            SkinScan.status == "completed",
            SkinScan.captured_at >= window_start,
            SkinScan.captured_at <= window_end,
        )
        .order_by(SkinScan.captured_at)
    )
    scans = list(scans_result.scalars())

    metrics_result = await db.execute(
        select(DailyMetric).where(
            DailyMetric.persona_id == persona_id,
            DailyMetric.metric_date >= start_date,
            DailyMetric.metric_date <= end_date,
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
        "period": {
            "period_days": period_days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        "summary": summary,
        "observations": observations,
        "patterns": patterns,
        "recommendations": recommendations,
        "limitations": "의료적 진단이 아닌 참고 정보입니다.",
        # 명세서상 고정값: 이 리포트는 의료적 진단이 아닌 웰니스 참고 정보임을 나타내는 상수.
        "safety_status": "wellness_only",
    }
