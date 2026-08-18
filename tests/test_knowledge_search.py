from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument, KnowledgeIndex
from app.modules.knowledge.search import keyword_search


@pytest.fixture()
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _make_approved_doc_with_chunk(db, claim_id: str, content: str) -> KnowledgeChunk:
    doc = KnowledgeDocument(
        source_url="https://example.com",
        title="테스트",
        collected_at=datetime.now(UTC),
        review_status="approved",
        claim_id=claim_id,
    )
    db.add(doc)
    await db.flush()
    chunk = KnowledgeChunk(
        document_id=doc.id,
        chunk_index=0,
        content=content,
        status="approved",
    )
    db.add(chunk)
    await db.flush()
    return chunk


@pytest.mark.asyncio
async def test_returns_empty_when_no_active_index(db_session) -> None:
    await _make_approved_doc_with_chunk(db_session, "claim-1", "피부 보습 크림")
    await db_session.commit()

    result = await keyword_search(db_session, ["피부"])
    assert result == []


@pytest.mark.asyncio
async def test_returns_empty_when_active_index_has_no_matching_claim(db_session) -> None:
    await _make_approved_doc_with_chunk(db_session, "claim-1", "피부 보습 크림")
    idx = KnowledgeIndex(version="v1", is_active=True, claim_ids=["other-claim"], chunk_count=0)
    db_session.add(idx)
    await db_session.commit()

    result = await keyword_search(db_session, ["피부"])
    assert result == []


@pytest.mark.asyncio
async def test_keyword_match_returns_chunk(db_session) -> None:
    chunk = await _make_approved_doc_with_chunk(db_session, "claim-1", "피부 보습에 좋은 크림")
    idx = KnowledgeIndex(version="v1", is_active=True, claim_ids=["claim-1"], chunk_count=1)
    db_session.add(idx)
    await db_session.commit()

    result = await keyword_search(db_session, ["보습"])
    assert len(result) == 1
    assert str(result[0].chunk_id) == str(chunk.id)
    assert result[0].score == 1


@pytest.mark.asyncio
async def test_multiple_keywords_score_higher(db_session) -> None:
    # 두 키워드 모두 포함하는 청크 vs 하나만 포함
    chunk_a = await _make_approved_doc_with_chunk(db_session, "claim-1", "피부 보습 수분 케어")
    await _make_approved_doc_with_chunk(db_session, "claim-1", "피부 보습만")
    idx = KnowledgeIndex(version="v1", is_active=True, claim_ids=["claim-1"], chunk_count=2)
    db_session.add(idx)
    await db_session.commit()

    result = await keyword_search(db_session, ["피부", "수분"])
    # chunk_a가 두 키워드 매칭 → 먼저 나와야 함
    assert str(result[0].chunk_id) == str(chunk_a.id)
    assert result[0].score == 2
    assert result[1].score == 1


@pytest.mark.asyncio
async def test_draft_chunks_excluded(db_session) -> None:
    """draft 상태 청크는 결과에 포함되지 않는다."""
    doc = KnowledgeDocument(
        source_url="https://example.com",
        title="테스트",
        collected_at=datetime.now(UTC),
        review_status="approved",
        claim_id="claim-1",
    )
    db_session.add(doc)
    await db_session.flush()
    chunk = KnowledgeChunk(
        document_id=doc.id,
        chunk_index=0,
        content="피부 보습",
        status="draft",  # draft 상태
    )
    db_session.add(chunk)
    idx = KnowledgeIndex(version="v1", is_active=True, claim_ids=["claim-1"], chunk_count=1)
    db_session.add(idx)
    await db_session.commit()

    result = await keyword_search(db_session, ["피부"])
    assert result == []


@pytest.mark.asyncio
async def test_limit_respected(db_session) -> None:
    for i in range(6):
        await _make_approved_doc_with_chunk(db_session, "claim-1", f"피부 보습 아이템 {i}")
    idx = KnowledgeIndex(version="v1", is_active=True, claim_ids=["claim-1"], chunk_count=6)
    db_session.add(idx)
    await db_session.commit()

    result = await keyword_search(db_session, ["피부"], limit=3)
    assert len(result) <= 3
