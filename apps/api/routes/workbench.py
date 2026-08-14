from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["workbench"])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.get("/workbench", response_class=HTMLResponse)
def workbench_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("workbench.html", {"request": request})
