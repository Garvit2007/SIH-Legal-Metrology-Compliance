from fastapi import APIRouter, UploadFile, File
import os
import shutil

from app.services.image_service import process_image

router = APIRouter()

UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@router.post("/analyze")
async def analyze(file: UploadFile = File(...)):

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    result = process_image(file_path)

    return {
        "message": "Image uploaded successfully",
        "filename": file.filename,
        "file_path": file_path,
        "processing": result
    }