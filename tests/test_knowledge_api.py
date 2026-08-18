"""Admin Knowledge API + Internal Search API 통합 테스트."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app

ADMIN_HEADERS = {"X-Admin-Key": "dev-admin-key"}
COLLECTED_AT = datetime.now(UTC).isoformat()
RAW_TEXT = (
    "피부 보습에는 세라마이드 성분이 중요합니다.\n\n수분 유지를 위해 히알루론산도 효과적입니다."
)


@pytest.fixture()
async def client():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


# ── 문서 등록 ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_document_without_admin_key_returns_403(client) -> None:
    resp = await client.post(
        "/api/v1/admin/knowledge/documents",
        json={
            "source_url": "https://x.com",
            "title": "t",
            "collected_at": COLLECTED_AT,
            "raw_text": "a",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_document_success(client) -> None:
    resp = await client.post(
        "/api/v1/admin/knowledge/documents",
        headers=ADMIN_HEADERS,
        json={
            "source_url": "https://example.com/skin",
            "title": "피부 보습 가이드",
            "collected_at": COLLECTED_AT,
            "raw_text": RAW_TEXT,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["review_status"] == "draft"
    assert data["chunk_count"] >= 1
    assert "id" in data


@pytest.mark.asyncio
async def test_get_document_success(client) -> None:
    create_resp = await client.post(
        "/api/v1/admin/knowledge/documents",
        headers=ADMIN_HEADERS,
        json={
            "source_url": "https://example.com/skin",
            "title": "피부 보습 가이드",
            "collected_at": COLLECTED_AT,
            "raw_text": RAW_TEXT,
        },
    )
    doc_id = create_resp.json()["id"]

    get_resp = await client.get(
        f"/api/v1/admin/knowledge/documents/{doc_id}",
        headers=ADMIN_HEADERS,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == doc_id


@pytest.mark.asyncio
async def test_get_nonexistent_document_returns_404(client) -> None:
    resp = await client.get(
        "/api/v1/admin/knowledge/documents/00000000-0000-0000-0000-000000000000",
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 404


# ── 문서 승인 ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_approve_document_success(client) -> None:
    create_resp = await client.post(
        "/api/v1/admin/knowledge/documents",
        headers=ADMIN_HEADERS,
        json={
            "source_url": "https://example.com/skin",
            "title": "피부 보습 가이드",
            "collected_at": COLLECTED_AT,
            "raw_text": RAW_TEXT,
        },
    )
    doc_id = create_resp.json()["id"]

    approve_resp = await client.post(
        f"/api/v1/admin/knowledge/documents/{doc_id}/approve",
        headers=ADMIN_HEADERS,
        json={
            "claim_id": "skin-001",
            "claim_version": 1,
            "topic": "보습",
        },
    )
    assert approve_resp.status_code == 200
    data = approve_resp.json()
    assert data["review_status"] == "approved"
    assert data["claim_id"] == "skin-001"
    assert data["claim_version"] == 1


# ── 인덱스 생성 및 활성화 ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_and_activate_index(client) -> None:
    # 문서 등록 → 승인
    create_resp = await client.post(
        "/api/v1/admin/knowledge/documents",
        headers=ADMIN_HEADERS,
        json={
            "source_url": "https://example.com/skin",
            "title": "보습 가이드",
            "collected_at": COLLECTED_AT,
            "raw_text": RAW_TEXT,
        },
    )
    doc_id = create_resp.json()["id"]
    await client.post(
        f"/api/v1/admin/knowledge/documents/{doc_id}/approve",
        headers=ADMIN_HEADERS,
        json={"claim_id": "skin-001", "claim_version": 1},
    )

    # 인덱스 생성
    idx_resp = await client.post(
        "/api/v1/admin/knowledge/indexes",
        headers=ADMIN_HEADERS,
        json={"version": "v1", "claim_ids": ["skin-001"]},
    )
    assert idx_resp.status_code == 201
    assert idx_resp.json()["is_active"] is False

    # 인덱스 활성화
    activate_resp = await client.post(
        "/api/v1/admin/knowledge/indexes/v1/activate",
        headers=ADMIN_HEADERS,
    )
    assert activate_resp.status_code == 200
    assert activate_resp.json()["is_active"] is True


@pytest.mark.asyncio
async def test_activate_nonexistent_index_returns_404(client) -> None:
    resp = await client.post(
        "/api/v1/admin/knowledge/indexes/nonexistent/activate",
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 404


# ── 내부 검색 ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_internal_search_after_full_flow(client) -> None:
    """문서 등록 → 승인 → 인덱스 활성화 후 검색이 동작한다."""
    create_resp = await client.post(
        "/api/v1/admin/knowledge/documents",
        headers=ADMIN_HEADERS,
        json={
            "source_url": "https://example.com/skin",
            "title": "보습 가이드",
            "collected_at": COLLECTED_AT,
            "raw_text": "세라마이드는 피부 장벽을 강화한다.",
        },
    )
    doc_id = create_resp.json()["id"]
    await client.post(
        f"/api/v1/admin/knowledge/documents/{doc_id}/approve",
        headers=ADMIN_HEADERS,
        json={"claim_id": "skin-001", "claim_version": 1},
    )
    await client.post(
        "/api/v1/admin/knowledge/indexes",
        headers=ADMIN_HEADERS,
        json={"version": "v1", "claim_ids": ["skin-001"]},
    )
    await client.post(
        "/api/v1/admin/knowledge/indexes/v1/activate",
        headers=ADMIN_HEADERS,
    )

    search_resp = await client.post(
        "/internal/knowledge/search",
        headers=ADMIN_HEADERS,
        json={"keywords": ["세라마이드"], "limit": 5},
    )
    assert search_resp.status_code == 200
    results = search_resp.json()["results"]
    assert len(results) >= 1
    assert results[0]["score"] >= 1


@pytest.mark.asyncio
async def test_internal_search_without_admin_key_returns_403(client) -> None:
    resp = await client.post(
        "/internal/knowledge/search",
        json={"keywords": ["세라마이드"], "limit": 5},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_internal_search_no_match_returns_empty(client) -> None:
    search_resp = await client.post(
        "/internal/knowledge/search",
        headers=ADMIN_HEADERS,
        json={"keywords": ["없는키워드xyz"], "limit": 5},
    )
    assert search_resp.status_code == 200
    assert search_resp.json()["results"] == []


@pytest.mark.asyncio
async def test_internal_search_invalid_limit_returns_422(client) -> None:
    # limit < 1
    resp_low = await client.post(
        "/internal/knowledge/search",
        headers=ADMIN_HEADERS,
        json={"keywords": ["보습"], "limit": 0},
    )
    assert resp_low.status_code == 422

    # limit > 20
    resp_high = await client.post(
        "/internal/knowledge/search",
        headers=ADMIN_HEADERS,
        json={"keywords": ["보습"], "limit": 21},
    )
    assert resp_high.status_code == 422
