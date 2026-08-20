"""키워드 기반 청크 검색 서비스.

approved 상태 청크만 대상으로, is_active=True인 인덱스의 claim_id와
연결된 문서의 청크를 content ilike 검색한다.
SQLite에서는 like를 사용하고 PostgreSQL에서는 ilike를 사용한다.
"""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeChunk, KnowledgeDocument, KnowledgeIndex
from app.modules.knowledge.schemas import KnowledgeChunkResult


async def active_claim_ids(db: AsyncSession) -> set[str]:
    """활성 인덱스(is_active=True)들이 함께 참조하는 claim_id 전체."""
    idx_result = await db.execute(
        select(KnowledgeIndex).where(KnowledgeIndex.is_active == True)  # noqa: E712
    )
    allowed: set[str] = set()
    for idx in idx_result.scalars():
        allowed.update(idx.claim_ids or [])
    return allowed


async def active_claim_versions(db: AsyncSession) -> dict[str, int]:
    """활성 인덱스가 생성될 때 고정한 claim_id별 버전."""
    idx_result = await db.execute(
        select(KnowledgeIndex).where(KnowledgeIndex.is_active == True)  # noqa: E712
    )
    allowed: dict[str, int] = {}
    for idx in idx_result.scalars():
        allowed.update(idx.claim_versions or {})
    return allowed


async def keyword_search(
    db: AsyncSession,
    keywords: list[str],
    limit: int = 5,
) -> list[KnowledgeChunkResult]:
    if not keywords:
        return []

    allowed_claim_ids = await active_claim_ids(db)
    if not allowed_claim_ids:
        return []

    # approved 문서 중 allowed_claim_ids에 속하는 것
    doc_result = await db.execute(
        select(KnowledgeDocument.id).where(
            KnowledgeDocument.review_status == "approved",
            KnowledgeDocument.claim_id.in_(allowed_claim_ids),
        )
    )
    allowed_doc_ids = [row[0] for row in doc_result.all()]
    if not allowed_doc_ids:
        return []

    # approved 청크 중 허용 문서에 속하고 키워드를 포함하는 것 (DB 1차 필터링)
    keyword_filters = [KnowledgeChunk.content.ilike(f"%{kw}%") for kw in keywords]
    chunk_result = await db.execute(
        select(KnowledgeChunk).where(
            KnowledgeChunk.status == "approved",
            KnowledgeChunk.document_id.in_(allowed_doc_ids),
            or_(*keyword_filters),
        )
    )
    candidates = chunk_result.scalars().all()

    # 키워드 매칭 스코어 계산 (대소문자 무시)
    scored: list[tuple[int, KnowledgeChunk]] = []
    lower_keywords = [kw.lower() for kw in keywords]
    for chunk in candidates:
        content_lower = chunk.content.lower()
        score = sum(1 for kw in lower_keywords if kw in content_lower)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:limit]

    return [
        KnowledgeChunkResult(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            content=chunk.content,
            score=score,
        )
        for score, chunk in top
    ]
