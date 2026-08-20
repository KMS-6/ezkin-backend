"""persona_001/002/003에 30일치 daily_metrics·skin_scans·consents seed 데이터 추가 —
프론트 장기 사용자 데모(persona_003)와 리포트/브리핑 API가 실제 DB 입력값으로 동작하도록 준비."""

import math
import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta

import sqlalchemy as sa

from alembic import op

revision: str = "20260821_0013"
down_revision: str | None = "20260821_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEED_DAYS = 30
# "three_to_five_glasses"는 20260821_0012에서 컬럼 폭을 VARCHAR(30)으로 넓힌 뒤 사용 가능.
WATER_LEVELS = ["under_3_glasses", "three_to_five_glasses", "over_5_glasses"]
DIET_FLAGS = [None, "normal", "spicy", "late_night_meal"]

# persona별 스캔 점수 베이스라인 — summary_traits(20260816_0002 migration)와 정합.
PERSONA_BASELINES = {
    "persona_001": {  # 복합성·트러블 케어: T존 유분·트러블 위주
        "sleep_base": 6.5,
        "hrv_base": 48.0,
        "redness_base": 0.35,
        "dryness_base": 0.25,
        "oiliness_base": 0.6,
    },
    "persona_002": {  # 건성·민감 케어: 건조·붉은기 위주
        "sleep_base": 6.8,
        "hrv_base": 52.0,
        "redness_base": 0.45,
        "dryness_base": 0.65,
        "oiliness_base": 0.2,
    },
    "persona_003": {  # 생리 주기·장기 사용 시나리오
        # 프론트 장기 사용자 데모(persona_long_term_yeonseo)의
        # health_baseline(sleep_hours=6.1, hrv_ms=50.6)과 동일한 값.
        "sleep_base": 6.1,
        "hrv_base": 50.6,
        "redness_base": 0.4,
        "dryness_base": 0.4,
        "oiliness_base": 0.45,
    },
}

# persona_003 최근 3일 오버라이드 — 프론트 mock의 current_health(sleep_hours=4, hrv_ms=33)와
# pattern_analysis 서술("최근 3일 평균 수면 1.8시간 짧음", "HRV 크게 낮은 날 이틀 연속")을 재현한다.
# day_index: 0=오늘(current_health와 동일), 1~2=그 이전 날.
PERSONA_003_RECENT_DIP_OVERRIDES = {
    0: {"sleep_hours": 4.0, "hrv_ms": 33.0},
    1: {"sleep_hours": 4.3, "hrv_ms": 33.0},
    2: {"sleep_hours": 4.5, "hrv_ms": 42.0},
}


def _round(value: float, digits: int = 2) -> float:
    return round(value, digits)


