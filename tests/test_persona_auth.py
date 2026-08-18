from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.persona import get_persona_id

_app = FastAPI()


@_app.get("/protected")
def protected(persona_id: Annotated[str, Depends(get_persona_id)]) -> dict[str, str]:
    return {"persona_id": persona_id}


client = TestClient(_app)


def test_valid_persona_passes() -> None:
    response = client.get("/protected", headers={"X-Mock-Persona-Id": "persona_a1_seoyeon"})
    assert response.status_code == 200
    assert response.json() == {"persona_id": "persona_a1_seoyeon"}


def test_all_allowed_personas_pass() -> None:
    allowed = [
        "persona_a1_seoyeon",
        "persona_a2_haneul",
        "persona_b1_eunji",
        "persona_b2_doyoon",
        "persona_c1_minjun",
        "persona_c2_haeun",
    ]
    for persona_id in allowed:
        response = client.get("/protected", headers={"X-Mock-Persona-Id": persona_id})
        assert response.status_code == 200, f"{persona_id} should be allowed"


def test_missing_header_returns_400() -> None:
    response = client.get("/protected")
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "mock_persona_required"


def test_invalid_persona_returns_400() -> None:
    response = client.get("/protected", headers={"X-Mock-Persona-Id": "unknown_persona"})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "mock_persona_required"
