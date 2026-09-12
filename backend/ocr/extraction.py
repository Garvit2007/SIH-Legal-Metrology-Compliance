<<<<<<< HEAD
import re
from typing import Any


# -----------------------------
# Config
# -----------------------------

QUANTITY_UNITS = (
    r"(?:kgs?|g|gm|gms|grams?|mg|milligrams?|l|ltrs?|litres?|liters?|ml|mls?)"
)

STOP_KEYWORDS = [
    "mrp", "m.r.p", "net wt", "net qty", "net quantity", "net weight",
    "net vol", "net volume", "contents", "best before", "use by",
    "expiry", "exp dt", "exp date", "batch", "lot no", "b.no", "b. no",
    "fssai", "customer care", "consumer care", "helpline", "toll free",
    "mfg", "mfd", "manufactured", "packed on", "pkd on", "marketed by",
    "packed by", "country of origin", "made in", "product of",
    "ingredients", "barcode"
]


def is_stop_line(line: str) -> bool:
    lower = line.lower()
    return any(k in lower for k in STOP_KEYWORDS)


def empty_product() -> dict[str, Any]:
    return {
        "manufacturer_address": "",
        "commodity_name": "",
        "net_quantity": "",
        "net_quantity_value_g_ml": None,
        "quantity_type": "",
        "mrp": "",
        "mrp_value": None,
        "mfg_date": "",
        "best_before_or_expiry": "",
        "batch_no": "",
        "fssai_license_no": "",
        "consumer_care": "",
        "is_imported": False,
        "country_of_origin": "",
        "buyer_type": "retail",
        "category": "packaged_food",
        "detected_language": "en",
        "pdp_area_cm2": None,
        "pdp_box": None,
        "font_heights_mm": {},
        "is_embossed": False,
        "letter_width_height_ratios": {},
        "declaration_boxes": {},
        "nearest_other_text_distance_mm": {},
        "body_text_height_mm": None,
        "contrast_ok": {}
    }


def normalize_text(text: str) -> str:
    text = str(text).replace("|", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def box_height(box) -> float:
    try:
        ys = [p[1] for p in box]
        return max(ys) - min(ys)
    except Exception:
        return 0.0


def box_top(box) -> float:
    try:
        ys = [p[1] for p in box]
        return min(ys)
    except Exception:
        return 0.0


# -----------------------------
# Individual field matchers (run per line, and as a full-text fallback)
# -----------------------------

def _normalize_unit(value: float, unit: str) -> float:
    unit = unit.lower()
    if unit.startswith("kg"):
        return value * 1000
    if unit.startswith("mg"):
        return value / 1000
    if unit in {"g", "gm", "gms"} or unit.startswith("gram"):
        return value
    if unit in {"l", "ltr", "ltrs", "litre", "litres", "liter", "liters"}:
        return value * 1000
    if unit in {"ml", "mls"}:
        return value
    return value


def match_quantity(text: str):
    # multipack, e.g. "4 x 100 g", "10x20ml"
    multi = re.search(
        rf"(\d+)\s*[x×]\s*(\d+(?:\.\d+)?)\s*({QUANTITY_UNITS})\b",
        text, re.IGNORECASE
    )
    if multi:
        count = float(multi.group(1))
        value = float(multi.group(2))
        unit = multi.group(3).lower()
        total = _normalize_unit(value, unit) * count
        return multi.group(0), total, "weight_or_volume"

    single = re.search(
        rf"\b(\d+(?:\.\d+)?)\s*({QUANTITY_UNITS})\b",
        text, re.IGNORECASE
    )
    if single:
        value = float(single.group(1))
        unit = single.group(2).lower()
        total = _normalize_unit(value, unit)
        return single.group(0), total, "weight_or_volume"

    return None


def match_mrp(text: str):
    match = re.search(
        r"(?:mrp|m\.r\.p\.?|max(?:imum)?\s*retail\s*price)\s*[:\-]?\s*"
        r"(?:₹|rs\.?|inr)?\s*"
        r"([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?)",
        text, re.IGNORECASE
    )
    if not match:
        return None
    raw_value = match.group(1).replace(",", "")
    try:
        value = float(raw_value)
    except ValueError:
        value = None
    return match.group(0), value


def match_mfg_date(text: str):
    match = re.search(
        r"(?:mfg|mfd|manufactured|manufacturing|date\s*of\s*mfg|"
        r"pkd\s*on|packed\s*on|date\s*of\s*packing)"
        r".{0,25}?"
        r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}"
        r"|\d{1,2}[/\-.]\d{2,4}"
        r"|[A-Za-z]{3,9}\s+\d{4})",
        text, re.IGNORECASE
    )
    return match.group(1) if match else None


