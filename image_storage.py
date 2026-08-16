"""Image optimization and storage for knowledge attachments."""

import io
import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGES = 2
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_IMAGE_EDGE = 1600
WEBP_QUALITY = 85
DEFAULT_OBJECT_PREFIX = "SPOTV Tech Copilot/knowledge"
LOCAL_ROOT = Path(__file__).with_name(".data") / "SPOTV Tech Copilot" / "knowledge"
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreparedImage:
    content: bytes
    original_name: str
    width: int
    height: int


def _cloud_enabled():
    return os.getenv("DATABASE_BACKEND", "sqlite").strip().lower() == "firestore"


def _bucket_name():
    configured = os.getenv("IMAGE_BUCKET_NAME", "").strip()
    if configured:
        return configured
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    if not project:
        raise RuntimeError("IMAGE_BUCKET_NAME 또는 GOOGLE_CLOUD_PROJECT 환경변수가 필요합니다.")
    return f"{project}-spotv-tech-copilot"


def _object_prefix():
    return os.getenv("IMAGE_OBJECT_PREFIX", DEFAULT_OBJECT_PREFIX).strip().strip("/") or DEFAULT_OBJECT_PREFIX


def _safe_original_name(name):
    return str(name or "image").replace("\\", "/").rsplit("/", 1)[-1][:180]


def prepare_images(uploaded_files):
    files = list(uploaded_files or [])
    if len(files) > MAX_IMAGES:
        raise ValueError(f"사진은 지식당 최대 {MAX_IMAGES}장까지 등록할 수 있습니다.")

    prepared = []
    for uploaded in files:
        raw = uploaded.getvalue()
        original_name = _safe_original_name(getattr(uploaded, "name", "image"))
        if not raw:
            raise ValueError(f"{original_name}: 빈 파일은 등록할 수 없습니다.")
        if len(raw) > MAX_UPLOAD_BYTES:
            raise ValueError(f"{original_name}: 원본 파일은 5MB 이하여야 합니다.")
        try:
            with Image.open(io.BytesIO(raw)) as source:
                if source.width * source.height > MAX_IMAGE_PIXELS:
                    raise ValueError(f"{original_name}: 이미지 해상도가 너무 큽니다.")
                source.load()
                image = ImageOps.exif_transpose(source)
                image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)
                has_alpha = image.mode in {"RGBA", "LA"} or "transparency" in image.info
                image = image.convert("RGBA" if has_alpha else "RGB")
                output = io.BytesIO()
                image.save(output, format="WEBP", quality=WEBP_QUALITY, method=6)
                prepared.append(PreparedImage(output.getvalue(), original_name, image.width, image.height))
        except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as exc:
            raise ValueError(f"{original_name}: 지원되는 이미지 파일이 아닙니다.") from exc
    return prepared


def upload_images(item_id, prepared_images):
    images = list(prepared_images or [])
    if not images:
        return []
    return _upload_cloud(item_id, images) if _cloud_enabled() else _upload_local(item_id, images)


def _metadata(path, prepared):
    return {
        "path": path,
        "name": prepared.original_name,
        "content_type": "image/webp",
        "size": len(prepared.content),
        "width": prepared.width,
        "height": prepared.height,
    }


def _upload_cloud(item_id, prepared_images):
    from google.cloud import storage

    bucket = storage.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT") or None).bucket(_bucket_name())
    uploaded = []
    try:
        for prepared in prepared_images:
            path = f"{_object_prefix()}/{item_id}/{uuid.uuid4().hex}.webp"
            blob = bucket.blob(path)
            blob.metadata = {"original_name": prepared.original_name}
            blob.upload_from_string(prepared.content, content_type="image/webp")
            uploaded.append(_metadata(path, prepared))
    except Exception:
        delete_images(uploaded)
        raise
    return uploaded


def _local_path(object_path):
    relative = Path(*str(object_path).replace("\\", "/").split("/"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("올바르지 않은 이미지 경로입니다.")
    root = LOCAL_ROOT.resolve()
    path = (root / relative).resolve()
    if path != root and root not in path.parents:
        raise ValueError("올바르지 않은 이미지 경로입니다.")
    return path


def _upload_local(item_id, prepared_images):
    uploaded = []
    try:
        for prepared in prepared_images:
            path = f"{item_id}/{uuid.uuid4().hex}.webp"
            target = _local_path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(prepared.content)
            uploaded.append(_metadata(path, prepared))
    except Exception:
        delete_images(uploaded)
        raise
    return uploaded


def download_image(image):
    path = str((image or {}).get("path") or "")
    if not path:
        raise ValueError("이미지 경로가 없습니다.")
    if _cloud_enabled():
        from google.cloud import storage

        bucket = storage.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT") or None).bucket(_bucket_name())
        return bucket.blob(path).download_as_bytes()
    return _local_path(path).read_bytes()


def delete_images(images):
    for image in images or []:
        path = str((image or {}).get("path") or "")
        if not path:
            continue
        try:
            if _cloud_enabled():
                from google.cloud import storage

                bucket = storage.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT") or None).bucket(_bucket_name())
                bucket.blob(path).delete()
            else:
                _local_path(path).unlink(missing_ok=True)
        except Exception:
            # Best-effort cleanup; callers log the primary operation failure.
            LOGGER.warning("Failed to delete image object: %s", path, exc_info=True)
            continue
