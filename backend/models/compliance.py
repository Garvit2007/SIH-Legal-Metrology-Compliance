from datetime import datetime, timezone
from typing import Literal
import uuid

from pydantic import BaseModel, Field


Status = Literal["compliant", "non_compliant", "review"]


class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class DeclarationResult(BaseModel):
    key: str
    field_name: str
    detected_value: str | None = None
    status: Status
    rule_code: str
    requirement: str
    reason: str
    font_size_mm: float | None = None
    bbox: BoundingBox


class RuleEngineViolation(BaseModel):
    rule_id: str
    rule_ref: str
    severity: str
    message: str
    field: str | None = None


class RuleEngineReport(BaseModel):
    product_id: str
    rule_version: str
    out_of_scope: bool
    scope_reason: str | None = None
    exempt: bool
    exempt_reason: str | None = None
    is_compliant: bool
    critical_violations: int
    total_violations: int
    violations: list[RuleEngineViolation]
    passed_checks: list[str]


class ScanRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    product_name: str
    manufacturer: str
    category: str
    region: str
    inspector: str
    status: Status
    scanned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    image_url: str
    declarations: list[DeclarationResult]
    violation_count: int
    review_status: Literal["not_required", "pending", "verified"]
    remarks: str = ""
    rule_engine_report: RuleEngineReport | None = None


class ScanCreate(BaseModel):
    product_name: str = "Uploaded packaged commodity"
    category: str = "Food & Grocery"
    region: str = "Delhi NCR"
    inspector: str = "INS-042 · Aditi Rao"
    image_base64: str | None = None
    mime_type: str = "image/jpeg"
    image_url: str | None = None


class ScanReviewUpdate(BaseModel):
    remarks: str = ""
    review_status: Literal["pending", "verified"] = "verified"
    status: Status | None = None


class TrendPoint(BaseModel):
    month: str
    compliant: int
    violations: int


class BreakdownPoint(BaseModel):
    name: str
    value: int


class DashboardStats(BaseModel):
    total_scanned: int
    violation_rate: float
    pending_reviews: int
    reports_issued: int


class DashboardResponse(BaseModel):
    stats: DashboardStats
    violation_types: list[BreakdownPoint]
    regions: list[BreakdownPoint]
    trend: list[TrendPoint]


class RuleItem(BaseModel):
    id: str
    title: str
    rule_code: str
    requirement: str
    min_font_height_mm: float
    mandatory: bool
    updated_at: str