import pytest

from app.modules.care.rules import CareInputs, CareMode, select_care_mode


@pytest.mark.parametrize(
    ("inputs", "expected"),
    [
        (CareInputs(), CareMode.BASIC),
        (CareInputs(humidity=20), CareMode.MOISTURE_FOCUSED),
        (CareInputs(uv_index=8), CareMode.UV_FOCUSED),
        (
            CareInputs(humidity=20, uv_index=8, user_reports_discomfort=True),
            CareMode.MINIMAL_ROUTINE,
        ),
    ],
)
def test_select_care_mode(inputs: CareInputs, expected: CareMode) -> None:
    assert select_care_mode(inputs) == expected
