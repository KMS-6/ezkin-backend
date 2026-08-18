"""Deterministic, rule-based scoring for the `questionnaire` capture method.

Camera-based scoring would require an image classification model, which is
not implemented (see docs/openapi.yaml) — those scans resolve to a
`model_not_implemented` failure instead of a score.
"""

SEVERITY_SCORE = {"none": 0.0, "mild": 0.33, "moderate": 0.66, "severe": 1.0}
QUESTION_METRIC = {
    "redness": "redness",
    "tightness": "dryness",
    "oiliness": "oiliness",
    "new_lesions": "new_lesions",
}


def score_questionnaire(answers: list[dict]) -> dict[str, float]:
    return {
        QUESTION_METRIC[answer["question_id"]]: SEVERITY_SCORE[answer["value"]]
        for answer in answers
    }
