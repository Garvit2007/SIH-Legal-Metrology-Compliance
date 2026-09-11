import os
import json
import re
import cv2
from paddleocr import PaddleOCR


# ============================================================
# CONFIG
# ============================================================

IMAGE_PATH = r"D:\yanshi\sih\sample_label.jpg"
OUTPUT_DIR = r"D:\yanshi\sih\output"

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
# EMPTY CONTRACT
# ============================================================

def empty_contract():
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

        # Optional fields
        "country_of_origin": "",
        "pdp_area_cm2": None,
        "pdp_box": None,
        "declaration_boxes": {},
        "nearest_other_text_distance_mm": {},
        "body_text_height_mm": None,
        "contrast_ok": {}
    }


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def clean_text(text):
    text = str(text)
    text = text.replace("|", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


# ============================================================
# QUANTITY
# ============================================================

def extract_quantity(text):

    pattern = (
        r"\b"
        r"(\d+(?:\.\d+)?)"
        r"\s*"
        r"(kg|kgs|g|gm|mg|l|ltr|litre|ml)"
        r"\b"
    )

    match = re.search(
        pattern,
        text,
        re.IGNORECASE
    )

    if not match:
        return "", None, ""

    value = float(match.group(1))
    unit = match.group(2).lower()

    if unit in ("kg", "kgs"):
        normalized = value * 1000

    elif unit in ("g", "gm"):
        normalized = value

    elif unit == "mg":
        normalized = value / 1000

    elif unit in ("l", "ltr", "litre"):
        normalized = value * 1000

    else:
        normalized = value

    return (
        match.group(0),
        normalized,
        "weight_or_volume"
    )


# ============================================================
# MRP
# ============================================================

def extract_mrp(text):

    pattern = (
        r"(?:mrp|m\.r\.p\.?)"
        r"\s*[:\-]?\s*"
        r"(?:₹|rs\.?|inr)?"
        r"\s*"
        r"\d+(?:\.\d{1,2})?"
        r"(?:\s*\(.*?\))?"
    )

    match = re.search(
        pattern,
        text,
        re.IGNORECASE
    )

    return match.group(0).strip() if match else ""


# ============================================================
# MANUFACTURER
# ============================================================

def extract_manufacturer(lines):

    keywords = [
        "manufactured by",
        "manufactured and marketed by",
        "marketed by",
        "packed by",
        "packer",
        "manufacturer"
    ]

    found = []

    for line in lines:

        lower = line.lower()

        if any(keyword in lower for keyword in keywords):
            found.append(line.strip())

    return " ".join(found)


# ============================================================
# MANUFACTURING DATE
# ============================================================

def extract_mfg_date(text):

    pattern = (
        r"(?:mfg|mfd|manufactured|manufacturing|date\s*of\s*mfg)"
        r".{0,25}?"
        r"("
        r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
        r"|"
        r"\d{1,2}[/-]\d{2,4}"
        r"|"
        r"[A-Za-z]{3,9}\s+\d{4}"
        r")"
    )

    match = re.search(
        pattern,
        text,
        re.IGNORECASE
    )

    return match.group(1).strip() if match else ""


# ============================================================
# CONSUMER CARE
# ============================================================

def extract_consumer_care(lines):

    found = []

    for line in lines:

        lower = line.lower()

        if (
            "customer care" in lower
            or "consumer care" in lower
            or "helpline" in lower
            or "toll free" in lower
            or "email" in lower
            or "@" in line
            or re.search(r"\b1800[\d\s\-]{6,}\b", line)
        ):
            found.append(line.strip())

    return ", ".join(found)


# ============================================================
# IMPORT / COUNTRY OF ORIGIN
# ============================================================

def extract_import_information(text):

    imported = bool(
        re.search(
            r"imported by|country of origin|made in|product of",
            text,
            re.IGNORECASE
        )
    )

    country = ""

    if imported:

        match = re.search(
            r"(?:country of origin|made in|product of)"
            r"\s*[:\-]?\s*([^\n]+)",
            text,
            re.IGNORECASE
        )

        if match:
            country = match.group(1).strip()

    return imported, country


# ============================================================
# COMMODITY NAME
# ============================================================

def extract_commodity_name(lines):

    ignored = [
        "mrp",
        "m.r.p",
        "net quantity",
        "net wt",
        "manufactured",
        "manufacturing",
        "manufactured by",
        "marketed by",
        "packed by",
        "best before",
        "use by",
        "customer care",
        "consumer care",
        "batch",
        "ingredients",
        "barcode",
        "fssai",
        "country of origin",
        "made in",
        "imported by"
    ]

    # First try short clean text lines
    for line in lines:

        line = line.strip()
        lower = line.lower()

        if len(line) < 3:
            continue

        if len(line) > 100:
            continue

        if any(word in lower for word in ignored):
            continue

        # Skip lines containing numbers
        if re.search(r"\d", line):
            continue

        # Skip obvious contact/email text
        if "@" in line:
            continue

        return line

    return ""


# ============================================================
# BUILD CONTRACT
# ============================================================

def build_contract(lines, boxes):

    contract = empty_contract()

    full_text = "\n".join(lines)

    # Quantity
    (
        contract["net_quantity"],
        contract["net_quantity_value_g_ml"],
        contract["quantity_type"]
    ) = extract_quantity(full_text)

    # MRP
    contract["mrp"] = extract_mrp(full_text)

    # Manufacturing date
    contract["mfg_date"] = extract_mfg_date(full_text)

    # Manufacturer
    contract["manufacturer_address"] = extract_manufacturer(lines)

    # Consumer care
    contract["consumer_care"] = extract_consumer_care(lines)

    # Commodity
    contract["commodity_name"] = extract_commodity_name(lines)

    # Import
    (
        contract["is_imported"],
        contract["country_of_origin"]
    ) = extract_import_information(full_text)

    return contract


# ============================================================
# DRAW OCR LAYOUT
# ============================================================

def create_layout_image(image_path, lines, boxes):

    image = cv2.imread(image_path)

    if image is None:
        print("Could not load image for layout drawing.")
        return

    for text, box in zip(lines, boxes):

        try:

            points = []

            for point in box:
                x = int(point[0])
                y = int(point[1])
                points.append((x, y))

            # Draw OCR bounding box
            cv2.polylines(
                image,
                [__import__("numpy").array(points)],
                True,
                (0, 255, 0),
                2
            )

            # Text label
            x, y = points[0]

            cv2.putText(
                image,
                text[:40],
                (x, max(y - 5, 15)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
                cv2.LINE_AA
            )

        except Exception:
            continue

    output_path = os.path.join(
        OUTPUT_DIR,
        "annotated_layout.jpg"
    )

    cv2.imwrite(
        output_path,
        image
    )

    print("Layout saved:", output_path)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("SIH PACKAGED COMMODITY OCR")
    print("=" * 60)

    if not os.path.exists(IMAGE_PATH):

        print("\nERROR:")
        print("Image not found:")
        print(IMAGE_PATH)
        return

    # --------------------------------------------------------
    # LOAD OCR
    # --------------------------------------------------------

    print("\nLoading PaddleOCR...")

    ocr = PaddleOCR(
        lang="en",
        device="cpu",
        enable_mkldnn=False,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False
    )

    print("PaddleOCR loaded.")

    # --------------------------------------------------------
    # OCR
    # --------------------------------------------------------

    print("\nRunning OCR...")

    results = ocr.predict(IMAGE_PATH)

    lines = []
    scores = []
    boxes = []

    # --------------------------------------------------------
    # READ OCR RESULT
    # --------------------------------------------------------

    for result in results:

        data = result.json

        if isinstance(data, str):
            data = json.loads(data)

        if not isinstance(data, dict):
            continue

        texts = data.get("rec_texts", [])
        result_scores = data.get("rec_scores", [])
        result_boxes = (
            data.get("rec_polys", [])
            or data.get("dt_polys", [])
        )

        for i, text in enumerate(texts):

            text = clean_text(text)

            if not text:
                continue

            lines.append(text)

            if i < len(result_scores):
                scores.append(float(result_scores[i]))
            else:
                scores.append(0.0)

            if i < len(result_boxes):
                boxes.append(result_boxes[i])
            else:
                boxes.append([])

    # --------------------------------------------------------
    # DISPLAY OCR
    # --------------------------------------------------------

    print("\n========== DETECTED TEXT ==========")

    for i, text in enumerate(lines):

        score = scores[i]

        print(
            f"{i + 1:02d}. "
            f"{text} "
            f"[{score:.2f}]"
        )

    # --------------------------------------------------------
    # BUILD CONTRACT
    # --------------------------------------------------------

    print("\nCreating product contract...")

    contract = build_contract(
        lines,
        boxes
    )

    # --------------------------------------------------------
    # SAVE CONTRACT
    # --------------------------------------------------------

    contract_path = os.path.join(
        OUTPUT_DIR,
        "product_contract.json"
    )

    with open(
        contract_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            contract,
            f,
            indent=2,
            ensure_ascii=False
        )

    # --------------------------------------------------------
    # CREATE LAYOUT IMAGE
    # --------------------------------------------------------

    create_layout_image(
        IMAGE_PATH,
        lines,
        boxes
    )

    # --------------------------------------------------------
    # FINAL OUTPUT
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print("PRODUCT CONTRACT")
    print("=" * 60)

    print(
        json.dumps(
            contract,
            indent=2,
            ensure_ascii=False
        )
    )

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)

    print("\nFiles created:")

    print(
        os.path.join(
            OUTPUT_DIR,
            "product_contract.json"
        )
    )

    print(
        os.path.join(
            OUTPUT_DIR,
            "annotated_layout.jpg"
        )
    )


if __name__ == "__main__":
    main()