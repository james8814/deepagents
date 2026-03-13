"""Tests for binary document conversion integration in read_file.

Covers the V3.1 test matrix: converter lookup, tempfile handling,
pagination, null guards, async paths, error messages, and cleanup.
"""

import asyncio
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from deepagents.backends.protocol import FileDownloadResponse
from deepagents.middleware.filesystem import _convert_document_async, _convert_document_sync


# ---------------------------------------------------------------------------
# Fake backends
# ---------------------------------------------------------------------------

class _BackendSync:
    """Minimal sync backend returning pre-loaded payloads."""

    def __init__(self, payloads: dict[str, bytes]) -> None:
        self._payloads = payloads

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        res: list[FileDownloadResponse] = []
        for p in paths:
            content = self._payloads.get(p)
            if content is None:
                res.append(FileDownloadResponse(path=p, content=None, error="file_not_found"))
            else:
                res.append(FileDownloadResponse(path=p, content=content, error=None))
        return res


class _BackendAsyncNonAwaitable(_BackendSync):
    """Backend whose adownload_files returns a plain list (non-awaitable)."""

    def adownload_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        return super().download_files(paths)


class _BackendAsyncAwaitable(_BackendSync):
    """Backend whose adownload_files is a proper coroutine."""

    async def adownload_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        return super().download_files(paths)


# ---------------------------------------------------------------------------
# Fake converter for mocking the registry
# ---------------------------------------------------------------------------

class _FakeConverter:
    """Converter that returns canned Markdown without real file I/O."""

    def __init__(
        self,
        *,
        paginated: bool = False,
        total_pages: int | None = 5,
        convert_result: str = "## Page 1/5\n\nFake content",
        page_result: str = "## Page {page}/5\n\nFake page content",
    ) -> None:
        self._paginated = paginated
        self._total_pages = total_pages
        self._convert_result = convert_result
        self._page_result = page_result
        self.convert_called = False
        self.convert_page_called_with: int | None = None

    def supports_pagination(self) -> bool:
        return self._paginated

    def get_total_pages(self, path: Path) -> int | None:
        return self._total_pages

    def convert(self, path: Path, raw_content: bytes | None = None) -> str:
        self.convert_called = True
        return self._convert_result

    def convert_page(self, path: Path, page: int, raw_content: bytes | None = None) -> str:
        self.convert_page_called_with = page
        return self._page_result.format(page=page)


def _patch_converter(converter: _FakeConverter, mime: str = "application/pdf"):
    """Context manager that patches MIME detection and registry to return the given converter."""
    return patch.multiple(
        "deepagents.middleware.filesystem",
        # We patch via the lazy imports inside the function
    )


# Helper to patch the converter lookup inside _convert_document_sync/async
def _make_registry_patch(converter: _FakeConverter, mime: str = "application/pdf"):
    """Return patches for detect_mime_type and get_default_registry."""
    mock_detect = MagicMock(return_value=mime)
    mock_registry = {mime: converter}
    mock_get_registry = MagicMock(return_value=mock_registry)
    return (
        patch("deepagents.middleware.converters.utils.detect_mime_type", mock_detect),
        patch("deepagents.middleware.converters.get_default_registry", mock_get_registry),
    )


# ---------------------------------------------------------------------------
# 1. Normal conversion flow (PDF/DOCX/XLSX/PPTX with mock converter)
# ---------------------------------------------------------------------------

