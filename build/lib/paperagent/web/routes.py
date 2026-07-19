from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
        "manifest-src 'self'; script-src 'self'; style-src 'self'; worker-src 'self'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


def _asset_root() -> Path:
    return Path(str(files("paperagent.web").joinpath("assets")))


def register_web_routes(app: FastAPI) -> None:
    root = _asset_root()
    app.mount(
        "/app-static",
        StaticFiles(directory=str(root), check_dir=True),
        name="paperagent-web-assets",
    )

    @app.get("/app/manifest.webmanifest", include_in_schema=False)
    async def web_manifest() -> FileResponse:
        return FileResponse(
            root / "manifest.webmanifest",
            media_type="application/manifest+json",
            headers={"Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff"},
        )

    @app.get("/app/service-worker.js", include_in_schema=False)
    async def service_worker() -> FileResponse:
        return FileResponse(
            root / "service-worker.js",
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-cache",
                "Service-Worker-Allowed": "/app",
                "X-Content-Type-Options": "nosniff",
            },
        )

    async def shell() -> FileResponse:
        return FileResponse(root / "index.html", media_type="text/html", headers=_SECURITY_HEADERS)

    app.add_api_route("/app", shell, methods=["GET"], include_in_schema=False)
    app.add_api_route("/app/", shell, methods=["GET"], include_in_schema=False)
    app.add_api_route("/app/{task_id}", shell, methods=["GET"], include_in_schema=False)
