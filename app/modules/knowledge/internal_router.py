from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_auth import get_admin
from app.db.session import get_db
from app.modules.knowledge.schemas import KnowledgeSearchRequest, KnowledgeSearchResponse
from app.modules.knowledge.search import keyword_search

router = APIRouter(prefix="/internal/knowledge", include_in_schema=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post("/search", dependencies=[Depends(get_admin)])
async def internal_search(
    body: KnowledgeSearchRequest,
    db: DbSession,
) -> KnowledgeSearchResponse:
    results = await keyword_search(db, body.keywords, body.limit)
    return KnowledgeSearchResponse(results=results)