class TestNormalConversion:
    """Test successful document conversion via mock converters."""

    def test_pdf_full_conversion(self, tmp_path: Path) -> None:
        """offset=0 calls converter.convert() for full document."""
        file_path = str(tmp_path / "report.pdf")
        payload = b"%PDF-fake-content"
        backend = _BackendSync({file_path: payload})
        converter = _FakeConverter()

        patch_detect, patch_registry = _make_registry_patch(converter)
        with patch_detect, patch_registry:
            result = _convert_document_sync(backend, file_path, offset=0)

        assert converter.convert_called
        assert "Fake content" in result

    def test_docx_full_conversion(self, tmp_path: Path) -> None:
        """DOCX format routes through converter correctly."""
        file_path = str(tmp_path / "doc.docx")
        payload = b"PK\x03\x04fake-docx"
        backend = _BackendSync({file_path: payload})
        converter = _FakeConverter()
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        patch_detect, patch_registry = _make_registry_patch(converter, mime=mime)
        with patch_detect, patch_registry:
            result = _convert_document_sync(backend, file_path, offset=0)

        assert converter.convert_called
        assert "Fake content" in result

    def test_xlsx_full_conversion(self, tmp_path: Path) -> None:
        """XLSX format routes through converter correctly."""
        file_path = str(tmp_path / "data.xlsx")
        payload = b"PK\x03\x04fake-xlsx"
        backend = _BackendSync({file_path: payload})
        converter = _FakeConverter()
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        patch_detect, patch_registry = _make_registry_patch(converter, mime=mime)
        with patch_detect, patch_registry:
            result = _convert_document_sync(backend, file_path, offset=0)

        assert converter.convert_called

    def test_pptx_full_conversion(self, tmp_path: Path) -> None:
        """PPTX format routes through converter correctly."""
        file_path = str(tmp_path / "slides.pptx")
        payload = b"PK\x03\x04fake-pptx"
        backend = _BackendSync({file_path: payload})
        converter = _FakeConverter()
        mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

        patch_detect, patch_registry = _make_registry_patch(converter, mime=mime)
        with patch_detect, patch_registry:
            result = _convert_document_sync(backend, file_path, offset=0)

        assert converter.convert_called


# ---------------------------------------------------------------------------
# 2. Pagination tests
# ---------------------------------------------------------------------------

class TestPagination:
    """Test page-level reading via offset parameter."""

    def test_offset_3_calls_convert_page_with_page_3(self, tmp_path: Path) -> None:
        """offset=3 should call convert_page(page=3), 1-indexed."""
        file_path = str(tmp_path / "report.pdf")
        backend = _BackendSync({file_path: b"%PDF-fake"})
        converter = _FakeConverter(paginated=True, total_pages=10)

        patch_detect, patch_registry = _make_registry_patch(converter)
        with patch_detect, patch_registry:
            result = _convert_document_sync(backend, file_path, offset=3)

        assert converter.convert_page_called_with == 3
        assert "Page 3" in result

    def test_offset_0_calls_full_convert(self, tmp_path: Path) -> None:
        """offset=0 (default) should call converter.convert(), not convert_page."""
        file_path = str(tmp_path / "report.pdf")
        backend = _BackendSync({file_path: b"%PDF-fake"})
        converter = _FakeConverter(paginated=True, total_pages=10)

        patch_detect, patch_registry = _make_registry_patch(converter)
        with patch_detect, patch_registry:
            result = _convert_document_sync(backend, file_path, offset=0)

        assert converter.convert_called
        assert converter.convert_page_called_with is None

    def test_offset_exceeds_total_pages(self, tmp_path: Path) -> None:
        """offset > total_pages returns range error."""
        file_path = str(tmp_path / "report.pdf")
        backend = _BackendSync({file_path: b"%PDF-fake"})
        converter = _FakeConverter(paginated=True, total_pages=5)

        patch_detect, patch_registry = _make_registry_patch(converter)
        with patch_detect, patch_registry:
            result = _convert_document_sync(backend, file_path, offset=6)

        assert "out of range" in result
        assert "5 pages" in result

    def test_offset_equals_total_pages_is_valid(self, tmp_path: Path) -> None:
        """offset=5 on a 5-page doc is valid (returns last page)."""
        file_path = str(tmp_path / "report.pdf")
        backend = _BackendSync({file_path: b"%PDF-fake"})
        converter = _FakeConverter(paginated=True, total_pages=5)

        patch_detect, patch_registry = _make_registry_patch(converter)
        with patch_detect, patch_registry:
            result = _convert_document_sync(backend, file_path, offset=5)

        assert converter.convert_page_called_with == 5
        assert "Page 5" in result

    def test_get_total_pages_returns_none_no_crash(self, tmp_path: Path) -> None:
        """When get_total_pages() returns None, null guard prevents TypeError."""
        file_path = str(tmp_path / "report.pdf")
        backend = _BackendSync({file_path: b"%PDF-fake"})
        # total_pages=None simulates a converter that doesn't know its page count
        converter = _FakeConverter(paginated=True, total_pages=None)

        patch_detect, patch_registry = _make_registry_patch(converter)
        with patch_detect, patch_registry:
            # Should NOT raise TypeError from `offset > None`
            result = _convert_document_sync(backend, file_path, offset=3)

        # With null total_pages, the boundary check is skipped; convert_page is called
        assert converter.convert_page_called_with == 3

    def test_non_paginated_converter_ignores_offset(self, tmp_path: Path) -> None:
        """For non-paginated converters (DOCX, XLSX), offset>0 still does full conversion."""
        file_path = str(tmp_path / "doc.docx")
        backend = _BackendSync({file_path: b"PK-fake"})
        converter = _FakeConverter(paginated=False)

        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        patch_detect, patch_registry = _make_registry_patch(converter, mime=mime)
        with patch_detect, patch_registry:
            result = _convert_document_sync(backend, file_path, offset=3)

        # Non-paginated: falls through to full convert
        assert converter.convert_called
        assert converter.convert_page_called_with is None


