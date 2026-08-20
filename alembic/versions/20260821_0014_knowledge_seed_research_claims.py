"""docs/research.md 2절 안드로겐 경로 근거로 인용된 논문 5편을 공통 지식 RAG에 시드 —
sleep 주제만 승인(approved) Claim Card + 활성 인덱스로 등록해 Briefing/Report의
find_claim(topic="sleep")이 실제로 근거를 찾도록 하고, 나머지 4편(생리주기 2편·스트레스·
식단/안드로겐 병인)은 `공통지식_RAG_근거와_응답규칙_v1.md` 4.7/4.8절의 인과 주장 금지
규칙에 따라 draft 상태(참고용, 미검색)로만 등록한다."""

from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "20260821_0014"
down_revision: str | None = "20260821_0013"
branch_labels: str | None = None
depends_on: str | None = None

COLLECTED_AT = datetime(2026, 8, 21, tzinfo=UTC)
NEXT_REVIEW_AT = datetime(2027, 8, 21, tzinfo=UTC)
# 기존 knowledge_chunks 테이블의 created_at/updated_at server_default가
# Postgres 전용 now()라 SQLite 테스트 마이그레이션에서 실패한다 — 세 테이블 모두
# 명시적으로 값을 채워 server_default에 의존하지 않는다(20260821_0013 seed와 동일 패턴).
SEEDED_AT = datetime.now(UTC)

SLEEP_DOC_ID = uuid4()
TRIGGER_DOC_ID = uuid4()
PREMENSTRUAL_DOC_ID = uuid4()
STRESS_DOC_ID = uuid4()
DIET_DOC_ID = uuid4()

CLAIM_ID = "claim_sleep_barrier_001"
CLAIM_VERSION = 1
INDEX_VERSION = "knowledge-index-2026-08-21-v1"

