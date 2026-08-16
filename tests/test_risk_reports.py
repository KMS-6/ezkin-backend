import json
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

QUESTIONNAIRE_ANSWERS = json.dumps(
    [
        {"question_id": "redness", "value": "mild"},
        {"question_id": "tightness", "value": "mild"},
        {"question_id": "oiliness", "value": "mild"},
    ]
)


async def _submit_scan(client: AsyncClient, headers: dict[str, str], captured_at: datetime) -> None:
    response = await client.post(
        "/api/v1/skin-scans",
        headers={**headers, "Idempotency-Key": f"idem-{captured_at.isoformat()}"},
        data={
            "capture_method": "questionnaire",
            "captured_at": captured_at.isoformat(),
            "questionnaire_version": "v1",
            "answers": QUESTIONNAIRE_ANSWERS,
        },
    )
    assert response.status_code == 202


async def test_risk_assessment_defaults_to_low_with_no_data(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    response = await client.get("/api/v1/risk-assessments/today", headers=persona_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["risk_level"] == "low"
    assert body["contributing_factors"] == []
    assert body["risk_levels_enum"] == ["low", "moderate", "high", "very_high"]


async def test_eligibility_and_report_lifecycle(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    eligibility_before = await client.get("/api/v1/analysis/eligibility", headers=persona_headers)
    assert eligibility_before.json()["eligible"] is False

    report_too_early = await client.post(
        "/api/v1/reports", headers=persona_headers, json={"period_days": 14}
    )
    assert report_too_early.status_code == 409

    invalid_period = await client.post(
        "/api/v1/reports", headers=persona_headers, json={"period_days": 7}
    )
    assert invalid_period.status_code == 422

    now = datetime.now(UTC)
    for i in range(14):
        await _submit_scan(client, persona_headers, now - timedelta(days=i, minutes=1))

    eligibility_after = await client.get("/api/v1/analysis/eligibility", headers=persona_headers)
    assert eligibility_after.json()["eligible"] is True

    create_report = await client.post(
        "/api/v1/reports", headers=persona_headers, json={"period_days": 14}
    )
    assert create_report.status_code == 202
    report_id = create_report.json()["report_id"]

    report = await client.get(f"/api/v1/reports/{report_id}", headers=persona_headers)
    assert report.status_code == 200
    body = report.json()
    assert body["status"] == "completed"
    assert len(body["observations"]) == 1
    assert body["observations"][0]["evidence_ids"]

    feedback = await client.post(
        f"/api/v1/generations/{report_id}/feedback",
        headers=persona_headers,
        json={"rating": "helpful"},
    )
    assert feedback.status_code == 201

    unknown_generation_feedback = await client.post(
        "/api/v1/generations/not-a-real-id/feedback",
        headers=persona_headers,
        json={"rating": "helpful"},
    )
    assert unknown_generation_feedback.status_code == 404
