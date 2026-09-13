import base64
import hashlib
import io
import os
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError

from models.compliance import ImageQuality, ScanImageCreate


MAX_IMAGES = int(os.environ.get("MAX_INSPECTION_IMAGES", "8"))
MAX_FILE_SIZE_BYTES = int(os.environ.get("MAX_IMAGE_BYTES", str(6 * 1024 * 1024)))
MAX_TOTAL_SIZE_BYTES = int(os.environ.get("MAX_TOTAL_IMAGE_BYTES", str(24 * 1024 * 1024)))
MIN_WIDTH = int(os.environ.get("MIN_IMAGE_WIDTH", "640"))
MIN_HEIGHT = int(os.environ.get("MIN_IMAGE_HEIGHT", "480"))
RECOMMENDED_WIDTH = int(os.environ.get("RECOMMENDED_IMAGE_WIDTH", "1600"))
RECOMMENDED_HEIGHT = int(os.environ.get("RECOMMENDED_IMAGE_HEIGHT", "1200"))
SUPPORTED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


class ImageValidationError(ValueError):
    def __init__(self, errors: list[dict]):
        super().__init__("One or more images are unsuitable for OCR")
        self.errors = errors


@dataclass
class PreparedImage:
    source: ScanImageCreate
    raw_bytes: bytes
    original_data_url: str
    enhanced_base64: str
    quality: ImageQuality
    sha256: str


def upload_config() -> dict:
    return {
        "max_images": MAX_IMAGES,
        "max_file_size_bytes": MAX_FILE_SIZE_BYTES,
        "max_total_size_bytes": MAX_TOTAL_SIZE_BYTES,
        "supported_mime_types": sorted(SUPPORTED_MIME_TYPES),
        "min_width": MIN_WIDTH,
        "min_height": MIN_HEIGHT,
        "recommended_width": RECOMMENDED_WIDTH,
        "recommended_height": RECOMMENDED_HEIGHT,
    }


def _decode(data_url: str) -> bytes:
    payload = data_url.split(",", 1)[1] if data_url.startswith("data:") else data_url
    return base64.b64decode(payload, validate=True)


def _quality(image: Image.Image) -> ImageQuality:
    rgb = image.convert("RGB")
    preview = rgb.copy()
    preview.thumbnail((720, 720))
    gray = np.asarray(preview.convert("L"), dtype=np.float32)
    brightness = float(gray.mean())
    glare_ratio = float((gray > 247).mean())
    gx = np.abs(np.diff(gray, axis=1)).mean() if gray.shape[1] > 1 else 0.0
    gy = np.abs(np.diff(gray, axis=0)).mean() if gray.shape[0] > 1 else 0.0
    blur_score = float((gx + gy) / 2)
    warnings: list[str] = []
    blocking = False
    if image.width < MIN_WIDTH or image.height < MIN_HEIGHT:
        warnings.append(f"Resolution is too low ({image.width}×{image.height}); minimum is {MIN_WIDTH}×{MIN_HEIGHT}.")
        blocking = image.width < 400 or image.height < 300
    if blur_score < 4.2:
        warnings.append("The image appears excessively blurred; retake it with the label in focus.")
        blocking = blocking or blur_score < 2.2
    if brightness < 42:
        warnings.append("The image is very dark; use brighter, even lighting.")
        blocking = blocking or brightness < 24
    if glare_ratio > 0.22:
        warnings.append("Strong glare or reflection may hide printed declarations; change the camera angle.")
        blocking = blocking or glare_ratio > 0.48
    return ImageQuality(width=image.width, height=image.height, blur_score=round(blur_score, 2), brightness=round(brightness, 2), glare_ratio=round(glare_ratio, 4), warnings=warnings, suitable=not blocking)


def prepare_images(inputs: list[ScanImageCreate]) -> list[PreparedImage]:
    if not inputs:
        raise ImageValidationError([{"message": "Upload at least one package-face image."}])
    if len(inputs) > MAX_IMAGES:
        raise ImageValidationError([{"message": f"A maximum of {MAX_IMAGES} images is supported per inspection."}])
    prepared: list[PreparedImage] = []
    errors: list[dict] = []
    total = 0
    for item in inputs:
        if item.mime_type not in SUPPORTED_MIME_TYPES:
            errors.append({"client_id": item.client_id, "file_name": item.file_name, "message": "Unsupported format. Use JPEG, PNG, or WEBP."})
            continue
        try:
            raw = _decode(item.image_base64)
        except Exception:
            errors.append({"client_id": item.client_id, "file_name": item.file_name, "message": "The image data is invalid or incomplete."})
            continue
        total += len(raw)
        if len(raw) > MAX_FILE_SIZE_BYTES:
            errors.append({"client_id": item.client_id, "file_name": item.file_name, "message": f"File exceeds the configured {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB per-image limit."})
            continue
        try:
            image = Image.open(io.BytesIO(raw))
            image.verify()
            image = Image.open(io.BytesIO(raw))
            image = ImageOps.exif_transpose(image).convert("RGB")
        except (UnidentifiedImageError, OSError):
            errors.append({"client_id": item.client_id, "file_name": item.file_name, "message": "The file is not a readable JPEG, PNG, or WEBP image."})
            continue
        quality = _quality(image)
        if not quality.suitable:
            errors.append({"client_id": item.client_id, "file_name": item.file_name, "message": "Image quality is insufficient for reliable OCR.", "warnings": quality.warnings})
            continue
        enhanced = image.copy()
        if enhanced.width < RECOMMENDED_WIDTH and enhanced.height < RECOMMENDED_HEIGHT:
            scale = min(2.0, RECOMMENDED_WIDTH / enhanced.width, RECOMMENDED_HEIGHT / enhanced.height)
            enhanced = enhanced.resize((int(enhanced.width * scale), int(enhanced.height * scale)), Image.Resampling.LANCZOS)
        enhanced = ImageOps.autocontrast(enhanced, cutoff=1)
        enhanced = enhanced.filter(ImageFilter.MedianFilter(size=3)).filter(ImageFilter.UnsharpMask(radius=1.2, percent=125, threshold=3))
        buffer = io.BytesIO()
        enhanced.save(buffer, format="JPEG", quality=92, optimize=True)
        prepared.append(PreparedImage(
            source=item,
            raw_bytes=raw,
            original_data_url=f"data:{item.mime_type};base64,{base64.b64encode(raw).decode('ascii')}",
            enhanced_base64=base64.b64encode(buffer.getvalue()).decode("ascii"),
            quality=quality,
            sha256=hashlib.sha256(raw).hexdigest(),
        ))
    if total > MAX_TOTAL_SIZE_BYTES:
        errors.append({"message": f"Combined image size exceeds the configured {MAX_TOTAL_SIZE_BYTES // (1024 * 1024)} MB inspection limit."})
    if errors:
        raise ImageValidationError(errors)
    return prepared