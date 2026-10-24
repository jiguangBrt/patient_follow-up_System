"""Render static page templates with the reverse proxy's application prefix."""

from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse

WEB_ROOT = Path(__file__).resolve().parent / "web"


def page_response(name: str, request: Request) -> HTMLResponse:
    prefix = request.scope.get("root_path", "").rstrip("/")
    content = (WEB_ROOT / name).read_text(encoding="utf-8")
    for attribute in ("href", "src"):
        content = content.replace(f'{attribute}="/', f'{attribute}="{prefix}/')
    content = content.replace(
        "<head>",
        f'<head><script src="{prefix}/static/paths.js?v=20261022"></script>',
        1,
    )
    return HTMLResponse(content, headers={"Cache-Control": "no-store"})
