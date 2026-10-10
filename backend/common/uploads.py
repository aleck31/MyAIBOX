"""Upload storage: the single place that decides where uploaded files live
and which client-supplied references are allowed to resolve to a file.

Clients never get to name a path. They hold a `file_id` (``<uuid4 hex>.<ext>``)
and anything they send back (bare id, ``/api/upload/<id>`` URL, or the
``storage/uploads/<id>`` path returned by the upload endpoint) is reduced to
that id and re-validated before touching the filesystem.
"""
from __future__ import annotations

import os
import re
import uuid
from typing import Optional, Tuple

from fastapi import HTTPException, UploadFile

from backend.common.logger import logger

UPLOAD_DIR = os.path.join("storage", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {
    # Images
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    # Documents
    ".pdf", ".csv", ".doc", ".docx", ".xls", ".xlsx", ".txt", ".md",
    # Video
    ".mp4", ".webm", ".mov",
}

# Matches the frontend's 20MB client-side limit by default.
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "20")) * 1024 * 1024
_CHUNK = 1024 * 1024

_FILE_ID = re.compile(r"^[0-9a-f]{32}\.[a-z0-9]{1,8}$")


def resolve_upload(ref: str) -> Optional[str]:
    """Map a client-supplied reference to an existing upload path, or None.

    Only the final path component is considered, and it must be exactly a
    ``<uuid4 hex>.<ext>`` id produced by `save_upload`.
    """
    if not ref or not isinstance(ref, str):
        return None
    file_id = ref.strip().replace("\\", "/").split("/")[-1]
    if not _FILE_ID.match(file_id):
        return None
    path = os.path.join(UPLOAD_DIR, file_id)
    return path if os.path.isfile(path) else None


async def save_upload(file: UploadFile) -> Tuple[str, str]:
    """Stream an upload to disk. Returns ``(path, file_id)``.

    Raises HTTPException 400 for a disallowed extension and 413 when the file
    exceeds ``MAX_UPLOAD_BYTES`` (the partial file is removed).
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext or '(none)'}")

    file_id = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, file_id)
    written = 0
    try:
        with open(path, "wb") as out:
            while chunk := await file.read(_CHUNK):
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit",
                    )
                out.write(chunk)
    except BaseException:
        if os.path.exists(path):
            os.remove(path)
        raise
    return path, file_id


def log_rejected(ref: str) -> None:
    logger.warning(f"[uploads] Rejected unresolvable file reference: {ref!r}")
