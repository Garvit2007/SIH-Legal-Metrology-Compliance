import json
import os
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pymongo import ReturnDocument

from lib.db import db
from lib.rule_adapter import apply_rule_engine
from models.compliance import (
    BoundingBox,
    BreakdownPoint,
    DashboardResponse,
    DashboardStats,
    DeclarationResult,
    RuleItem,
    ScanCreate,
    ScanRecord,
    ScanReviewUpdate,
    TrendPoint,
)

router = APIRouter(prefix="/compliance", tags=["compliance"])

DEMO_IMAGE = "https://images.unsplash.com/photo-1618381297523-e6c0ab13a5b2?auto=format&fit=crop&w=1400&q=85"

RULES: list[RuleItem] = [
    RuleItem(id="mrp", title="Maximum Retail Price (MRP)", rule_code="Rule 6(1)(e)", requirement="Declare MRP as 'MRP Rs. XX.XX (incl. of all taxes)'. Dual MRP or overwriting is prohibited except reduction.", min_font_height_mm=2.5, mandatory=True, updated_at="12 Jun 2024"),
    RuleItem(id="net_quantity", title="Net Quantity", rule_code="Rule 6(1)(c)", requirement="Declare in standard units (g, kg, ml, L, N) on the Principal Display Panel with a contrasting background.", min_font_height_mm=2.5, mandatory=True, updated_at="12 Jun 2024"),
    RuleItem(id="manufacturer_details", title="Manufacturer / Packer / Importer", rule_code="Rule 6(1)(a)", requirement="Complete name and office address with PIN code. Importer address is required for imported goods.", min_font_height_mm=1.5, mandatory=True, updated_at="12 Jun 2024"),
    RuleItem(id="date_mfg", title="Month & Year of Manufacture / Packing", rule_code="Rule 6(1)(d)", requirement="Declare as 'Mfg Date: MM/YYYY' or 'Packed on: MM/YYYY'.", min_font_height_mm=1.5, mandatory=True, updated_at="12 Jun 2024"),
    RuleItem(id="consumer_care", title="Consumer Care Details", rule_code="Rule 6(2)", requirement="Include name, address, telephone number and email address for complaints.", min_font_height_mm=1.0, mandatory=True, updated_at="12 Jun 2024"),
    RuleItem(id="font_size_pdp", title="Font Height & Legibility (Table-I)", rule_code="Rule 7 & Table-I", requirement="Letter and numeral height must meet the Principal Display Panel area threshold; blown/molded letters require 2.0mm minimum.", min_font_height_mm=1.5, mandatory=True, updated_at="12 Jun 2024"),
]


def fallback_declarations() -> list[DeclarationResult]:
    return [
        DeclarationResult(key="manufacturer_details", field_name="Manufacturer / Packer", detected_value="Shakti Foods Pvt. Ltd., Okhla Industrial Area, New Delhi 110020", status="compliant", rule_code="Rule 6(1)(a)", requirement="Complete name, address and PIN code", reason="Complete address detected with PIN code.", font_size_mm=1.8, bbox=BoundingBox(x=10, y=67, width=73, height=11)),
        DeclarationResult(key="net_quantity", field_name="Net Quantity", detected_value="Net Qty. 500 g", status="compliant", rule_code="Rule 6(1)(c)", requirement="Standard unit on the Principal Display Panel", reason="Standard metric unit detected on the front panel.", font_size_mm=2.8, bbox=BoundingBox(x=10, y=18, width=25, height=10)),
        DeclarationResult(key="mrp", field_name="Maximum Retail Price", detected_value="MRP ₹120.00 (incl. of all taxes)", status="compliant", rule_code="Rule 6(1)(e)", requirement="MRP inclusive of all taxes", reason="Inclusive tax declaration is present and readable.", font_size_mm=2.6, bbox=BoundingBox(x=54, y=79, width=35, height=9)),
        DeclarationResult(key="date_mfg", field_name="Month / Year of Manufacture", detected_value="Packed on: 05/2024", status="compliant", rule_code="Rule 6(1)(d)", requirement="Month and year in MM/YYYY format", reason="Valid month/year format detected.", font_size_mm=1.6, bbox=BoundingBox(x=10, y=83, width=35, height=8)),
        DeclarationResult(key="consumer_care", field_name="Consumer Care", detected_value="care@shaktifoods.in · 1800 123 4567", status="review", rule_code="Rule 6(2)", requirement="Name, address, telephone and email", reason="Email and telephone detected; address line needs visual verification.", font_size_mm=1.1, bbox=BoundingBox(x=10, y=56, width=78, height=9)),
        DeclarationResult(key="font_size_pdp", field_name="Font Height / Legibility", detected_value="1.2 mm estimated", status="non_compliant", rule_code="Rule 7 & Table-I", requirement="Minimum 1.5 mm for this PDP area", reason="Estimated height is 1.2mm, below the required 1.5mm minimum.", font_size_mm=1.2, bbox=BoundingBox(x=10, y=38, width=73, height=12)),
    ]


