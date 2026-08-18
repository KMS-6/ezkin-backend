from httpx import AsyncClient


async def test_mock_persona_header_required(client: AsyncClient) -> None:
    response = await client.get("/api/v1/consents")
    assert response.status_code == 400


async def test_unknown_persona_id_rejected(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/consents", headers={"X-Mock-Persona-Id": "persona_missing"}
    )
    assert response.status_code == 400


async def test_list_and_get_persona(client: AsyncClient) -> None:
    list_response = await client.get("/api/v1/personas")
    assert list_response.status_code == 200
    assert [p["id"] for p in list_response.json()["personas"]] == ["persona_001", "persona_003"]

    detail_response = await client.get("/api/v1/personas/persona_001")
    assert detail_response.status_code == 200
    body = detail_response.json()
    features = {f["feature"] for f in body["features"]}
    assert features == {
        "watch_data",
        "risk_assessment_health",
        "risk_assessment_weather",
        "pattern_analysis",
    }
    # persona_001은 워치 없음 → watch_status = no_watch, watch_data 제한
    assert body["watch_status"] == "no_watch"
    watch_feature = next(f for f in body["features"] if f["feature"] == "watch_data")
    assert watch_feature["status"] == "limited"

    missing_response = await client.get("/api/v1/personas/persona_999")
    assert missing_response.status_code == 404


async def test_watch_persona_has_watch_data_normal(client: AsyncClient) -> None:
    # persona_003은 has_watch → watch_data normal, reason/fallback 없음
    response = await client.get("/api/v1/personas/persona_003")
    assert response.status_code == 200
    body = response.json()
    assert body["watch_status"] == "has_watch"
    watch_feature = next(f for f in body["features"] if f["feature"] == "watch_data")
    assert watch_feature["status"] == "normal"
    assert "reason" not in watch_feature or watch_feature["reason"] is None
    assert "fallback" not in watch_feature or watch_feature["fallback"] is None


async def test_skin_concerns_are_public(client: AsyncClient) -> None:
    response = await client.get("/api/v1/onboarding/skin-concerns")
    assert response.status_code == 200
    assert len(response.json()["concerns"]) > 0


async def test_onboarding_profile_and_consents_flow(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    profile_response = await client.post(
        "/api/v1/onboarding/profile",
        headers=persona_headers,
        json={"skin_concern_ids": ["cn_dryness"], "birth_year": 1998},
    )
    assert profile_response.status_code == 200
    assert profile_response.json() == {"onboarding_completed": True}

    consents_response = await client.get("/api/v1/consents", headers=persona_headers)
    assert consents_response.status_code == 200
    consents = {c["type"]: c for c in consents_response.json()["consents"]}
    assert consents["apple_health"]["consented"] is False
    assert consents["apple_health"]["updated_at"] is None

    update_response = await client.put(
        "/api/v1/consents/apple_health", headers=persona_headers, json={"consented": True}
    )
    assert update_response.status_code == 200
    assert update_response.json()["consented"] is True
    assert update_response.json()["updated_at"] is not None

    invalid_type_response = await client.put(
        "/api/v1/consents/not_a_real_type", headers=persona_headers, json={"consented": True}
    )
    assert invalid_type_response.status_code == 422

    availability_response = await client.get(
        "/api/v1/me/feature-availability", headers=persona_headers
    )
    assert availability_response.status_code == 200
    features = {f["feature"]: f for f in availability_response.json()["features"]}
    assert features["risk_assessment_health"]["status"] == "normal"
    assert features["risk_assessment_weather"]["status"] == "limited"
