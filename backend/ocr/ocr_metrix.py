<<<<<<< HEAD
# -----------------------------
# OCR Module for Backend
# -----------------------------

import os

# PaddlePaddle compatibility
os.environ["FLAGS_enable_pir_api"] = "0"

import json
import traceback

from paddleocr import PaddleOCR


# -----------------------------
# Output paths
# -----------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CONTRACT_PATH = os.path.join(
    OUTPUT_DIR,
    "product_contract.json"
)


# -----------------------------
# Convert PaddleOCR result
# -----------------------------

def convert_to_dict(obj):

    if obj is None:
        return {}

    if isinstance(obj, dict):
        return obj

    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict()
        except Exception:
            pass

    if hasattr(obj, "__dict__"):
        try:
            return obj.__dict__
        except Exception:
            pass

    if isinstance(obj, str):
        try:
            return json.loads(obj)
        except Exception:
            return {}

    return {}


# -----------------------------
# Extract OCR data
# -----------------------------

def find_ocr_data(data):

    texts = []
    scores = []
    boxes = []

    if not isinstance(data, dict):
        return {
            "texts": texts,
            "scores": scores,
            "boxes": boxes
        }

    # Text
    for key in ["rec_texts", "texts"]:
        if key in data and isinstance(data[key], list):
            texts = data[key]
            break

    # Confidence scores
    for key in ["rec_scores", "scores"]:
        if key in data and isinstance(data[key], list):
            scores = data[key]
            break

    # Bounding boxes
    for key in ["rec_boxes", "dt_polys", "boxes"]:
        if key in data and isinstance(data[key], list):
            boxes = data[key]
            break

    return {
        "texts": texts,
        "scores": scores,
        "boxes": boxes
    }


# -----------------------------
# Normalize OCR text
# -----------------------------

def normalize_text(text):

    if text is None:
        return ""

    text = str(text)

    text = text.replace("\n", " ")
    text = text.replace("\r", " ")

    # Remove excessive spaces
    text = " ".join(text.split())

    return text.strip()


# -----------------------------
# Build product contract
# -----------------------------

def create_product_contract(
    lines,
    scores,
    boxes
):

    full_text = " ".join(lines)

    product = {
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
        "contrast_ok": {},
        "raw_ocr_text": full_text,
        "ocr_lines": lines,
        "ocr_scores": scores,
        "ocr_boxes": boxes
    }

    # Basic extraction
    for line in lines:

        lower = line.lower()

        if "mrp" in lower:
            product["mrp"] = line

        elif (
            "net qty" in lower
            or "net quantity" in lower
            or "net wt" in lower
            or "net weight" in lower
        ):
            product["net_quantity"] = line

        elif (
            "mfg" in lower
            or "mfd" in lower
            or "manufacturing" in lower
        ):
            product["mfg_date"] = line

        elif (
            "consumer care" in lower
            or "customer care" in lower
            or "helpline" in lower
            or "toll free" in lower
        ):
            product["consumer_care"] = line

        elif "fssai" in lower:
            product["fssai_license_no"] = line

        elif (
            "batch" in lower
            or "lot no" in lower
            or "lot number" in lower
        ):
            product["batch_no"] = line

        elif (
            "manufactured by" in lower
            or "manufactured at" in lower
            or "marketed by" in lower
        ):
            product["manufacturer_address"] = line

    # Commodity name
    for line in lines:

        lower = line.lower()

        if len(line.strip()) >= 3 and not any(
            keyword in lower
            for keyword in [
                "mrp",
                "mfg",
                "mfd",
                "manufactur",
                "net qty",
                "net quantity",
                "net weight",
                "batch",
                "fssai",
                "customer care",
                "consumer care"
            ]
        ):
            product["commodity_name"] = line
            break

    # Quantity extraction
    import re

    quantity_pattern = re.compile(
        r"(\d+(?:\.\d+)?)\s*"
        r"(kg|g|gm|gram|grams|mg|l|ml|litre|liter|litres|liters)",
        re.IGNORECASE
    )

    for line in lines:

        match = quantity_pattern.search(line)

        if match:

            value = float(match.group(1))
            unit = match.group(2).lower()

            if unit == "kg":
                value = value * 1000

            product["net_quantity_value_g_ml"] = value
            product["quantity_type"] = "weight_or_volume"

            if not product["net_quantity"]:
                product["net_quantity"] = line

            break

    # MRP value
    mrp_pattern = re.compile(
        r"(?:mrp|m\.r\.p\.?)\s*[:\-]?\s*"
        r"(?:rs\.?|₹)?\s*(\d+(?:\.\d+)?)",
        re.IGNORECASE
    )

    for line in lines:

        match = mrp_pattern.search(line)

        if match:

            product["mrp_value"] = float(match.group(1))
            product["mrp"] = line
            break

    # Imported product
    for line in lines:

        lower = line.lower()

        if (
            "imported" in lower
            or "country of origin" in lower
            or "made in" in lower
        ):

            product["is_imported"] = True

            if "country of origin" in lower:
                product["country_of_origin"] = line

            break

    return product


