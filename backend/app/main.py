"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import auth_router, meta_router, repo_router
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.db.session import get_engine, init_db
from app.services.indexer import recover_interrupted_jobs

log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    log.info("Starting (env=%s, llm=%s)", settings.environment, settings.llm_provider)
    init_db()
    recovered = recover_interrupted_jobs()
    if recovered:
        log.warning("Marked %d interrupted indexing job(s) as failed", recovered)
    yield
    log.info("Shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="AI Software Engineer API", version="1.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=(settings.cors_origin_regex or "").strip() or None,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=False,  # JWT travels in the Authorization header, not cookies
        max_age=600,
    )

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        t0 = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("rid=%s unhandled error %s %s", rid, request.method, request.url.path)
            raise
        ms = int((time.monotonic() - t0) * 1000)
        response.headers["x-request-id"] = rid
        response.headers["x-content-type-options"] = "nosniff"
        if request.url.path != f"{settings.api_prefix}/health":
            log.info("rid=%s %s %s -> %d (%dms)", rid, request.method, request.url.path, response.status_code, ms)
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError):
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message, "code": exc.code}, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError):
        # Never echo submitted values back (they may contain passwords).
        errors = [{"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]} for e in exc.errors()]
        first = errors[0] if errors else {"field": "", "message": "Invalid request"}
        detail = f"{first['field']}: {first['message']}" if first["field"] else first["message"]
        return JSONResponse(status_code=422, content={"detail": detail, "code": "validation_error", "errors": errors})

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(_: Request, exc: StarletteHTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "code": "http_error"})

    @app.exception_handler(Exception)
    async def unhandled_handler(_: Request, exc: Exception):
        log.exception("Unhandled exception")
        return JSONResponse(status_code=500, content={"detail": "Internal server error", "code": "internal_error"})

    api = settings.api_prefix

    @app.get(f"{api}/health", tags=["meta"])
    def health():
        """Liveness probe (does not touch the database, so Render health checks stay cheap)."""
        return {"status": "ok"}

    @app.get(f"{api}/health/ready", tags=["meta"])
    def ready():
        """Readiness: verifies database connectivity."""
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            log.exception("readiness check failed")
            return JSONResponse(status_code=503, content={"status": "database_unavailable"})
        return {"status": "ready"}

    app.include_router(auth_router, prefix=api)
    app.include_router(repo_router, prefix=api)
    app.include_router(meta_router, prefix=api)

    @app.get("/", include_in_schema=False)
    def root():
        return {"service": "ai-software-engineer-api", "docs": "/docs", "health": f"{api}/health"}

    return app


app = create_app()
