from datetime import datetime, timezone
from typing import Literal
import uuid

from pydantic import BaseModel, Field


Confidence = Literal["high", "medium", "low"]
DeclarationStatus = Literal["compliant", "non_compliant", "not_detected", "not_applicable", "manual_review", "review"]
OverallStatus = Literal["compliant", "partially_compliant", "non_compliant", "manual_review", "review"]
RuleResultStatus = Literal["compliant", "non_compliant", "not_detected", "not_applicable", "manual_verification"]


class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class ImageQuality(BaseModel):
    width: int
    height: int
    blur_score: float
    brightness: float
    glare_ratio: float
    warnings: list[str] = []
    suitable: bool = True


class ScanImageCreate(BaseModel):
    client_id: str
    face_label: str
    file_name: str
    mime_type: str
    image_base64: str


class ScanImage(BaseModel):
    id: str
    inspection_id: str
    face_label: str
    file_name: str
    mime_type: str
    data_url: str
    sha256: str
    quality: ImageQuality


class DeclarationResult(BaseModel):
    key: str
    field_name: str
    detected_value: str | None = None
    status: DeclarationStatus
    confidence: Confidence = "medium"
    rule_code: str
    requirement: str
    reason: str
    consumer_explanation: str = ""
    font_size_mm: float | None = None
    bbox: BoundingBox
    evidence_image_id: str | None = None
    evidence_face: str | None = None


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


class RuleResult(BaseModel):
    rule_id: str
    rule_number: str
    rule_title: str
    requirement: str
    extracted_value: str | None = None
    status: RuleResultStatus
    severity: str
    confidence: Confidence
    evidence_image_id: str | None = None
    evidence_face: str | None = None
    explanation: str
    consumer_explanation: str
    official_source: str


class ExtractedProduct(BaseModel):
    product_name: str
    brand: str | None = None
    category: str
    manufacturer: str | None = None
    net_quantity: str | None = None
    mrp: str | None = None
    mfg_date: str | None = None
    batch_lot: str | None = None
    consumer_care: str | None = None


class ScanRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    owner_id: str = "legacy"
    owner_role: str = "inspector"
    product_name: str
    brand: str | None = None
    manufacturer: str
    category: str
    region: str
    inspector: str
    status: OverallStatus
    scanned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    image_url: str = ""
    image_ids: list[str] = []
    images: list[ScanImage] = []
    declarations: list[DeclarationResult]
    extracted_product: ExtractedProduct | None = None
    ocr_texts: list[dict] = []
    processing_notes: list[str] = []
    rule_results: list[RuleResult] = []
    violation_count: int
    review_status: Literal["not_required", "pending", "verified"]
    remarks: str = ""
    consumer_review: str = ""
    rule_engine_report: RuleEngineReport | None = None


class ScanCreate(BaseModel):
    product_name: str = "Uploaded packaged commodity"
    category: str = "Other"
    region: str = "Delhi NCR"
    images: list[ScanImageCreate] = []
    image_base64: str | None = None
    mime_type: str = "image/jpeg"
    image_url: str | None = None


class ScanReviewUpdate(BaseModel):
    remarks: str = ""
    consumer_review: str = ""
    review_status: Literal["pending", "verified"] = "verified"
    status: OverallStatus | None = None


class UploadConfig(BaseModel):
    max_images: int
    max_file_size_bytes: int
    max_total_size_bytes: int
    supported_mime_types: list[str]
    min_width: int
    min_height: int
    recommended_width: int
    recommended_height: int


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
    rule_number: str
    title: str
    rule_code: str
    requirement: str
    description: str
    applicability: str
    required_declaration: str | None = None
    detection_keywords: list[str] = []
    validation_logic: str
    violation_condition: str
    severity: str
    consumer_explanation: str
    inspector_explanation: str
    official_source: str
    min_font_height_mm: float = 0
    mandatory: bool = False
    updated_at: str = "Official 2011 rule set"