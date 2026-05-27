"""Filename sanitization for upload validation and download headers."""

import re
from urllib.parse import quote

_UNSAFE_FILENAME_CHARS = re.compile(r'["\\\r\n\x00-\x1f]')


def sanitize_upload_filename(raw: str) -> str:
    """Sanitize a filename from a multipart upload before database storage.

    Extracts the basename, strips control characters and header-breaking chars,
    collapses repeated dots, and strips leading/trailing dots and whitespace.
    """
    name = raw.rsplit("/", 1)[-1]
    name = name.rsplit("\\", 1)[-1]
    name = _UNSAFE_FILENAME_CHARS.sub("", name)
    name = name.strip().strip(".")
    name = re.sub(r"\.{2,}", ".", name)
    return name.strip()


def sanitize_download_filename(filename: str) -> str:
    """Defense-in-depth sanitization for Content-Disposition filenames."""
    sanitized = _UNSAFE_FILENAME_CHARS.sub("", filename)
    sanitized = sanitized.replace("/", "_").replace("\\", "_")
    return sanitized or "download"


def content_disposition_header(filename: str) -> str:
    """Build an RFC 5987 Content-Disposition header value.

    Emits both filename= (ASCII fallback) and filename*= (UTF-8 percent-encoded).
    """
    sanitized = sanitize_download_filename(filename)
    ascii_safe = (
        sanitized.encode("ascii", errors="replace").decode("ascii").replace("?", "_")
    )
    utf8_encoded = quote(sanitized, safe="")
    return f"attachment; filename=\"{ascii_safe}\"; filename*=UTF-8''{utf8_encoded}"
