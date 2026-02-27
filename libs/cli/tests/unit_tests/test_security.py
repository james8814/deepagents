"""Tests for CLI security validation utilities."""

import tempfile
from pathlib import Path

import pytest

from deepagents_cli.utils.security import (
    MAX_FILE_SIZE,
    SecurityError,
    ValidationError,
    validate_file_type,
)


class TestValidateFileType:
    """Tests for validate_file_type function."""

    def test_valid_text_file(self):
        """Test validation of a valid text file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Hello, World!")
            temp_path = f.name

        try:
            mime_type = validate_file_type(temp_path)
            assert mime_type == "text/plain"
        finally:
            Path(temp_path).unlink()

    def test_valid_python_file(self):
        """Test validation of a valid Python file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("print('hello')")
            temp_path = f.name

        try:
            mime_type = validate_file_type(temp_path)
            # Python files might be detected as text/x-python or text/plain
            assert mime_type in ("text/x-python", "text/plain")
        finally:
            Path(temp_path).unlink()

    def test_valid_json_file(self):
        """Test validation of a valid JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"key": "value"}')
            temp_path = f.name

        try:
            mime_type = validate_file_type(temp_path)
            assert mime_type == "application/json"
        finally:
            Path(temp_path).unlink()

    def test_file_not_found(self):
        """Test validation fails for non-existent file."""
        with pytest.raises(ValidationError, match="File not found"):
            validate_file_type("/nonexistent/path/file.txt")

    def test_directory_not_allowed(self):
        """Test validation fails for directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ValidationError, match="Not a file"):
                validate_file_type(temp_dir)

    def test_file_too_large(self, monkeypatch):
        """Test validation fails for oversized file."""
        # Create a temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("x")
            temp_path = f.name

        try:
            # Mock the file size to be larger than MAX_FILE_SIZE
            original_stat = Path.stat

            def mock_stat(self):
                class MockStat:
                    st_size = MAX_FILE_SIZE + 1
                return MockStat()

            monkeypatch.setattr(Path, "stat", mock_stat)

            with pytest.raises(ValidationError, match="File too large"):
                validate_file_type(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_binary_file_rejected(self):
        """Test that unauthorized binary files are rejected."""
        # Create a file with binary content
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".bin", delete=False) as f:
            f.write(b"\x00\x01\x02\x03\x04\x05")
            temp_path = f.name

        try:
            with pytest.raises(SecurityError):
                validate_file_type(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_returns_mime_type_for_images(self):
        """Test that image files return correct MIME type."""
        # Create a minimal valid PNG file header
        png_header = b"\x89PNG\r\n\x1a\n"

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".png", delete=False) as f:
            f.write(png_header)
            # Add minimal PNG chunks to make it valid enough
            f.write(b"\x00" * 100)
            temp_path = f.name

        try:
            mime_type = validate_file_type(temp_path)
            assert mime_type == "image/png"
        finally:
            Path(temp_path).unlink()

    def test_returns_mime_type_for_pdf(self):
        """Test that PDF files return correct MIME type."""
        # Create a minimal PDF header
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4\n")
            temp_path = f.name

        try:
            mime_type = validate_file_type(temp_path)
            assert mime_type == "application/pdf"
        finally:
            Path(temp_path).unlink()


