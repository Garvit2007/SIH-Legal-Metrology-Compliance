import base64
import json
import os
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pymongo import ReturnDocument

from lib.auth import current_user, require_roles
from lib.db import db
from lib.image_pipeline import ImageValidationError, PreparedImage, prepare_images, upload_config
from lib.mrp import detect_mrp
from lib.report_service import build_docx, build_pdf
from lib.rule_adapter import apply_rule_engine
from lib.rule_catalog import RULES, build_rule_results
from models.auth import UserPublic
from models.compliance import (
    BoundingBox,
    BreakdownPoint,
    DashboardResponse,
    DashboardStats,
    DeclarationResult,
    ExtractedProduct,
    RuleItem,
    ScanCreate,
    ScanImage,
    ScanRecord,
    ScanReviewUpdate,
    TrendPoint,
    UploadConfig,
)


router = APIRouter(prefix="/compliance", tags=["compliance"])
DEMO_IMAGE = "https://images.unsplash.com/photo-1618381297523-e6c0ab13a5b2?auto=format&fit=crop&w=1400&q=85"
CATEGORIES = ["Food & Beverages", "Grocery", "Edible Oil", "Spices", "Snacks", "Household Products", "Home Décor/Home Products", "Personal Care", "Cosmetics", "Medical/Healthcare", "Cleaning Products", "Stationery", "Electrical/Consumer Products", "Other"]

DECLARATION_META = {
    "manufacturer_details": ("Manufacturer / Packer / Importer", "Rule 6(1)(a), Rule 10", "Complete name and address of the responsible business", "Check that the business name and address are clearly printed."),
    "commodity_name": ("Product / Commodity Name", "Rule 6(1)(b)", "Common or generic name of the commodity", "The package should clearly identify what the product is."),
    "net_quantity": ("Net Quantity", "Rule 6(1)(c), Rules 12-13", "Net quantity in a standard SI unit", "Check that the quantity is clearly stated in g, kg, ml, L, N or U."),
    "mrp": ("Maximum Retail Price", "Rule 6(1)(e)", "MRP inclusive of all taxes", "Check that the MRP is clearly displayed and do not pay above it."),
    "date_mfg": ("Manufacturing / Packing Date", "Rule 6(1)(d)", "Month and year of manufacture, packing or import", "Check the manufacture/packing date and shelf-life information."),
    "batch_lot": ("Batch / Lot Number", "Rule 6(1)(g)", "Batch or lot traceability information where declared", "Keep the batch number for complaints or recalls."),
    "consumer_care": ("Consumer Care", "Rule 6(2)", "Consumer complaint contact details", "Look for a phone number or email for complaints."),
    "font_size_pdp": ("Legibility / Type Size", "Rules 7-9", "Legible, prominent declarations meeting applicable type-size rules", "Mandatory information should be easy to read."),
}


def fallback_declarations(image_id: str | None = None, face: str | None = None) -> list[DeclarationResult]:
    values = {
        "manufacturer_details": "Shakti Foods Pvt. Ltd., Okhla Industrial Area, New Delhi 110020",
        "commodity_name": "Whole Wheat Flour",
        "net_quantity": "Net Qty. 500 g",
        "mrp": "MRP ₹120.00 (incl. of all taxes)",
        "date_mfg": "Packed on: 05/2024",
        "batch_lot": "Batch No. SF2405A",
        "consumer_care": "care@shaktifoods.in · 1800 123 4567",
        "font_size_pdp": "1.2 mm estimated",
    }
    boxes = [(10, 67, 73, 11), (10, 8, 45, 9), (10, 18, 25, 10), (54, 79, 35, 9), (10, 83, 35, 8), (52, 68, 34, 8), (10, 56, 78, 9), (10, 38, 73, 12)]
    output = []
    for index, (key, value) in enumerate(values.items()):
        title, rule, requirement, consumer = DECLARATION_META[key]
        x, y, width, height = boxes[index]
        output.append(DeclarationResult(key=key, field_name=title, detected_value=value, status="review", confidence="high", rule_code=rule, requirement=requirement, reason="Awaiting configured rule-engine evaluation.", consumer_explanation=consumer, font_size_mm=1.2 if key == "font_size_pdp" else 2.8 if key in {"mrp", "net_quantity"} else None, bbox=BoundingBox(x=x, y=y, width=width, height=height), evidence_image_id=image_id, evidence_face=face))
    return output


