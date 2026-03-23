import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text

from apps.api.routes.content import router as content_router
from apps.api.routes.delivery import router as delivery_router
from apps.api.routes.documents import router as documents_router
from apps.api.routes.evals import router as evals_router
from apps.api.routes.ingestion import router as ingestion_router
from apps.api.routes.memory import router as memory_router
from apps.api.routes.ops import router as ops_router
from apps.api.routes.registry import router as registry_router
from apps.api.routes.research import router as research_router
from apps.api.routes.search import router as search_router
from apps.api.routes.tasks import router as tasks_router
from packages.core.config import get_settings
from packages.core.logging import bind_log_context, clear_log_context, configure_logging
from packages.core.utils import utc_now_iso
from packages.db.session import SessionLocal
from packages.tasks.metrics import metrics_content_type, metrics_payload, record_api_request

LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.settings = settings
    yield


app = FastAPI(title="Invest Agent API", lifespan=lifespan)
app.include_router(ingestion_router)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(research_router)
app.include_router(content_router)
app.include_router(memory_router)
app.include_router(delivery_router)
app.include_router(tasks_router)
app.include_router(evals_router)
app.include_router(ops_router)
app.include_router(registry_router)


def _request_path_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    return request.url.path


@app.middleware("http")
async def request_observability_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    started = time.perf_counter()

    with bind_log_context(request_id=request_id):
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001
            elapsed = max(time.perf_counter() - started, 0.0)
            record_api_request(
                method=request.method,
                path=_request_path_template(request),
                status_code=500,
                duration_seconds=elapsed,
            )
            LOGGER.exception("request failed method=%s path=%s", request.method, request.url.path)
            raise

    elapsed = max(time.perf_counter() - started, 0.0)
    record_api_request(
        method=request.method,
        path=_request_path_template(request),
        status_code=response.status_code,
        duration_seconds=elapsed,
    )
    response.headers["X-Request-ID"] = request_id
    clear_log_context()
    return response


@app.get("/healthz", tags=["system"])
async def healthz(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
        "timestamp": utc_now_iso(),
    }


@app.get("/readyz", tags=["system"])
async def readyz(request: Request):
    settings = request.app.state.settings
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("readiness check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "service": settings.app_name,
                "environment": settings.app_env,
                "database": "error",
                "error": str(exc),
                "timestamp": utc_now_iso(),
            },
        )

    return {
        "status": "ready",
        "service": settings.app_name,
        "environment": settings.app_env,
        "database": "ok",
        "timestamp": utc_now_iso(),
    }


@app.get("/metrics", tags=["system"], include_in_schema=False)
async def metrics() -> Response:
    return Response(content=metrics_payload(), media_type=metrics_content_type())