def match_expiry(text: str):
    match = re.search(
        r"(?:best\s*before|use\s*by|exp(?:iry)?\s*(?:dt|date)?)"
        r".{0,30}?"
        r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}"
        r"|\d{1,2}[/\-.]\d{2,4}"
        r"|[A-Za-z]{3,9}\s+\d{4}"
        r"|\d+\s*(?:months?|years?|days?)\s*(?:from|of)?\s*"
        r"(?:mfg|packing|manufacture)?)",
        text, re.IGNORECASE
    )
    return match.group(1).strip() if match else None


def match_batch(text: str):
    match = re.search(
        r"(?:batch\s*no\.?|lot\s*no\.?|b\.?\s*no\.?)\s*[:\-]?\s*"
        r"([A-Za-z0-9\-/]{2,20})",
        text, re.IGNORECASE
    )
    return match.group(1) if match else None


def match_fssai(text: str):
    match = re.search(
        r"fssai(?:\s*(?:lic(?:ense|\.)?\s*no\.?|no\.?|reg(?:\.|istration)?\s*no\.?))?"
        r"\s*[:\-]?\s*(\d{10,14})",
        text, re.IGNORECASE
    )
    return match.group(1) if match else None


def match_consumer_care(line: str) -> bool:
    lower = line.lower()
    return bool(
        "customer care" in lower
        or "consumer care" in lower
        or "helpline" in lower
        or "toll free" in lower
        or "@" in line
        or re.search(r"\b1800[-\d ]{6,}\b", line)
        or re.search(r"\b\d{10}\b", line)
    )


def match_manufacturer(line: str) -> bool:
    lower = line.lower()
    return any(k in lower for k in [
        "manufactured by", "manufactured and marketed by",
        "marketed by", "packed by", "packer", "manufacturer"
    ])


def match_country_of_origin(text: str):
    match = re.search(
        r"(?:country of origin|made in|product of)\s*[:\-]?\s*([^\n]+)",
        text, re.IGNORECASE
    )
    return match.group(1).strip() if match else None


# -----------------------------
# Commodity name (uses box heights - product name is usually the biggest font)
# -----------------------------

def infer_commodity_name(lines: list[str], boxes: list, tagged_indices: set) -> str:
    candidates = []

    for idx, line in enumerate(lines):
        clean = line.strip()

        if idx in tagged_indices:
            continue
        if len(clean) < 3 or len(clean) > 80:
            continue
        if is_stop_line(clean):
            continue
        if re.fullmatch(r"[\d\W_]+", clean):
            continue

        height = box_height(boxes[idx]) if idx < len(boxes) and boxes[idx] else 0
        top = box_top(boxes[idx]) if idx < len(boxes) and boxes[idx] else idx

        candidates.append((height, -top, idx, clean))

    if not candidates:
        return ""

    # Prefer the tallest text (largest font = product name), tie-break topmost
    candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
    return candidates[0][3]


# -----------------------------
# Full contract builder
# -----------------------------