# -----------------------------
# Backend OCR function
# -----------------------------

def run_ocr(image_path):

    print("Starting OCR...")
    print("Image path:", image_path)
    print("Image exists:", os.path.exists(image_path))

    if not os.path.exists(image_path):

        raise FileNotFoundError(
            "Image file was not found: " + image_path
        )

    try:

        print("\nLoading PaddleOCR model...")

        ocr = PaddleOCR(
            lang="en",
            device="cpu",
            enable_mkldnn=False,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False
        )

        print("Model loaded.")
        print("Running prediction...\n")

        try:

            results = ocr.predict(image_path)

        except Exception:

            results = ocr.ocr(image_path)

        all_lines = []
        all_scores = []
        all_boxes = []

        for result in results:

            raw_data = getattr(
                result,
                "json",
                None
            )

            if callable(raw_data):

                try:
                    raw_data = raw_data()
                except Exception:
                    raw_data = None

            data = convert_to_dict(raw_data)

            if "res" in data:
                ocr_data = data["res"]
            else:
                ocr_data = data

            extracted = find_ocr_data(
                ocr_data
            )

            for text in extracted["texts"]:

                text = normalize_text(text)

                if text:
                    all_lines.append(text)

            all_scores.extend(
                extracted["scores"]
            )

            all_boxes.extend(
                extracted["boxes"]
            )

        if not all_lines:

            raise ValueError(
                "NO TEXT FOUND IN THE IMAGE."
            )

        product = create_product_contract(
            all_lines,
            all_scores,
            all_boxes
        )

        with open(
            CONTRACT_PATH,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                product,
                f,
                indent=2,
                ensure_ascii=False,
                default=str
            )

        print("\nOCR completed successfully.")

        return product

    except Exception:

        print("\nOCR ERROR:")
        traceback.print_exc()

        raise


# -----------------------------
# Standalone testing
# -----------------------------

def main():

    print("Starting OCR test...")

    test_image_path = os.path.join(
        os.path.dirname(__file__),
        "sample_label.jpg"
    )

    print(
        "Image path:",
        test_image_path
    )

    if not os.path.exists(
        test_image_path
    ):

        print(
            "\nERROR: sample_label.jpg was not found."
        )

        return

    try:

        product = run_ocr(
            test_image_path
        )

        print(
            "\n========== PRODUCT CONTRACT =========="
        )

        print(
            json.dumps(
                product,
                indent=2,
                ensure_ascii=False,
                default=str
            )
        )

        print(
            "\nProduct contract saved to:"
        )

        print(
            CONTRACT_PATH
        )

    except Exception:

        print(
            "\nOCR ERROR:"
        )

        traceback.print_exc()


if __name__ == "__main__":

    main()
   
=======
# -*- coding: utf-8 -*-
import os
import json
import re
import sys
import traceback

# Must be set before importing PaddleOCR
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "0"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

from paddleocr import PaddleOCR