def empty_declarations() -> list[DeclarationResult]:
    return [DeclarationResult(key=key, field_name=meta[0], detected_value=None, status="not_detected", confidence="low", rule_code=meta[1], requirement=meta[2], reason="Not detected across the uploaded package faces. Manual verification is required.", consumer_explanation=meta[3], bbox=BoundingBox(x=8, y=8 + index * 10, width=84, height=8)) for index, (key, meta) in enumerate(DECLARATION_META.items())]


def clean_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Vision response did not contain JSON")
    return json.loads(text[start:end + 1])


async def analyze_with_gemini(images: list[PreparedImage], enhanced: bool = True) -> dict:
    from emergentintegrations.llm.chat import ImageContent, LlmChat, StreamDone, TextDelta, UserMessage
    key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not key:
        raise RuntimeError("EMERGENT_LLM_KEY is not configured")
    labels = ", ".join(f"image {index + 1}={item.source.face_label}" for index, item in enumerate(images))
    prompt = f"""You are the OCR/extraction stage for Indian packaged commodity labels. The user uploaded multiple faces of ONE product in this order: {labels}. Read English, Hindi and mixed text across ALL faces. Combine duplicate declarations and do not mark a field absent until every image has been searched. Return JSON only with: product_name, brand, category (one of {CATEGORIES}), manufacturer, ocr_texts (array of {{image_index, text}}), declarations (array of {{key, field_name, detected_value, confidence high|medium|low, evidence_image_index, bbox {{x,y,width,height}}}}), and rule_input matching the provided rule-engine contract. Required keys are manufacturer_details, commodity_name, net_quantity, mrp, date_mfg, batch_lot, consumer_care, font_size_pdp. For MRP, prefer text explicitly near MRP/M.R.P./Maximum Retail Price and never confuse selling price, offer price, quantity, batch, barcode, phone, GST or product code. If multiple prices exist, preserve the surrounding line in ocr_texts and set MRP confidence low unless context is explicit. Never invent physical millimetre font heights without a visible scale. Use null for missing or unreliable values. This is extraction only; do not decide legal compliance."""
    contents = []
    for item in images:
        payload = item.enhanced_base64 if enhanced else base64.b64encode(item.raw_bytes).decode("ascii")
        contents.append(ImageContent(image_base64=payload))
    chat = LlmChat(api_key=key, session_id=f"multi-scan-{uuid.uuid4()}", system_message="Return valid JSON only. Search every uploaded package face before declaring a field absent.").with_model("gemini", "gemini-3.1-pro-preview")
    chunks: list[str] = []
    async for event in chat.stream_message(UserMessage(text=prompt, file_contents=contents)):
        if isinstance(event, TextDelta):
            chunks.append(event.content)
        elif isinstance(event, StreamDone):
            break
    result = clean_json("".join(chunks))
    if not result.get("declarations"):
        raise ValueError("No declarations were extracted")
    return result


def classify_category(product_name: str, texts: list[str], proposed: str | None) -> str:
    if proposed in CATEGORIES:
        return proposed
    text = f"{product_name} {' '.join(texts)}".lower()
    mapping = [
        ("Edible Oil", ["edible oil", "cooking oil", "sunflower", "mustard oil", "soyabean oil"]),
        ("Spices", ["masala", "turmeric", "haldi", "chilli powder", "spice"]),
        ("Snacks", ["namkeen", "chips", "biscuit", "snack"]),
        ("Cleaning Products", ["detergent", "cleaner", "dishwash", "toilet cleaner"]),
        ("Personal Care", ["shampoo", "soap", "hand wash", "toothpaste"]),
        ("Cosmetics", ["cosmetic", "lipstick", "foundation", "cream"]),
        ("Medical/Healthcare", ["medical", "tablet", "capsule", "sanitizer"]),
        ("Stationery", ["pen", "pencil", "notebook", "stationery"]),
        ("Electrical/Consumer Products", ["electrical", "charger", "bulb", "battery"]),
        ("Home Décor/Home Products", ["bedsheet", "curtain", "towel", "decor"]),
        ("Household Products", ["household", "storage", "container"]),
        ("Grocery", ["atta", "rice", "dal", "pulses", "flour", "salt"]),
        ("Food & Beverages", ["food", "drink", "juice", "beverage"]),
    ]
    return next((category for category, words in mapping if any(word in text for word in words)), "Other")


