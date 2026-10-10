"""Chat attachments: client-supplied paths must never reach the filesystem."""
from __future__ import annotations

import os

import pytest

# API modules build the Cognito singleton at import time; give it dummy config so
# these tests don't depend on a real .env. Must run before the imports below.
os.environ.setdefault("USER_POOL_ID", "unit-test-pool")
os.environ.setdefault("CLIENT_ID", "unit-test-client")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

from backend.api import chat  # noqa: E402
from backend.common import uploads  # noqa: E402

VALID_ID = "b" * 32 + ".png"


# ── chat attachments ────────────────────────────────────────────────────────

@pytest.fixture
def stored_upload(tmp_path, monkeypatch):
    monkeypatch.setattr(uploads, "UPLOAD_DIR", str(tmp_path))
    (tmp_path / VALID_ID).write_bytes(b"x")
    return str(tmp_path / VALID_ID)


def _binary(data: str) -> dict:
    return {"type": "binary", "mimeType": "image/png", "data": data}


def test_chat_keeps_stored_upload(stored_upload):
    text, files = chat._extract_text_and_files([{"type": "text", "text": "hi"}, _binary(f"storage/uploads/{VALID_ID}")])
    assert text == "hi"
    assert files == [stored_upload]


@pytest.mark.parametrize("evil", ["/etc/passwd", "/home/ubuntu/repos/my-aibox/.env", "../../secret.png", "/tmp/x.png"])
def test_chat_drops_client_supplied_paths(stored_upload, evil):
    _, files = chat._extract_text_and_files([_binary(evil)])
    assert files == []
