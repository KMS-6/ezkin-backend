from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument, KnowledgeIndex


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


@pytest.mark.asyncio
async def test_create_knowledge_document(db_session) -> None:
    doc = KnowledgeDocument(
        source_url="https://example.com/article",
        title="테스트 문서",
        collected_at=datetime.now(UTC),
        review_status="draft",
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    assert doc.id is not None
    assert doc.review_status == "draft"
    assert doc.claim_id is None


@pytest.mark.asyncio
async def test_create_chunk_linked_to_document(db_session) -> None:
    doc = KnowledgeDocument(
        source_url="https://example.com/article",
        title="문서",
        collected_at=datetime.now(UTC),
    )
    db_session.add(doc)
    await db_session.flush()

    chunk = KnowledgeChunk(
        document_id=doc.id,
        chunk_index=0,
        content="테스트 청크 내용",
        status="draft",
    )
    db_session.add(chunk)
    await db_session.commit()
    await db_session.refresh(chunk)

    assert chunk.document_id == doc.id
    assert chunk.chunk_index == 0


@pytest.mark.asyncio
async def test_create_knowledge_index(db_session) -> None:
    idx = KnowledgeIndex(
        version="v1",
        is_active=False,
        claim_ids=["claim-001"],
        chunk_count=10,
    )
    db_session.add(idx)
    await db_session.commit()
    await db_session.refresh(idx)

    assert idx.version == "v1"
    assert idx.is_active is False
    assert idx.claim_ids == ["claim-001"]
