# -----------------------------
# OCR Module for Backend
# -----------------------------

import os
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "0"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

import json
import re
import traceback

from paddleocr import PaddleOCR

BASE_DIR = os.path.dirname(os.path.abspath(_file_))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
CONTRACT_PATH = os.path.join(OUTPUT_DIR, "product_contract.json")


def convert_to_dict(value):
    if value is None:
        return {}
    if callable(value):
        value = value()
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {"raw_value": value}
    if hasattr(value, "to_dict"):
        try:
            return value.to_dict()
        except Exception:
            pass
    try:
        return dict(value)
    except Exception:
        return {"raw_value": str(value)}


def find_ocr_data(data):
    if isinstance(data, dict):
        if "rec_texts" in data:
            return {
                "texts": data.get("rec_texts") or [],
                "scores": data.get("rec_scores") or [],
                "boxes": data.get("rec_polys") or data.get("dt_polys") or []
            }
        if "rec_text" in data:
            return {
                "texts": [data.get("rec_text", "")],
                "scores": [data.get("rec_score", 0.0)],
                "boxes": []
            }
        for v in data.values():
            found = find_ocr_data(v)
            if found["texts"]:
                return found
    elif isinstance(data, list):
        all_texts, all_scores, all_boxes = [], [], []
        for item in data:
            f = find_ocr_data(item)
            all_texts.extend(f["texts"])
            all_scores.extend(f["scores"])
            all_boxes.extend(f["boxes"])
        return {"texts": all_texts, "scores": all_scores, "boxes": all_boxes}
    return {"texts": [], "scores": [], "boxes": []}


def normalize_text(text):
    text = str(text)
    text = text.replace("|", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def join_lines_for_context(lines, window=4):
    chunks = []
    for i in range(len(lines)):
        chunks.append(" ".join(lines[i:i + window]))
    chunks.append(" ".join(lines))
    return chunks


def extract_quantity(text):
    m = re.search(r"\b(\d+(?:\.\d+)?)\s*(kg|kgs|g|gm|mg|l|ltr|litre|ml)\b", text, re.IGNORECASE)
    if not m:
        return "", None, ""
    value = float(m.group(1))
    unit = m.group(2).lower()
    if unit in {"kg", "kgs"}:
        nv = value * 1000
    elif unit in {"g", "gm"}:
        nv = value
    elif unit == "mg":
        nv = value / 1000
    elif unit in {"l", "ltr", "litre"}:
        nv = value * 1000
    else:
        nv = value
    return m.group(0), nv, "weight_or_volume"


def extract_mrp(context_chunks):
    pattern = re.compile(
        r"(?:mrp|m\.r\.p\.?)\s*[:\-]?\s*(?:₹|rs\.?|inr)?\s*\d+(?:\.\d{1,2})?",
        re.IGNORECASE
    )
    for chunk in context_chunks:
        m = pattern.search(chunk)
        if m:
            return m.group(0)
    return ""


def extract_mfg_date(context_chunks):
    pattern = re.compile(
        r"(?:mfg|mfd|manufactured|manufacturing|date\s*of\s*mfg).{0,40}?"
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}[/-]\d{2,4}|[A-Za-z]{3,9}\s+\d{4})",
        re.IGNORECASE
    )
    for chunk in context_chunks:
        m = pattern.search(chunk)
        if m:
            return m.group(1)
    return ""


def extract_consumer_care(lines):
    selected = []
    for line in lines:
        low = line.lower()
        if any(k in low for k in ["customer care", "consumer care", "helpline", "toll free"]):
            selected.append(line)
        elif "@" in line and "." in line:
            selected.append(line)
        elif re.search(r"\b1800[\d\s\-]{6,}\b", line):
            selected.append(line)
    return ", ".join(selected)


def extract_manufacturer(lines):
    selected = []
    for line in lines:
        low = line.lower()
        if any(k in low for k in [
            "manufactured by", "manufactured and marketed by", "marketed by",
            "packed by", "packer", "manufacturer", "mfd by", "mfg by"
        ]):
            selected.append(line)
    address_like = []
    for line in lines:
        if re.search(r"\b\d{5,6}\b", line) or re.search(
            r"new\s*delhi|delhi|uttarakhand|mumbai|pune|bangalore|kolkata|chennai",
            line, re.IGNORECASE
        ):
            address_like.append(line)
    raw = " ".join(selected + address_like)
    return re.sub(r"\s+", " ", raw).strip()


