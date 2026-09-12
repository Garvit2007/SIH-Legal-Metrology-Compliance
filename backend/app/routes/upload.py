from fastapi import APIRouter, UploadFile, File
import os
import shutil
import uuid

router = APIRouter()

UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):

    # Create a unique ID for the uploaded image
    image_id = str(uuid.uuid4())

    # Keep the original file extension
    extension = os.path.splitext(file.filename)[1]

    # Create a unique filename
    filename = image_id + extension

    # Complete path where image will be saved
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    # Save the uploaded image
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "message": "Image uploaded successfully",
        "image_id": image_id,
        "filename": file.filename,
        "file_path": file_path
    }