from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.onboarding import Consent
from app.models.skin_scan import SkinScan

PATTERN_ANALYSIS_MIN_SCANS = 3
PATTERN_ANALYSIS_WINDOW_DAYS = 14


async def _consented(db: AsyncSession, persona_id: str, consent_type: str) -> bool:
    result = await db.execute(
        select(Consent.consented).where(
            Consent.persona_id == persona_id, Consent.type == consent_type
        )
    )
    return bool(result.scalar_one_or_none())


async def compute_feature_availability(db: AsyncSession, persona_id: str) -> list[dict]:
    """Rule-based feature-availability derived from consent + observed data coverage."""
    health_ok = await _consented(db, persona_id, "apple_health")
    weather_ok = await _consented(db, persona_id, "weather_location")

    cutoff = datetime.now(UTC) - timedelta(days=PATTERN_ANALYSIS_WINDOW_DAYS)
    result = await db.execute(
        select(func.count(SkinScan.id)).where(
            SkinScan.persona_id == persona_id,
            SkinScan.captured_at >= cutoff,
            SkinScan.status == "completed",
        )
    )
    completed_scans = result.scalar_one()
    pattern_ok = completed_scans >= PATTERN_ANALYSIS_MIN_SCANS

    return [
        {
            "feature": "risk_assessment_health",
            "status": "normal" if health_ok else "limited",
            **(
                {}
                if health_ok
                else {
                    "reason": "apple_health 동의 없음",
                    "fallback": "간편 문진 기반 위험도 산출로 대체됩니다.",
                }
            ),
        },
        {
            "feature": "risk_assessment_weather",
            "status": "normal" if weather_ok else "limited",
            **(
                {}
                if weather_ok
                else {
                    "reason": "weather_location 동의 없음",
                    "fallback": "실내 환경 가정값으로 대체됩니다.",
                }
            ),
        },
        {
            "feature": "pattern_analysis",
            "status": "normal" if pattern_ok else "limited",
            **(
                {}
                if pattern_ok
                else {
                    "reason": "유효 관찰 데이터 부족",
                    "fallback": f"스캔을 {PATTERN_ANALYSIS_MIN_SCANS}회 이상 진행하면 제공됩니다.",
                }
            ),
        },
    ]
