"""Health endpoint — no authentication required."""

from fastapi import APIRouter, Depends

from ..config import get_settings
from ..models import HealthResponse
from ..storage_manager import StorageManager, get_storage_manager

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(
    storage: StorageManager = Depends(get_storage_manager),
) -> HealthResponse:
    """Return service health and content type information."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version="1.0.0",
        content_types=storage.get_content_types(),
        data_dir=str(settings.data_dir),
    )
