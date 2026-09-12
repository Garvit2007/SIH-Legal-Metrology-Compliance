import os
import cv2
from ocr.ocr_metrix import run_ocr

PROCESSED_DIR = "uploads/processed"
os.makedirs(PROCESSED_DIR, exist_ok=True)


def extract_declarations(image, metadata):
    """
    image: numpy array returned by preprocess_image()
    metadata: dict returned by preprocess_image()
    """
    filename = f"processed_{os.getpid()}_{id(image)}.png"
    processed_path = os.path.join(PROCESSED_DIR, filename)

    cv2.imwrite(processed_path, image)

    result = run_ocr(processed_path)

    os.remove(processed_path)  # cleanup temp file

    return result