# -----------------------------
# Paths
# -----------------------------
IMAGE_PATH = r"D:\yanshi\sih\sample_label.jpg"
OUTPUT_DIR = r"D:\yanshi\sih\output"
CONTRACT_PATH = os.path.join(OUTPUT_DIR, "product_contract.json")
LAYOUT_IMG_PATH = os.path.join(OUTPUT_DIR, "layout_annotated.png")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Force UTF-8 on Windows console
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# -----------------------------
# Helpers
# -----------------------------
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

def join_lines_for_context(lines, window=3):
    """
    Create overlapping joined strings so regex can match across line breaks.
    Each chunk is up to `window` consecutive lines joined with space.
    """
    chunks = []
    for i in range(len(lines)):
        chunk = " ".join(lines[i:i+window])
        chunks.append(chunk)
    # Also add the full text as one chunk
    chunks.append(" ".join(lines))
    return chunks

# -----------------------------
# Field extraction (improved)
# -----------------------------
def extract_quantity(text):
    m = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(kg|kgs|g|gm|mg|l|ltr|litre|ml)\b",
        text,
        re.IGNORECASE
    )
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
    """
    Search across joined line chunks for MRP patterns.
    Handles: [MRP incl. of all taxes: 55", "MRP Rs. 55", etc.
    """
    # Pattern that allows value on same or next "word" after MRP label
    pattern = re.compile(
        r"(?:mrp|m\.r\.p\.?|\[\s*mrp)\s*[:\-]?\s*"
        r"(?:₹|rs\.?|inr)?\s*"
        r"\d+(?:\.\d{1,2})?"
        r"(?:\s*$$.*?$$)?",
        re.IGNORECASE
    )

    for chunk in context_chunks:
        m = pattern.search(chunk)
        if m:
            return m.group(0)
    return ""

