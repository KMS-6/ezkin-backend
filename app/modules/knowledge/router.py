from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_auth import require_admin
from app.db.session import get_db
from app.models.knowledge import KnowledgeDocument, KnowledgeIndex
from app.modules.knowledge.schemas import (
    ClaimApproveIn,
    KnowledgeDocumentCreateIn,
    KnowledgeDocumentOut,
    KnowledgeIndexCreateIn,
    KnowledgeIndexOut,
)

router = APIRouter(
    prefix="/admin/knowledge", tags=["admin-knowledge"], dependencies=[Depends(require_admin)]
)
DbSession = Annotated[AsyncSession, Depends(get_db)]


def _to_document_out(document: KnowledgeDocument) -> KnowledgeDocumentOut:
    return KnowledgeDocumentOut(
        id=str(document.id),
        source_url=document.source_url,
        title=document.title,
        collected_at=document.collected_at,
        license=document.license,
        review_status=document.review_status,
        claim_id=document.claim_id,
        claim_version=document.claim_version,
        topic=document.topic,
        population=document.population,
        evidence_level=document.evidence_level,
        allowed_features=document.allowed_features,
        required_user_facts=document.required_user_facts,
        next_review_at=document.next_review_at,
    )


@router.post("/documents", response_model=KnowledgeDocumentOut, status_code=status.HTTP_201_CREATED)
async def create_document(
    payload: KnowledgeDocumentCreateIn, db: DbSession
) -> KnowledgeDocumentOut:
    document = KnowledgeDocument(**payload.model_dump(), review_status="draft")
    db.add(document)
    await db.commit()
    return _to_document_out(document)


@router.post("/documents/{document_id}/approve", response_model=KnowledgeDocumentOut)
async def approve_document(
    document_id: UUID, payload: ClaimApproveIn, db: DbSession
) -> KnowledgeDocumentOut:
    document = await db.get(KnowledgeDocument, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="문서를 찾을 수 없습니다."
        )
    for field, value in payload.model_dump().items():
        setattr(document, field, value)
    document.review_status = "approved"
    await db.commit()
    await db.refresh(document)
    return _to_document_out(document)


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentOut)
async def get_document(document_id: UUID, db: DbSession) -> KnowledgeDocumentOut:
    document = await db.get(KnowledgeDocument, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="문서를 찾을 수 없습니다."
        )
    return _to_document_out(document)


@router.post("/indexes", response_model=KnowledgeIndexOut, status_code=status.HTTP_201_CREATED)
async def create_index(payload: KnowledgeIndexCreateIn, db: DbSession) -> KnowledgeIndexOut:
    result = await db.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.review_status == "approved")
    )
    claim_ids = sorted({doc.claim_id for doc in result.scalars() if doc.claim_id})
    index = KnowledgeIndex(version=payload.version, claim_ids=claim_ids, is_active=False)
    db.add(index)
    await db.commit()
    return KnowledgeIndexOut(
        version=index.version, claim_ids=index.claim_ids, is_active=index.is_active
    )


@router.post("/indexes/{version}/activate", response_model=KnowledgeIndexOut)
async def activate_index(version: str, db: DbSession) -> KnowledgeIndexOut:
    result = await db.execute(select(KnowledgeIndex).where(KnowledgeIndex.version == version))
    index = result.scalar_one_or_none()
    if index is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="인덱스를 찾을 수 없습니다."
        )
    await db.execute(update(KnowledgeIndex).values(is_active=False))
    index.is_active = True
    await db.commit()
    await db.refresh(index)
    return KnowledgeIndexOut(
        version=index.version, claim_ids=index.claim_ids, is_active=index.is_active
    )
