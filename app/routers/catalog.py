"""Catalog endpoints — listing, searching, and metadata retrieval.

API compatibility with vyra_storage_pool and v2_modulemanager:
  GET /index.json                         → unified index (backward compat)
  GET /api/v1/{content_type}              → list all items
  GET /api/v1/{content_type}/{name}       → list all versions of one item
  GET /api/v1/{content_type}/{name}/{version} → metadata for a specific version
  GET /api/v1/search?q=...               → search across all types
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..config import Settings, get_settings
from ..models import IndexResponse
from ..storage_manager import StorageManager, get_storage_manager

router = APIRouter(tags=["catalog"])


def _maybe_require_key(
    storage: StorageManager = Depends(get_storage_manager),
    settings: Settings = Depends(get_settings),
) -> StorageManager:
    """No-op dependency — auth is optional for the local repository."""
    return storage


@router.get(
    "/index.json",
    response_model=IndexResponse,
    summary="Unified index (v2_modulemanager backward compat)",
)
def get_unified_index(
    storage: Annotated[StorageManager, Depends(_maybe_require_key)],
) -> IndexResponse:
    """Return the full unified index.json.

    This endpoint is compatible with v2_modulemanager's file-based and HTTPS
    repository clients that fetch ``{base_url}/index.json``.
    """
    index = storage.get_index()
    return IndexResponse(**index)


@router.get(
    "/api/v1/{content_type}",
    summary="List all items of a content type",
)
def list_items(
    content_type: str,
    storage: Annotated[StorageManager, Depends(_maybe_require_key)],
) -> dict:
    """Return all index entries for the given content type."""
    try:
        items = storage.get_items_for_type(content_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return {content_type: items, "count": len(items)}


@router.get(
    "/api/v1/{content_type}/{name}",
    summary="List all versions of one item",
)
def list_item_versions(
    content_type: str,
    name: str,
    storage: Annotated[StorageManager, Depends(_maybe_require_key)],
) -> dict:
    """Return all version entries for *name* within *content_type*."""
    try:
        versions = storage.get_item_versions(content_type, name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if not versions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No versions found for {content_type}/{name}",
        )
    return {"name": name, "content_type": content_type, "versions": versions}


@router.get(
    "/api/v1/{content_type}/{name}/{version}",
    summary="Get metadata for a specific version",
)
def get_item_metadata(
    content_type: str,
    name: str,
    version: str,
    storage: Annotated[StorageManager, Depends(_maybe_require_key)],
) -> dict:
    """Return the full metadata.json (or manifest.yaml content) for one version."""
    try:
        meta = storage.get_item_metadata(content_type, name, version)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metadata not found for {content_type}/{name}/{version}",
        )
    return meta


@router.get(
    "/api/v1/search",
    summary="Search across all content types",
)
def search(
    q: Annotated[str, Query(description="Search query string")],
    storage: Annotated[StorageManager, Depends(_maybe_require_key)],
) -> dict:
    """Search modules, plugins, and images by name or description."""
    results = storage.search_items(q)
    return {"query": q, "count": len(results), "results": results}
