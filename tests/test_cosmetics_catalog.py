from httpx import AsyncClient

from tests.conftest import ADMIN_HEADERS


async def test_ingredient_admin_create_requires_admin_key(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/admin/ingredients",
        json={"name": "살리실산", "risk_level": "caution", "target_concern": "청소년성 피부"},
    )
    assert response.status_code == 403


async def test_cosmetic_registration_flags_caution_ingredient(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    create_ingredient = await client.post(
        "/api/v1/admin/ingredients",
        headers=ADMIN_HEADERS,
        json={"name": "살리실산", "risk_level": "caution", "target_concern": "청소년성 피부"},
    )
    assert create_ingredient.status_code == 201

    duplicate = await client.post(
        "/api/v1/admin/ingredients",
        headers=ADMIN_HEADERS,
        json={"name": "살리실산", "risk_level": "caution"},
    )
    assert duplicate.status_code == 409

    create_cosmetic = await client.post(
        "/api/v1/cosmetics",
        headers=persona_headers,
        data={
            "brand": "AAC",
            "product_name": "진정 토너",
            "product_type": "toner",
            "ingredients_raw": '["살리실산", "글리세린"]',
        },
    )
    assert create_cosmetic.status_code == 201
    body = create_cosmetic.json()
    assert body["risk_alerts"][0]["ingredient"] == "살리실산"
    cosmetic_id = body["cosmetic_id"]

    list_response = await client.get("/api/v1/cosmetics", headers=persona_headers)
    assert [item["cosmetic_id"] for item in list_response.json()["items"]] == [cosmetic_id]

    update_response = await client.patch(
        f"/api/v1/cosmetics/{cosmetic_id}", headers=persona_headers, json={"product_type": "serum"}
    )
    assert update_response.status_code == 200
    assert update_response.json()["product_type"] == "serum"

    null_brand_response = await client.patch(
        f"/api/v1/cosmetics/{cosmetic_id}", headers=persona_headers, json={"brand": None}
    )
    assert null_brand_response.status_code == 422

    delete_response = await client.delete(
        f"/api/v1/cosmetics/{cosmetic_id}", headers=persona_headers
    )
    assert delete_response.status_code == 204

    empty_list = await client.get("/api/v1/cosmetics", headers=persona_headers)
    assert empty_list.json() == {"items": []}


async def test_ingredients_catalog_filter_by_risk_level(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    await client.post(
        "/api/v1/admin/ingredients",
        headers=ADMIN_HEADERS,
        json={"name": "글리세린", "risk_level": "safe"},
    )
    await client.post(
        "/api/v1/admin/ingredients",
        headers=ADMIN_HEADERS,
        json={"name": "레티놀", "risk_level": "caution", "target_concern": "임신·수유"},
    )

    response = await client.get(
        "/api/v1/ingredients", headers=persona_headers, params={"risk_level": "caution"}
    )
    assert response.status_code == 200
    names = [i["name"] for i in response.json()["ingredients"]]
    assert names == ["레티놀"]
