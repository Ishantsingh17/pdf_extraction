"""FastAPI application entrypoint."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import claims, documents
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import init_db
from app.services.ocr_service import ocr_service
from app.services.structure_service import structure_analyzer

configure_logging()
logger = get_logger(__name__)

app = FastAPI(title=settings.app_name, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router, prefix=settings.api_prefix)
app.include_router(claims.router, prefix=settings.api_prefix)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    logger.info(
        "ready: ocr=%s structure=%s", ocr_service.backend_name, structure_analyzer.model
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never leak internals or bill content to the client.
    logger.exception("unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": {"code": "server_error", "message": "Something went wrong. Please try again."}},
    )


@app.get("/api/v1/health")
def health() -> dict:
    return {
        "status": "ok",
        "ocr_backend": ocr_service.backend_name,
        "structure_model": structure_analyzer.model,
    }
