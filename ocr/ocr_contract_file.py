import re
from typing import Any


def empty_product() -> dict[str, Any]:
    return {
        "manufacturer_address": "",
        "commodity_name": "",
        "net_quantity": "",
        "net_quantity_value_g_ml": None,
        "quantity_type": "",
        "mrp": "",
        "mfg_date": "",
        "consumer_care": "",
        "is_imported": False,
        "buyer_type": "retail",
        "category": "packaged_food",
        "font_heights_mm": {},
        "is_embossed": False,
        "letter_width_height_ratios": {},
        "detected_language": "en",

        "country_of_origin": "",
        "pdp_area_cm2": None,
        "pdp_box": None,
        "declaration_boxes": {},
        "nearest_other_text_distance_mm": {},
        "body_text_height_mm": None,
        "contrast_ok": {}
    }


def normalize_text(text: str) -> str:
    text = text.replace("|", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def extract_quantity(text: str):
    pattern = r"\b(\d+(?:\.\d+)?)\s*(kg|kgs|g|gm|mg|l|ltr|litre|ml)\b"
    match = re.search(pattern, text, re.IGNORECASE)

    if not match:
        return "", None, ""

    value = float(match.group(1))
    unit = match.group(2).lower()

    if unit in {"kg", "kgs"}:
        normalized = value * 1000
        quantity_type = "weight_or_volume"
    elif unit in {"g", "gm"}:
        normalized = value
        quantity_type = "weight_or_volume"
    elif unit == "mg":
        normalized = value / 1000
        quantity_type = "weight_or_volume"
    elif unit in {"l", "ltr", "litre"}:
        normalized = value * 1000
        quantity_type = "weight_or_volume"
    else:
        normalized = value
        quantity_type = "weight_or_volume"

    return match.group(0), normalized, quantity_type


def extract_product_fields(text: str) -> dict[str, Any]:
    product = empty_product()
    text = normalize_text(text)
    lower_text = text.lower()

    product["net_quantity"], product["net_quantity_value_g_ml"], \
        product["quantity_type"] = extract_quantity(text)

    mrp = re.search(
        r"(?:mrp|m\.r\.p\.?)\s*[:\-]?\s*(?:₹|rs\.?|inr)?\s*"
        r"[0-9]+(?:\.[0-9]{1,2})?(?:\s*\(.*?\))?",
        text,
        re.IGNORECASE
    )

    if mrp:
        product["mrp"] = mrp.group(0)

    mfg_date = re.search(
        r"(?:mfg|mfd|manufactured|manufacturing|date of mfg)"
        r".{0,20}?\b([0-9]{1,2}[/-][0-9]{2,4}|"
        r"[0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4}|"
        r"[A-Za-z]{3,9}\s+[0-9]{4})\b",
        text,
        re.IGNORECASE
    )

    if mfg_date:
        product["mfg_date"] = mfg_date.group(1)

    care_lines = []

    for line in text.splitlines():
        line_lower = line.lower()

        if (
            "customer care" in line_lower
            or "consumer care" in line_lower
            or "helpline" in line_lower
            or "toll free" in line_lower
            or "@" in line
            or re.search(r"\b1800[-\d ]{6,}\b", line)
        ):
            care_lines.append(line.strip())

    product["consumer_care"] = ", ".join(care_lines)

    imported_words = [
        "imported by",
        "country of origin",
        "made in",
        "product of"
    ]

    product["is_imported"] = any(
        word in lower_text for word in imported_words
    )

    if product["is_imported"]:
        origin = re.search(
            r"(?:country of origin|made in|product of)\s*[:\-]?\s*([^\n]+)",
            text,
            re.IGNORECASE
        )
        if origin:
            product["country_of_origin"] = origin.group(1).strip()

    manufacturer_lines = []

    for line in text.splitlines():
        line_lower = line.lower()

        if any(keyword in line_lower for keyword in [
            "manufactured by",
            "manufactured",
            "marketed by",
            "packed by",
            "manufactured and marketed"
        ]):
            manufacturer_lines.append(line.strip())

    product["manufacturer_address"] = " ".join(manufacturer_lines)

    product["commodity_name"] = infer_commodity_name(text)

    return product


def infer_commodity_name(text: str) -> str:
    ignored_words = [
        "mrp",
        "net quantity",
        "manufactured",
        "manufacturing",
        "best before",
        "use by",
        "customer care",
        "consumer care",
        "batch",
        "ingredients"
    ]

    for line in text.splitlines():
        clean_line = line.strip()

        if not clean_line:
            continue

        if len(clean_line) < 3 or len(clean_line) > 80:
            continue

        if any(word in clean_line.lower() for word in ignored_words):
            continue

        if not re.search(r"\d", clean_line):
            return clean_line

    return ""