def build_contract(lines: list[str], scores: list, boxes: list) -> dict[str, Any]:
    product = empty_product()
    field_line_indices: dict[str, list[int]] = {}
    tagged: set = set()

    def tag(field, idx):
        field_line_indices.setdefault(field, []).append(idx)
        tagged.add(idx)

    manufacturer_lines = []
    consumer_care_lines = []

    for idx, line in enumerate(lines):
        q = match_quantity(line)
        if q and not product["net_quantity"]:
            (product["net_quantity"], product["net_quantity_value_g_ml"],
             product["quantity_type"]) = q
            tag("net_quantity", idx)

        mrp = match_mrp(line)
        if mrp and not product["mrp"]:
            product["mrp"], product["mrp_value"] = mrp
            tag("mrp", idx)

        mfg = match_mfg_date(line)
        if mfg and not product["mfg_date"]:
            product["mfg_date"] = mfg
            tag("mfg_date", idx)

        exp = match_expiry(line)
        if exp and not product["best_before_or_expiry"]:
            product["best_before_or_expiry"] = exp
            tag("best_before_or_expiry", idx)

        batch = match_batch(line)
        if batch and not product["batch_no"]:
            product["batch_no"] = batch
            tag("batch_no", idx)

        fssai = match_fssai(line)
        if fssai and not product["fssai_license_no"]:
            product["fssai_license_no"] = fssai
            tag("fssai_license_no", idx)

        if match_consumer_care(line):
            consumer_care_lines.append(line.strip())
            tag("consumer_care", idx)

        if match_manufacturer(line):
            manufacturer_lines.append(line.strip())
            tag("manufacturer_address", idx)

        origin = match_country_of_origin(line)
        if origin and not product["country_of_origin"]:
            product["country_of_origin"] = origin
            product["is_imported"] = True
            tag("country_of_origin", idx)

    # Fallback: fields split across a line break, searched on the joined text
    full_text = "\n".join(lines)

    if not product["net_quantity"]:
        q = match_quantity(full_text)
        if q:
            (product["net_quantity"], product["net_quantity_value_g_ml"],
             product["quantity_type"]) = q

    if not product["mrp"]:
        mrp = match_mrp(full_text)
        if mrp:
            product["mrp"], product["mrp_value"] = mrp

    if not product["mfg_date"]:
        mfg = match_mfg_date(full_text)
        if mfg:
            product["mfg_date"] = mfg

    if not product["best_before_or_expiry"]:
        exp = match_expiry(full_text)
        if exp:
            product["best_before_or_expiry"] = exp

    if not product["batch_no"]:
        batch = match_batch(full_text)
        if batch:
            product["batch_no"] = batch

    if not product["fssai_license_no"]:
        fssai = match_fssai(full_text)
        if fssai:
            product["fssai_license_no"] = fssai

    if not product["is_imported"]:
        product["is_imported"] = bool(re.search(
            r"imported by|country of origin|made in|product of",
            full_text, re.IGNORECASE
        ))

    product["consumer_care"] = ", ".join(dict.fromkeys(consumer_care_lines))
    product["manufacturer_address"] = " ".join(dict.fromkeys(manufacturer_lines))
    product["commodity_name"] = infer_commodity_name(lines, boxes, tagged)

    if product["commodity_name"]:
        for idx, line in enumerate(lines):
            if line.strip() == product["commodity_name"]:
                tag("commodity_name", idx)
                break

    valid_scores = []
    for s in scores:
        try:
            valid_scores.append(float(s))
        except (TypeError, ValueError):
            pass

    average_confidence = (
        sum(valid_scores) / len(valid_scores) if valid_scores else None
    )

    product["_ocr"] = {
        "text_count": len(lines),
        "average_confidence": average_confidence,
        "rec_texts": lines,
        "rec_scores": scores
    }

    # internal-only, popped by the caller before saving the contract json
    product["_field_line_indices"] = field_line_indices

=======
import re
from typing import Any


# -----------------------------
# Config
# -----------------------------

QUANTITY_UNITS = (
    r"(?:kgs?|g|gm|gms|grams?|mg|milligrams?|l|ltrs?|litres?|liters?|ml|mls?)"
)

STOP_KEYWORDS = [
    "mrp", "m.r.p", "net wt", "net qty", "net quantity", "net weight",
    "net vol", "net volume", "contents", "best before", "use by",
    "expiry", "exp dt", "exp date", "batch", "lot no", "b.no", "b. no",
    "fssai", "customer care", "consumer care", "helpline", "toll free",
    "mfg", "mfd", "manufactured", "packed on", "pkd on", "marketed by",
    "packed by", "country of origin", "made in", "product of",
    "ingredients", "barcode"
]


def is_stop_line(line: str) -> bool:
    lower = line.lower()
    return any(k in lower for k in STOP_KEYWORDS)


def empty_product() -> dict[str, Any]:
    return {
        "manufacturer_address": "",
        "commodity_name": "",
        "net_quantity": "",
        "net_quantity_value_g_ml": None,
        "quantity_type": "",
        "mrp": "",
        "mrp_value": None,
        "mfg_date": "",
        "best_before_or_expiry": "",
        "batch_no": "",
        "fssai_license_no": "",
        "consumer_care": "",
        "is_imported": False,
        "country_of_origin": "",
        "buyer_type": "retail",
        "category": "packaged_food",
        "detected_language": "en",
        "pdp_area_cm2": None,
        "pdp_box": None,
        "font_heights_mm": {},
        "is_embossed": False,
        "letter_width_height_ratios": {},
        "declaration_boxes": {},
        "nearest_other_text_distance_mm": {},
        "body_text_height_mm": None,
        "contrast_ok": {}
    }


