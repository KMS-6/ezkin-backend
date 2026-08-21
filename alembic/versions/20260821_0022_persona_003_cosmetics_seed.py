"""persona_003(장기 사용자 데모)에 화장품 7종 seed 데이터 추가 —
Briefing 오늘 루틴/쉬어갈 제품, SOS 성분 답변이 실제 보유 제품 컨텍스트로 동작하도록 준비.
같은 리비전에서 persona_003의 오늘자 캐시된 Briefing이 있다면 함께 삭제해 다음 조회 시
새 보유 제품을 반영해 재생성되도록 한다."""

import uuid
from collections.abc import Sequence
from datetime import datetime
from zoneinfo import ZoneInfo

import sqlalchemy as sa

from alembic import op

revision: str = "20260821_0022"
down_revision: str | None = "20260821_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KST = ZoneInfo("Asia/Seoul")
PERSONA_ID = "persona_003"

# id는 uuid5로 고정해 downgrade에서 정확히 같은 row만 되돌릴 수 있게 한다.
_NAMESPACE = uuid.NAMESPACE_URL
PERSONA_003_COSMETICS = [
    {
        "brand": "G사",
        "product_name": "클렌징 오일",
        "product_type": "cleanser",
        "ingredients_raw": None,
    },
    {
        "brand": "E사",
        "product_name": "나이아신아마이드 토너",
        "product_type": "toner",
        "ingredients_raw": ["나이아신아마이드"],
    },
    {
        "brand": "C사",
        "product_name": "레티놀 세럼",
        "product_type": "serum",
        "ingredients_raw": ["레티놀"],
    },
    {
        "brand": "B사",
        "product_name": "세라마이드 크림",
        "product_type": "moisturizer",
        "ingredients_raw": ["세라마이드"],
    },
    {
        "brand": "F사",
        "product_name": "판테놀 진정크림",
        "product_type": "moisturizer",
        "ingredients_raw": ["판테놀"],
    },
    {
        "brand": "D사",
        "product_name": "선크림",
        "product_type": "sunscreen",
        "ingredients_raw": None,
    },
    {
        "brand": "A사",
        "product_name": "비타민C 앰플",
        "product_type": "serum",
        "ingredients_raw": ["비타민C"],
    },
]


def _cosmetic_id(product_name: str) -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, f"{PERSONA_ID}:persona_cosmetic:{product_name}")


def upgrade() -> None:
    connection = op.get_bind()

    rows = [
        {
            "id": _cosmetic_id(item["product_name"]),
            "persona_id": PERSONA_ID,
            "brand": item["brand"],
            "product_name": item["product_name"],
            "product_type": item["product_type"],
            "ingredients_raw": item["ingredients_raw"],
        }
        for item in PERSONA_003_COSMETICS
    ]

    connection.execute(
        sa.table(
            "persona_cosmetics",
            sa.column("id", sa.Uuid),
            sa.column("persona_id", sa.String),
            sa.column("brand", sa.String),
            sa.column("product_name", sa.String),
            sa.column("product_type", sa.String),
            sa.column("ingredients_raw", sa.JSON),
        ).insert(),
        rows,
    )

    # persona_003의 오늘자 Briefing이 이미 생성·캐시돼 있다면 삭제해, 다음 조회 시
    # 방금 추가한 보유 제품을 반영해 재생성되도록 한다(get_or_generate_briefing은
    # 같은 날짜 row가 있으면 재생성하지 않고 그대로 반환한다).
    today = datetime.now(KST).date()
    connection.execute(
        sa.text("DELETE FROM briefings WHERE persona_id = :persona_id AND briefing_date = :today"),
        {"persona_id": PERSONA_ID, "today": today},
    )


def downgrade() -> None:
    connection = op.get_bind()
    ids = tuple(_cosmetic_id(item["product_name"]) for item in PERSONA_003_COSMETICS)
    connection.execute(
        sa.text("DELETE FROM persona_cosmetics WHERE id IN :ids").bindparams(
            sa.bindparam("ids", expanding=True)
        ),
        {"ids": ids},
    )
