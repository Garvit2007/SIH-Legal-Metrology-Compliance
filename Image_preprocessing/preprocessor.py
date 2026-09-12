import os
import math
import cv2
import numpy as np
from PIL import Image


def load_and_validate(
    image_path: str,
    blur_threshold: float = 100.0,
    min_width: int = 600,
    min_height: int = 600
):
    """
    Load an image and perform basic quality checks.

    Returns:
        image: OpenCV BGR image
        quality: dictionary containing quality information
    """

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    image = cv2.imread(image_path)

    if image is None:
        raise ValueError(f"Could not read image: {image_path}")

    height, width = image.shape[:2]

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Blur detection using Laplacian variance
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    warnings = []

    if blur_score < blur_threshold:
        warnings.append(
            f"Image may be blurry. Laplacian variance = {blur_score:.2f}"
        )

    if width < min_width or height < min_height:
        warnings.append(
            f"Resolution is low: {width}x{height}px"
        )

    quality = {
        "width_px": width,
        "height_px": height,
        "blur_score": blur_score,
        "is_blurry": blur_score < blur_threshold,
        "low_resolution": width < min_width or height < min_height,
        "warnings": warnings
    }

    return image, quality


def _rotate_bound(image, angle):
    """Rotate image without cropping its corners."""

    h, w = image.shape[:2]
    center = (w / 2, h / 2)

    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)

    cos = abs(matrix[0, 0])
    sin = abs(matrix[0, 1])

    new_w = int((h * sin) + (w * cos))
    new_h = int((h * cos) + (w * sin))

    matrix[0, 2] += (new_w / 2) - center[0]
    matrix[1, 2] += (new_h / 2) - center[1]

    return cv2.warpAffine(
        image,
        matrix,
        (new_w, new_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE
    )


def deskew(image, angle_limit: float = 15.0):
    """
    Correct small rotations using Hough lines and contours.

    Returns:
        corrected_image
        correction_angle
    """

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Improve edge detection
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    edges = cv2.Canny(blur, 50, 150)

    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=80,
        minLineLength=max(50, min(gray.shape) // 5),
        maxLineGap=20
    )

    angles = []

    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = np.asarray(line).reshape(-1)[:4]

            angle = math.degrees(
                math.atan2(y2 - y1, x2 - x1)
            )

            # Keep mostly horizontal lines
            if abs(angle) <= angle_limit:
                angles.append(angle)

    correction_angle = 0.0

    if angles:
        correction_angle = float(np.median(angles))

    # If no useful Hough lines were found, try contour-based estimation
    if not angles:
        _, thresh = cv2.threshold(
            gray,
            0,
            255,
            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )

        contours, _ = cv2.findContours(
            thresh,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        candidate_angles = []

        for contour in contours:
            area = cv2.contourArea(contour)

            if area < 0.05 * image.shape[0] * image.shape[1]:
                continue

            rect = cv2.minAreaRect(contour)
            angle = rect[2]

            if rect[1][0] < rect[1][1]:
                angle += 90

            if abs(angle) <= angle_limit:
                candidate_angles.append(angle)

        if candidate_angles:
            correction_angle = float(np.median(candidate_angles))

    # Rotate opposite to detected tilt
    corrected = _rotate_bound(image, -correction_angle)

    return corrected, -correction_angle


def reduce_glare(image):
    """
    Conservative glare reduction.
    Detects very bright, low-saturation areas and inpaints them.
    """

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    lower = np.array([0, 0, 235])
    upper = np.array([180, 45, 255])

    mask = cv2.inRange(hsv, lower, upper)

    # Avoid aggressive removal of large areas
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    if np.count_nonzero(mask) > 0.20 * mask.size:
        return image

    return cv2.inpaint(
        image,
        mask,
        3,
        cv2.INPAINT_TELEA
    )


def denoise_and_enhance(image):
    """
    Denoise image and improve local contrast using CLAHE.
    """

    denoised = cv2.fastNlMeansDenoisingColored(
        image,
        None,
        h=7,
        hColor=7,
        templateWindowSize=7,
        searchWindowSize=21
    )

    # Reduce mild glare
    denoised = reduce_glare(denoised)

    lab = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)

    l_channel, a_channel, b_channel = cv2.split(lab)

    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8)
    )

    l_channel = clahe.apply(l_channel)

    enhanced = cv2.merge(
        [l_channel, a_channel, b_channel]
    )

    enhanced = cv2.cvtColor(
        enhanced,
        cv2.COLOR_LAB2BGR
    )

    return enhanced


