import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

_MAGIC_BYTES: dict[bytes, str] = {
    b"\xff\xd8\xff": "jpg",
    b"\x89PNG\r\n\x1a\n": "png",
}
_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/heic"}


def _invalid_image_type() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="invalid_image_type: 지원하지 않는 이미지 형식입니다.",
    )


def _sniff_extension(head: bytes) -> str:
    for magic, ext in _MAGIC_BYTES.items():
        if head.startswith(magic):
            return ext
    if head[4:8] == b"ftyp" and head[8:12] in {b"heic", b"heix", b"mif1", b"msf1"}:
        return "heic"
    raise _invalid_image_type()


async def read_and_validate_image(file: UploadFile) -> bytes:
    """Read an uploaded image fully, enforcing content-type, size, and magic bytes."""
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise _invalid_image_type()

    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > settings.max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="image_too_large: 이미지 크기가 10 MiB를 초과합니다.",
            )
        chunks.append(chunk)
    content = b"".join(chunks)
    if not content:
        raise _invalid_image_type()

    _sniff_extension(content[:16])
    return content


def store_bytes(content: bytes, subdir: str) -> str:
    """Persist already-validated image bytes locally and return an `image_key`."""
    ext = _sniff_extension(content[:16])
    filename = f"{uuid.uuid4()}.{ext}"
    directory = Path(settings.upload_dir) / subdir
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_bytes(content)
    return f"{subdir}/{filename}"


async def save_upload(file: UploadFile, subdir: str) -> str:
    content = await read_and_validate_image(file)
    return store_bytes(content, subdir)
