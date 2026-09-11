import os

os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "0"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

from paddleocr import PaddleOCR

image_path = "sample_label.jpg"

if not os.path.exists(image_path):
    print("Image not found:", image_path)
    raise SystemExit

print("Image found. Starting OCR...")

ocr = PaddleOCR(
    lang="en",
    device="cpu",
    enable_mkldnn=False,
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False
)

print("Running prediction...")

results = ocr.predict(image_path)

for result in results:
    result.print()
    result.save_to_json("output")
    result.save_to_img("output")

print("OCR completed. Check the output folder.")