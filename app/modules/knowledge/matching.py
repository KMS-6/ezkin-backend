"""승인된 Claim Card 중 조건에 맞는 근거 1개를 고른다.

`AAC 공통 지식 RAG 근거와 응답 규칙 v1` 9절(검색 filter), Morning Briefing 8.3절
("한 Briefing에는 common_knowledge를 최대 1개만 포함") 기준. 이 모듈은 어떤 근거를
"보여줄지"만 고르며, 위험도나 제품 선택 같은 판정 자체는 절대 바꾸지 않는다 — 판정은
이미 Rule Engine(risk/logic.py)이 끝낸 뒤 호출된다.

population 검증(RAG 문서 2.1절: 연령대가 명백히 다르면 후보에서 제외)은 구현하지
않는다 — Persona 모델(app/models/persona.py)에 나이 같은 구조화 인구통계 필드가
없고 summary_traits는 자유 텍스트라, 신뢰성 있게 비교할 데이터 자체가 없다. 이후
Persona에 해당 필드가 추가되면 여기서 걸러야 한다.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeDocument
from app.modules.knowledge.search import active_claim_ids


@dataclass
class ClaimMatch:
    claim_id: str
    version: int
    sentence: str


async def find_claim(
    db: AsyncSession,
    *,
    feature: str,
    topic: str,
    facts: set[str],
) -> ClaimMatch | None:
    """`topic`이 일치하고 `feature`가 allowed_features에 있으며, 문서의
    required_user_facts가 전부 `facts` 안에 있는 approved 클레임 하나를 고른다.

    required_user_facts가 비어 있는 문서는 제외한다(3절 필수 metadata 누락으로
    보고, 조건 없이 아무 때나 노출되는 걸 막는다). 여러 후보가 있으면 최신
    version을 우선한다.
    """
    allowed_claim_ids = await active_claim_ids(db)
    if not allowed_claim_ids:
        return None

    doc_result = await db.execute(
        select(KnowledgeDocument)
        .where(
            KnowledgeDocument.review_status == "approved",
            KnowledgeDocument.claim_id.in_(allowed_claim_ids),
            KnowledgeDocument.topic == topic,
        )
        .order_by(KnowledgeDocument.claim_version.desc())
    )
    for document in doc_result.scalars():
        if feature not in (document.allowed_features or []):
            continue
        required = set(document.required_user_facts or [])
        if not required or not required.issubset(facts):
            continue
        if not document.allowed_expressions or document.claim_id is None:
            continue
        return ClaimMatch(
            claim_id=document.claim_id,
            version=document.claim_version or 1,
            sentence=document.allowed_expressions,
        )
    return None