def normalize_text(text: str) -> str:
    text = str(text).replace("|", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def box_height(box) -> float:
    try:
        ys = [p[1] for p in box]
        return max(ys) - min(ys)
    except Exception:
        return 0.0


def box_top(box) -> float:
    try:
        ys = [p[1] for p in box]
        return min(ys)
    except Exception:
        return 0.0


# -----------------------------
# Individual field matchers (run per line, and as a full-text fallback)
# -----------------------------

def _normalize_unit(value: float, unit: str) -> float:
    unit = unit.lower()
    if unit.startswith("kg"):
        return value * 1000
    if unit.startswith("mg"):
        return value / 1000
    if unit in {"g", "gm", "gms"} or unit.startswith("gram"):
        return value
    if unit in {"l", "ltr", "ltrs", "litre", "litres", "liter", "liters"}:
        return value * 1000
    if unit in {"ml", "mls"}:
        return value
    return value


def match_quantity(text: str):
    # multipack, e.g. "4 x 100 g", "10x20ml"
    multi = re.search(
        rf"(\d+)\s*[x×]\s*(\d+(?:\.\d+)?)\s*({QUANTITY_UNITS})\b",
        text, re.IGNORECASE
    )
    if multi:
        count = float(multi.group(1))
        value = float(multi.group(2))
        unit = multi.group(3).lower()
        total = _normalize_unit(value, unit) * count
        return multi.group(0), total, "weight_or_volume"

    single = re.search(
        rf"\b(\d+(?:\.\d+)?)\s*({QUANTITY_UNITS})\b",
        text, re.IGNORECASE
    )
    if single:
        value = float(single.group(1))
        unit = single.group(2).lower()
        total = _normalize_unit(value, unit)
        return single.group(0), total, "weight_or_volume"

    return None


def match_mrp(text: str):
    match = re.search(
        r"(?:mrp|m\.r\.p\.?|max(?:imum)?\s*retail\s*price)\s*[:\-]?\s*"
        r"(?:₹|rs\.?|inr)?\s*"
        r"([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?)",
        text, re.IGNORECASE
    )
    if not match:
        return None
    raw_value = match.group(1).replace(",", "")
    try:
        value = float(raw_value)
    except ValueError:
        value = None
    return match.group(0), value


def match_mfg_date(text: str):
    match = re.search(
        r"(?:mfg|mfd|manufactured|manufacturing|date\s*of\s*mfg|"
        r"pkd\s*on|packed\s*on|date\s*of\s*packing)"
        r".{0,25}?"
        r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}"
        r"|\d{1,2}[/\-.]\d{2,4}"
        r"|[A-Za-z]{3,9}\s+\d{4})",
        text, re.IGNORECASE
    )
    return match.group(1) if match else None


def match_expiry(text: str):
    match = re.search(
        r"(?:best\s*before|use\s*by|exp(?:iry)?\s*(?:dt|date)?)"
        r".{0,30}?"
        r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}"
        r"|\d{1,2}[/\-.]\d{2,4}"
        r"|[A-Za-z]{3,9}\s+\d{4}"
        r"|\d+\s*(?:months?|years?|days?)\s*(?:from|of)?\s*"
        r"(?:mfg|packing|manufacture)?)",
        text, re.IGNORECASE
    )
    return match.group(1).strip() if match else None


def match_batch(text: str):
    match = re.search(
        r"(?:batch\s*no\.?|lot\s*no\.?|b\.?\s*no\.?)\s*[:\-]?\s*"
        r"([A-Za-z0-9\-/]{2,20})",
        text, re.IGNORECASE
    )
    return match.group(1) if match else None


def match_fssai(text: str):
    match = re.search(
        r"fssai(?:\s*(?:lic(?:ense|\.)?\s*no\.?|no\.?|reg(?:\.|istration)?\s*no\.?))?"
        r"\s*[:\-]?\s*(\d{10,14})",
        text, re.IGNORECASE
    )
    return match.group(1) if match else None


def match_consumer_care(line: str) -> bool:
    lower = line.lower()
    return bool(
        "customer care" in lower
        or "consumer care" in lower
        or "helpline" in lower
        or "toll free" in lower
        or "@" in line
        or re.search(r"\b1800[-\d ]{6,}\b", line)
        or re.search(r"\b\d{10}\b", line)
    )


def match_manufacturer(line: str) -> bool:
    lower = line.lower()
    return any(k in lower for k in [
        "manufactured by", "manufactured and marketed by",
        "marketed by", "packed by", "packer", "manufacturer"
    ])


def match_country_of_origin(text: str):
    match = re.search(
        r"(?:country of origin|made in|product of)\s*[:\-]?\s*([^\n]+)",
        text, re.IGNORECASE
    )
    return match.group(1).strip() if match else None


# -----------------------------
# Commodity name (uses box heights - product name is usually the biggest font)
# -----------------------------

