from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import os

from image_preprocessing.preprocessor import preprocess_image
from app.services.ocr_service import extract_declarations
from app.services.rule_service import check_compliance

from app.database.connection import SessionLocal
from app.database.models import Scan, ComplianceReport, Violation

router = APIRouter()

UPLOAD_FOLDER = "uploads"

ALLOWED_SEVERITIES = {"critical", "major", "minor"}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/scan/{image_id}")
async def scan_image(image_id: str, db: Session = Depends(get_db)):

    image_path = None

    if not os.path.exists(UPLOAD_FOLDER):
        raise HTTPException(status_code=404, detail="Upload folder not found")

    for filename in os.listdir(UPLOAD_FOLDER):
        if filename.startswith(image_id):
            image_path = os.path.join(UPLOAD_FOLDER, filename)
            break

    if image_path is None:
        raise HTTPException(status_code=404, detail="Image not found")

    # Create the scan record up front
    scan = Scan(image_url=image_path, status="processing")
    db.add(scan)
    db.commit()
    db.refresh(scan)

    # 1. IMAGE PREPROCESSING
    try:
        processed_image, metadata = preprocess_image(image_path)
    except Exception as e:
        scan.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Image preprocessing failed: {str(e)}")

    # 2. OCR
    try:
        structured_json = extract_declarations(processed_image, metadata)
    except Exception as e:
        scan.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"OCR failed: {str(e)}")

    # 3. RULE ENGINE
    try:
        compliance_report = check_compliance(image_id, structured_json)
    except Exception as e:
        scan.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Rule engine failed: {str(e)}")

    # ---- Save results to database ----
    scan.raw_ocr_text = structured_json.get("raw_ocr_text", "")
    scan.extracted_data = structured_json
    scan.status = "completed"
    db.commit()

    if compliance_report.get("out_of_scope") or compliance_report.get("exempt"):
        overall_status = "compliant"
    elif compliance_report.get("is_compliant"):
        overall_status = "compliant"
    else:
        overall_status = "non_compliant"

    total_checks = compliance_report.get("total_violations", 0) + len(compliance_report.get("passed_checks", []))
    compliance_score = None
    if total_checks > 0:
        compliance_score = round(
            (len(compliance_report.get("passed_checks", [])) / total_checks) * 100, 2
        )

    report_row = ComplianceReport(
        scan_id=scan.id,
        overall_status=overall_status,
        compliance_score=compliance_score
    )
    db.add(report_row)
    db.commit()
    db.refresh(report_row)

    for v in compliance_report.get("violations", []):
        severity = v.get("severity", "minor")
        if severity not in ALLOWED_SEVERITIES:
            severity = "minor"  # clamp 'info' or anything unexpected

        violation_row = Violation(
            report_id=report_row.id,
            field_name=v.get("field"),
            rule_citation=v.get("rule_ref"),
            severity=severity,
            message=v.get("message")
        )
        db.add(violation_row)
    db.commit()

    return {
        "image_id": image_id,
        "scan_id": scan.id,
        "report_id": report_row.id,
        "pipeline": {
            "preprocessing": "completed",
            "ocr": "completed",
            "rule_engine": "completed"
        },
        "structured_data": structured_json,
        "compliance_report": compliance_report
    }
