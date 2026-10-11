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
    (tmp_path / (VALID_ID + uploads.OWNER_SUFFIX)).write_text("alice")
    return str(tmp_path / VALID_ID)


def _binary(data: str) -> dict:
    return {"type": "binary", "mimeType": "image/png", "data": data}


def test_chat_keeps_stored_upload(stored_upload):
    text, files = chat._extract_text_and_files([{"type": "text", "text": "hi"}, _binary(f"storage/uploads/{VALID_ID}")], owner="alice")
    assert text == "hi"
    assert files == [stored_upload]


@pytest.mark.parametrize("evil", ["/etc/passwd", "/home/ubuntu/repos/my-aibox/.env", "../../secret.png", "/tmp/x.png"])
def test_chat_drops_client_supplied_paths(stored_upload, evil):
    _, files = chat._extract_text_and_files([_binary(evil)], owner="alice")
    assert files == []


def test_chat_drops_another_users_upload(stored_upload):
    _, files = chat._extract_text_and_files([_binary(f"storage/uploads/{VALID_ID}")], owner="mallory")
    assert files == []


def test_chat_ignores_attachments_without_an_owner(stored_upload):
    """History rendering passes no owner and only needs the text."""
    text, files = chat._extract_text_and_files([{"type": "text", "text": "hi"}, _binary(VALID_ID)])
    assert (text, files) == ("hi", [])


# ── AG-UI 1.x content parts ──────────────────────────────────────────────────

def _image_part(value: str) -> dict:
    """What the AG-UI 1.x client sends for an attachment (it converts the app's binary part to this)."""
    return {"type": "image", "source": {"type": "data", "value": value, "mime_type": "image/png"}}


def test_chat_reads_attachments_sent_as_ag_ui_1_media_parts(stored_upload):
    """Regression: only `binary` parts were read, so since the 1.x upgrade every image was silently dropped
    and the model answered "I don't see an image"."""
    text, files = chat._extract_text_and_files([{"type": "text", "text": "hi"}, _image_part(f"storage/uploads/{VALID_ID}")], owner="alice")
    assert (text, files) == ("hi", [stored_upload])
    _, files = chat._extract_text_and_files([_image_part("/etc/passwd")], owner="alice")
    assert files == []                                           # same path checks as before


def test_a_request_with_a_legacy_binary_part_is_accepted():
    """Regression: a page from before the upgrade sent `binary`, and the request failed with a 422."""
    from ag_ui.core import RunAgentInput
    raw = {"threadId": "t", "runId": "r", "tools": [], "context": [], "state": {}, "forwardedProps": {},
           "messages": [{"id": "u1", "role": "user", "content": [
               {"type": "text", "text": "look"},
               {"type": "binary", "mimeType": "image/png", "data": f"storage/uploads/{VALID_ID}", "filename": "a.png"}]}]}
    body = RunAgentInput.model_validate(chat._upgrade_legacy_parts(raw))
    part = body.messages[0].content[1].model_dump()
    assert part["type"] == "image" and chat._attachment_ref(part) == f"storage/uploads/{VALID_ID}"
