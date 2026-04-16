"""File download endpoint.

  GET /files/{content_type}/{name}/{version}/{filename}

Only *.tar.gz and *.sha256 filenames are served.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from ..storage_manager import StorageManager, get_storage_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["files"])


@router.get(
    "/files/{content_type}/{name}/{version}/{filename}",
    summary="Download a versioned archive or checksum file",
)
async def download_file(
    content_type: str,
    name: str,
    version: str,
    filename: str,
    storage: Annotated[StorageManager, Depends(get_storage_manager)],
) -> StreamingResponse:
    """Stream a .tar.gz or .sha256 file from the data directory.

    Raises 404 if the file does not exist and 400 for disallowed file types.
    """
    try:
        generator = storage.stream_file(content_type, name, version, filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{content_type}/{name}/{version}/{filename} not found",
        )

    media_type = (
        "application/gzip" if filename.endswith(".tar.gz") else "text/plain"
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(generator, media_type=media_type, headers=headers)
