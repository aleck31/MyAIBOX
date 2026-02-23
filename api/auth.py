# Copyright iX.
# SPDX-License-Identifier: MIT-0
import json
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import JSONResponse
from common.auth import cognito_auth
from common.logger import setup_logger

logger = setup_logger('api.auth')


# --- Auth helpers (migrated from webui/login) ---

def _log_unauth_access(request: Request, details: str):
    client_ip = request.headers.get('x-forwarded-for') or request.headers.get('x-real-ip') or request.client.host
    security_log = {
        'client_ip': client_ip, 'method': request.method,
        'request_url': str(request.url), 'user_agent': request.headers.get('user-agent'),
        'details': details,
    }
    logger.warning(f"SECURITY_ALERT: Unauthorized access - {json.dumps(security_log, indent=2)}")


def _handle_auth_failure(request: Request, error_detail: str, log_message: str):
    is_api_request = request.url.path.startswith('/api/') or request.headers.get('accept') == 'application/json'
    if is_api_request:
        raise HTTPException(status_code=401, detail=error_detail)
    else:
        if log_message:
            logger.debug(f"[Auth] {log_message}")
        raise HTTPException(status_code=302, headers={"Location": "/login"}, detail="Redirecting to login page")


def get_auth_user(request: Request):
    """Get current authorized username with token verification."""
    auth_user = request.session.get('auth_user')

    if not auth_user:
        _log_unauth_access(request, 'Attempted to access protected route without valid session')
        redirect_url = request.url.path
        _handle_auth_failure(request, "Not authenticated",
                             f"Redirecting unauthenticated user to login page, from: {redirect_url}")

    username = auth_user.get('username')
    if access_token := auth_user.get('access_token'):
        if validated_token := cognito_auth.verify_token(access_token):
            request.session['auth_user']['access_token'] = validated_token
            return username
        else:
            _log_unauth_access(request, f'Invalid or expired token for user: {username}')
            request.session.clear()
            _handle_auth_failure(request, "Authentication token expired or invalid",
                                 "Redirecting user with expired token to login page")
    else:
        logger.warning(f"Missing access token for user [{username}]")
        _handle_auth_failure(request, "Invalid authentication token",
                             "Redirecting user with invalid token to login page")


# --- Router ---

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def get_me(username: str = Depends(get_auth_user)):
    return {"username": username}


@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    auth_result = cognito_auth.authenticate(username, password)
    if auth_result['success']:
        request.session['auth_user'] = {
            'username': username,
            'access_token': auth_result['tokens']['AccessToken']
        }
        logger.debug(f"[Auth] Login successful for {username}")
        return {"success": True, "username": username}

    logger.warning(f"[Auth] Login failed for {username}")
    return JSONResponse({"success": False, "error": "Invalid username or password"}, status_code=401)


@router.post("/logout")
async def logout_api(request: Request, username: str = Depends(get_auth_user)):
    try:
        auth_user = request.session.get('auth_user')
        if auth_user and auth_user.get('access_token'):
            cognito_auth.logout(auth_user['access_token'])
        request.session.clear()
        logger.debug(f"[Auth] Logout for {username}")
        return {"success": True}
    except Exception as e:
        logger.error(f"[Auth] Logout error: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)