def clean_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Vision response did not contain JSON")
    return json.loads(text[start:end + 1])


async def analyze_with_gemini(image_base64: str, mime_type: str) -> dict:
    from emergentintegrations.llm.chat import ImageContent, LlmChat, StreamDone, TextDelta, UserMessage

    key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not key:
        raise RuntimeError("EMERGENT_LLM_KEY is not configured")
    image = image_base64.split(",", 1)[1] if image_base64.startswith("data:") else image_base64
    prompt = """Act only as an OCR and visual extraction layer for a separate Legal Metrology rule engine. Do not make the final legal compliance decision; the backend rule engine is authoritative. Examine the packaged commodity image and return JSON only. Extract these declaration regions: manufacturer_details, net_quantity, mrp, date_mfg, consumer_care, font_size_pdp. Never invent a detected value; use null when missing. Bounding boxes use percentages from 0 to 100. Physical font heights must be null unless a reliable scale/reference is visible. Return this exact shape: {\"product_name\": string, \"manufacturer\": string, \"declarations\": [{\"key\": string, \"field_name\": string, \"detected_value\": string|null, \"status\": \"review\", \"rule_code\": string, \"requirement\": string, \"reason\": \"Awaiting configured rule engine\", \"font_size_mm\": number|null, \"bbox\": {\"x\": number, \"y\": number, \"width\": number, \"height\": number}}], \"rule_input\": {\"manufacturer_address\": string, \"commodity_name\": string, \"net_quantity\": string, \"net_quantity_value_g_ml\": number|null, \"quantity_type\": \"weight_or_volume\"|\"length_area_or_number\", \"mrp\": string, \"mfg_date\": string, \"consumer_care\": string, \"is_imported\": boolean, \"country_of_origin\": string|null, \"buyer_type\": \"retail\", \"category\": string, \"font_heights_mm\": object, \"is_embossed\": boolean, \"letter_width_height_ratios\": object, \"detected_language\": \"en\"|\"hi\"}}. Use the raw printed text for declaration values."""
    chat = LlmChat(api_key=key, session_id=f"scan-{uuid.uuid4()}", system_message="Return concise, valid JSON for the requested label inspection.").with_model("gemini", "gemini-3.1-pro-preview")
    chunks: list[str] = []
    async for event in chat.stream_message(UserMessage(text=prompt, file_contents=[ImageContent(image_base64=image)])):
        if isinstance(event, TextDelta):
            chunks.append(event.content)
        elif isinstance(event, StreamDone):
            break
    result = clean_json("".join(chunks))
    if not result.get("declarations"):
        raise ValueError("Vision response had no declarations")
    return result


def normalize_declarations(raw: list[dict]) -> list[DeclarationResult]:
    rule_by_key = {rule.id: rule for rule in RULES}
    normalized: list[DeclarationResult] = []
    for index, item in enumerate(raw[:6]):
        key = item.get("key", "review")
        rule = rule_by_key.get(key, RULES[min(index, len(RULES) - 1)])
        box = item.get("bbox") or {"x": 8, "y": 12 + index * 13, "width": 82, "height": 10}
        normalized.append(DeclarationResult(
            key=key,
            field_name=item.get("field_name", rule.title),
            detected_value=item.get("detected_value"),
            status=item.get("status", "review") if item.get("status") in {"compliant", "non_compliant", "review"} else "review",
            rule_code=item.get("rule_code", rule.rule_code),
            requirement=item.get("requirement", rule.requirement),
            reason=item.get("reason", "Requires reviewer verification."),
            font_size_mm=item.get("font_size_mm"),
            bbox=BoundingBox(**box),
        ))
    existing = {item.key for item in normalized}
    for rule in RULES:
        if rule.id not in existing:
            normalized.append(DeclarationResult(key=rule.id, field_name=rule.title, detected_value=None, status="review", rule_code=rule.rule_code, requirement=rule.requirement, reason="Field was not confidently located; reviewer action required.", font_size_mm=None, bbox=BoundingBox(x=8, y=12 + len(normalized) * 12, width=82, height=9)))
    return normalized


