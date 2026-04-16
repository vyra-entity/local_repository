"""Pydantic response models for the local repository REST API."""

from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response body for GET /health."""

    status: str
    version: str
    content_types: list[str]
    data_dir: str


class IndexResponse(BaseModel):
    """Unified index response body (mirrors index.json structure)."""

    name: str
    description: str
    version: str
    type: str
    base_url: str
    last_updated: str
    modules: list[dict[str, Any]] = []
    plugins: list[dict[str, Any]] = []
    images: list[dict[str, Any]] = []

    model_config = {"extra": "allow"}


class ErrorDetail(BaseModel):
    """Standard error response body."""

    detail: str
