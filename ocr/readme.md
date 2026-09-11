Core Python packages
Install globally (or in a venv) with:

bash
pip install paddlepaddle paddleocr opencv-python

D:\yanshi\sih
│
├─ ocr_metrix.py              # Main OCR + contract generation script
├─ sample_label.jpg           # Example input image
├─ rules.json                 # Static Legal Metrology rules config
├─ rule_engine.py             # Rule engine that uses rules.json + product_contract.json
│
└─ output
   ├─ product_contract.json   # JSON consumed by rule_engine.py
   └─ layout_annotated.png    # Image with OCR boxes & text

4. Connecting to the Rule Engine
You already have:

rules.json – the big JSON with:

meta

scope_exclusions

exemptions

mandatory_declarations

font_and_placement_rules

language_rule

rule_engine.py – code that:

Loads rules.json.

Loads a product contract JSON.

Evaluates each rule against the product fields.

Expected call pattern
Typical CLI usage:

bash
python rule_engine.py rules.json output\product_contract.json
Or in Python:

python
import json
from rule_engine import run_checks  # example name; adjust to your actual API

with open("rules.json", "r", encoding="utf-8") as f:
    rules = json.load(f)

with open(r"output\product_contract.json", "r", encoding="utf-8") as f:
    product = json.load(f)

results = run_checks(rules, product)
print(results)
Key point:
Do not modify rules.json from the OCR script.
OCR only produces product_contract.json. The rule engine combines both.

5. Backend Integration Overview
For a web/API backend (FastAPI, Flask, Django, etc.), the flow is:

Frontend / client uploads a label image (e.g., via POST /upload).

Backend:

Saves the image to a temp path, e.g. tmp/<uuid>.jpg.

Calls the OCR pipeline (either by importing functions from ocr_metrix.py or by invoking it as a subprocess).

Gets product_contract.json (as a Python dict).

Backend loads rules.json once at startup (or caches it).

Backend calls rule_engine.run_checks(rules, product_contract) and gets:

Pass/fail per rule.

Severity (critical/major/minor).

Messages for violations.

Backend returns a structured response, e.g.:

json
{
  "status": "non_compliant",
  "violations": [
    {
      "id": "MRP",
      "rule_ref": "Rule 6(1)(e), Rule 2(m)",
      "severity": "critical",
      "message": "MRP missing, or not declared as 'MRP Rs.___ inclusive of all taxes'."
    }
  ],
  "product_contract": { ... }
}
Recommended design
Move core logic from ocr_metrix.py into reusable functions, e.g.:

python
# ocr_engine.py
def run_ocr_and_build_contract(image_path: str) -> dict:
    ...
    return product_contract
In your backend:

python
from ocr_engine import run_ocr_and_build_contract
from rule_engine import run_checks
import json

RULES = json.load(open("rules.json", "r", encoding="utf-8"))

def process_label(image_path: str):
    product = run_ocr_and_build_contract(image_path)
    results = run_checks(RULES, product)
    return {
        "product_contract": product,
        "compliance": results
    }
This keeps OCR, rule evaluation, and HTTP handling cleanly separated.

6. Image Pre-processing (Current & Future)
Current MVP
Uses raw image as-is.

PaddleOCR runs with:

lang="en"

CPU

MKL-DNN disabled (to avoid the oneDNN crash).

Works best when:

The declaration panel is clearly visible.

Text is not too small or heavily distorted.

Recommended improvements (fast wins)
All of these can be added without changing the rule engine or JSON schema.

6.1. Crop the declaration panel
Instead of OCR’ing the full package:

Crop the side panel that contains:

MRP

Net quantity

Manufacturing date

Manufacturer address

Consumer care

Then run OCR on the crop.

Benefits:

Less noise (no decorative text, logos, recipes).

Better recognition of small declaration text.

Implementation options:

Fixed crop coordinates (if your capture setup is controlled).

Simple UI/tool to let a user draw a rectangle once per package type, then reuse those coordinates.

Later: auto-detect the declaration panel using heuristics or a small detection model.

You can add a helper in ocr_metrix.py:

python
def crop_and_ocr(image_path, x, y, w, h):
    import cv2
    img = cv2.imread(image_path)
    crop = img[y:y+h, x:x+w]
    crop_path = "tmp_crop.png"
    cv2.imwrite(crop_path, crop)
    # run PaddleOCR on crop_path instead of original
