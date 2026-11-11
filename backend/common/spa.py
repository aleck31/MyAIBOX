from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException


class SPAStaticFiles(StaticFiles):
    """Serve index.html for any path that doesn't match a real file.

    Required for React Router (client-side routing): requests like
    /chat/assistant don't correspond to files on disk, so we fall back to
    index.html and let the browser-side router handle the path.
    """
    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as e:
            if e.status_code == 404 and not path.startswith("api/"):
                response = await super().get_response("index.html", scope)
            else:
                raise
        response.headers["Cache-Control"] = cache_control(path)
        return response


def cache_control(path: str) -> str:
    """Cache policy for a file of the built frontend.

    Without one, browsers guess a lifetime from Last-Modified (about a tenth of the file's age): a phone kept an
    old manifest and old icons, so a new app icon did not show even after reinstalling. Files under assets/
    have a content hash in their name and never change, so they are cached for good; everything else (index.html,
    the manifest, icons) is revalidated on every use, which costs a 304 when nothing changed.
    """
    if path.startswith("assets/"):
        return "public, max-age=31536000, immutable"
    return "no-cache"
