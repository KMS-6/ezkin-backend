from dataclasses import dataclass
from enum import StrEnum

from app.modules.risk.logic import LOW_HUMIDITY_THRESHOLD, UV_HIGH_THRESHOLD


class CareMode(StrEnum):
    BASIC = "basic"
    MOISTURE_FOCUSED = "moisture_focused"
    SOOTHING_FOCUSED = "soothing_focused"
    UV_FOCUSED = "uv_focused"
    MINIMAL_ROUTINE = "minimal_routine"


@dataclass(frozen=True)
class CareInputs:
    humidity: float | None = None
    uv_index: float | None = None
    user_reports_discomfort: bool = False


def select_care_mode(inputs: CareInputs) -> CareMode:
    if inputs.user_reports_discomfort:
        return CareMode.MINIMAL_ROUTINE
    if inputs.uv_index is not None and inputs.uv_index >= UV_HIGH_THRESHOLD:
        return CareMode.UV_FOCUSED
    if inputs.humidity is not None and inputs.humidity < LOW_HUMIDITY_THRESHOLD:
        return CareMode.MOISTURE_FOCUSED
    return CareMode.BASIC
