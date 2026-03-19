"""
app/services/storage_service.py
────────────────────────────────
Private file storage using MinIO (S3-compatible).

Why MinIO?
- Self-hosted (data never leaves your infrastructure)
- S3-compatible API (easy to switch to AWS S3 in production)
- Supports pre-signed URLs (images served securely, time-limited)

Images are:
1. Validated (type, size)
2. Stored in MinIO under a private bucket
3. Never publicly accessible — only via signed URLs with expiry
4. Referenced in the DB by object path, not URL
"""

import uuid
import base64
from io import BytesIO
from datetime import timedelta
from typing import Optional
from loguru import logger

from minio import Minio
from minio.error import S3Error
from PIL import Image

from app.config import settings

# ── MinIO Client ──────────────────────────────────────────────────────────────
_minio_client: Optional[Minio] = None


def get_minio_client() -> Minio:
    global _minio_client
    if _minio_client is None:
        _minio_client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
    return _minio_client


def ensure_bucket_exists():
    """Create the images bucket if it doesn't exist. Called on startup."""
    client = get_minio_client()
    bucket = settings.MINIO_BUCKET_IMAGES

    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        logger.info(f"Created MinIO bucket: {bucket}")

        # Set bucket policy to private (no public access)
        # Images are only accessible via pre-signed URLs


# ── Image Validation ──────────────────────────────────────────────────────────

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_SIZE_BYTES = settings.MAX_IMAGE_SIZE_MB * 1024 * 1024


def validate_image(image_data: bytes, mime_type: str) -> tuple[bool, str]:
    """Validate image type and size. Returns (is_valid, error_message)."""
    if mime_type not in ALLOWED_IMAGE_TYPES:
        return False, f"Unsupported image type: {mime_type}. Allowed: {ALLOWED_IMAGE_TYPES}"

    if len(image_data) > MAX_IMAGE_SIZE_BYTES:
        return False, f"Image too large ({len(image_data) // 1024 // 1024}MB). Max: {settings.MAX_IMAGE_SIZE_MB}MB"

    # Verify it's actually an image (not a malicious file)
    try:
        img = Image.open(BytesIO(image_data))
        img.verify()  # Checks file structure
    except Exception:
        return False, "Invalid image file"

    return True, ""


# ── Upload / Download ─────────────────────────────────────────────────────────

def upload_image(
    image_data: bytes,
    mime_type: str,
    chat_id: str,
    message_id: Optional[str] = None,
) -> str:
    """
    Upload an image to MinIO.

    Returns:
        object_path: The MinIO object path (e.g., "chat_id/uuid.jpg")
        Store this in the database. Never store the signed URL.
    """
    is_valid, error = validate_image(image_data, mime_type)
    if not is_valid:
        raise ValueError(f"Image validation failed: {error}")

    extension = mime_type.split("/")[-1].replace("jpeg", "jpg")
    object_name = f"{chat_id}/{message_id or uuid.uuid4()}.{extension}"

    client = get_minio_client()
    client.put_object(
        bucket_name=settings.MINIO_BUCKET_IMAGES,
        object_name=object_name,
        data=BytesIO(image_data),
        length=len(image_data),
        content_type=mime_type,
    )

    logger.info(f"Uploaded image: {object_name} ({len(image_data)} bytes)")
    return object_name


def upload_image_base64(
    base64_data: str,
    mime_type: str,
    chat_id: str,
    message_id: Optional[str] = None,
) -> str:
    """Upload base64-encoded image. Decodes and calls upload_image."""
    image_data = base64.b64decode(base64_data)
    return upload_image(image_data, mime_type, chat_id, message_id)


def get_signed_url(object_path: str, expires_minutes: int = 60) -> str:
    """
    Generate a time-limited pre-signed URL for secure image access.

    The URL expires after `expires_minutes` minutes.
    Never store this URL — generate a fresh one for each request.
    """
    client = get_minio_client()

    url = client.presigned_get_object(
        bucket_name=settings.MINIO_BUCKET_IMAGES,
        object_name=object_path,
        expires=timedelta(minutes=expires_minutes),
    )
    return url


def delete_image(object_path: str) -> bool:
    """Delete an image from MinIO (e.g., when a message is deleted)."""
    try:
        client = get_minio_client()
        client.remove_object(settings.MINIO_BUCKET_IMAGES, object_path)
        return True
    except S3Error as e:
        logger.error(f"Failed to delete image {object_path}: {e}")
        return False


def get_image_for_llm(object_path: str) -> tuple[str, str]:
    """
    Retrieve an image from MinIO as base64 for LLM API input.

    Returns:
        (base64_data, mime_type)
    """
    client = get_minio_client()

    response = client.get_object(settings.MINIO_BUCKET_IMAGES, object_path)
    image_bytes = response.read()

    # Determine MIME type from object path
    ext = object_path.rsplit(".", 1)[-1].lower()
    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
    mime_type = mime_map.get(ext, "image/jpeg")

    return base64.b64encode(image_bytes).decode(), mime_type


# Singleton
storage_service = type("StorageService", (), {
    "upload_image": staticmethod(upload_image),
    "upload_image_base64": staticmethod(upload_image_base64),
    "get_signed_url": staticmethod(get_signed_url),
    "delete_image": staticmethod(delete_image),
    "get_image_for_llm": staticmethod(get_image_for_llm),
    "ensure_bucket_exists": staticmethod(ensure_bucket_exists),
})()
