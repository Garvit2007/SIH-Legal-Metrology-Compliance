from ocr.ocr_metrix import run_ocr


def extract_declarations(image, metadata):
    """
    Backend adapter for the OCR module.

    image:
        Path of the uploaded image.

    metadata:
        Preprocessing metadata.
    """

    image_path = image

    return run_ocr(image_path)