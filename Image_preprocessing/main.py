from pathlib import Path
from preprocessor import preprocess_image
import cv2

BASE_DIR = Path(__file__).resolve().parent
image_path = BASE_DIR / "sample" / "product.png"

print("Looking for image at:")
print(image_path)

processed_image, metadata = preprocess_image(str(image_path))

print("\nProcessing completed!")
print("\nMetadata:")
print(metadata)

output_path = BASE_DIR / "processed_product.png"
cv2.imwrite(str(output_path), processed_image)

print("\nProcessed image saved at:")
print(output_path)
