"""Shapefile download response for `GET /areas/{areaId}`, shared by STR and CA."""

from fastapi import HTTPException, Response, status

from app.api.common.filename import (
    content_disposition_header,
    sanitize_download_filename,
)
from app.models.area import Area


def area_zip_response(area: Area | None, area_id: str) -> Response:
    """Return the area shapefile as a zip download, or raise 404 when area is None."""
    if area is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Area with areaId '{area_id}' not found",
        )

    # Return raw binary data (or empty bytes if filedata is None)
    binary_data = area.filedata if area.filedata is not None else b""
    filename = sanitize_download_filename(area.filename)

    return Response(
        content=binary_data,
        media_type="application/zip",
        headers={"Content-Disposition": content_disposition_header(filename)},
    )
