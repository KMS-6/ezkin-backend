"""공통지식_RAG_근거와_응답규칙_v1.md 4.2절(습도와 피부 건조) 근거로 humidity 주제
Claim Card(claim_humidity_dryness_001)를 시드한다. briefings/logic.py의
select_common_knowledge가 이미 topic="humidity"로 find_claim을 호출하고 있어 이
Claim Card가 없으면 항상 None을 반환하던 상태였다.

ADR 002(20260821_0010_pin_knowledge_claim_versions)에 따라 기존 활성 인덱스를
재사용하지 않고, sleep+humidity 두 claim을 모두 포함하는 새 인덱스 버전을 만들어
활성화하고 이전 인덱스는 비활성화한다."""

from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "20260821_0016"
down_revision: str | None = "20260821_0015"
branch_labels: str | None = None
depends_on: str | None = None

SEEDED_AT = datetime.now(UTC)
COLLECTED_AT = datetime(2026, 8, 21, tzinfo=UTC)
NEXT_REVIEW_AT = datetime(2027, 8, 21, tzinfo=UTC)

HUMIDITY_DOC_ID = uuid4()
HUMIDITY_CHUNK_ID = uuid4()
NEW_INDEX_ID = uuid4()

PREVIOUS_INDEX_VERSION = "knowledge-index-2026-08-21-v1"
NEW_INDEX_VERSION = "knowledge-index-2026-08-21-v2"

SLEEP_CLAIM_ID = "claim_sleep_barrier_001"
SLEEP_CLAIM_VERSION = 1
HUMIDITY_CLAIM_ID = "claim_humidity_dryness_001"
HUMIDITY_CLAIM_VERSION = 1

HUMIDITY_RAW_TEXT = (
    "습도와 각질층 수분, 피부 거칠기, 경피수분손실(TEWL) 등의 관계를 정리한 리뷰는 "
    "낮은 습도가 피부 건조 지표와 관련될 가능성을 제시하지만, 연구 대상과 결과가 "
    "완전히 일관되지는 않는다고 설명한다. 이 리뷰는 여러 인체·실험 연구를 종합한 "
    "것으로 단일 population에 국한되지 않으며, 습도 하나만으로 피부 장벽 손상을 "
    "단정할 수 없다는 한계를 함께 언급한다."
)
HUMIDITY_ALLOWED_EXPRESSIONS = (
    "오늘은 습도가 낮아 건조함이 나타날 수 있어요. 보습에 조금 더 신경 써주세요."
)
HUMIDITY_FORBIDDEN_EXPRESSIONS = (
    "낮은 습도가 오늘 트러블의 원인입니다. / 습도 때문에 피부 장벽이 무너졌어요."
)


def upgrade() -> None:
    connection = op.get_bind()

    documents_table = sa.table(
        "knowledge_documents",
        sa.column("id", sa.Uuid),
        sa.column("source_url", sa.Text),
        sa.column("title", sa.String),
        sa.column("collected_at", sa.DateTime(timezone=True)),
        sa.column("license", sa.Text),
        sa.column("source_type_note", sa.Text),
        sa.column("review_status", sa.String),
        sa.column("claim_id", sa.String),
        sa.column("claim_version", sa.Integer),
        sa.column("topic", sa.Text),
        sa.column("population", sa.Text),
        sa.column("evidence_level", sa.String),
        sa.column("allowed_features", sa.JSON),
        sa.column("required_user_facts", sa.JSON),
        sa.column("allowed_expressions", sa.Text),
        sa.column("forbidden_expressions", sa.Text),
        sa.column("next_review_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    chunks_table = sa.table(
        "knowledge_chunks",
        sa.column("id", sa.Uuid),
        sa.column("document_id", sa.Uuid),
        sa.column("chunk_index", sa.Integer),
        sa.column("content", sa.Text),
        sa.column("status", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    indexes_table = sa.table(
        "knowledge_indexes",
        sa.column("id", sa.Uuid),
        sa.column("version", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("claim_ids", sa.JSON),
        sa.column("claim_versions", sa.JSON),
        sa.column("chunk_count", sa.Integer),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    connection.execute(
        documents_table.insert(),
        [
            {
                "id": HUMIDITY_DOC_ID,
                "source_url": "https://pubmed.ncbi.nlm.nih.gov/27306376/",
                "title": "Ambient humidity and the skin",
                "collected_at": COLLECTED_AT,
                "license": None,
                "source_type_note": (
                    "공통지식_RAG_근거와_응답규칙_v1.md 4.2절(습도와 피부 건조) 근거"
                ),
                "review_status": "approved",
                "claim_id": HUMIDITY_CLAIM_ID,
                "claim_version": HUMIDITY_CLAIM_VERSION,
                "topic": "humidity",
                "population": "성인",
                "evidence_level": "C",
                "allowed_features": ["briefing", "report"],
                "required_user_facts": [
                    "weather_consent",
                    "fresh_humidity_data",
                    "humidity_below_rule_threshold",
                ],
                "allowed_expressions": HUMIDITY_ALLOWED_EXPRESSIONS,
                "forbidden_expressions": HUMIDITY_FORBIDDEN_EXPRESSIONS,
                "next_review_at": NEXT_REVIEW_AT,
                "created_at": SEEDED_AT,
                "updated_at": SEEDED_AT,
            }
        ],
    )
    connection.execute(
        chunks_table.insert(),
        [
            {
                "id": HUMIDITY_CHUNK_ID,
                "document_id": HUMIDITY_DOC_ID,
                "chunk_index": 0,
                "content": HUMIDITY_RAW_TEXT,
                "status": "approved",
                "created_at": SEEDED_AT,
                "updated_at": SEEDED_AT,
            }
        ],
    )
    connection.execute(
        indexes_table.insert(),
        [
            {
                "id": NEW_INDEX_ID,
                "version": NEW_INDEX_VERSION,
                "is_active": True,
                "claim_ids": [SLEEP_CLAIM_ID, HUMIDITY_CLAIM_ID],
                "claim_versions": {
                    SLEEP_CLAIM_ID: SLEEP_CLAIM_VERSION,
                    HUMIDITY_CLAIM_ID: HUMIDITY_CLAIM_VERSION,
                },
                "chunk_count": 2,
                "created_at": SEEDED_AT,
                "updated_at": SEEDED_AT,
            }
        ],
    )
    connection.execute(
        sa.text("UPDATE knowledge_indexes SET is_active = false WHERE version = :version"),
        {"version": PREVIOUS_INDEX_VERSION},
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("UPDATE knowledge_indexes SET is_active = true WHERE version = :version"),
        {"version": PREVIOUS_INDEX_VERSION},
    )
    connection.execute(
        sa.text("DELETE FROM knowledge_indexes WHERE version = :version"),
        {"version": NEW_INDEX_VERSION},
    )
    connection.execute(
        sa.text("DELETE FROM knowledge_chunks WHERE document_id = :doc_id"),
        {"doc_id": str(HUMIDITY_DOC_ID)},
    )
    connection.execute(
        sa.text("DELETE FROM knowledge_documents WHERE id = :doc_id"),
        {"doc_id": str(HUMIDITY_DOC_ID)},
    )
