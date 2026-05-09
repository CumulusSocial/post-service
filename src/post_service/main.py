from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import httpx
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from post_service.api import follows as follows_router
from post_service.api import health as health_router
from post_service.api import media as media_router
from post_service.api import posts as posts_router
from post_service.config import settings
from post_service.logging import configure_logging, log
from post_service.queue.publisher import SNSPublisher, make_sns_client
from post_service.services.media import MediaService, make_s3_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    app.state.http_client = httpx.AsyncClient(timeout=10.0)
    app.state.sns = SNSPublisher(make_sns_client(), settings.sns_topic_arn)
    app.state.media = MediaService(make_s3_client(), settings.s3_bucket)
    log.info("post_service.startup", env=settings.app_env)
    try:
        yield
    finally:
        await app.state.http_client.aclose()
        log.info("post_service.shutdown")


app = FastAPI(title="post-service", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    structlog.contextvars.bind_contextvars(request_id=request_id)
    try:
        response = await call_next(request)
    finally:
        structlog.contextvars.clear_contextvars()
    response.headers["x-request-id"] = request_id
    return response


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_exception", path=request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal server error"})


app.include_router(posts_router.router, tags=["posts"])
app.include_router(follows_router.router, tags=["follows"])
app.include_router(media_router.router, tags=["media"])
app.include_router(health_router.router, tags=["health"])
