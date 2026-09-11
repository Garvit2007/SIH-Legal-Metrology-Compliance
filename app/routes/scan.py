from fastapi import APIRouter, HTTPException
import os

from Image_preprocessing.preprocessor import preprocess_image
from app.services.ocr_service import extract_declarations
from app.services.rule_service import check_compliance

router = APIRouter()

UPLOAD_FOLDER = "uploads"


@router.post("/scan/{image_id}")
async def scan_image(image_id: str):

    image_path = None

    if not os.path.exists(UPLOAD_FOLDER):
        raise HTTPException(
            status_code=404,
            detail="Upload folder not found"
        )

    for filename in os.listdir(UPLOAD_FOLDER):
        if filename.startswith(image_id):
            image_path = os.path.join(
                UPLOAD_FOLDER,
                filename
            )
            break

    if image_path is None:
        raise HTTPException(
            status_code=404,
            detail="Image not found"
        )

    # 1. IMAGE PREPROCESSING
    try:
        processed_image, metadata = preprocess_image(
            image_path
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Image preprocessing failed: {str(e)}"
        )

    # 2. OCR
    try:
        structured_json = extract_declarations(
            processed_image,
            metadata
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"OCR failed: {str(e)}"
        )

    # 3. RULE ENGINE
    try:
        compliance_report = check_compliance(
            image_id,
            structured_json
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Rule engine failed: {str(e)}"
        )

    return {
        "image_id": image_id,
        "pipeline": {
            "preprocessing": "completed",
            "ocr": "completed",
            "rule_engine": "completed"
        },
        "structured_data": structured_json,
        "compliance_report": compliance_report
    }