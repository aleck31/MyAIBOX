"""Upload storage — the boundary between client-supplied references and the filesystem."""
from __future__ import annotations

import io

import pytest
from fastapi import HTTPException, UploadFile

from backend.common import uploads

VALID_ID = "a" * 32 + ".png"


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(uploads, "UPLOAD_DIR", str(tmp_path))
    return tmp_path


def _upload(name: str, data: bytes) -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename=name)


@pytest.mark.parametrize("ref", [
    "", None, "..", "../../etc/passwd.png", "/etc/passwd", "/etc/shadow.png",
    "notauuid.png", "a" * 32, "a" * 32 + ".png/..", "A" * 32 + ".png",
    ".env", "storage/uploads/../../.env",
])
def test_resolve_rejects_anything_that_is_not_a_stored_id(upload_dir, ref):
    assert uploads.resolve_upload(ref, "alice") is None


def test_resolve_rejects_directory_named_like_an_id(upload_dir):
    (upload_dir / VALID_ID).mkdir()
    assert uploads.resolve_upload(VALID_ID, "alice") is None


async def test_save_rejects_disallowed_extension(upload_dir):
    with pytest.raises(HTTPException) as e:
        await uploads.save_upload(_upload("evil.sh", b"x"), "alice")
    assert e.value.status_code == 400
    assert list(upload_dir.iterdir()) == []


async def test_save_rejects_oversize_and_cleans_up(upload_dir, monkeypatch):
    monkeypatch.setattr(uploads, "MAX_UPLOAD_BYTES", 10)
    monkeypatch.setattr(uploads, "_CHUNK", 4)
    with pytest.raises(HTTPException) as e:
        await uploads.save_upload(_upload("big.txt", b"x" * 11), "alice")
    assert e.value.status_code == 413
    assert list(upload_dir.iterdir()) == []


async def test_owner_can_resolve_but_other_user_cannot(upload_dir):
    _, file_id = await uploads.save_upload(_upload("a.png", b"x"), "alice")
    assert uploads.resolve_upload(file_id, "alice")
    assert uploads.resolve_upload(file_id, "mallory") is None


async def test_owner_sidecar_is_not_addressable_as_an_upload(upload_dir):
    _, file_id = await uploads.save_upload(_upload("a.png", b"x"), "alice")
    assert uploads.resolve_upload(file_id + uploads.OWNER_SUFFIX, "alice") is None


def test_legacy_file_without_sidecar_stays_accessible(upload_dir):
    (upload_dir / VALID_ID).write_bytes(b"x")
    assert uploads.resolve_upload(VALID_ID, "anyone")