def normalize_declarations(raw: list[dict], images: list[ScanImage]) -> list[DeclarationResult]:
    confidence_rank = {"low": 0, "medium": 1, "high": 2}
    chosen: dict[str, dict] = {}
    for item in raw:
        key = item.get("key")
        if key not in DECLARATION_META:
            continue
        confidence = item.get("confidence", "low")
        current = chosen.get(key)
        if not current or confidence_rank.get(confidence, 0) > confidence_rank.get(current.get("confidence", "low"), 0):
            chosen[key] = item
    results: list[DeclarationResult] = []
    for index, (key, meta) in enumerate(DECLARATION_META.items()):
        item = chosen.get(key, {})
        image_index = item.get("evidence_image_index")
        evidence = images[image_index] if isinstance(image_index, int) and 0 <= image_index < len(images) else None
        box = item.get("bbox") or {"x": 8, "y": 8 + index * 10, "width": 84, "height": 8}
        value = item.get("detected_value")
        confidence = item.get("confidence", "low") if item.get("confidence") in {"high", "medium", "low"} else "low"
        results.append(DeclarationResult(key=key, field_name=meta[0], detected_value=value, status="review" if value else "not_detected", confidence=confidence, rule_code=meta[1], requirement=meta[2], reason="Awaiting configured rule-engine evaluation." if value else "Not detected across the uploaded package faces.", consumer_explanation=meta[3], font_size_mm=item.get("font_size_mm"), bbox=BoundingBox(**box), evidence_image_id=evidence.id if evidence else None, evidence_face=evidence.face_label if evidence else None))
    return results


def to_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


async def hydrate(doc: dict) -> ScanRecord:
    image_docs = await db.inspection_images.find({"inspection_id": doc["id"]}, {"_id": 0, "owner_id": 0}).sort("position", 1).to_list(8)
    doc = {**doc, "scanned_at": to_utc(doc["scanned_at"]), "images": image_docs}
    return ScanRecord(**doc)


def access_query(user: UserPublic) -> dict:
    return {} if user.role == "admin" else {"owner_id": user.id}


async def get_record(scan_id: str, user: UserPublic) -> ScanRecord:
    query = {"id": scan_id, **access_query(user)}
    doc = await db.scans.find_one(query)
    if not doc:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return await hydrate(doc)


@router.get("/config", response_model=UploadConfig)
async def config() -> UploadConfig:
    return UploadConfig(**upload_config())


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(user: UserPublic = Depends(current_user)) -> DashboardResponse:
    docs = await db.scans.find(access_query(user)).sort("scanned_at", -1).to_list(200)
    records = [ScanRecord(**{**doc, "scanned_at": to_utc(doc["scanned_at"])}) for doc in docs]
    violation_total = sum(1 for record in records if record.status == "non_compliant")
    pending = sum(1 for record in records if record.review_status == "pending")
    types: dict[str, int] = {}
    regions: dict[str, int] = {}
    for record in records:
        regions[record.region] = regions.get(record.region, 0) + 1
        for result in record.rule_results:
            if result.status == "non_compliant":
                types[result.rule_title] = types.get(result.rule_title, 0) + 1
    return DashboardResponse(stats=DashboardStats(total_scanned=len(records), violation_rate=round((violation_total / len(records) * 100) if records else 0, 1), pending_reviews=pending, reports_issued=sum(1 for record in records if record.review_status == "verified")), violation_types=[BreakdownPoint(name=name, value=value) for name, value in sorted(types.items(), key=lambda item: item[1], reverse=True)[:5]], regions=[BreakdownPoint(name=name, value=value) for name, value in regions.items()], trend=[TrendPoint(month=month, compliant=compliant, violations=violations) for month, compliant, violations in [("Jan", 28, 6), ("Feb", 34, 7), ("Mar", 42, 5), ("Apr", 39, 9), ("May", 48, 8), ("Jun", max(len(records), 1), max(violation_total, 0))]])