def infer_commodity_name(lines: list[str], boxes: list, tagged_indices: set) -> str:
    candidates = []

    for idx, line in enumerate(lines):
        clean = line.strip()

        if idx in tagged_indices:
            continue
        if len(clean) < 3 or len(clean) > 80:
            continue
        if is_stop_line(clean):
            continue
        if re.fullmatch(r"[\d\W_]+", clean):
            continue

        height = box_height(boxes[idx]) if idx < len(boxes) and boxes[idx] else 0
        top = box_top(boxes[idx]) if idx < len(boxes) and boxes[idx] else idx

        candidates.append((height, -top, idx, clean))

    if not candidates:
        return ""

    # Prefer the tallest text (largest font = product name), tie-break topmost
    candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
    return candidates[0][3]


# -----------------------------
# Full contract builder
# -----------------------------

def build_contract(lines: list[str], scores: list, boxes: list) -> dict[str, Any]:
    product = empty_product()
    field_line_indices: dict[str, list[int]] = {}
    tagged: set = set()

    def tag(field, idx):
        field_line_indices.setdefault(field, []).append(idx)
        tagged.add(idx)

    manufacturer_lines = []
    consumer_care_lines = []

    for idx, line in enumerate(lines):
        q = match_quantity(line)
        if q and not product["net_quantity"]:
            (product["net_quantity"], product["net_quantity_value_g_ml"],
             product["quantity_type"]) = q
            tag("net_quantity", idx)

        mrp = match_mrp(line)
        if mrp and not product["mrp"]:
            product["mrp"], product["mrp_value"] = mrp
            tag("mrp", idx)

        mfg = match_mfg_date(line)
        if mfg and not product["mfg_date"]:
            product["mfg_date"] = mfg
            tag("mfg_date", idx)

        exp = match_expiry(line)
        if exp and not product["best_before_or_expiry"]:
            product["best_before_or_expiry"] = exp
            tag("best_before_or_expiry", idx)

        batch = match_batch(line)
        if batch and not product["batch_no"]:
            product["batch_no"] = batch
            tag("batch_no", idx)

        fssai = match_fssai(line)
        if fssai and not product["fssai_license_no"]:
            product["fssai_license_no"] = fssai
            tag("fssai_license_no", idx)

        if match_consumer_care(line):
            consumer_care_lines.append(line.strip())
            tag("consumer_care", idx)

        if match_manufacturer(line):
            manufacturer_lines.append(line.strip())
            tag("manufacturer_address", idx)

        origin = match_country_of_origin(line)
        if origin and not product["country_of_origin"]:
            product["country_of_origin"] = origin
            product["is_imported"] = True
            tag("country_of_origin", idx)

    # Fallback: fields split across a line break, searched on the joined text
    full_text = "\n".join(lines)

    if not product["net_quantity"]:
        q = match_quantity(full_text)
        if q:
            (product["net_quantity"], product["net_quantity_value_g_ml"],
             product["quantity_type"]) = q

    if not product["mrp"]:
        mrp = match_mrp(full_text)
        if mrp:
            product["mrp"], product["mrp_value"] = mrp

    if not product["mfg_date"]:
        mfg = match_mfg_date(full_text)
        if mfg:
            product["mfg_date"] = mfg

    if not product["best_before_or_expiry"]:
        exp = match_expiry(full_text)
        if exp:
            product["best_before_or_expiry"] = exp

    if not product["batch_no"]:
        batch = match_batch(full_text)
        if batch:
            product["batch_no"] = batch

    if not product["fssai_license_no"]:
        fssai = match_fssai(full_text)
        if fssai:
            product["fssai_license_no"] = fssai

    if not product["is_imported"]:
        product["is_imported"] = bool(re.search(
            r"imported by|country of origin|made in|product of",
            full_text, re.IGNORECASE
        ))

    product["consumer_care"] = ", ".join(dict.fromkeys(consumer_care_lines))
    product["manufacturer_address"] = " ".join(dict.fromkeys(manufacturer_lines))
    product["commodity_name"] = infer_commodity_name(lines, boxes, tagged)

    if product["commodity_name"]:
        for idx, line in enumerate(lines):
            if line.strip() == product["commodity_name"]:
                tag("commodity_name", idx)
                break

    valid_scores = []
    for s in scores:
        try:
            valid_scores.append(float(s))
        except (TypeError, ValueError):
            pass

    average_confidence = (
        sum(valid_scores) / len(valid_scores) if valid_scores else None
    )

    product["_ocr"] = {
        "text_count": len(lines),
        "average_confidence": average_confidence,
        "rec_texts": lines,
        "rec_scores": scores
    }

    # internal-only, popped by the caller before saving the contract json
    product["_field_line_indices"] = field_line_indices

>>>>>>> 85f71584a3767e7a750eda7a3739d57ad654866f
    return product