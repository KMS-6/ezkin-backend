from httpx import AsyncClient

from tests.conftest import ADMIN_HEADERS


async def test_admin_product_crud_requires_admin_key(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/admin/products",
        json={"name": "약산성 클렌저", "brand": "AAC", "external_url": "https://example.com/p"},
    )
    assert response.status_code == 403


async def test_recommendations_match_onboarding_concern(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    create = await client.post(
        "/api/v1/admin/products",
        headers=ADMIN_HEADERS,
        json={
            "name": "고보습 크림",
            "brand": "AAC",
            "category": "moisturizer",
            "external_url": "https://example.com/moisturizer",
        },
    )
    assert create.status_code == 201

    duplicate = await client.post(
        "/api/v1/admin/products",
        headers=ADMIN_HEADERS,
        json={
            "name": "고보습 크림",
            "brand": "AAC",
            "external_url": "https://example.com/moisturizer",
        },
    )
    assert duplicate.status_code == 409

    await client.post(
        "/api/v1/onboarding/profile",
        headers=persona_headers,
        json={"skin_concern_ids": ["cn_dryness"]},
    )

    response = await client.get("/api/v1/recommendations", headers=persona_headers)
    assert response.status_code == 200
    names = [r["name"] for r in response.json()["recommendations"]]
    assert "고보습 크림" in names

    list_products = await client.get("/api/v1/admin/products", headers=ADMIN_HEADERS)
    assert list_products.status_code == 200
    assert len(list_products.json()["items"]) == 1


async def test_knowledge_document_approve_and_index_lifecycle(client: AsyncClient) -> None:
    create = await client.post(
        "/api/v1/admin/knowledge/documents",
        headers=ADMIN_HEADERS,
        json={
            "source_url": "https://example.com/study",
            "title": "수면과 피부 장벽",
            "collected_at": "2026-08-01T00:00:00Z",
        },
    )
    assert create.status_code == 201
    document_id = create.json()["id"]
    assert create.json()["review_status"] == "draft"

    approve = await client.post(
        f"/api/v1/admin/knowledge/documents/{document_id}/approve",
        headers=ADMIN_HEADERS,
        json={
            "claim_id": "claim_sleep_barrier_001",
            "claim_version": 1,
            "topic": "sleep",
            "population": "성인",
            "evidence_level": "B",
            "allowed_features": ["briefings"],
            "required_user_facts": ["sleep_hours"],
            "allowed_expressions": "수면 부족은 피부 장벽 회복 지연과 관련될 수 있어요.",
            "forbidden_expressions": "치료·처방 표현",
            "next_review_at": "2027-08-01T00:00:00Z",
        },
    )
    assert approve.status_code == 200
    assert approve.json()["review_status"] == "approved"

    create_index = await client.post(
        "/api/v1/admin/knowledge/indexes", headers=ADMIN_HEADERS, json={"version": "v1"}
    )
    assert create_index.status_code == 201
    assert create_index.json()["claim_ids"] == ["claim_sleep_barrier_001"]

    activate = await client.post(
        "/api/v1/admin/knowledge/indexes/v1/activate", headers=ADMIN_HEADERS
    )
    assert activate.status_code == 200
    assert activate.json()["is_active"] is True
