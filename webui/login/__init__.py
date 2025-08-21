import json
from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from common.auth import cognito_auth
from common.logger import logger


# Create router
router = APIRouter()

# Setup templates
templates = Jinja2Templates(directory="webui/login")

def log_unauth_access(request: Request, details: str):
    """Log unauthorized access attempts with detailed information"""
    # Get client IP - check for proxy headers first
    client_ip = request.headers.get('x-forwarded-for') or request.headers.get('x-real-ip') or request.client.host

    # Build security log entry
    security_log = {
        'client_ip': client_ip,
        'method': request.method,
        'request_url': str(request.url),
        'user_agent': request.headers.get('user-agent'),
        'details': details,
    }

    # Log as JSON for better parsing
    logger.warning(f"SECURITY_ALERT: Unauthorized access - {json.dumps(security_log, indent=2)}")


def handle_auth_failure(request: Request, error_detail: str, log_message: str):
    """Handle authentication failure with appropriate response based on request type

    Raises:
        HTTPException: Either a 401 error or a 302 redirect
    """
    # Check if this is an API request or a UI request
    is_api_request = request.url.path.startswith('/api/') or request.headers.get('accept') == 'application/json'
    
    if is_api_request:
        # For API requests, return a 401 error
        raise HTTPException(status_code=401, detail=error_detail)
    else:
        # For UI requests, redirect to the login page
        if log_message:
            logger.debug(f"[Auth] {log_message}")
        raise HTTPException(status_code=302, headers={"Location": "/login"}, detail="Redirecting to login page")


# Dependency to get the current user or redirects to login page
def get_auth_user(request: Request):
    """Get current authorized username with token verification"""
    auth_user = request.session.get('auth_user')

    if not auth_user:
        # Log unauthorized access attempt
        log_unauth_access(
            request=request,
            details='Attempted to access protected route without valid session'
        )
        # Handle authentication failure
        redirect_url = request.url.path
        handle_auth_failure(
            request, 
            "Not authenticated",
            f"Redirecting unauthenticated user to login page, from: {redirect_url}"
        )

    username = auth_user.get('username')
    if access_token := auth_user.get('access_token'):
        # Verify token with Cognito (refresh if expired)
        if validated_token := cognito_auth.verify_token(access_token):
            request.session['auth_user']['access_token'] = validated_token
            return username
        else:
            log_unauth_access(
                request=request,
                details=f'Invalid or expired token for user: {username}'
            )
            # Clear invalid session
            request.session.clear()
            # Handle authentication failure
            handle_auth_failure(
                request, 
                "Authentication token expired or invalid",
                "Redirecting user with expired token to login page"
            )
    else:
        # Log token verification issues for debugging
        logger.warning(f"Missing access token for user [{username}]")
        # Handle authentication failure
        handle_auth_failure(
            request, 
            "Invalid authentication token",
            "Redirecting user with invalid token to login page"
        )


@router.get('/login')
async def login_page(request: Request, error: str = None):
    """Render login page"""
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": error}
    )


@router.post('/auth')
async def auth(request: Request, username: str = Form(...), password: str = Form(...)):
    """Handle authentication"""
    auth_result = cognito_auth.authenticate(username, password)
    if auth_result['success']:
        # Store user info and token in session
        request.session['auth_user'] = {
            'username': username,
            'access_token': auth_result['tokens']['AccessToken']
        }
        logger.debug(f"[Auth] Authentication successful for {username}")
        
        # Create response with redirect
        response = RedirectResponse(url='/main', status_code=303)
        return response

    # Log failed authentication attempt
    log_unauth_access(
        request=request,
        details=f'Failed authentication attempt for user: {username}'
    )

    # Redirect back to login with error
    return RedirectResponse(
        url=f'/login?error=Invalid username or password',
        status_code=303
    )


@router.get('/logout')
async def logout(request: Request):
    """Handle logout request"""
    try:
        auth_user = request.session.get('auth_user')
        if auth_user and auth_user.get('access_token'):
            cognito_auth.logout(auth_user['access_token'])
        # logger.debug(f"[Auth] Session data before clear: {dict(request.session)}")
        request.session.clear()
        logger.debug(f"[Auth] Session cleared for {auth_user.get('username')}")

        # response with redirect
        return RedirectResponse(url='/login')

    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(status_code=500, detail="Logout failed")
