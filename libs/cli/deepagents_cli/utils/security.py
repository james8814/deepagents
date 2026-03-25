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


class ValidationError(Exception):
    """Raised when a validation fails."""


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
    try:
        with file_path.open("rb"):
            pass
    except FileNotFoundError as err:
        msg = f"File not found: {path}"
        raise ValidationError(msg) from err
    except IsADirectoryError as err:
        msg = f"Not a file: {path}"
        raise ValidationError(msg) from err
    except OSError as err:
        msg = f"File access error: {path}"
        raise ValidationError(msg) from err
    try:
        size = file_path.stat().st_size
    except OSError as err:
        msg = f"File access error: {path}"
        raise ValidationError(msg) from err

    if size > MAX_FILE_SIZE:
        msg = f"File too large (>100MB): {path}"
        raise ValidationError(msg)

    try:
        # Get MIME type from magic bytes
        mime = puremagic.from_file(str(file_path), mime=True)

        # puremagic might return a list if multiple matches found
        if isinstance(mime, list):
            mime = mime[0] if mime else "application/octet-stream"

        if mime not in ALLOWED_MIME_TYPES:
            # Fallback for text files that might be identified as
            # 'application/octet-stream' or unknown.
            # Attempt to read as text to verify.
            if _is_text_file(file_path):
                return "text/plain"
            msg = f"Unauthorized file type: {mime}"
            raise SecurityError(msg)

    except puremagic.PureError as err:
        # If magic check fails, try text check
        if _is_text_file(file_path):
            return "text/plain"
        msg = "Unknown file format"
        raise SecurityError(msg) from err

    return mime


def _is_text_file(path: Path) -> bool:
    """Check if file is text by attempting to read it.

    Args:
        path: Path to the file to check.

    Returns:
        True if file is text, False otherwise.
    """
    try:
        with path.open("r", encoding="utf-8") as f:
            # Read first 1KB to check for binary characters
            chunk = f.read(1024)
            return "\0" not in chunk
    except (UnicodeDecodeError, OSError):
        return False
