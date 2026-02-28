from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException


class SPAStaticFiles(StaticFiles):
    """Serve index.html for any path that doesn't match a real file.

    Required for React Router (client-side routing): requests like
    /persona don't correspond to files on disk, so we fall back to
    index.html and let the browser-side router handle the path.

    Excludes /api/ and /main paths — those are handled by FastAPI/Gradio.
    """
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as e:
            if e.status_code == 404 and not path.startswith("api/") and not path.startswith("main"):
                return await super().get_response("index.html", scope)
            raise
