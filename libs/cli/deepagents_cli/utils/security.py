"""Security utilities for Deep Agents CLI."""

from pathlib import Path

import puremagic

# 100MB limit
MAX_FILE_SIZE = 100 * 1024 * 1024

# Allowed MIME types for upload
# This list covers common code, document, and image formats
ALLOWED_MIME_TYPES = {
    # Text/Code
    "text/plain",
    "text/x-python",
    "text/javascript",
    "text/html",
    "text/css",
    "text/xml",
    "text/markdown",
    "text/csv",
    "application/json",
    "application/xml",
    "application/x-yaml",
    "text/x-yaml",

    # Documents
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",

    # Images
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",

    # Archives (optional, but useful for analysis)
    "application/zip",
    "application/x-tar",
    "application/gzip",
}

class SecurityError(Exception):
    """Raised when a security validation fails."""
    pass

class ValidationError(Exception):
    """Raised when a validation fails."""
    pass

def validate_file_type(path: str | Path) -> str:
    """Validate a file's type and size for secure upload.

    Args:
        path: Path to the file to validate.

    Returns:
        The detected MIME type of the file.

    Raises:
        ValidationError: If file is too large or doesn't exist.
        SecurityError: If file type is not allowed.
    """
    file_path = Path(path)

    if not file_path.exists():
        raise ValidationError(f"File not found: {path}")

    if not file_path.is_file():
        raise ValidationError(f"Not a file: {path}")

    if file_path.stat().st_size > MAX_FILE_SIZE:
        raise ValidationError(f"File too large (>100MB): {path}")

    try:
        # Get MIME type from magic bytes
        mime = puremagic.from_file(str(file_path), mime=True)

        # puremagic might return a list if multiple matches found
        if isinstance(mime, list):
            mime = mime[0] if mime else "application/octet-stream"

        if mime not in ALLOWED_MIME_TYPES:
            # Fallback for text files that might be identified as 'application/octet-stream' or unknown
            # Attempt to read as text to verify
            if _is_text_file(file_path):
                return "text/plain"

            raise SecurityError(f"Unauthorized file type: {mime}")

        return mime

    except puremagic.PureError:
        # If magic check fails, try text check
        if _is_text_file(file_path):
            return "text/plain"
        raise SecurityError("Unknown file format")

def _is_text_file(path: Path) -> bool:
    """Check if file is text by attempting to read it."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            # Read first 1KB to check for binary characters
            chunk = f.read(1024)
            return "\0" not in chunk
    except (UnicodeDecodeError, OSError):
        return False
