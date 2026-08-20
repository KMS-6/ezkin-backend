from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_auth import get_admin
from app.db.session import get_db
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument, KnowledgeIndex
from app.modules.knowledge.chunker import chunk_text
from app.modules.knowledge.schemas import (
    DocumentApproveRequest,
    DocumentApproveResponse,
    DocumentCreateRequest,
    DocumentResponse,
    IndexCreateRequest,
    IndexResponse,
)

router = APIRouter(prefix="/admin/knowledge", tags=["admin-knowledge"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
AdminDep = Annotated[None, Depends(get_admin)]


@router.post("/documents", status_code=status.HTTP_201_CREATED, response_model=DocumentResponse)
async def create_document(
    body: DocumentCreateRequest,
    db: DbSession,
    _: AdminDep,
) -> DocumentResponse:
    doc = KnowledgeDocument(
        source_url=body.source_url,
        title=body.title,
        collected_at=body.collected_at,
        license=body.license,
        source_type_note=body.source_type_note,
        review_status="draft",
    )
    db.add(doc)
    await db.flush()

    chunks = chunk_text(body.raw_text)
    for idx, content in enumerate(chunks):
        db.add(
            KnowledgeChunk(
                document_id=doc.id,
                chunk_index=idx,
                content=content,
                status="draft",
            )
        )
    await db.commit()
    await db.refresh(doc)

    return DocumentResponse(
        id=doc.id,
        source_url=doc.source_url,
        title=doc.title,
        collected_at=doc.collected_at,
        review_status=doc.review_status,
        chunk_count=len(chunks),
        created_at=doc.created_at,
    )


@router.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: UUID,
    db: DbSession,
    _: AdminDep,
) -> DocumentResponse:
    result = await db.execute(select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})

    chunk_result = await db.execute(
        select(KnowledgeChunk).where(KnowledgeChunk.document_id == doc_id)
    )
    chunk_count = len(chunk_result.scalars().all())

    return DocumentResponse(
        id=doc.id,
        source_url=doc.source_url,
        title=doc.title,
        collected_at=doc.collected_at,
        review_status=doc.review_status,
        chunk_count=chunk_count,
        created_at=doc.created_at,
    )


@router.post("/documents/{doc_id}/approve", response_model=DocumentApproveResponse)
async def approve_document(
    doc_id: UUID,
    body: DocumentApproveRequest,
    db: DbSession,
    _: AdminDep,
) -> DocumentApproveResponse:
    result = await db.execute(select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})

    doc.review_status = "approved"
    doc.claim_id = body.claim_id
    doc.claim_version = body.claim_version
    doc.topic = body.topic
    doc.population = body.population
    doc.evidence_level = body.evidence_level
    doc.allowed_features = body.allowed_features
    doc.required_user_facts = body.required_user_facts
    doc.allowed_expressions = body.allowed_expressions
    doc.forbidden_expressions = body.forbidden_expressions
    doc.next_review_at = body.next_review_at

    # 청크도 approved로
    chunk_result = await db.execute(
        select(KnowledgeChunk).where(KnowledgeChunk.document_id == doc_id)
    )
    for chunk in chunk_result.scalars().all():
        chunk.status = "approved"

    await db.commit()
    await db.refresh(doc)

    return DocumentApproveResponse(
        id=doc.id,
        review_status=doc.review_status,
        claim_id=doc.claim_id,
        claim_version=doc.claim_version,
    )


@router.post("/indexes", status_code=status.HTTP_201_CREATED, response_model=IndexResponse)
async def create_index(
    body: IndexCreateRequest,
    db: DbSession,
    _: AdminDep,
) -> IndexResponse:
    # claim_ids에 해당하는 approved 청크 수 계산
    doc_result = await db.execute(
        select(
            KnowledgeDocument.id,
            KnowledgeDocument.claim_id,
            KnowledgeDocument.claim_version,
        ).where(
            KnowledgeDocument.review_status == "approved",
            KnowledgeDocument.claim_id.in_(body.claim_ids),
        )
    )
    documents = doc_result.all()
    doc_ids = [row.id for row in documents]
    claim_versions: dict[str, int] = {}
    for row in documents:
        if row.claim_id is None or row.claim_version is None:
            continue
        claim_versions[row.claim_id] = max(
            row.claim_version, claim_versions.get(row.claim_id, row.claim_version)
        )

    chunk_result = await db.execute(
        select(KnowledgeChunk).where(
            KnowledgeChunk.status == "approved",
            KnowledgeChunk.document_id.in_(doc_ids),
        )
    )
    chunks = chunk_result.scalars().all()

    idx = KnowledgeIndex(
        version=body.version,
        is_active=False,
        claim_ids=body.claim_ids,
        claim_versions=claim_versions,
        chunk_count=len(chunks),
    )
    db.add(idx)
    await db.commit()
    await db.refresh(idx)

    return IndexResponse(
        id=idx.id,
        version=idx.version,
        is_active=idx.is_active,
        claim_ids=idx.claim_ids,
        claim_versions=idx.claim_versions,
        chunk_count=idx.chunk_count,
        created_at=idx.created_at,
    )


@router.post("/indexes/{version}/activate", response_model=IndexResponse)
async def activate_index(
    version: str,
    db: DbSession,
    _: AdminDep,
) -> IndexResponse:
    result = await db.execute(select(KnowledgeIndex).where(KnowledgeIndex.version == version))
    idx = result.scalar_one_or_none()
    if idx is None:
        raise HTTPException(status_code=404, detail={"code": "not_found"})

    # 기존 활성 인덱스 비활성화
    all_result = await db.execute(
        select(KnowledgeIndex).where(KnowledgeIndex.is_active == True)  # noqa: E712
    )
    for active_idx in all_result.scalars().all():
        active_idx.is_active = False

    idx.is_active = True
    await db.commit()
    await db.refresh(idx)

    return IndexResponse(
        id=idx.id,
        version=idx.version,
        is_active=idx.is_active,
        claim_ids=idx.claim_ids,
        claim_versions=idx.claim_versions,
        chunk_count=idx.chunk_count,
        created_at=idx.created_at,
    )
