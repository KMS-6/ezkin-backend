import re
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metrics import DailyMetric
from app.models.skin_scan import SkinScan

PATTERN_WINDOW_HOURS = 72
IRRITATING_DIET_FLAGS = {"spicy", "late_night_meal", "alcohol"}
ELEVATED_THRESHOLD = 0.66
MIN_SAMPLE_SIZE = 3

URGENT_KEYWORDS = ("호흡곤란", "숨을못", "숨쉬기힘", "의식", "심한부종", "눈이부어", "붓기가심")

FAQ_ENTRIES = [
    {
        "faq_id": "faq_after_irritating_food",
        "version": 1,
        "keywords": ["야식", "매운", "자극적인 음식"],
        "reply": "오늘 등록된 진정·보습 제품 위주로 순하게 관리해 보세요.",
    },
    {
        "faq_id": "faq_new_product_irritation",
        "version": 1,
        "keywords": ["따가", "화끈", "새 제품", "새제품"],
        "reply": "새로 사용한 제품이 있다면 사용을 중단하고 순한 세안 후 보습에 집중해 주세요.",
    },
    {
        "faq_id": "faq_dryness",
        "version": 1,
        "keywords": ["건조", "당김"],
        "reply": "보습 제품을 층층이 덧발라 수분 손실을 줄여보세요.",
    },
]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text)


def is_urgent(message: str) -> bool:
    normalized = _normalize(message)
    return any(keyword in normalized for keyword in URGENT_KEYWORDS)


def match_faq(message: str) -> dict | None:
    normalized = _normalize(message)
    for entry in FAQ_ENTRIES:
        if any(_normalize(keyword) in normalized for keyword in entry["keywords"]):
            return entry
    return None


async def build_pattern_analysis(db: AsyncSession, scan: SkinScan) -> dict:
    window_start = scan.captured_at - timedelta(hours=PATTERN_WINDOW_HOURS)
    window_end = scan.captured_at

    metrics_result = await db.execute(
        select(DailyMetric).where(
            DailyMetric.persona_id == scan.persona_id,
            DailyMetric.metric_date >= window_start.date(),
            DailyMetric.metric_date <= window_end.date(),
        )
    )
    metrics_in_window = list(metrics_result.scalars())

    raw_facts = []
    short_sleep_days = [
        m for m in metrics_in_window if m.sleep_hours is not None and m.sleep_hours < 6
    ]
    if short_sleep_days:
        raw_facts.append(
            {
                "type": "sleep",
                "text": f"최근 72시간 내 수면 6시간 미만 날이 {len(short_sleep_days)}일 있었어요.",
            }
        )
    irritating_days = [m for m in metrics_in_window if m.diet_flag in IRRITATING_DIET_FLAGS]
    if irritating_days:
        raw_facts.append(
            {
                "type": "diet",
                "text": f"자극 유발 가능 식습관이 {len(irritating_days)}일 기록됐어요.",
            }
        )

    all_metrics_result = await db.execute(
        select(DailyMetric).where(DailyMetric.persona_id == scan.persona_id)
    )
    condition_days = [
        m
        for m in all_metrics_result.scalars()
        if (m.sleep_hours is not None and m.sleep_hours < 6) or m.diet_flag in IRRITATING_DIET_FLAGS
    ]

    all_scans_result = await db.execute(
        select(SkinScan).where(
            SkinScan.persona_id == scan.persona_id, SkinScan.status == "completed"
        )
    )
    all_scans = list(all_scans_result.scalars())

    match_count = 0
    for day in condition_days:
        next_day_scans = [
            s for s in all_scans if s.captured_at.date() == day.metric_date + timedelta(days=1)
        ]
        if any(
            s.scores and any(v >= ELEVATED_THRESHOLD for v in s.scores.values())
            for s in next_day_scans
        ):
            match_count += 1

    sample_size = len(condition_days)
    observed_pattern = None
    if sample_size >= MIN_SAMPLE_SIZE:
        observed_pattern = {
            "text": f"비슷한 조건 {sample_size}번 중 {match_count}번 함께 높은 수치가 관찰됐어요.",
            "sample_size": sample_size,
            "match_count": match_count,
        }

    return {
        "window": {"start": window_start, "end": window_end},
        "raw_facts": raw_facts,
        "observed_pattern": observed_pattern,
        "common_knowledge": None,
        "disclaimer": "통계적 상관관계는 의료 진단이 아닌 예방적 참고용 관찰입니다.",
    }
