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


def test_non_urgent_message_can_continue() -> None:
    response = client.post(
        "/api/v1/quick-care/safety-check",
        json={"message": "오늘 피부가 조금 건조해요"},
    )

    assert response.status_code == 200
    assert response.json()["action"] == "continue_general_guidance"