@router.get("/scans", response_model=list[ScanRecord])
async def scans(user: UserPublic = Depends(current_user)) -> list[ScanRecord]:
    docs = await db.scans.find(access_query(user)).sort("scanned_at", -1).to_list(100)
    return [await hydrate(doc) for doc in docs]


@router.get("/scans/{scan_id}", response_model=ScanRecord)
async def scan(scan_id: str, user: UserPublic = Depends(current_user)) -> ScanRecord:
    return await get_record(scan_id, user)


@router.post("/scans", response_model=ScanRecord)
async def create_scan(input: ScanCreate, user: UserPublic = Depends(current_user)) -> ScanRecord:
    scan_id = str(uuid.uuid4())
    prepared: list[PreparedImage] = []
    image_models: list[ScanImage] = []
    processing_notes: list[str] = []
    is_demo = not input.images and bool(input.image_url)
    if input.images:
        try:
            prepared = prepare_images(input.images)
        except ImageValidationError as exc:
            raise HTTPException(status_code=422, detail={"code": "image_quality", "message": "Please replace unsuitable images before scanning.", "errors": exc.errors}) from exc
        for position, item in enumerate(prepared):
            image_id = str(uuid.uuid4())
            image_model = ScanImage(id=image_id, inspection_id=scan_id, face_label=item.source.face_label, file_name=item.source.file_name, mime_type=item.source.mime_type, data_url=item.original_data_url, sha256=item.sha256, quality=item.quality)
            image_models.append(image_model)
            await db.inspection_images.insert_one({**image_model.model_dump(), "owner_id": user.id, "position": position})
            processing_notes.extend(item.quality.warnings)
    elif not is_demo:
        raise HTTPException(status_code=422, detail={"code": "images_required", "message": "Upload at least one package-face image."})

    vision: dict | None = None
    ocr_texts: list[dict] = []
    if is_demo:
        declarations = fallback_declarations()
        product_name = input.product_name
        brand = "Shakti"
        manufacturer = "Shakti Foods Pvt. Ltd."
        category = "Grocery"
    else:
        try:
            vision = await analyze_with_gemini(prepared, enhanced=True)
        except Exception:
            try:
                vision = await analyze_with_gemini(prepared, enhanced=False)
                processing_notes.append("OCR fallback used the original images after enhanced processing was inconclusive.")
            except Exception:
                vision = None
        if vision:
            ocr_texts = [item for item in vision.get("ocr_texts", []) if isinstance(item, dict)]
            text_values = [str(item.get("text", "")) for item in ocr_texts]
            declarations = normalize_declarations(vision.get("declarations", []), image_models)
            product_name = vision.get("product_name") or input.product_name
            brand = vision.get("brand")
            manufacturer = vision.get("manufacturer") or next((item.detected_value for item in declarations if item.key == "manufacturer_details" and item.detected_value), "Not reliably detected")
            category = classify_category(product_name, text_values, vision.get("category"))
            mrp_match = detect_mrp(text_values)
            mrp_decl = next(item for item in declarations if item.key == "mrp")
            if mrp_match.value and mrp_match.image_index is not None and mrp_match.image_index < len(image_models):
                evidence = image_models[mrp_match.image_index]
                mrp_decl = mrp_decl.model_copy(update={"detected_value": mrp_match.value, "confidence": mrp_match.confidence, "status": "review", "evidence_image_id": evidence.id, "evidence_face": evidence.face_label, "reason": f"Contextual MRP match score {mrp_match.score}."})
            elif mrp_match.confidence == "low":
                mrp_decl = mrp_decl.model_copy(update={"detected_value": None, "confidence": "low", "status": "manual_review", "reason": "MRP requires manual verification."})
            declarations = [mrp_decl if item.key == "mrp" else item for item in declarations]
        else:
            declarations = empty_declarations()
            product_name = input.product_name
            brand = None
            manufacturer = "Not reliably detected"
            category = input.category if input.category in CATEGORIES else "Other"
            processing_notes.append("Text could not be reliably extracted after enhanced and original-image OCR attempts.")

    extracted_rule_input = vision.get("rule_input") if vision else None
    declarations, engine_report = apply_rule_engine(scan_id, product_name, category, declarations, extracted_rule_input)
    quality_warnings = [warning for image in image_models for warning in image.quality.warnings]
    rule_results = build_rule_results(declarations, engine_report, category, quality_warnings)
    if any(result.status == "non_compliant" for result in rule_results):
        status = "non_compliant"
    elif any(result.status == "manual_verification" for result in rule_results):
        status = "manual_review"
    elif any(result.status == "not_detected" for result in rule_results):
        status = "partially_compliant"
    else:
        status = "compliant"
    by_key = {item.key: item for item in declarations}
    extracted = ExtractedProduct(product_name=product_name, brand=brand, category=category, manufacturer=manufacturer, net_quantity=by_key.get("net_quantity").detected_value if by_key.get("net_quantity") else None, mrp=by_key.get("mrp").detected_value if by_key.get("mrp") else None, mfg_date=by_key.get("date_mfg").detected_value if by_key.get("date_mfg") else None, batch_lot=by_key.get("batch_lot").detected_value if by_key.get("batch_lot") else None, consumer_care=by_key.get("consumer_care").detected_value if by_key.get("consumer_care") else None)
    record = ScanRecord(id=scan_id, owner_id=user.id, owner_role=user.role, product_name=product_name, brand=brand, manufacturer=manufacturer, category=category, region=user.region, inspector=user.name, status=status, image_url=image_models[0].data_url if image_models else input.image_url or DEMO_IMAGE, image_ids=[image.id for image in image_models], images=image_models, declarations=declarations, extracted_product=extracted, ocr_texts=ocr_texts, processing_notes=list(dict.fromkeys(processing_notes)), rule_results=rule_results, violation_count=sum(1 for result in rule_results if result.status == "non_compliant"), review_status="pending" if status != "compliant" else "not_required", rule_engine_report=engine_report)
    await db.scans.insert_one(record.model_dump(exclude={"images"}))
    return record


