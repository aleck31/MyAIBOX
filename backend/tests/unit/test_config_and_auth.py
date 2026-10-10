"""Config validation and the Cognito-mode auth dependency."""
from __future__ import annotations

import os

import pytest

# API modules build the Cognito singleton at import time; give it dummy config so
# these tests don't depend on a real .env. Must run before the imports below.
os.environ.setdefault("USER_POOL_ID", "unit-test-pool")
os.environ.setdefault("CLIENT_ID", "unit-test-client")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

from fastapi import Depends, FastAPI, Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.middleware.sessions import SessionMiddleware  # noqa: E402

from backend.api import auth  # noqa: E402
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


def test_cors_explicit_origins_are_split_and_trimmed(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example, https://b.example ,")
    assert app_config.cors_config["allow_origins"] == ["https://a.example", "https://b.example"]


def test_cors_wildcard_is_rejected_with_credentials(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "*")
    with pytest.raises(RuntimeError):
        _ = app_config.cors_config


# ── get_auth_user (Cognito mode) ────────────────────────────────────────────

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(auth, "_sso_enabled", False)
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="unit-test")

    @app.post("/seed")
    async def seed(request: Request):
        request.session["auth_user"] = {"sub": "sub-1", "access_token": "tok"}
        return {}

    @app.get("/api/whoami")
    async def whoami(sub: str = Depends(auth.get_auth_user)):
        return {"sub": sub}

    return TestClient(app)


def test_rejects_request_without_session(client):
    assert client.get("/api/whoami").status_code == 401


def test_accepts_valid_token_and_returns_sub(client, monkeypatch):
    monkeypatch.setattr(auth.cognito_auth, "verify_token", lambda t: t)
    client.post("/seed")
    resp = client.get("/api/whoami")
    assert (resp.status_code, resp.json()) == (200, {"sub": "sub-1"})


def test_rejects_and_clears_session_when_token_invalid(client, monkeypatch):
    monkeypatch.setattr(auth.cognito_auth, "verify_token", lambda t: None)
    client.post("/seed")
    assert client.get("/api/whoami").status_code == 401
    # Session was cleared, so even a now-valid verifier can't resurrect it.
    monkeypatch.setattr(auth.cognito_auth, "verify_token", lambda t: t)
    assert client.get("/api/whoami").status_code == 401


def test_uses_refreshed_token_returned_by_verifier(client, monkeypatch):
    seen = []
    monkeypatch.setattr(auth.cognito_auth, "verify_token", lambda t: seen.append(t) or "tok-2")
    client.post("/seed")
    client.get("/api/whoami")
    client.get("/api/whoami")
    assert seen == ["tok", "tok-2"]
