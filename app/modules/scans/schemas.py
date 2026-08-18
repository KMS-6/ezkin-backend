from datetime import datetime

from pydantic import BaseModel


class SkinScanAccepted(BaseModel):
    scan_id: str
    status: str
    capture_method: str
    status_url: str


class SkinScanFailure(BaseModel):
    code: str
    message: str
    retryable: bool


class SkinScanModel(BaseModel):
    provider: str
    name: str
    version: str


class SkinScanResult(BaseModel):
    scan_id: str
    status: str
    capture_method: str
    created_at: datetime
    lower_accuracy: bool
    schema_version: str | None = None
    scores: dict[str, float] | None = None
    confidence: dict[str, float] | None = None
    delta_vs_baseline: dict[str, float] | None = None
    delta_vs_previous: dict[str, float] | None = None
    model: SkinScanModel | None = None
    limitation_notice: str | None = None
    retry_after_seconds: int | None = None
    failure: SkinScanFailure | None = None


class SkinScanListItem(BaseModel):
    scan_id: str
    status: str
    captured_at: datetime


class SkinScanListResponse(BaseModel):
    items: list[SkinScanListItem]
    next_cursor: str | None = None
    has_more: bool
