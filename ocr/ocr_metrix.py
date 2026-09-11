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
   