DOCUMENTS = [
    {
        "id": SLEEP_DOC_ID,
        "source_url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8775463/",
        "title": "Sleep and Skin Barrier — NCBI PMC 2022",
        "collected_at": COLLECTED_AT,
        "license": "PMC Open Access",
        "source_type_note": "research.md 2절 안드로겐 경로 근거 — 수면 부족 카테고리",
        "review_status": "approved",
        "claim_id": CLAIM_ID,
        "claim_version": CLAIM_VERSION,
        "topic": "sleep",
        "population": "성인",
        "evidence_level": "C",
        "allowed_features": ["briefing", "report"],
        "required_user_facts": [
            "sleep_hours_available",
            "sleep_below_personal_baseline_or_threshold",
        ],
        "allowed_expressions": (
            "최근 수면이 짧아 오늘은 피부 자극을 줄여보세요. "
            "수면의 질이 낮으면 피부 장벽 회복이 더뎌질 수 있어요."
        ),
        "forbidden_expressions": (
            "수면 부족 때문에 트러블이 생겼어요. / 수면 부족으로 피부 장벽이 손상됐어요."
        ),
        "next_review_at": NEXT_REVIEW_AT,
        "raw_text": (
            "폐쇄성 수면무호흡증(OSAS) 환자와 건강한 대조군 86명을 비교한 단면연구에서, "
            "OSAS 환자군은 경피수분손실(TEWL)이 더 높고 수면의 질(PSQI)이 유의하게 낮았다. "
            "중증도가 높을수록 TEWL 수치도 함께 높아지는 경향이 관찰됐다. 연구진은 수면 장애, "
            "불안, 우울, 스트레스, 식습관 등 여러 노출 요인이 함께 작용해 피부 장벽 기능에 "
            "영향을 줄 수 있다고 설명한다. 다만 이 연구는 관찰 연구로 개인의 인과관계를 "
            "증명하지 않으며, 하루의 짧은 수면만으로 만성적인 장벽 손상을 단정할 수 없다."
        ),
    },
    {
        "id": TRIGGER_DOC_ID,
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/32832440/",
        "title": "Trigger Factors in Adult Female Acne — PubMed 2020",
        "collected_at": COLLECTED_AT,
        "license": None,
        "source_type_note": (
            "보류(참고용, 미검색): 자기 보고 기반 트리거 순위 연구 — 4.8절 식단 인과 주장 "
            "금지 규칙 검토 전"
        ),
        "review_status": "draft",
        "claim_id": None,
        "claim_version": None,
        "topic": None,
        "population": "성인 여성",
        "evidence_level": None,
        "allowed_features": None,
        "required_user_facts": None,
        "allowed_expressions": None,
        "forbidden_expressions": None,
        "next_review_at": None,
        "raw_text": (
            "성인 여성 165명을 대상으로 여드름 악화 요인에 대한 인식을 조사한 설문 연구에서, "
            "응답자들은 생리 전 호르몬 변화를 가장 흔한 악화 요인으로 꼽았고, 이어서 식단, "
            "화장품, 스트레스 순으로 응답했다. 이 결과는 사용자 자기 보고 기반 순위이며, "
            "실험적으로 인과관계를 증명한 연구는 아니다."
        ),
    },
    {
        "id": PREMENSTRUAL_DOC_ID,
        "source_url": "https://jamanetwork.com/journals/jamadermatology/fullarticle/480456",
        "title": "Quantitative Premenstrual Acne Flare — JAMA Dermatology",
        "collected_at": COLLECTED_AT,
        "license": None,
        "source_type_note": (
            "보류(참고용, 미검색): 생리주기-여드름 연관 연구 — 개인 생리주기 fact 산출 "
            "로직이 아직 없어 Claim Card 미생성"
        ),
        "review_status": "draft",
        "claim_id": None,
        "claim_version": None,
        "topic": None,
        "population": "성인 여성",
        "evidence_level": None,
        "allowed_features": None,
        "required_user_facts": None,
        "allowed_expressions": None,
        "forbidden_expressions": None,
        "next_review_at": None,
        "raw_text": (
            "생리 주기와 여드름 악화의 관계를 정량적으로 조사한 연구에서, 여성 응답자의 "
            "상당수(약 36~78%로 보고된 범위)가 생리 전 여드름이 악화된다고 보고했다. "
            "다만 연구마다 보고 비율 편차가 크고, 자기 보고에 의존하는 한계가 있다."
        ),
    },
    {
        "id": STRESS_DOC_ID,
        "source_url": "https://www.researchsquare.com/article/rs-4477781/v1",
        "title": "Stress-Induced Acne Mechanisms — Research Square 2024",
        "collected_at": COLLECTED_AT,
        "license": "프리프린트(동료 심사 전)",
        "source_type_note": (
            "보류(참고용, 미검색): HRV·스트레스는 4.7절에 따라 evidence level D로 "
            "취급하며 피부 원인 설명용 Claim Card를 만들지 않는다"
        ),
        "review_status": "draft",
        "claim_id": None,
        "claim_version": None,
        "topic": None,
        "population": "성인",
        "evidence_level": None,
        "allowed_features": None,
        "required_user_facts": None,
        "allowed_expressions": None,
        "forbidden_expressions": None,
        "next_review_at": None,
        "raw_text": (
            "스트레스가 여드름 발생·악화에 관여할 수 있는 다양한 기전(호르몬 변화, 염증, "
            "피부 장벽 기능 저하, 면역 조절, 신경펩타이드, 산화 스트레스, 인슐린 저항성, "
            "피부 pH 변화, 혈관 변화, 생활습관, 피부 미생물총 변화 등)을 정리한 문헌 "
            "리뷰다. 저자는 여러 기전 후보를 종합적으로 제시했으나, 개별 기전 각각의 "
            "인과적 기여도를 정량화하지는 않았다."
        ),
    },
    {
        "id": DIET_DOC_ID,
        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12042216/",
        "title": "Etiology of Adult Female Acne Systematic Review 2025 — PMC",
        "collected_at": COLLECTED_AT,
        "license": "PMC Open Access",
        "source_type_note": (
            "보류(참고용, 미검색): 고GI 식단-IGF-1-안드로겐 경로 리뷰 — 4.8절 식단 인과 "
            "주장 금지 규칙에 따라 Claim Card 미생성"
        ),
        "review_status": "draft",
        "claim_id": None,
        "claim_version": None,
        "topic": None,
        "population": "성인 여성",
        "evidence_level": None,
        "allowed_features": None,
        "required_user_facts": None,
        "allowed_expressions": None,
        "forbidden_expressions": None,
        "next_review_at": None,
        "raw_text": (
            "성인 여드름의 병인을 다룬 체계적 문헌고찰로, 고안드로겐혈증·가족력·고혈당지수"
            "(고GI) 식단이 성인 여드름 발생과 연관될 수 있다고 정리한다. 고GI 식단이 IGF-1 "
            "수치를 높이고, IGF-1이 피지선 성장·피지 분비·각질세포 증식을 촉진하며 안드로겐 "
            "합성을 활성화하는 경로를 설명한다. 다만 유제품과 여드름의 연관성은 연구마다 "
            "결과가 상반돼 합의된 결론이 없다고 명시한다."
        ),
    },
]


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
                **{key: value for key, value in doc.items() if key != "raw_text"},
                "created_at": SEEDED_AT,
                "updated_at": SEEDED_AT,
            }
            for doc in DOCUMENTS
        ],
    )
    connection.execute(
        chunks_table.insert(),
        [
            {
                "id": uuid4(),
                "document_id": doc["id"],
                "chunk_index": 0,
                "content": doc["raw_text"],
                "status": "approved" if doc["review_status"] == "approved" else "draft",
                "created_at": SEEDED_AT,
                "updated_at": SEEDED_AT,
            }
            for doc in DOCUMENTS
        ],
    )
    connection.execute(
        indexes_table.insert(),
        [
            {
                "id": uuid4(),
                "version": INDEX_VERSION,
                "is_active": True,
                "claim_ids": [CLAIM_ID],
                "claim_versions": {CLAIM_ID: CLAIM_VERSION},
                "chunk_count": 1,
                "created_at": SEEDED_AT,
                "updated_at": SEEDED_AT,
            }
        ],
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("DELETE FROM knowledge_indexes WHERE version = :version"),
        {"version": INDEX_VERSION},
    )
    doc_ids = tuple(str(doc["id"]) for doc in DOCUMENTS)
    connection.execute(
        sa.text("DELETE FROM knowledge_chunks WHERE document_id IN :ids").bindparams(
            sa.bindparam("ids", expanding=True)
        ),
        {"ids": doc_ids},
    )
    connection.execute(
        sa.text("DELETE FROM knowledge_documents WHERE id IN :ids").bindparams(
            sa.bindparam("ids", expanding=True)
        ),
        {"ids": doc_ids},
    )