def extract_mfg_date(context_chunks):
    """
    Search across joined chunks for MFD/MFG + date.
    Handles 'Lot No. - MFD.-USE BY: 08/2026' split across lines.
    """
    pattern = re.compile(
        r"(?:mfg|mfd|manufactured|manufacturing|date\s*of\s*mfg).{0,40}?"
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
        r"|\d{1,2}[/-]\d{2,4}"
        r"|[A-Za-z]{3,9}\s+\d{4})",
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
        elif re.search(r"\b\d{10}\b", line) and any(k in low for k in ["care", "contact", "call"]):
            selected.append(line)
    return ", ".join(selected)

def extract_manufacturer(lines):
    selected = []
    for line in lines:
        low = line.lower()
        if any(k in low for k in [
            "manufactured by",
            "manufactured and marketed by",
            "marketed by",
            "packed by",
            "packer",
            "manufacturer",
            "mfd by",
            "mfg by",
            "mig by"
        ]):
            # Clean obvious OCR garbage but keep address-like parts
            cleaned = re.sub(r"\bldia\b", "India", line, flags=re.IGNORECASE)
            cleaned = re.sub(r"\bHesle\b", "Nestle", cleaned, flags=re.IGNORECASE)
            selected.append(cleaned)

    address_like = []
    for line in lines:
        if re.search(r"\b\d{5,6}\b", line) or re.search(
            r"new\s*delhi|delhi|uttarakhand|mumbai|pune|bangalore|kolkata|chennai",
            line, re.IGNORECASE
        ):
            address_like.append(line)

    raw = " ".join(selected + address_like)
    # Remove duplicate spaces and trim
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw

def extract_commodity_name(lines):
    ignored = [
        "mrp","m.r.p","net quantity","manufactured","manufacturing","best before","use by",
        "customer care","consumer care","batch","ingredients","barcode","fssai",
        "imported","country of origin","made in","product of","lot no","mfd","mfg",
        "declaration","packed by","packer","manufacturer"
    ]

    candidates = []
    for line in lines:
        line = line.strip()
        if len(line) < 3 or len(line) > 80:
            continue
        low = line.lower()
        if any(w in low for w in ignored):
            continue
        # Prefer mostly alphabetic lines (allow some digits for brand codes)
        alpha_ratio = sum(c.isalpha() or c.isspace() for c in line) / max(len(line), 1)
        if alpha_ratio < 0.6:
            continue
        # Penalize lines with many commas or weird symbols
        if line.count(",") > 2:
            continue
        candidates.append((alpha_ratio, -len(line), line))

    if not candidates:
        return ""

    # Sort by higher alpha_ratio, then shorter length
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

    contract = {
        "manufacturer_address": extract_manufacturer(lines),
        "commodity_name": extract_commodity_name(lines),
        "net_quantity": net_quantity,
        "net_quantity_value_g_ml": quantity_value,
        "quantity_type": quantity_type,
        "mrp": extract_mrp(context_chunks),
        "mfg_date": extract_mfg_date(context_chunks),
        "consumer_care": extract_consumer_care(lines),
        "is_imported": imported,
        "buyer_type": "retail",
        "category": "packaged_food",
        "font_heights_mm": {},
        "is_embossed": False,
        "letter_width_height_ratios": {},
        "detected_language": "en",
        "country_of_origin": country_of_origin,
        "pdp_area_cm2": None,
        "pdp_box": None,
        "declaration_boxes": {},
        "nearest_other_text_distance_mm": {},
        "body_text_height_mm": None,
        "contrast_ok": {}
    }
    return contract

def draw_layout_and_save(image_path, boxes, texts, out_path):
    try:
        import cv2
        import numpy as np
    except Exception:
        print("OpenCV not available; skipping layout image generation.")
        return

    img = cv2.imread(image_path)
    if img is None:
        print("Could not read image for layout drawing.")
        return

    for i, (box, text) in enumerate(zip(boxes, texts)):
        pts = np.array(box, dtype="int32")
        cv2.polylines(img, [pts], isClosed=True, color=(0, 255, 0), thickness=2)

        x_min = min(p[0] for p in pts)
        y_min = min(p[1] for p in pts)
        label = text[:40]
        cv2.putText(
            img, label, (x_min, max(0, y_min - 5)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1
        )

    cv2.imwrite(out_path, img)

# -----------------------------
# Main
# -----------------------------
def main():
    print("Starting OCR...")
    print("Image path:", IMAGE_PATH)
    print("Image exists:", os.path.exists(IMAGE_PATH))

    if not os.path.exists(IMAGE_PATH):
        print("\nERROR: Image file was not found.")
        print("Change IMAGE_PATH at the top of this file.")
        input("\nPress Enter to close...")
        return

    try:
        print("\nLoading PaddleOCR model...")
        ocr = PaddleOCR(
            lang="en",
            device="cpu",
            enable_mkldnn=False,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False
        )
        print("Model loaded.")
        print("Running prediction...\n")

        try:
            results = ocr.predict(IMAGE_PATH)
        except Exception:
            results = ocr.ocr(IMAGE_PATH)

        all_lines, all_scores, all_boxes = [], [], []

        for result in results:
            raw_data = getattr(result, "json", None)
            data = convert_to_dict(raw_data)
            ocr_data = data.get("res") if "res" in data else data
            extracted = find_ocr_data(ocr_data)

            lines = [normalize_text(t) for t in extracted["texts"] if normalize_text(t)]
            scores = extracted["scores"]
            boxes = extracted["boxes"]

            all_lines.extend(lines)
            all_scores.extend(scores)
            all_boxes.extend(boxes)

        if not all_lines:
            print("NO TEXT FOUND IN THE IMAGE.")
            input("\nPress Enter to close...")
            return

        draw_layout_and_save(IMAGE_PATH, all_boxes, all_lines, LAYOUT_IMG_PATH)
        print("\nLayout image saved to:", LAYOUT_IMG_PATH)

        product = create_product_contract(all_lines, all_scores, all_boxes)

        with open(CONTRACT_PATH, "w", encoding="utf-8") as f:
            json.dump(product, f, indent=2, ensure_ascii=False, default=str)

        print("\n========== PRODUCT CONTRACT ==========")
        print(json.dumps(product, indent=2, ensure_ascii=False, default=str))
        print("\nSaved files:")
        print(CONTRACT_PATH)
        print(LAYOUT_IMG_PATH)

    except Exception:
        print("\nOCR ERROR:")
        traceback.print_exc()

    input("\nPress Enter to close...")

if __name__ == "__main__":
    main()
>>>>>>> 85f71584a3767e7a750eda7a3739d57ad654866f