6.2. Resize & sharpen
Before OCR:

Upscale the crop by 2–3× (helps small text).

Apply mild sharpening and contrast enhancement.

Example (OpenCV):

python
import cv2

img = cv2.imread(path)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# Upscale
scale = 2.0
upscaled = cv2.resize(
    gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
)

# Sharpen
kernel = np.array([[-1, -1, -1],
                   [-1,  8, -1],
                   [-1, -1, -1]])
sharpened = cv2.filter2D(upscaled, -1, kernel)

# Contrast (CLAHE)
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
enhanced = clahe.apply(sharpened)
Then pass enhanced to PaddleOCR.

6.3. Controlled capture setup (for pilot / demo)
For more reliable results:

Fixed camera position and distance.

Good, uniform lighting.

Optionally, a reference object (e.g., a ruler or marker) in the frame to:

Estimate px→mm scale.

Enable font-height checks in mm later.

You can explicitly note in your demo that font-height checks in mm require either:

A calibrated setup (fixed distance + known focal length), or

A known reference dimension (e.g., “this is a 500 ml bottle, height = 20 cm”), or

A physical scale/marker in the image.

Judges usually accept this as a clearly stated limitation for MVP.

7. JSON Contract & Rule Engine Contract
Product contract (from OCR)
This is what ocr_metrix.py generates:

json
{
  "manufacturer_address": "string",
  "commodity_name": "string",
  "net_quantity": "string",
  "net_quantity_value_g_ml": 500,
  "quantity_type": "weight_or_volume",
  "mrp": "Rs.55 (incl. of all taxes)",
  "mfg_date": "08/2026",
  "consumer_care": "care@abcfoods.com, 1800-XXX-XXXX",
  "is_imported": false,
  "buyer_type": "retail",
  "category": "packaged_food",
  "font_heights_mm": {},
  "is_embossed": false,
  "letter_width_height_ratios": {},
  "detected_language": "en",
  "country_of_origin": "",
  "pdp_area_cm2": null,
  "pdp_box": null,
  "declaration_boxes": {},
  "nearest_other_text_distance_mm": {},
  "body_text_height_mm": null,
  "contrast_ok": {}
}
Required fields for basic compliance checks:

manufacturer_address

commodity_name

net_quantity

net_quantity_value_g_ml

quantity_type

mrp

mfg_date

consumer_care

is_imported

buyer_type

category

font_heights_mm

is_embossed

letter_width_height_ratios

detected_language

Optional (geometry-related) fields:

country_of_origin

pdp_area_cm2

pdp_box

declaration_boxes

nearest_other_text_distance_mm

body_text_height_mm

contrast_ok

The rule engine should treat missing/empty optional fields as N/A, not as failures.

Rules config (static)
The large JSON you showed (meta, scope_exclusions, etc.) stays as rules.json. It does not change per product. It is loaded once and reused.

8. Next Steps / Extensions
Once the MVP is stable:

Tune extraction per category
Add category-specific parsing (e.g., textiles, cement, LPG) with slightly different patterns.

Add language detection
Use a small model or heuristic to set detected_language more accurately (en vs hi).

Geometry checks
When you have:

Reliable px→mm scale, and/or

Controlled capture setup,
populate font_heights_mm, pdp_area_cm2, etc., and enable those rules.

Confidence-based flags
Use OCR confidence scores to:

Flag low-confidence MRP / net quantity for manual review.

Show a “trust score” in the UI.

Batch processing
Allow uploading multiple images and generating a report (CSV + JSON) for a brand/SKU list.

9. Quick Start Checklist
Install dependencies:

bash
pip install paddlepaddle paddleocr opencv-python
Place:

ocr_metrix.py

sample_label.jpg

rules.json

rule_engine.py

in the same folder (e.g. D:\yanshi\sih).

Run OCR:

bash
python -X utf8 -u "D:\yanshi\sih\ocr_metrix.py"
Verify:

output\product_contract.json exists and has non-empty mrp, mfg_date, etc.

output\layout_annotated.png shows boxes and text.

Run rule engine (example):

bash
python rule_engine.py rules.json output\product_contract.json
Integrate with backend by calling the OCR function and rule engine from your API handler.
