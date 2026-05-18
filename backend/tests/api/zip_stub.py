"""Minimal ZIP test data with valid magic bytes (PK\\x03\\x04)."""

import io
import zipfile

_buf = io.BytesIO()
with zipfile.ZipFile(_buf, "w") as zf:
    zf.writestr("stub.txt", "test")
ZIP = _buf.getvalue()


def zip_named(tag: str = "") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("stub.txt", tag or "test")
    return buf.getvalue()
