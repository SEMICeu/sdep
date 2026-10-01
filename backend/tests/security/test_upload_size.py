"""Upload size limit: rejected before the endpoint parses the body."""

import pytest
from app.api.common.exception_handlers import register_exception_handlers
from app.main import app as main_app
from app.security.upload_size import UploadSizeLimitMiddleware
from fastapi import FastAPI, File, UploadFile, status
from httpx import ASGITransport, AsyncClient

MAX_BYTES = 1024


def _app() -> tuple[FastAPI, list[str]]:
    app = FastAPI()
    register_exception_handlers(app)
    app.add_middleware(
        UploadSizeLimitMiddleware, max_bytes=MAX_BYTES, path_pattern="/upload"
    )
    reached: list[str] = []

    @app.post("/upload")
    async def upload(file: UploadFile = File(...)):
        reached.append("upload")
        return {"size": len(await file.read())}

    @app.post("/other")
    async def other(file: UploadFile = File(...)):
        return {"size": len(await file.read())}

    return app, reached


@pytest.mark.asyncio
async def test_advertised_oversize_is_rejected_before_the_endpoint():
    app, reached = _app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        response = await c.post(
            "/upload", files={"file": ("a.zip", b"x" * (MAX_BYTES + 1))}
        )
    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    assert response.json()["detail"][0]["type"] == "validation_error"
    assert reached == []


@pytest.mark.asyncio
async def test_streamed_oversize_without_content_length_is_rejected():
    app, reached = _app()

    body = (
        b'--b\r\nContent-Disposition: form-data; name="file"; filename="a.zip"\r\n'
        b"Content-Type: application/zip\r\n\r\n"
        + b"x" * (2 * MAX_BYTES)
        + b"\r\n--b--\r\n"
    )

    async def chunks():
        for start in range(0, len(body), 256):
            yield body[start : start + 256]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        response = await c.post(
            "/upload",
            content=chunks(),
            headers={"content-type": "multipart/form-data; boundary=b"},
        )
    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    assert reached == []


@pytest.mark.asyncio
async def test_small_upload_and_other_paths_pass():
    app, reached = _app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        small = await c.post("/upload", files={"file": ("a.zip", b"x" * 10)})
        other = await c.post(
            "/other", files={"file": ("a.zip", b"x" * (MAX_BYTES + 1))}
        )
        bad_length = await c.post(
            "/upload",
            files={"file": ("a.zip", b"x" * 10)},
            headers={"content-length": "not-a-number"},
        )
    assert small.status_code == status.HTTP_200_OK
    assert other.status_code == status.HTTP_200_OK
    assert bad_length.status_code != status.HTTP_413_CONTENT_TOO_LARGE
    assert reached[0] == "upload"


@pytest.mark.asyncio
async def test_area_upload_of_every_ca_version_is_limited():
    """Wiring: the main app limits POST /api/ca/v{N}/areas, before auth runs."""
    oversize = b"x" * (2 * 1024 * 1024)
    async with AsyncClient(
        transport=ASGITransport(app=main_app), base_url="http://t"
    ) as c:
        for version in ("v1", "v2"):
            response = await c.post(
                f"/api/ca/{version}/areas", files={"file": ("a.zip", oversize)}
            )
            assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
