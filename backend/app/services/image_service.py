from app.services.ocr_service import extract_text


def process_image(file_path):
    ocr_result = extract_text(file_path)

    return {
        "status": "success",
        "file_path": file_path,
        "ocr": ocr_result
    }