def crop_to_label(image, min_area_ratio: float = 0.12):
    """
    Detect a large rectangular label/package region.

    Returns:
        cropped_image
        crop_box = (x1, y1, x2, y2)
    """

    original_h, original_w = image.shape[:2]

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    edges = cv2.Canny(gray, 50, 150)

    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (7, 7)
    )

    edges = cv2.morphologyEx(
        edges,
        cv2.MORPH_CLOSE,
        kernel
    )

    contours, _ = cv2.findContours(
        edges,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    image_area = original_w * original_h

    best_box = None
    best_score = 0

    for contour in contours:

        area = cv2.contourArea(contour)

        if area < min_area_ratio * image_area:
            continue

        x, y, w, h = cv2.boundingRect(contour)

        box_area = w * h
        area_ratio = box_area / image_area

        if area_ratio > 0.95:
            continue

        aspect_ratio = w / max(h, 1)

        # Prefer reasonable rectangular regions
        if aspect_ratio < 0.3 or aspect_ratio > 4.0:
            continue

        score = area_ratio

        if score > best_score:
            best_score = score
            best_box = (x, y, x + w, y + h)

    # If no suitable label is found, use the full image
    if best_box is None:
        return image.copy(), (0, 0, original_w, original_h)

    x1, y1, x2, y2 = best_box

    # Small padding
    pad_x = int(0.01 * original_w)
    pad_y = int(0.01 * original_h)

    x1 = max(0, x1 - pad_x)
    y1 = max(0, y1 - pad_y)
    x2 = min(original_w, x2 + pad_x)
    y2 = min(original_h, y2 + pad_y)

    cropped = image[y1:y2, x1:x2].copy()

    return cropped, (x1, y1, x2, y2)


def read_embedded_dpi(image_path):
    """
    Read DPI metadata from an image when available.

    Returns:
        dpi or None
    """

    try:
        with Image.open(image_path) as img:
            dpi = img.info.get("dpi")

            if dpi is not None:
                if isinstance(dpi, tuple):
                    x_dpi = dpi[0]

                    if x_dpi and x_dpi > 0:
                        return float(x_dpi)

                elif isinstance(dpi, (int, float)):
                    if dpi > 0:
                        return float(dpi)

    except Exception:
        pass

    return None


def normalize_resolution(
    image,
    source_dpi,
    target_dpi=300,
    min_width=600,
    min_height=600
):
    """
    Upscale small images.

    Note:
        If source DPI is unavailable, target_dpi is a processing target,
        not a measured physical DPI.
    """

    h, w = image.shape[:2]

    scale = 1.0

    if source_dpi is not None and source_dpi < target_dpi:
        scale = target_dpi / source_dpi

    if w < min_width:
        scale = max(scale, min_width / w)

    if h < min_height:
        scale = max(scale, min_height / h)

    # Prevent excessive upscaling
    scale = min(scale, 4.0)

    if scale > 1.01:
        new_w = int(w * scale)
        new_h = int(h * scale)

        image = cv2.resize(
            image,
            (new_w, new_h),
            interpolation=cv2.INTER_CUBIC
        )

    return image, float(scale)


def to_ocr_ready(image):
    """
    Convert enhanced image to an OCR-friendly grayscale image.
    """

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8)
    )

    gray = clahe.apply(gray)

    # Adaptive thresholding
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11
    )

    # Remove tiny noise
    kernel = np.ones((2, 2), np.uint8)

    binary = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        kernel
    )

    return binary


def preprocess_image(
    raw_image_path: str,
    target_dpi: int = 300,
    blur_threshold: float = 100.0,
    min_width: int = 600,
    min_height: int = 600,
    angle_limit: float = 15.0
):
    """
    Complete preprocessing pipeline.

    Returns:
        processed_image: np.ndarray
        metadata: dict
    """

    # 1. Load and validate
    image, quality = load_and_validate(
        raw_image_path,
        blur_threshold=blur_threshold,
        min_width=min_width,
        min_height=min_height
    )

    # 2. Deskew
    image, deskew_angle = deskew(
        image,
        angle_limit=angle_limit
    )

    # 3. Crop label
    image, crop_box = crop_to_label(image)

    # 4. Denoise and enhance
    image = denoise_and_enhance(image)

    # 5. DPI
    source_dpi = read_embedded_dpi(raw_image_path)

    # 6. Normalize resolution
    image, upscale_factor = normalize_resolution(
        image,
        source_dpi=source_dpi,
        target_dpi=target_dpi,
        min_width=min_width,
        min_height=min_height
    )

    # 7. OCR-ready image
    processed_image = to_ocr_ready(image)

    height, width = processed_image.shape[:2]

    dpi_is_embedded = source_dpi is not None

    effective_dpi = (
        source_dpi
        if dpi_is_embedded
        else target_dpi
    )

    metadata = {
        "dpi": float(effective_dpi),
        "source_dpi": source_dpi,
        "dpi_is_embedded": dpi_is_embedded,
        "dpi_note": (
            "Embedded DPI from image metadata."
            if dpi_is_embedded
            else
            "300 DPI is a processing target; "
            "actual physical DPI cannot be inferred "
            "from pixels alone."
        ),
        "width_px": width,
        "height_px": height,
        "crop_box": {
            "x1": int(crop_box[0]),
            "y1": int(crop_box[1]),
            "x2": int(crop_box[2]),
            "y2": int(crop_box[3])
        },
        "deskew_angle_deg": float(deskew_angle),
        "upscale_factor": float(upscale_factor),
        "input_quality": quality,
        "processing": [
            "load_and_validate",
            "deskew",
            "crop_to_label",
            "denoise",
            "glare_reduction",
            "CLAHE_contrast_enhancement",
            "resolution_normalization",
            "adaptive_thresholding"
        ]
    }

    return processed_image, metadata