"""Tests for CLI /upload command functionality."""

import asyncio
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from deepagents_cli.utils.security import SecurityError, ValidationError


class TestUploadCommand:
    """Test suite for /upload command handling."""

    def test_upload_text_file_success(self):
        """Test successful upload of a text file shows correct guidance."""
        from deepagents_cli.app import DeepAgentsApp

        # Create a test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Hello, World!")
            temp_path = f.name

        try:
            # Create app instance with mocked dependencies
            app = DeepAgentsApp()
            app._mount_message = MagicMock()

            # Mock backend
            mock_backend = MagicMock()
            mock_response = MagicMock()
            mock_response.error = None
            mock_backend.upload_files.return_value = [mock_response]
            app._backend = mock_backend

            # Execute upload
            asyncio.run(app._handle_command(f"/upload {temp_path}"))

            # Verify success messages were displayed
            calls = app._mount_message.call_args_list
            messages = [str(call) for call in calls]

            # Should show uploaded message
            assert any("uploaded" in msg for msg in messages)

            # Should show guidance for text files
            assert any("read_file" in msg for msg in messages)

        finally:
            Path(temp_path).unlink()

    def test_upload_binary_file_shows_warning(self):
        """Test that uploading binary files shows appropriate warning."""
        from deepagents_cli.app import DeepAgentsApp

        # Create a minimal PNG file
        png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".png", delete=False) as f:
            f.write(png_header)
            temp_path = f.name

        try:
            app = DeepAgentsApp()
            app._mount_message = MagicMock()

            mock_backend = MagicMock()
            mock_response = MagicMock()
            mock_response.error = None
            mock_backend.upload_files.return_value = [mock_response]
            app._backend = mock_backend

            asyncio.run(app._handle_command(f"/upload {temp_path}"))

            calls = app._mount_message.call_args_list
            messages = [str(call) for call in calls]

            # Should show warning for binary files
            assert any("cannot be read directly" in msg or "Binary" in msg for msg in messages)

        finally:
            Path(temp_path).unlink()

    def test_upload_pdf_shows_specific_guidance(self):
        """Test that uploading PDF shows PDF-specific guidance."""
        from deepagents_cli.app import DeepAgentsApp

        # Create a minimal PDF file
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4\n")
            temp_path = f.name

        try:
            app = DeepAgentsApp()
            app._mount_message = MagicMock()

            mock_backend = MagicMock()
            mock_response = MagicMock()
            mock_response.error = None
            mock_backend.upload_files.return_value = [mock_response]
            app._backend = mock_backend

            asyncio.run(app._handle_command(f"/upload {temp_path}"))

            calls = app._mount_message.call_args_list
            messages = [str(call) for call in calls]

            # Should show PDF-specific guidance
            assert any("PDF" in msg or "pdftotext" in msg for msg in messages)

        finally:
            Path(temp_path).unlink()

    def test_upload_archive_shows_extraction_guidance(self):
        """Test that uploading archive files shows extraction guidance."""
        from deepagents_cli.app import DeepAgentsApp

        # Create a minimal zip file
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".zip", delete=False) as f:
            temp_path = f.name

        # Create a valid zip file
        with zipfile.ZipFile(temp_path, "w") as zf:
            zf.writestr("test.txt", "test content")

        try:
            app = DeepAgentsApp()
            app._mount_message = MagicMock()

            mock_backend = MagicMock()
            mock_response = MagicMock()
            mock_response.error = None
            mock_backend.upload_files.return_value = [mock_response]
            app._backend = mock_backend

            asyncio.run(app._handle_command(f"/upload {temp_path}"))

            calls = app._mount_message.call_args_list
            messages = [str(call) for call in calls]

            # Should show extraction guidance
            assert any("unzip" in msg or "extract" in msg for msg in messages)

        finally:
            Path(temp_path).unlink()

    def test_upload_office_document_shows_pandoc_guidance(self):
        """Test that uploading Office documents shows pandoc guidance."""
        from deepagents_cli.app import DeepAgentsApp

        # Create a minimal docx file (actually a zip with XML inside)
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".docx", delete=False) as f:
            temp_path = f.name

        # Create minimal docx structure
        with zipfile.ZipFile(temp_path, "w") as zf:
            zf.writestr("[Content_Types].xml", "<?xml version='1.0' encoding='UTF-8'?>")
            zf.writestr("word/document.xml", "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'/>")

        try:
            app = DeepAgentsApp()
            app._mount_message = MagicMock()

            mock_backend = MagicMock()
            mock_response = MagicMock()
            mock_response.error = None
            mock_backend.upload_files.return_value = [mock_response]
            app._backend = mock_backend

            asyncio.run(app._handle_command(f"/upload {temp_path}"))

            calls = app._mount_message.call_args_list
            messages = [str(call) for call in calls]

            # Should show pandoc guidance for Office documents
            assert any("pandoc" in msg for msg in messages)

        finally:
            Path(temp_path).unlink()

    def test_upload_nonexistent_file_shows_error(self):
        """Test that uploading non-existent file shows error."""
        from deepagents_cli.app import DeepAgentsApp

        app = DeepAgentsApp()
        app._mount_message = MagicMock()

        asyncio.run(app._handle_command("/upload /nonexistent/file.txt"))

        calls = app._mount_message.call_args_list
        messages = [str(call) for call in calls]

        # Should show error message
        assert any("File not found" in msg or "Error" in msg for msg in messages)

    def test_upload_without_path_shows_usage(self):
        """Test that /upload without path shows usage error."""
        from deepagents_cli.app import DeepAgentsApp

        app = DeepAgentsApp()
        app._mount_message = MagicMock()

        asyncio.run(app._handle_command("/upload"))

        calls = app._mount_message.call_args_list
        messages = [str(call) for call in calls]

        # Should show usage message
        assert any("Usage" in msg for msg in messages)

    def test_upload_with_quoted_path(self):
        """Test that quoted paths are handled correctly."""
        from deepagents_cli.app import DeepAgentsApp

        # Create a file with spaces in name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("content")
            temp_path = f.name

        try:
            app = DeepAgentsApp()
            app._mount_message = MagicMock()

            mock_backend = MagicMock()
            mock_response = MagicMock()
            mock_response.error = None
            mock_backend.upload_files.return_value = [mock_response]
            app._backend = mock_backend

            # Test with quoted path
            quoted_path = f'"{temp_path}"'
            asyncio.run(app._handle_command(f"/upload {quoted_path}"))

            calls = app._mount_message.call_args_list
            messages = [str(call) for call in calls]

            # Should succeed
            assert any("uploaded" in msg for msg in messages)

        finally:
            Path(temp_path).unlink()

    def test_upload_backend_error_handling(self):
        """Test handling of backend upload errors."""
        from deepagents_cli.app import DeepAgentsApp

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("content")
            temp_path = f.name

        try:
            app = DeepAgentsApp()
            app._mount_message = MagicMock()

            mock_backend = MagicMock()
            mock_response = MagicMock()
            mock_response.error = "Storage full"
            mock_backend.upload_files.return_value = [mock_response]
            app._backend = mock_backend

            asyncio.run(app._handle_command(f"/upload {temp_path}"))

            calls = app._mount_message.call_args_list
            messages = [str(call) for call in calls]

            # Should show backend error
            assert any("Upload failed" in msg or "Storage full" in msg for msg in messages)

        finally:
            Path(temp_path).unlink()