def upgrade() -> None:
    connection = op.get_bind()
    today = date.today()

    daily_metrics_rows: list[dict] = []
    skin_scans_rows: list[dict] = []
    consents_rows: list[dict] = []

    for persona_id, baseline in PERSONA_BASELINES.items():
        consents_rows.append(
            {
                "id": uuid.uuid4(),
                "persona_id": persona_id,
                "type": "apple_health",
                "consented": True,
            }
        )
        consents_rows.append(
            {
                "id": uuid.uuid4(),
                "persona_id": persona_id,
                "type": "weather_location",
                "consented": True,
            }
        )

        for offset in range(SEED_DAYS):
            day_index = SEED_DAYS - 1 - offset  # 0 = 오늘, 29 = 29일 전
            metric_date = today - timedelta(days=day_index)
            wave = math.sin(offset / 4)

            dip_override = (
                PERSONA_003_RECENT_DIP_OVERRIDES.get(day_index)
                if persona_id == "persona_003"
                else None
            )
            is_recent_dip_day = dip_override is not None
            sleep_hours = (
                dip_override["sleep_hours"]
                if dip_override
                else _round(baseline["sleep_base"] + wave * 0.6)
            )
            hrv_ms = (
                dip_override["hrv_ms"]
                if dip_override
                else _round(baseline["hrv_base"] + wave * 4.0)
            )

            daily_metrics_rows.append(
                {
                    "id": uuid.uuid4(),
                    "persona_id": persona_id,
                    "metric_date": metric_date,
                    "water_intake_level": WATER_LEVELS[offset % len(WATER_LEVELS)],
                    "diet_flag": DIET_FLAGS[offset % len(DIET_FLAGS)],
                    "sleep_hours": max(sleep_hours, 0),
                    "hrv_ms": max(hrv_ms, 0),
                    "active_energy_kcal": _round(300 + wave * 60),
                }
            )

            redness = min(
                baseline["redness_base"] + wave * 0.1 + (0.15 if is_recent_dip_day else 0), 1.0
            )
            dryness = min(
                baseline["dryness_base"] + wave * 0.1 + (0.1 if is_recent_dip_day else 0), 1.0
            )
            oiliness = min(max(baseline["oiliness_base"] - wave * 0.1, 0.0), 1.0)
            captured_at = datetime.combine(metric_date, time(8, 0), tzinfo=UTC)

            skin_scans_rows.append(
                {
                    "id": uuid.uuid4(),
                    "persona_id": persona_id,
                    "capture_method": "camera",
                    "captured_at": captured_at,
                    "completed_at": captured_at,
                    "status": "completed",
                    "lower_accuracy": False,
                    "redness_score": _round(redness),
                    "dryness_score": _round(dryness),
                    "oiliness_score": _round(oiliness),
                    "redness_confidence": 0.85,
                    "dryness_confidence": 0.85,
                    "oiliness_confidence": 0.85,
                    "created_at": captured_at,
                    "updated_at": captured_at,
                }
            )

    connection.execute(
        sa.table(
            "consents",
            sa.column("id", sa.Uuid),
            sa.column("persona_id", sa.String),
            sa.column("type", sa.String),
            sa.column("consented", sa.Boolean),
        ).insert(),
        consents_rows,
    )
    connection.execute(
        sa.table(
            "daily_metrics",
            sa.column("id", sa.Uuid),
            sa.column("persona_id", sa.String),
            sa.column("metric_date", sa.Date),
            sa.column("water_intake_level", sa.String),
            sa.column("diet_flag", sa.String),
            sa.column("sleep_hours", sa.Float),
            sa.column("hrv_ms", sa.Float),
            sa.column("active_energy_kcal", sa.Float),
        ).insert(),
        daily_metrics_rows,
    )
    connection.execute(
        sa.table(
            "skin_scans",
            sa.column("id", sa.Uuid),
            sa.column("persona_id", sa.String),
            sa.column("capture_method", sa.String),
            sa.column("captured_at", sa.DateTime(timezone=True)),
            sa.column("completed_at", sa.DateTime(timezone=True)),
            sa.column("status", sa.String),
            sa.column("lower_accuracy", sa.Boolean),
            sa.column("redness_score", sa.Float),
            sa.column("dryness_score", sa.Float),
            sa.column("oiliness_score", sa.Float),
            sa.column("redness_confidence", sa.Float),
            sa.column("dryness_confidence", sa.Float),
            sa.column("oiliness_confidence", sa.Float),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        ).insert(),
        skin_scans_rows,
    )


def downgrade() -> None:
    connection = op.get_bind()
    persona_ids = tuple(PERSONA_BASELINES.keys())
    connection.execute(
        sa.text("DELETE FROM skin_scans WHERE persona_id IN :ids").bindparams(
            sa.bindparam("ids", expanding=True)
        ),
        {"ids": persona_ids},
    )
    connection.execute(
        sa.text("DELETE FROM daily_metrics WHERE persona_id IN :ids").bindparams(
            sa.bindparam("ids", expanding=True)
        ),
        {"ids": persona_ids},
    )
    connection.execute(
        sa.text(
            "DELETE FROM consents WHERE persona_id IN :ids "
            "AND type IN ('apple_health', 'weather_location')"
        ).bindparams(sa.bindparam("ids", expanding=True)),
        {"ids": persona_ids},
    )
