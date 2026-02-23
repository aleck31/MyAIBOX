# Copyright iX.
# SPDX-License-Identifier: MIT-0
import os
import uvicorn
import gradio as gr
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException


class SPAStaticFiles(StaticFiles):
    """Serve index.html for any path that doesn't match a real file.

    Required for React Router (client-side routing): requests like
    /ui/persona don't correspond to files on disk, so we fall back to
    index.html and let the browser-side router handle the path.
    """
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as e:
            if e.status_code == 404:
                return await super().get_response("index.html", scope)
            raise
from core.config import app_config
from common.logger import setup_logger, logger
from genai.models.model_manager import model_manager
from api.auth import get_auth_user
from webui.main import create_main_interface
from api.auth import router as auth_api_router
from api.assistant import router as assistant_router
from api.persona import router as persona_router
from api.text import router as text_router
from api.summary import router as summary_router
from api.asking import router as asking_router
from api.vision import router as vision_router
from api.draw import router as draw_router
from api.settings import router as settings_router
from api.upload import router as upload_router


# Get configurations from app_config
server_config = app_config.server_config
security_config = app_config.security_config
cors_config = app_config.cors_config

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app"""
    try:
        # Startup
        logger.info("Initializing application...")
        # Initialize default LLM models if none exist
        model_manager.init_default_models()
        logger.info("Application initialization complete")
        yield
    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down application...")

# Create FastAPI app
app = FastAPI(lifespan=lifespan)

# Add session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=security_config['secret_key'],
    session_cookie="session",
    max_age=None,  # Let Cognito handle token expiration
    same_site="lax",  # Prevents CSRF while allowing normal navigation
    https_only=security_config['ssl_enabled'],  # Enable for production with HTTPS
    path="/",  # Make cookie available for all paths
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_config['allow_origins'],
    allow_credentials=True,
    allow_methods=cors_config['allow_methods'],
    allow_headers=cors_config['allow_headers'],
    expose_headers=["*"],
    max_age=3600
)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "OK!"}

# Include API routes
app.include_router(auth_api_router, prefix="/api")
app.include_router(assistant_router, prefix="/api")
app.include_router(persona_router, prefix="/api")
app.include_router(text_router, prefix="/api")
app.include_router(summary_router, prefix="/api")
app.include_router(asking_router, prefix="/api")
app.include_router(vision_router, prefix="/api")
app.include_router(draw_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(upload_router, prefix="/api")

# Create main interface
main_ui = create_main_interface()

# Load and process CSS with Svelte class name
SVELTE_CLASS = 'svelte-99kmwu'
with open('webui/styles.css', 'r') as f:
    css_content = f.read().replace('{SVELTE_CLASS}', SVELTE_CLASS)

# Mount Gradio app with auth_dependency
app = gr.mount_gradio_app(
    app, 
    main_ui, 
    path="/main",
    auth_dependency=get_auth_user,
    footer_links=['settings'],
    css=css_content,
    theme="Ocean"
)

# Mount React SPA at root — MUST be after all other mounts (API, Gradio)
# so that /api/*, /main, /auth, /logout are handled first.
if os.path.exists("frontend/dist"):
    app.mount("/", SPAStaticFiles(directory="frontend/dist", html=True), name="react-ui")

if __name__ == "__main__":
    # Start server with configuration from app_config
    uvicorn.run(
        app,
        host=server_config['host'],
        port=server_config['port'],
        log_level=server_config['log_level']
    )