class TestUploadSecurity:
    """Test security aspects of upload command."""

    def test_upload_rejects_unauthorized_file_type(self):
        """Test that unauthorized file types are rejected."""
        from deepagents_cli.app import DeepAgentsApp

        # Create a binary file that will fail validation
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".exe", delete=False) as f:
            f.write(b"\x4d\x5a")  # Windows executable header
            f.write(b"\x00" * 100)
            temp_path = f.name

        try:
            app = DeepAgentsApp()
            app._mount_message = MagicMock()

            asyncio.run(app._handle_command(f"/upload {temp_path}"))

            calls = app._mount_message.call_args_list
            messages = [str(call) for call in calls]

            # Should show security error
            assert any("Unauthorized" in msg or "file type" in msg for msg in messages)

        finally:
            Path(temp_path).unlink()

    def test_upload_validates_file_size(self, monkeypatch):
        """Test that oversized files are rejected."""
        from deepagents_cli.app import DeepAgentsApp
        from deepagents_cli.utils.security import MAX_FILE_SIZE

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("x")
            temp_path = f.name

        try:
            # Mock file size check to return oversized value
            original_stat = Path.stat

            def mock_stat(self):
                class MockStat:
                    st_size = MAX_FILE_SIZE + 1
                return MockStat()

            monkeypatch.setattr(Path, "stat", mock_stat)

            app = DeepAgentsApp()
            app._mount_message = MagicMock()

            asyncio.run(app._handle_command(f"/upload {temp_path}"))

            calls = app._mount_message.call_args_list
            messages = [str(call) for call in calls]

            # Should show size error
            assert any("too large" in msg or "File too large" in msg for msg in messages)

        finally:
            Path(temp_path).unlink()


class TestUploadFilePathHandling:
    """Test file path handling in upload command."""

    def test_upload_path_with_single_quotes(self):
        """Test handling of single-quoted paths."""
        from deepagents_cli.app import DeepAgentsApp

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("content")
            temp_path = f.name

        try:
            app = DeepAgentsApp()
            app._mount_message = MagicMock()

            mock_backend = MagicMock()
            mock_response = MagicMock()
            mock_response.error = None
            mock_backend.upload_files.return_value = [mock_response]
            app._backend = mock_backend

            # Test with single-quoted path
            quoted_path = f"'{temp_path}'"
            asyncio.run(app._handle_command(f"/upload {quoted_path}"))

            calls = app._mount_message.call_args_list
            messages = [str(call) for call in calls]

            # Should succeed
            assert any("uploaded" in msg for msg in messages)

        finally:
            Path(temp_path).unlink()

    def test_upload_target_path_construction(self):
        """Test that target path is correctly constructed as /uploads/filename."""
        from deepagents_cli.app import DeepAgentsApp

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("content")
            temp_path = f.name

        try:
            app = DeepAgentsApp()
            app._mount_message = MagicMock()

            mock_backend = MagicMock()
            mock_response = MagicMock()
            mock_response.error = None

            captured_paths = []

            def capture_upload(files):
                captured_paths.extend([f[0] for f in files])
                return [mock_response]

            mock_backend.upload_files = capture_upload
            app._backend = mock_backend

            filename = Path(temp_path).name
            asyncio.run(app._handle_command(f"/upload {temp_path}"))

            # Verify target path is /uploads/filename
            assert len(captured_paths) == 1
            assert captured_paths[0] == f"/uploads/{filename}"

        finally:
            Path(temp_path).unlink()
