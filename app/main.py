from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse

from app.api.router import api_router
from app.core.config import settings
from app.modules.knowledge.internal_router import router as internal_knowledge_router

OPENAPI_DOCUMENT = Path(__file__).resolve().parent.parent / "docs" / "openapi.yaml"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield


app = FastAPI(
    title="AAC API",
    description="생활·환경 데이터를 활용한 비의료적 피부 관리 참고 서비스",
    version="0.1.0",
    docs_url=None,
    lifespan=lifespan,
)
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.include_router(api_router, prefix=settings.api_prefix)
app.include_router(internal_knowledge_router)


@app.get("/docs/openapi.yaml", include_in_schema=False)
async def openapi_document() -> FileResponse:
    if not OPENAPI_DOCUMENT.is_file():
        raise HTTPException(status_code=404, detail="openapi.yaml not found")
    return FileResponse(OPENAPI_DOCUMENT, media_type="application/yaml")


@app.get("/docs", include_in_schema=False)
async def swagger_ui():
    return get_swagger_ui_html(
        openapi_url="/docs/openapi.yaml",
        title="AAC API - Swagger UI",
    )


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
