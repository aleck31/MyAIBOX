# Copyright iX.
# SPDX-License-Identifier: MIT-0
import uuid
import os
from fastapi import APIRouter, Depends, UploadFile, File
from api.auth import get_auth_user

router = APIRouter(prefix="/upload", tags=["upload"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {
    # Images
    '.jpg', '.jpeg', '.png', '.gif', '.webp',
    # Documents
    '.pdf', '.csv', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.md',
    # Video
    '.mp4', '.webm', '.mov',
}


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    username: str = Depends(get_auth_user)
):
    """Upload a file and return its temporary path for use in chat."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return {"ok": False, "error": f"Unsupported file type: {ext}"}

    file_id = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, file_id)

    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)

    return {"ok": True, "path": path, "name": file.filename}


@router.get("/file/{file_id}")
async def serve_file(file_id: str, username: str = Depends(get_auth_user)):
    """Serve an uploaded file by its ID."""
    from fastapi.responses import FileResponse
    # Sanitize: only allow filename, no path traversal
    if '/' in file_id or '\\' in file_id or '..' in file_id:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "Invalid file ID"}, status_code=400)
    path = os.path.join(UPLOAD_DIR, file_id)
    if not os.path.isfile(path):
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "File not found"}, status_code=404)
    return FileResponse(path)