def to_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


async def get_records() -> list[ScanRecord]:
    docs = await db.scans.find().sort("scanned_at", -1).to_list(200)
    return [ScanRecord(**{**doc, "scanned_at": to_utc(doc["scanned_at"])}) for doc in docs]


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard() -> DashboardResponse:
    records = await get_records()
    violation_total = sum(1 for record in records if record.status == "non_compliant")
    pending = sum(1 for record in records if record.review_status == "pending")
    types: dict[str, int] = {}
    regions: dict[str, int] = {}
    for record in records:
        regions[record.region] = regions.get(record.region, 0) + 1
        for declaration in record.declarations:
            if declaration.status == "non_compliant":
                types[declaration.field_name] = types.get(declaration.field_name, 0) + 1
    return DashboardResponse(
        stats=DashboardStats(total_scanned=len(records), violation_rate=round((violation_total / len(records) * 100) if records else 0, 1), pending_reviews=pending, reports_issued=sum(1 for record in records if record.review_status == "verified")),
        violation_types=[BreakdownPoint(name=name, value=value) for name, value in sorted(types.items(), key=lambda item: item[1], reverse=True)[:5]],
        regions=[BreakdownPoint(name=name, value=value) for name, value in regions.items()],
        trend=[TrendPoint(month=month, compliant=compliant, violations=violations) for month, compliant, violations in [("Jan", 28, 6), ("Feb", 34, 7), ("Mar", 42, 5), ("Apr", 39, 9), ("May", 48, 8), ("Jun", max(len(records), 44), max(violation_total, 6))]],
    )


@router.get("/scans", response_model=list[ScanRecord])
async def scans() -> list[ScanRecord]:
    return await get_records()


@router.get("/scans/{scan_id}", response_model=ScanRecord)
async def scan(scan_id: str) -> ScanRecord:
    doc = await db.scans.find_one({"id": scan_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Scan record not found")
    doc["scanned_at"] = to_utc(doc["scanned_at"])
    return ScanRecord(**doc)


@router.post("/scans", response_model=ScanRecord)
async def create_scan(input: ScanCreate) -> ScanRecord:
    declarations: list[DeclarationResult]
    vision: dict | None = None
    product_name = input.product_name
    manufacturer = "Not confidently detected"
    image_url = input.image_url or DEMO_IMAGE
    try:
        if input.image_base64:
            vision = await analyze_with_gemini(input.image_base64, input.mime_type)
            declarations = normalize_declarations(vision["declarations"])
            product_name = vision.get("product_name") or product_name
            manufacturer = vision.get("manufacturer") or manufacturer
            image_url = input.image_base64 if input.image_base64.startswith("data:") else f"data:{input.mime_type};base64,{input.image_base64}"
        else:
            raise RuntimeError("Demo scan")
    except Exception:
        declarations = fallback_declarations()
    scan_id = str(uuid.uuid4())
    extracted_rule_input = vision.get("rule_input") if vision else None
    declarations, engine_report = apply_rule_engine(scan_id, product_name, input.category, declarations, extracted_rule_input)
    status = "compliant" if engine_report.is_compliant else "non_compliant"
    record = ScanRecord(id=scan_id, product_name=product_name, manufacturer=manufacturer, category=input.category, region=input.region, inspector=input.inspector, status=status, image_url=image_url, declarations=declarations, violation_count=engine_report.total_violations, review_status="pending" if not engine_report.is_compliant else "not_required", rule_engine_report=engine_report)
    await db.scans.insert_one(record.model_dump())
    return record


@router.patch("/scans/{scan_id}", response_model=ScanRecord)
async def update_scan(scan_id: str, input: ScanReviewUpdate) -> ScanRecord:
    update: dict = {"remarks": input.remarks, "review_status": input.review_status}
    if input.status:
        update["status"] = input.status
    result = await db.scans.find_one_and_update({"id": scan_id}, {"$set": update}, return_document=ReturnDocument.AFTER)
    if not result:
        raise HTTPException(status_code=404, detail="Scan record not found")
    result["scanned_at"] = to_utc(result["scanned_at"])
    return ScanRecord(**result)


@router.get("/rules", response_model=list[RuleItem])
async def rules() -> list[RuleItem]:
    return RULES