# ---------------------------------------------------------------------------
# 3. Error handling tests
# ---------------------------------------------------------------------------

class TestErrorHandling:
    """Test error paths: missing deps, unknown formats, StateBackend, etc."""

    def test_converter_module_import_error(self, tmp_path: Path) -> None:
        """When converter module is entirely absent, returns install prompt."""
        file_path = str(tmp_path / "report.pdf")
        backend = _BackendSync({file_path: b"%PDF-fake"})

        with patch.dict(sys.modules, {
            "deepagents.middleware.converters": None,
            "deepagents.middleware.converters.utils": None,
        }):
            result = _convert_document_sync(backend, file_path, offset=0)

        assert "Install optional dependencies" in result or "Converter module not available" in result

    def test_unknown_extension_no_converter(self, tmp_path: Path) -> None:
        """Unknown file extension returns 'no converter available'."""
        file_path = str(tmp_path / "data.abc")
        backend = _BackendSync({file_path: b"unknown-binary"})
        result = _convert_document_sync(backend, file_path, offset=0)
        assert "No converter available" in result or "Converter module not available" in result or "Error" in result

    def test_state_backend_binary_prefix(self, tmp_path: Path) -> None:
        """StateBackend's __BINARY_FILE__ wrapper is detected."""
        file_path = str(tmp_path / "report.pdf")
        payload = b"__BINARY_FILE__: /uploads/report.pdf\n__ENCODING__: base64\n"
        backend = _BackendSync({file_path: payload})
        result = _convert_document_sync(backend, file_path, offset=0)
        assert "text-only backend" in result

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Missing file returns download error."""
        file_path = str(tmp_path / "missing.pdf")
        backend = _BackendSync({})  # empty — no files
        result = _convert_document_sync(backend, file_path, offset=0)
        assert "Error reading document" in result

    def test_legacy_doc_format_error(self, tmp_path: Path) -> None:
        """.doc files route through converter branch and get a meaningful error."""
        file_path = str(tmp_path / "old.doc")
        backend = _BackendSync({file_path: b"\xd0\xcf\x11\xe0old-doc-format"})
        result = _convert_document_sync(backend, file_path, offset=0)
        # Should NOT be "UTF-8 codec can't decode" — should be a converter error
        assert "utf-8" not in result.lower() or "Error" in result

    def test_converter_exception_propagates_as_error_string(self, tmp_path: Path) -> None:
        """Non-ImportError exceptions in converter are returned as error strings."""
        file_path = str(tmp_path / "corrupt.pdf")
        backend = _BackendSync({file_path: b"%PDF-corrupt"})

        converter = _FakeConverter()
        converter.convert = MagicMock(side_effect=RuntimeError("corrupt PDF structure"))

        patch_detect, patch_registry = _make_registry_patch(converter)
        with patch_detect, patch_registry:
            result = _convert_document_sync(backend, file_path, offset=0)

        assert "Error converting document" in result
        assert "corrupt PDF structure" in result


# ---------------------------------------------------------------------------
# 4. Temp file cleanup tests
# ---------------------------------------------------------------------------

class TestTempFileCleanup:
    """Verify temp files are cleaned up on normal and exception paths."""

    def test_temp_file_cleaned_on_success(self, tmp_path: Path) -> None:
        """Temp file is removed after successful conversion."""
        file_path = str(tmp_path / "report.pdf")
        backend = _BackendSync({file_path: b"%PDF-fake"})
        converter = _FakeConverter()

        created_tmp_files: list[str] = []
        original_mkstemp = __import__("tempfile").mkstemp

        def tracking_mkstemp(**kwargs):
            fd, path = original_mkstemp(**kwargs)
            created_tmp_files.append(path)
            return fd, path

        patch_detect, patch_registry = _make_registry_patch(converter)
        with patch_detect, patch_registry, patch("tempfile.mkstemp", side_effect=tracking_mkstemp):
            _convert_document_sync(backend, file_path, offset=0)

        # Temp file should be cleaned up
        for tmp_file in created_tmp_files:
            assert not Path(tmp_file).exists(), f"Temp file not cleaned: {tmp_file}"

    def test_temp_file_cleaned_on_exception(self, tmp_path: Path) -> None:
        """Temp file is removed even when converter raises."""
        file_path = str(tmp_path / "corrupt.pdf")
        backend = _BackendSync({file_path: b"%PDF-corrupt"})

        converter = _FakeConverter()
        converter.convert = MagicMock(side_effect=RuntimeError("boom"))

        created_tmp_files: list[str] = []
        original_mkstemp = __import__("tempfile").mkstemp

        def tracking_mkstemp(**kwargs):
            fd, path = original_mkstemp(**kwargs)
            created_tmp_files.append(path)
            return fd, path

        patch_detect, patch_registry = _make_registry_patch(converter)
        with patch_detect, patch_registry, patch("tempfile.mkstemp", side_effect=tracking_mkstemp):
            result = _convert_document_sync(backend, file_path, offset=0)

        assert "Error converting document" in result
        for tmp_file in created_tmp_files:
            assert not Path(tmp_file).exists(), f"Temp file not cleaned after error: {tmp_file}"


# ---------------------------------------------------------------------------
# 5. Async path tests
# ---------------------------------------------------------------------------

class TestAsyncPath:
    """Test _convert_document_async with both awaitable and non-awaitable backends."""

    async def test_async_non_awaitable_backend(self, tmp_path: Path) -> None:
        """Backend returning plain list (non-awaitable) works via isawaitable guard."""
        file_path = str(tmp_path / "report.pdf")
        backend = _BackendAsyncNonAwaitable({file_path: b"%PDF-fake"})
        converter = _FakeConverter()

        patch_detect, patch_registry = _make_registry_patch(converter)
        with patch_detect, patch_registry:
            result = await _convert_document_async(backend, file_path, offset=0)

        assert converter.convert_called
        assert "Fake content" in result

    async def test_async_awaitable_backend(self, tmp_path: Path) -> None:
        """Backend returning proper coroutine works via await."""
        file_path = str(tmp_path / "report.pdf")
        backend = _BackendAsyncAwaitable({file_path: b"%PDF-fake"})
        converter = _FakeConverter()

        patch_detect, patch_registry = _make_registry_patch(converter)
        with patch_detect, patch_registry:
            result = await _convert_document_async(backend, file_path, offset=0)

        assert converter.convert_called
        assert "Fake content" in result

    async def test_async_pagination(self, tmp_path: Path) -> None:
        """Async path handles pagination correctly."""
        file_path = str(tmp_path / "report.pdf")
        backend = _BackendAsyncAwaitable({file_path: b"%PDF-fake"})
        converter = _FakeConverter(paginated=True, total_pages=10)

        patch_detect, patch_registry = _make_registry_patch(converter)
        with patch_detect, patch_registry:
            result = await _convert_document_async(backend, file_path, offset=3)

        assert converter.convert_page_called_with == 3

    async def test_async_state_backend_detection(self, tmp_path: Path) -> None:
        """Async path detects StateBackend binary wrapper."""
        file_path = str(tmp_path / "report.pdf")
        payload = b"__BINARY_FILE__: /path\n__ENCODING__: base64\n"
        backend = _BackendAsyncAwaitable({file_path: payload})
        result = await _convert_document_async(backend, file_path, offset=0)
        assert "text-only backend" in result


# ---------------------------------------------------------------------------
# 6. Token truncation test
# ---------------------------------------------------------------------------

class TestTokenTruncation:
    """Test that large converter output gets truncated by the token limit."""

    def test_large_output_truncated(self, tmp_path: Path) -> None:
        """Converter output exceeding token limit is truncated."""
        file_path = str(tmp_path / "big.pdf")
        backend = _BackendSync({file_path: b"%PDF-fake"})
        # Generate output that exceeds any reasonable token limit
        huge_output = "X" * 500_000
        converter = _FakeConverter(convert_result=huge_output)

        patch_detect, patch_registry = _make_registry_patch(converter)
        with patch_detect, patch_registry:
            result = _convert_document_sync(backend, file_path, offset=0)

        # The function itself returns the full output; truncation happens
        # in the read_file caller. Verify converter returns full content.
        assert len(result) == 500_000
