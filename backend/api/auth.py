# Copyright iX.
# SPDX-License-Identifier: MIT-0
import json
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import JSONResponse

from core.config import env_config
from common.auth import cognito_auth
from common.logger import setup_logger
from common.sso import introspect as sso_introspect, build_logout_url, SSOError

logger = setup_logger('api.auth')

_sso_enabled: bool = env_config.sso_config['enabled']
_sso_cookie: str = env_config.sso_config['cookie_name']


# --- helpers ---

def _log_unauth_access(request: Request, details: str):
    client_ip = request.headers.get('x-forwarded-for') or request.headers.get('x-real-ip') or request.client.host
    security_log = {
        'client_ip': client_ip, 'method': request.method,
        'request_url': str(request.url), 'user_agent': request.headers.get('user-agent'),
        'details': details,
    }
    logger.warning(f"SECURITY_ALERT: Unauthorized access - {json.dumps(security_log, indent=2)}")


def _unauthorized(request: Request, error_detail: str):
    """Raise 401 for API callers, 302 to /login for page requests."""
    is_api = request.url.path.startswith('/api/') or request.headers.get('accept') == 'application/json'
    if is_api:
        raise HTTPException(status_code=401, detail=error_detail)
    raise HTTPException(status_code=302, headers={"Location": "/login"}, detail="Redirecting to login page")


# --- auth dependency ---

async def get_auth_user(request: Request) -> str:
    """Return the current user's Cognito `sub`, or raise 401/302.

    - SSO mode: validate the SSO session cookie via the provider's /introspect.
    - Cognito mode: validate local session + refresh access token as needed.
    """
    if _sso_enabled:
        sid = request.cookies.get(_sso_cookie)
        if not sid:
            _log_unauth_access(request, 'No SSO cookie')
            _unauthorized(request, "Not authenticated")

        try:
            user = await sso_introspect(sid)
        except SSOError as e:
            logger.error(f"[Auth] SSO introspection unavailable: {e}")
            raise HTTPException(status_code=503, detail="auth service unavailable")

        if not user:
            _log_unauth_access(request, 'SSO sid rejected')
            _unauthorized(request, "Session expired")

        request.state.user = {
            'sub': user.sub,
            'email': user.email,
            'username': user.username,
        }
        return user.sub

    # --- Cognito mode ---
    auth_user = request.session.get('auth_user')
    if not auth_user:
        _log_unauth_access(request, 'No local session')
        _unauthorized(request, "Not authenticated")

    sub = auth_user.get('sub')
    access_token = auth_user.get('access_token')
    if not sub or not access_token:
        request.session.clear()
        _unauthorized(request, "Invalid authentication token")

    validated = cognito_auth.verify_token(access_token)
    if not validated:
        _log_unauth_access(request, f'Invalid or expired token for sub [{sub}]')
        request.session.clear()
        _unauthorized(request, "Authentication token expired or invalid")

    request.session['auth_user']['access_token'] = validated
    cached = cognito_auth.user_info.get(sub, {})
    request.state.user = {
        'sub': sub,
        'username': cached.get('username', ''),
        'email': cached.get('attributes', {}).get('email', ''),
    }
    return sub


# --- router ---

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def get_me(request: Request, sub: str = Depends(get_auth_user)):
    user = getattr(request.state, 'user', {}) or {}
    # `username` = Cognito username (e.g. `aleck`) for UI display.
    # `sub` = stable user id used as DDB partition key. Keep them separate so
    # the frontend can show a friendly name without touching identity keys.
    return {
        'sub': sub,
        'username': user.get('username') or sub,
        'email': user.get('email', ''),
    }


@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if _sso_enabled:
        raise HTTPException(status_code=404, detail="Password login disabled in SSO mode")

    auth_result = cognito_auth.authenticate(username, password)
    if auth_result['success']:
        request.session['auth_user'] = {
            'sub': auth_result['sub'],
            'access_token': auth_result['tokens']['AccessToken'],
        }
        logger.debug(f"[Auth] Login successful for {username} (sub={auth_result['sub']})")
        return {"success": True, "username": auth_result['sub']}

    logger.warning(f"[Auth] Login failed for {username}")
    return JSONResponse({"success": False, "error": "Invalid username or password"}, status_code=401)


@router.post("/logout")
async def logout_api(request: Request, sub: str = Depends(get_auth_user)):
    if _sso_enabled:
        # Logout is owned by the SSO provider; frontend should navigate there directly.
        return {"success": True, "redirect": build_logout_url()}

    try:
        auth_user = request.session.get('auth_user')
        if auth_user and auth_user.get('access_token'):
            cognito_auth.logout(auth_user['access_token'])
        request.session.clear()
        logger.debug(f"[Auth] Logout for sub={sub}")
        return {"success": True}
    except Exception as e:
        logger.error(f"[Auth] Logout error: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)