def extract_commodity_name(lines):
    ignored = [
        "mrp", "m.r.p", "net quantity", "manufactured", "manufacturing", "best before", "use by",
        "customer care", "consumer care", "batch", "ingredients", "barcode", "fssai",
        "imported", "country of origin", "made in", "product of", "lot no", "mfd", "mfg",
        "declaration", "packed by", "packer", "manufacturer"
    ]
    candidates = []
    for line in lines:
        line = line.strip()
        if len(line) < 3 or len(line) > 80:
            continue
        low = line.lower()
        if any(w in low for w in ignored):
            continue
        alpha_ratio = sum(c.isalpha() or c.isspace() for c in line) / max(len(line), 1)
        if alpha_ratio < 0.6:
            continue
        if line.count(",") > 2:
            continue
        candidates.append((alpha_ratio, -len(line), line))
    if not candidates:
        return ""
    candidates.sort(reverse=True)
    return candidates[0][2]


def create_product_contract(lines, scores, boxes):
    full_text = " ".join(lines)
    context_chunks = join_lines_for_context(lines, window=4)

    net_quantity, quantity_value, quantity_type = extract_quantity(full_text)
    imported = bool(re.search(r"imported by|country of origin|made in|product of", full_text, re.IGNORECASE))
    country_of_origin = ""
    origin_m = re.search(r"(?:country of origin|made in|product of)\s*[:\-]?\s*([^\n]+)", full_text, re.IGNORECASE)
    if origin_m:
        country_of_origin = origin_m.group(1).strip()

    return {
        "manufacturer_address": extract_manufacturer(lines),
        "commodity_name": extract_commodity_name(lines),
        "net_quantity": net_quantity,
        "net_quantity_value_g_ml": quantity_value,
        "quantity_type": quantity_type,
        "mrp": extract_mrp(context_chunks),
        "mrp_value": None,
        "mfg_date": extract_mfg_date(context_chunks),
        "best_before_or_expiry": "",
        "batch_no": "",
        "fssai_license_no": "",
        "consumer_care": extract_consumer_care(lines),
        "is_imported": imported,
        "country_of_origin": country_of_origin,
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
        "contrast_ok": {},
        "raw_ocr_text": full_text,
        "ocr_lines": lines,
        "ocr_scores": scores,
        "ocr_boxes": boxes
    }


def run_ocr(image_path):
    print("Starting OCR...")
    print("Image path:", image_path)
    print("Image exists:", os.path.exists(image_path))

    if not os.path.exists(image_path):
        raise FileNotFoundError("Image file was not found: " + image_path)

    try:
        ocr = PaddleOCR(
            lang="en",
            device="cpu",
            enable_mkldnn=False,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False
        )

        try:
            results = ocr.predict(image_path)
        except Exception:
            results = ocr.ocr(image_path)

        all_lines, all_scores, all_boxes = [], [], []

        for result in results:
            raw_data = getattr(result, "json", None)
            if callable(raw_data):
                try:
                    raw_data = raw_data()
                except Exception:
                    raw_data = None
            data = convert_to_dict(raw_data)
            ocr_data = data.get("res") if "res" in data else data
            extracted = find_ocr_data(ocr_data)

            for text in extracted["texts"]:
                text = normalize_text(text)
                if text:
                    all_lines.append(text)
            all_scores.extend(extracted["scores"])
            all_boxes.extend(extracted["boxes"])

        if not all_lines:
            raise ValueError("NO TEXT FOUND IN THE IMAGE.")

        product = create_product_contract(all_lines, all_scores, all_boxes)

        with open(CONTRACT_PATH, "w", encoding="utf-8") as f:
            json.dump(product, f, indent=2, ensure_ascii=False, default=str)

        print("\nOCR completed successfully.")
        return product

    except Exception:
        print("\nOCR ERROR:")
        traceback.print_exc()
        raise


def main():
    test_image_path = os.path.join(os.path.dirname(_file_), "sample_label.jpg")
    if not os.path.exists(test_image_path):
        print("ERROR: sample_label.jpg was not found.")
        return
    try:
        product = run_ocr(test_image_path)
        print(json.dumps(product, indent=2, ensure_ascii=False, default=str))
    except Exception:
        traceback.print_exc()


if _name_ == "_main_":
    main()