@router.patch("/scans/{scan_id}", response_model=ScanRecord)
async def update_scan(scan_id: str, input: ScanReviewUpdate, user: UserPublic = Depends(current_user)) -> ScanRecord:
    query = {"id": scan_id, **access_query(user)}
    update = {"remarks": input.remarks, "consumer_review": input.consumer_review, "review_status": input.review_status}
    if input.status and user.role in {"admin", "inspector"}:
        update["status"] = input.status
    result = await db.scans.find_one_and_update(query, {"$set": update}, return_document=ReturnDocument.AFTER)
    if not result:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return await hydrate(result)


@router.get("/scans/{scan_id}/report.pdf")
async def report_pdf(scan_id: str, user: UserPublic = Depends(current_user)) -> StreamingResponse:
    record = await get_record(scan_id, user)
    try:
        payload = build_pdf(record)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="PDF generation failed; no file was produced") from exc
    return StreamingResponse(iter([payload]), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="legal-metrology-{scan_id}.pdf"', "Content-Length": str(len(payload))})


@router.get("/scans/{scan_id}/report.docx")
async def report_docx(scan_id: str, user: UserPublic = Depends(current_user)) -> StreamingResponse:
    record = await get_record(scan_id, user)
    payload = build_docx(record)
    return StreamingResponse(iter([payload]), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": f'attachment; filename="legal-metrology-{scan_id}.docx"', "Content-Length": str(len(payload))})


@router.get("/rules", response_model=list[RuleItem])
async def rules(user: UserPublic = Depends(current_user)) -> list[RuleItem]:
    return RULES