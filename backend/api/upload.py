# Copyright iX.
# SPDX-License-Identifier: MIT-0
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from backend.api.auth import get_auth_user
from backend.common.uploads import resolve_upload, save_upload

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    username: str = Depends(get_auth_user)
):
    """Upload a file and return its temporary path for use in chat."""
    try:
        path, file_id = await save_upload(file)
    except HTTPException as e:
        return {"ok": False, "error": e.detail}
    return {"ok": True, "path": path, "name": file.filename, "file_id": file_id}


@router.get("/file/{file_id}")
@router.get("/{file_id}")
async def serve_file(file_id: str, username: str = Depends(get_auth_user)):
    """Serve an uploaded file by its ID (both URL shapes are used by the frontend)."""
    path = resolve_upload(file_id)
    if not path:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path)
