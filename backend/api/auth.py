# Copyright iX.
# SPDX-License-Identifier: MIT-0
"""Authentication: Myners SSO only (standards/SSO-INTEGRATION-GUIDE.md).

The app reads the `myners_sid` cookie and validates it with the auth service's /introspect. It holds no tokens and
no session of its own, and never writes the cookie: login and logout happen on the auth service.
"""
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.common.logger import setup_logger
from backend.common.sso import SSOError, build_login_url
from backend.common.sso import introspect as sso_introspect
from backend.common.sso import invalidate as sso_invalidate
from backend.core.config import app_config, env_config

logger = setup_logger('api.auth')

_sso_cookie: str = env_config.sso_config['cookie_name']


class AuthRequired(Exception):
    """Not logged in: 401 JSON for API calls, 302 to the auth service for pages (see `handle_auth_required`)."""

    def __init__(self, return_to: str):
        self.login_url = build_login_url(return_to)


def handle_auth_required(request: Request, exc: AuthRequired):
    is_api = request.url.path.startswith('/api/') or 'application/json' in request.headers.get('accept', '')
    if is_api:
        return JSONResponse({"error": "unauthorized", "login_url": exc.login_url}, status_code=401)
    return JSONResponse({"error": "unauthorized"}, status_code=302, headers={"Location": exc.login_url})


def _log_unauth_access(request: Request, details: str):
    client_ip = request.headers.get('x-forwarded-for') or request.headers.get('x-real-ip') or request.client.host
    security_log = {
        'client_ip': client_ip, 'method': request.method,
        'request_url': str(request.url), 'user_agent': request.headers.get('user-agent'),
        'details': details,
    }
    logger.warning(f"SECURITY_ALERT: Unauthorized access - {json.dumps(security_log, indent=2)}")


def _return_to(request: Request) -> str:
    """Where the auth service sends the user back to: the page they asked for (the app's home for API calls).

    TLS ends at CloudFront, so the app sees plain http; the auth service only accepts an https redirect (and the
    SSO cookie is Secure), so the URL is made https for anything but a local host.
    """
    if request.url.path.startswith('/api/'):
        url = request.headers.get('referer') or str(request.base_url)
    else:
        url = str(request.url)
    host = request.url.hostname or ''
    if url.startswith('http://') and host not in ('localhost', '127.0.0.1'):
        url = 'https://' + url[len('http://'):]
    return url


async def get_auth_user(request: Request) -> str:
    """Return the current user's `sub`, or raise AuthRequired (401 / 302) or 503 when the auth service is down."""
    sid = request.cookies.get(_sso_cookie)
    if not sid:
        _log_unauth_access(request, 'No SSO cookie')
        raise AuthRequired(_return_to(request))

    try:
        user = await sso_introspect(sid)
    except SSOError as e:
        logger.error(f"[Auth] SSO introspection unavailable: {e}")
        raise HTTPException(status_code=503, detail="auth service unavailable")

    if not user:
        _log_unauth_access(request, 'SSO sid rejected')
        raise AuthRequired(_return_to(request))

    request.state.user = {'sub': user.sub, 'email': user.email, 'username': user.username, 'agent_ids': list(user.agent_ids)}
    return user.sub


def is_admin(sub: str) -> bool:
    """True when `sub` is listed in ADMIN_SUBS."""
    return sub in app_config.admin_subs


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def get_me(request: Request, sub: str = Depends(get_auth_user)):
    """Current user, in the guide's /api/me shape. `sub` is the stable id; `username` is for display."""
    user = getattr(request.state, 'user', {}) or {}
    return {
        'sub': sub,
        'username': user.get('username') or sub,
        'email': user.get('email', ''),
        'agent_ids': user.get('agent_ids', []),
    }


@router.post("/logout")
async def logout_api(request: Request):
    """Drop this sid from the local cache; the browser then goes to the auth service's /logout.

    Without the invalidate this app would keep accepting the sid for up to the cache TTL after logout.
    """
    if sid := request.cookies.get(_sso_cookie):
        sso_invalidate(sid)
    return {"success": True}
