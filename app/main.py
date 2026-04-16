"""VYRA Local Repository — FastAPI application entry point."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import catalog, files, health

logger = logging.getLogger(__name__)

_START_TIME = time.monotonic()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: ensure data directories exist, then yield."""
    settings = get_settings()
    # Bootstrap required directories on first start
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "_registry").mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "modules").mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "plugins").mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "images").mkdir(parents=True, exist_ok=True)

    # Write default content_types.json if missing
    registry = settings.registry_file
    if not registry.exists():
        import json

        registry.write_text(json.dumps(["modules", "plugins", "images"], indent=2) + "\n")

    logger.info("VYRA Local Repository — data dir: %s", settings.data_dir)
    logger.info("API: http://%s:%d/docs", settings.domain, settings.port)
    yield
    logger.info("VYRA Local Repository shutting down.")


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="VYRA Local Repository",
        description=(
            "Local storage service for VYRA modules, plugins, and base images. "
            "Can be run without Docker — start with run_local.py or uvicorn. "
            "API is compatible with vyra_storage_pool (same endpoints)."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["Content-Type"],
    )

    app.include_router(health.router)
    app.include_router(catalog.router)
    app.include_router(files.router)

    return app


app = create_app()
