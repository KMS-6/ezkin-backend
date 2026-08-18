from typing import Annotated

from fastapi import Header, HTTPException, status

ALLOWED_PERSONA_IDS: frozenset[str] = frozenset(
    {
        "persona_a1_seoyeon",
        "persona_a2_haneul",
        "persona_b1_eunji",
        "persona_b2_doyoon",
        "persona_c1_minjun",
        "persona_c2_haeun",
    }
)


def get_persona_id(
    x_mock_persona_id: Annotated[str | None, Header(alias="X-Mock-Persona-Id")] = None,
) -> str:
    if x_mock_persona_id is None or x_mock_persona_id not in ALLOWED_PERSONA_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "mock_persona_required"},
        )
    return x_mock_persona_id
