"""Tests for filename sanitization utilities."""

from app.api.common.filename import (
    content_disposition_header,
    sanitize_download_filename,
    sanitize_upload_filename,
)


class TestSanitizeUploadFilename:
    def test_normal_filename_unchanged(self):
        assert sanitize_upload_filename("Area.zip") == "Area.zip"

    def test_strips_unix_path(self):
        assert sanitize_upload_filename("/tmp/uploads/Area.zip") == "Area.zip"

    def test_strips_windows_path(self):
        assert sanitize_upload_filename("C:\\Users\\data\\Area.zip") == "Area.zip"

    def test_strips_mixed_path(self):
        assert sanitize_upload_filename("C:\\Users/data\\Area.zip") == "Area.zip"

    def test_strips_control_characters(self):
        assert sanitize_upload_filename("Area\x00\x01\x1f.zip") == "Area.zip"

    def test_strips_crlf(self):
        assert sanitize_upload_filename("Area\r\n.zip") == "Area.zip"

    def test_strips_quotes_and_backslashes(self):
        assert sanitize_upload_filename('"Area".zip') == "Area.zip"

    def test_strips_leading_trailing_dots(self):
        assert sanitize_upload_filename("...Area....zip") == "Area.zip"

    def test_collapses_multiple_dots(self):
        assert sanitize_upload_filename("Area..extra..zip") == "Area.extra.zip"

    def test_strips_leading_trailing_whitespace(self):
        assert sanitize_upload_filename("  Area.zip  ") == "Area.zip"

    def test_pure_control_chars_result_empty(self):
        assert sanitize_upload_filename("\x00\x01\x02") == ""

    def test_only_zip_extension_after_path_strip(self):
        result = sanitize_upload_filename("/tmp/.zip")
        assert result == "zip"

    def test_unnamed_passthrough(self):
        assert sanitize_upload_filename("unnamed") == "unnamed"


class TestSanitizeDownloadFilename:
    def test_normal_filename_unchanged(self):
        assert sanitize_download_filename("Area.zip") == "Area.zip"

    def test_strips_control_chars(self):
        assert sanitize_download_filename("Area\x00.zip") == "Area.zip"

    def test_replaces_slashes(self):
        assert sanitize_download_filename("path/to/Area.zip") == "path_to_Area.zip"

    def test_strips_backslashes(self):
        assert sanitize_download_filename("path\\to\\Area.zip") == "pathtoArea.zip"

    def test_empty_returns_download(self):
        assert sanitize_download_filename("") == "download"

    def test_only_control_chars_returns_download(self):
        assert sanitize_download_filename("\x00\x01") == "download"


class TestContentDispositionHeader:
    def test_ascii_filename(self):
        header = content_disposition_header("Area.zip")
        assert 'filename="Area.zip"' in header
        assert "filename*=UTF-8''Area.zip" in header

    def test_starts_with_attachment(self):
        header = content_disposition_header("Area.zip")
        assert header.startswith("attachment; ")

    def test_unicode_filename_ascii_fallback(self):
        header = content_disposition_header("Été.zip")
        assert 'filename="' in header
        assert "filename*=UTF-8''" in header
        assert "%C3%89" in header

    def test_empty_filename_uses_download_fallback(self):
        header = content_disposition_header("")
        assert 'filename="download"' in header
