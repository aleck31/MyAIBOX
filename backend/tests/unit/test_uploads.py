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


def test_resolve_accepts_bare_id_url_and_returned_path(upload_dir):
    (upload_dir / VALID_ID).write_bytes(b"x")
    expected = str(upload_dir / VALID_ID)
    assert uploads.resolve_upload(VALID_ID) == expected
    assert uploads.resolve_upload(f"/api/upload/{VALID_ID}") == expected
    assert uploads.resolve_upload(f"storage/uploads/{VALID_ID}") == expected


@pytest.mark.parametrize("ref", [
    "", None, "..", "../../etc/passwd.png", "/etc/passwd", "/etc/shadow.png",
    "notauuid.png", "a" * 32, "a" * 32 + ".png/..", "A" * 32 + ".png",
    ".env", "storage/uploads/../../.env",
])
def test_resolve_rejects_anything_that_is_not_a_stored_id(upload_dir, ref):
    assert uploads.resolve_upload(ref) is None


def test_resolve_returns_none_when_file_missing(upload_dir):
    assert uploads.resolve_upload(VALID_ID) is None


def test_resolve_rejects_directory_named_like_an_id(upload_dir):
    (upload_dir / VALID_ID).mkdir()
    assert uploads.resolve_upload(VALID_ID) is None


async def test_save_writes_file_and_returns_resolvable_id(upload_dir):
    path, file_id = await uploads.save_upload(_upload("photo.PNG", b"data"))
    assert file_id.endswith(".png")
    assert open(path, "rb").read() == b"data"
    assert uploads.resolve_upload(file_id) == path


async def test_save_rejects_disallowed_extension(upload_dir):
    with pytest.raises(HTTPException) as e:
        await uploads.save_upload(_upload("evil.sh", b"x"))
    assert e.value.status_code == 400
    assert list(upload_dir.iterdir()) == []


async def test_save_rejects_oversize_and_cleans_up(upload_dir, monkeypatch):
    monkeypatch.setattr(uploads, "MAX_UPLOAD_BYTES", 10)
    monkeypatch.setattr(uploads, "_CHUNK", 4)
    with pytest.raises(HTTPException) as e:
        await uploads.save_upload(_upload("big.txt", b"x" * 11))
    assert e.value.status_code == 413
    assert list(upload_dir.iterdir()) == []


async def test_save_allows_exactly_the_limit(upload_dir, monkeypatch):
    monkeypatch.setattr(uploads, "MAX_UPLOAD_BYTES", 10)
    path, _ = await uploads.save_upload(_upload("ok.txt", b"x" * 10))
    assert len(open(path, "rb").read()) == 10
