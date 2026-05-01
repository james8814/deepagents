"""Utility functions for file format detection and conversion."""

import importlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Extension to MIME type mapping (fallback when python-magic is unavailable)
MIME_TYPE_FROM_EXT: dict[str, str] = {
    # PDF
    ".pdf": "application/pdf",
    # Word
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    # PowerPoint
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    # Excel
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    # Text
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
    ".xml": "application/xml",
    ".html": "text/html",
    ".htm": "text/html",
    ".yaml": "application/x-yaml",
    ".yml": "application/x-yaml",
    # Code
    ".py": "text/x-python",
    ".js": "text/javascript",
    ".ts": "text/typescript",
    ".java": "text/x-java",
    ".c": "text/x-c",
    ".cpp": "text/x-c++",
    ".h": "text/x-c",
    ".hpp": "text/x-c++",
    ".rs": "text/x-rust",
    ".go": "text/x-go",
    ".rb": "text/x-ruby",
    ".php": "text/x-php",
    ".sh": "text/x-shellscript",
    ".bash": "text/x-shellscript",
    ".sql": "application/x-sql",
    # Images (basic support - will return placeholder)
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    # Audio/Video (basic support)
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
}


def detect_mime_type(path: str | Path, content: bytes | None = None) -> str:
    """Detect the MIME type of a file.

    Uses a three-layer fallback strategy:
    1. Content-based detection via puremagic (if available)
    2. Extension-based detection
    3. Default to application/octet-stream

    Args:
        path: Path to the file (used for extension fallback).
        content: Optional file content for content-based detection.
            If not provided, will attempt to read from path.

    Returns:
        MIME type string (never None, defaults to application/octet-stream).
    """
    path = Path(path)
    ext = path.suffix.lower()

    # Attempt to read content if not provided (for tests and content-based detection)
    if content is None:
        try:
            content = path.read_bytes()
        except (OSError, PermissionError):
            content = b""

    # Layer 1: Try puremagic for content-based detection (if installed)
    try:
        puremagic = importlib.import_module("puremagic")

        if content:
            # puremagic returns a list of matches, sorted by confidence
            matches = puremagic.magic_string(content)
            if matches:
                mime_type = matches[0].mime_type
                if mime_type:
                    logger.debug("MIME detected via puremagic: %s -> %s", path, mime_type)
                    return mime_type
    except ModuleNotFoundError:
        logger.debug("puremagic not installed, using extension-based detection")
    except (AttributeError, OSError, TypeError, ValueError) as exc:
        logger.debug("puremagic detection failed for %s: %s", path, exc)

    # Layer 2: Extension-based detection
    mime_type = MIME_TYPE_FROM_EXT.get(ext)
    if mime_type:
        logger.debug("MIME detected via extension: %s -> %s", path, mime_type)
        return mime_type

    # Layer 3: Default
    logger.debug("MIME detection defaulted: %s -> application/octet-stream", path)
    return "application/octet-stream"


def is_text_mime_type(mime_type: str) -> bool:
    """Check if a MIME type represents text content.

    Args:
        mime_type: MIME type string.

    Returns:
        True if the content can be read as text, False for binary.
    """
    if not mime_type:
        return False

    # Text types
    text_prefixes = ("text/", "application/json", "application/xml", "application/x-yaml")
    if any(mime_type.startswith(p) for p in text_prefixes):
        return True

    # Code types (text/x-*)
    if mime_type.startswith("text/x-"):
        return True

    # Known text-based application types
    text_application_types = {
        "application/javascript",
        "application/typescript",
        "application/x-sh",
        "application/x-shellscript",
    }
    return mime_type in text_application_types


def is_binary_mime_type(mime_type: str) -> bool:
    """Check if a MIME type represents binary content.

    Args:
        mime_type: MIME type string.

    Returns:
        True if the content is binary and needs special handling.
    """
    binary_prefixes = (
        "image/",
        "audio/",
        "video/",
        "application/pdf",
        "application/zip",
        "application/x-tar",
        "application/gzip",
        "application/x-gzip",
    )

    if any(mime_type.startswith(p) for p in binary_prefixes):
        return True

    # Office documents are binary
    office_types = {
        "application/msword",
        "application/vnd.ms-powerpoint",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    return mime_type in office_types
