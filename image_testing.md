# Image Integration Testing Playbook

## Image Handling Rules
- Always use base64-encoded images for all tests and requests.
- Accepted formats: JPEG, PNG, WEBP only.
- Do not use blank, solid-color, or uniform-variance images.
- Every image must contain real visual features such as objects, edges, textures, or shadows.
- If an image is not PNG, JPEG, or WEBP, transcode it before upload and re-detect the MIME type.
- For animated images, extract the first frame only.
- Resize large images to reasonable bounds before upload.