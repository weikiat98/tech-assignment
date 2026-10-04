"""FastAPI application entry point."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import analyses, meta, ws
from app.config import get_settings
from app.db.init import create_schema, seed_internal
from app.main_limiter import limiter

settings = get_settings()
logging.basicConfig(level=settings.log_level)
structlog.configure(processors=[structlog.processors.add_log_level, structlog.processors.TimeStamper(fmt="iso"),
                                structlog.processors.JSONRenderer()])
log = structlog.get_logger()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await create_schema()
    seeded = await seed_internal()
    log.info("startup", env=settings.app_env, llm_mode=settings.llm_mode, seeded_internal_rows=seeded)
    yield


app = FastAPI(title="Agentic Policy Data Analytics Platform", version=settings.app_version, lifespan=lifespan)
app.state.limiter = limiter
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def request_id(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    structlog.contextvars.bind_contextvars(request_id=rid)
    response = await call_next(request)
    response.headers["x-request-id"] = rid
    structlog.contextvars.clear_contextvars()
    return response


def _problem(status: int, title: str, detail) -> JSONResponse:
    return JSONResponse(status_code=status, media_type="application/problem+json",
                        content={"type": "about:blank", "title": title, "status": status, "detail": detail})


@app.exception_handler(RateLimitExceeded)
async def rate_limited(_: Request, exc: RateLimitExceeded):
    return _problem(429, "Too Many Requests", str(exc.detail))


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException):
    return _problem(exc.status_code, "Request failed", exc.detail)


@app.exception_handler(RequestValidationError)
async def invalid(_: Request, exc: RequestValidationError):
    return _problem(422, "Validation error", exc.errors())


app.include_router(meta.public)
app.include_router(meta.router)
app.include_router(analyses.router)
app.include_router(ws.router)
