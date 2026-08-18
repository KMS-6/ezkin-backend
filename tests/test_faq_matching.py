from httpx import AsyncClient

from app.modules.triggers import logic


def test_faq_dataset_has_broad_mock_coverage() -> None:
    assert len(logic.FAQ_ENTRIES) >= 20
    faq_ids = [entry["faq_id"] for entry in logic.FAQ_ENTRIES]
    assert len(faq_ids) == len(set(faq_ids))
    for entry in logic.FAQ_ENTRIES:
        assert entry["keywords"]
        assert entry["reply"]
        assert entry["label"]


def test_faq_score_rewards_longer_and_multi_keyword_matches() -> None:
    weak = {
        "faq_id": "faq_weak",
        "version": 1,
        "label": "약한 후보",
        "keywords": ["피부"],
        "reply": "약한 답변",
    }
    strong = {
        "faq_id": "faq_strong",
        "version": 1,
        "label": "강한 후보",
        "keywords": ["각질제거", "필링"],
        "reply": "강한 답변",
    }
    normalized = logic._normalize("피부 각질제거랑 필링 자주 해도 되나요?")

    weak_score = logic._faq_score(normalized, weak)
    strong_score = logic._faq_score(normalized, strong)

    assert weak_score > 0
    assert strong_score > weak_score


def test_search_faq_ranks_candidates_by_score(monkeypatch) -> None:
    entries = [
        {
            "faq_id": "faq_weak",
            "version": 1,
            "label": "약한 후보",
            "keywords": ["피부"],
            "reply": "...",
        },
        {
            "faq_id": "faq_strong",
            "version": 1,
            "label": "강한 후보",
            "keywords": ["각질제거", "필링"],
            "reply": "...",
        },
    ]
    monkeypatch.setattr(logic, "FAQ_ENTRIES", entries)

    ranked = logic.search_faq("피부 각질제거랑 필링 자주 해도 되나요?")

    assert [entry["faq_id"] for _, entry in ranked] == ["faq_strong", "faq_weak"]


def test_resolve_faq_asks_for_clarification_when_top_two_scores_tie(monkeypatch) -> None:
    entries = [
        {
            "faq_id": "faq_a",
            "version": 1,
            "label": "후보 A",
            "keywords": ["붉음"],
            "reply": "A 답변",
        },
        {
            "faq_id": "faq_b",
            "version": 1,
            "label": "후보 B",
            "keywords": ["붉음"],
            "reply": "B 답변",
        },
    ]
    monkeypatch.setattr(logic, "FAQ_ENTRIES", entries)

    resolved = logic.resolve_faq("피부가 붉음이 있어요")

    assert resolved["selected"] is None
    assert {c["faq_id"] for c in resolved["candidates"]} == {"faq_a", "faq_b"}


def test_resolve_faq_returns_no_candidates_below_low_confidence(monkeypatch) -> None:
    entries = [
        {
            "faq_id": "faq_a",
            "version": 1,
            "label": "후보 A",
            "keywords": ["관련없음"],
            "reply": "A 답변",
        },
    ]
    monkeypatch.setattr(logic, "FAQ_ENTRIES", entries)

    resolved = logic.resolve_faq("완전히 다른 이야기입니다")

    assert resolved["selected"] is None
    assert resolved["candidates"] == []


async def test_sos_message_matches_new_mock_faq_topics(
    client: AsyncClient, persona_headers: dict[str, str]
) -> None:
    session = await client.post("/api/v1/sos/sessions", headers=persona_headers)
    session_id = session.json()["session_id"]

    response = await client.post(
        f"/api/v1/sos/sessions/{session_id}/messages",
        headers=persona_headers,
        json={"message": "패치 테스트는 어떻게 해요?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["reply_type"] == "answer"
    assert body["matched_faq"]["faq_id"] == "faq_patch_test"
    assert body["matched_faq"]["match_score"] >= logic.FAQ_HIGH_CONFIDENCE
