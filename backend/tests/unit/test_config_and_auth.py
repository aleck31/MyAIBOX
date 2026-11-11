"""Config validation and the SSO auth dependency."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.api import auth  # noqa: E402
from backend.common import sso  # noqa: E402
from backend.core import config as config_module  # noqa: E402
from backend.core.config import app_config  # noqa: E402


# ── .env location ───────────────────────────────────────────────────────────

def test_dotenv_is_loaded_from_the_project_root():
    root = config_module.env_path.parent
    assert (root / "pyproject.toml").is_file(), f"{config_module.env_path} is not at the project root"
    assert config_module.env_path.name == ".env"


# ── CORS ────────────────────────────────────────────────────────────────────

def test_cors_unset_means_same_origin_only(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert app_config.cors_config["allow_origins"] == []


def test_cors_wildcard_is_rejected_with_credentials(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "*")
    with pytest.raises(RuntimeError):
        _ = app_config.cors_config


# ── get_auth_user (SSO) ─────────────────────────────────────────────────────

@pytest.fixture
def client(monkeypatch):
    sso._cache.clear()
    app = FastAPI()
    app.add_exception_handler(auth.AuthRequired, auth.handle_auth_required)

    @app.get("/api/whoami")
    async def whoami(sub: str = Depends(auth.get_auth_user)):
        return {"sub": sub}

    @app.get("/chat/page")
    async def page(sub: str = Depends(auth.get_auth_user)):
        return {"sub": sub}

    return TestClient(app, follow_redirects=False)


def _auth_service(monkeypatch, verdicts: list):
    """Fake /introspect: each call pops the next verdict (a dict, or an Exception to raise)."""
    async def call(sid):
        v = verdicts.pop(0)
        if isinstance(v, Exception):
            raise v
        return v
    monkeypatch.setattr(sso, "_call_introspect", call)


VALID = {"valid": True, "sub": "sub-1", "username": "aleck", "email": "a@x", "agent_ids": ["x-main"], "exp": 9999999999}


def test_no_cookie_api_gets_401_json_with_the_login_url_and_pages_get_302(client):
    r = client.get("/api/whoami")
    assert r.status_code == 401 and r.json()["error"] == "unauthorized" and "/login?redirect=" in r.json()["login_url"]
    r = client.get("/chat/page")
    assert r.status_code == 302 and "/login?redirect=" in r.headers["location"]


def test_the_login_redirect_is_https_behind_the_tls_proxy(client):
    """TLS ends at CloudFront, so the app sees http; the auth service rejects an http redirect with a 400."""
    r = client.get("http://aibox.myners.net/api/whoami")
    assert "redirect=https%3A%2F%2Faibox.myners.net" in r.json()["login_url"]


def test_valid_sid_is_accepted_and_cached(client, monkeypatch):
    _auth_service(monkeypatch, [VALID])
    client.cookies.set(auth._sso_cookie, "sid-ok")
    assert client.get("/api/whoami").json() == {"sub": "sub-1"}
    assert client.get("/api/whoami").json() == {"sub": "sub-1"}      # second call from the cache (one verdict queued)


def test_rejected_sid_gets_401(client, monkeypatch):
    _auth_service(monkeypatch, [{"valid": False, "reason": "expired"}])
    client.cookies.set(auth._sso_cookie, "sid-bad")
    assert client.get("/api/whoami").status_code == 401


def test_auth_service_down_serves_the_stale_grace_then_503(client, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(sso, "_now", lambda: now[0])
    _auth_service(monkeypatch, [VALID, OSError("down"), OSError("down")])
    client.cookies.set(auth._sso_cookie, "sid-ok")
    assert client.get("/api/whoami").status_code == 200
    now[0] += sso._sso_conf["cache_ttl"] + 1                          # cache expired, inside the grace
    assert client.get("/api/whoami").status_code == 200
    now[0] += sso._sso_conf["stale_grace_ttl"]                         # grace over
    assert client.get("/api/whoami").status_code == 503


def test_logout_drops_the_sid_from_the_local_cache(client, monkeypatch):
    """Otherwise the app kept accepting a logged-out sid for up to the cache TTL."""
    _auth_service(monkeypatch, [VALID, {"valid": False, "reason": "not_found"}])
    app = client.app
    app.include_router(auth.router, prefix="/api")
    client.cookies.set(auth._sso_cookie, "sid-ok")
    assert client.get("/api/whoami").status_code == 200
    assert client.post("/api/auth/logout").json()["success"]
    assert client.get("/api/whoami").status_code == 401
