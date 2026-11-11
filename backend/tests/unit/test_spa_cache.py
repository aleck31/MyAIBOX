"""The built frontend tells browsers how long to keep each file.

Regression: no Cache-Control at all, so a phone kept an old manifest and old icons and a new app icon did not show
even after reinstalling the app.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.common.spa import SPAStaticFiles


def test_hashed_assets_are_kept_and_everything_else_is_revalidated(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "index-abc123.js").write_text("x")
    (tmp_path / "index.html").write_text("<html></html>")
    (tmp_path / "manifest.webmanifest").write_text("{}")
    (tmp_path / "pwa-512x512.png").write_bytes(b"png")
    app = FastAPI()
    app.mount("/", SPAStaticFiles(directory=str(tmp_path), html=True))
    client = TestClient(app)

    assert "immutable" in client.get("/assets/index-abc123.js").headers["cache-control"]
    for path in ("/manifest.webmanifest", "/pwa-512x512.png", "/", "/chat/assistant"):   # the last one: SPA fallback
        assert client.get(path).headers["cache-control"] == "no-cache", path
