import uuid

from httpx import AsyncClient

from app.core.auth import create_access_token


def _default_consents() -> dict:
    return {
        "consents": [
            {"type": "apple_health", "consented": False, "updated_at": None},
            {"type": "weather_location", "consented": False, "updated_at": None},
        ]
    }


def _auth_header(token: str) -> dict:
    scheme = "Bearer"
    return {"Authorization": scheme + " " + token}


async def test_bearer_user_can_call_persona_gated_endpoint_without_mock_header(
    client: AsyncClient,
) -> None:
    token = create_access_token(uuid.uuid4())

    response = await client.get("/api/v1/consents", headers=_auth_header(token))

    assert response.status_code == 200
    assert response.json() == _default_consents()


async def test_bearer_user_only_sees_own_consent_data(client: AsyncClient) -> None:
    user_a_token = create_access_token(uuid.uuid4())
    user_b_token = create_access_token(uuid.uuid4())
    headers_a = _auth_header(user_a_token)
    headers_b = _auth_header(user_b_token)

    update_response = await client.put(
        "/api/v1/consents/apple_health", json={"consented": True}, headers=headers_a
    )
    assert update_response.status_code == 200

    consents_a = await client.get("/api/v1/consents", headers=headers_a)
    assert consents_a.json()["consents"][0]["consented"] is True

    consents_b = await client.get("/api/v1/consents", headers=headers_b)
    assert consents_b.json() == _default_consents()


async def test_bearer_takes_precedence_over_mock_persona_header(client: AsyncClient) -> None:
    # persona_001에 동의를 설정해도, 실사용자 토큰 + X-Mock-Persona-Id가 함께 오면
    # 실사용자 자신의(비어 있는) 데이터가 조회돼야 한다 — persona_001 데이터가 새어나가면 안 된다.
    mock_headers = {"X-Mock-Persona-Id": "persona_001"}
    await client.put(
        "/api/v1/consents/apple_health", json={"consented": True}, headers=mock_headers
    )

    token = create_access_token(uuid.uuid4())
    combined_headers = _auth_header(token) | {"X-Mock-Persona-Id": "persona_001"}

    response = await client.get("/api/v1/consents", headers=combined_headers)

    assert response.status_code == 200
    assert response.json() == _default_consents()


async def test_mock_persona_header_flow_still_works(client: AsyncClient) -> None:
    response = await client.get("/api/v1/consents", headers={"X-Mock-Persona-Id": "persona_001"})

    assert response.status_code == 200
    assert response.json() == _default_consents()
