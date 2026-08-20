import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_urgent_message_stops_general_guidance() -> None:
    response = client.post(
        "/api/v1/quick-care/safety-check",
        json={"message": "눈이 부어 오르고 호흡 곤란이 있어요"},
    )

    assert response.status_code == 200
    assert response.json()["action"] == "stop_ai_guidance"
    assert response.json()["professional_help_suggested"] is True


@pytest.mark.parametrize(
    "message",
    ["숨쉬기 힘들어요", "붓기가 심해요", "갑자기 의식을 잃었어요"],
)
def test_urgent_message_variants_stop_general_guidance(message: str) -> None:
    response = client.post(
        "/api/v1/quick-care/safety-check",
        json={"message": message},
    )

    assert response.status_code == 200
    assert response.json()["action"] == "stop_ai_guidance"
    assert response.json()["professional_help_suggested"] is True


def test_self_harm_message_stops_general_guidance() -> None:
    response = client.post(
        "/api/v1/quick-care/safety-check",
        json={"message": "너무 힘들어서 자살하고 싶어요"},
    )

    assert response.status_code == 200
    assert response.json()["action"] == "stop_ai_guidance"
    assert "1393" in response.json()["reply"]
    assert response.json()["professional_help_suggested"] is True


@pytest.mark.parametrize(
    "message",
    ["팔에 번지는 발진이 생겼어요", "고열이 나요", "화학화상을 입었어요"],
)
def test_triggers_module_urgent_keywords_are_shared(message: str) -> None:
    response = client.post(
        "/api/v1/quick-care/safety-check",
        json={"message": message},
    )

    assert response.status_code == 200
    assert response.json()["action"] == "stop_ai_guidance"
    assert response.json()["professional_help_suggested"] is True


def test_non_urgent_message_can_continue() -> None:
    response = client.post(
        "/api/v1/quick-care/safety-check",
        json={"message": "오늘 피부가 조금 건조해요"},
    )

    assert response.status_code == 200
    assert response.json()["action"] == "continue_general_guidance"
