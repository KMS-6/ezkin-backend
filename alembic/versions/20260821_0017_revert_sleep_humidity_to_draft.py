"""sleep/humidity Claim Card를 draft로 되돌린다.

`공통지식_RAG_근거와_응답규칙_v1.md` 3.1절은 Claim Card를 `approved`로 전환하려면
의료 자문·법무 검토를 거쳐야 한다고 명시한다. 0014/0016 마이그레이션에서 sleep
(`claim_sleep_barrier_001`)과 humidity(`claim_humidity_dryness_001`) 두 건은 이
검토 없이 approved로 등록됐다 — 같은 규칙을 지켜 draft로 남긴 나머지 4건과
일관되지 않았던 실수를 바로잡는다.

`find_claim`(app/modules/knowledge/matching.py)은 `review_status == "approved"`
문서만 후보로 삼으므로, review_status만 draft로 되돌리면 두 Claim 모두 검색·인용
대상에서 제외된다. 인덱스(`knowledge_indexes`)의 claim_ids 구성 자체는 건드리지
않는다 — ADR 002에 따라 인덱스 버전은 불변으로 취급하고, 실제 노출 여부는
문서의 review_status로 통제한다.

검토가 끝나 approved로 전환할 때는 review_status를 다시 'approved'로 되돌리는
후속 마이그레이션을 새로 작성한다(이 마이그레이션을 재사용하지 않는다)."""

import sqlalchemy as sa

from alembic import op

revision: str = "20260821_0017"
down_revision: str | None = "20260821_0016"
branch_labels: str | None = None
depends_on: str | None = None

SLEEP_CLAIM_ID = "claim_sleep_barrier_001"
HUMIDITY_CLAIM_ID = "claim_humidity_dryness_001"


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE knowledge_documents SET review_status = 'draft' "
            "WHERE claim_id IN (:sleep_id, :humidity_id)"
        ),
        {"sleep_id": SLEEP_CLAIM_ID, "humidity_id": HUMIDITY_CLAIM_ID},
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE knowledge_documents SET review_status = 'approved' "
            "WHERE claim_id IN (:sleep_id, :humidity_id)"
        ),
        {"sleep_id": SLEEP_CLAIM_ID, "humidity_id": HUMIDITY_CLAIM_ID},
    )
