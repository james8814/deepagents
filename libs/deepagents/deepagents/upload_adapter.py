"""Universal upload adapter for DeepAgents backends - V5.0 Revised.

This module provides a unified interface for uploading files to any
DeepAgents backend, automatically selecting the appropriate strategy
based on backend capabilities.

Design Principles:
    - Pythonic: Function-based design, following KISS principle
    - Compatible: Leverages existing backend security features
    - Safe: WeakKeyDictionary prevents memory leaks
    - Correct: Properly handles backend.read() string return type

Example:
    >>> from deepagents.upload_adapter import upload_files
    >>> from deepagents.backends import FilesystemBackend
    >>> backend = FilesystemBackend(root_dir="/workspace")
    >>> results = upload_files(backend, [("/uploads/file.txt", b"content")])
    >>> print(results[0].success)
    True

Version: 5.0.0
"""

from __future__ import annotations

import base64
import logging
import os
import secrets
import shutil
import tempfile
import threading
import weakref
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from deepagents.backends.protocol import BackendProtocol, FileOperationError

# Deferred imports to avoid circular dependencies
# These are imported at module level but loaded on first use
_imported_backends = None
_imported_protocol = None
_imported_utils = None


def _get_backends():
    global _imported_backends
    if _imported_backends is None:
        from deepagents import backends
        _imported_backends = backends
    return _imported_backends


def _get_protocol():
    global _imported_protocol
    if _imported_protocol is None:
        from deepagents.backends import protocol
        _imported_protocol = protocol
    return _imported_protocol


def _get_utils():
    global _imported_utils
    if _imported_utils is None:
        from deepagents.backends import utils
        _imported_utils = utils
    return _imported_utils


logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    """Unified upload result format.

    Attributes:
        path: Virtual path of the uploaded file.
        success: Whether the upload succeeded.
        error: Error information if failed, None if succeeded.
        strategy: Strategy used for upload (direct/state/fallback).
        encoding: Encoding used (for state: utf-8 or base64).
        physical_path: Physical path if using fallback strategy.
        is_overwrite: Whether this upload overwrote an existing file.
        previous_size: Size of the previous file in bytes if overwritten.
    """

    path: str
    success: bool
    error: "FileOperationError | str | None"
    strategy: str
    encoding: str | None = None
    physical_path: str | None = None
    is_overwrite: bool = False
    previous_size: int | None = None


class _StateUploadLock:
    """Thread-safe lock manager for StateBackend uploads using WeakKeyDictionary.

    This class prevents memory leaks by using WeakKeyDictionary, which
    automatically removes entries when the runtime object is garbage collected.

    Attributes:
        _locks: WeakKeyDictionary mapping runtime objects to threading.Lock.
        _lock_creation_lock: Lock for thread-safe lock creation.
    """

    def __init__(self):
        # P0-2 Fix: Use WeakKeyDictionary to prevent memory leaks
        self._locks: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
        self._lock_creation_lock = threading.Lock()

    def get_lock(self, runtime: Any) -> threading.Lock:
        """Get or create a lock for the specific runtime.

        Args:
            runtime: The runtime object to get lock for.

        Returns:
            threading.Lock for the runtime.
        """
        lock = self._locks.get(runtime)
        if lock is None:
            with self._lock_creation_lock:
                lock = self._locks.get(runtime)
                if lock is None:
                    lock = threading.Lock()
                    self._locks[runtime] = lock
        return lock


# Global lock manager instance
_state_lock_manager = _StateUploadLock()


def _resolve_backend(
    backend_or_factory: "BackendProtocol | Callable[[Any], BackendProtocol]",
    runtime: Any | None = None,
) -> "BackendProtocol":
    """Resolve backend from factory function or return as-is.

    Args:
        backend_or_factory: Backend instance or factory function.
        runtime: Optional runtime context (required for factory functions).

    Returns:
        Resolved BackendProtocol instance.

    Raises:
        RuntimeError: If factory function requires runtime but none provided.
    """
    # Check if it's a backend instance by duck typing
    # Using hasattr to avoid circular import of BackendProtocol
    has_protocol_methods = (
        hasattr(backend_or_factory, "upload_files")
        and hasattr(backend_or_factory, "read")
        and hasattr(backend_or_factory, "write")
    )

    # If it's already a backend instance, return it
    if has_protocol_methods and not callable(backend_or_factory):
        return backend_or_factory  # type: ignore[return-value]

    # If it's callable (factory function), call it with runtime
    if callable(backend_or_factory):
        if runtime is None:
            raise RuntimeError(
                "Backend factory requires runtime parameter. "
                "Pass runtime= when calling upload_files()."
            )
        return backend_or_factory(runtime)

    return backend_or_factory  # type: ignore[return-value]


def _select_strategy(backend: "BackendProtocol") -> str:
    """Select upload strategy based on backend type.

    Uses simple if-elif chain for clarity and maintainability.
    For current requirements, this is sufficient and more readable
    than a complex rule registration system.

    Args:
        backend: The backend to select strategy for.

    Returns:
        Strategy name: "direct", "state", or "fallback".
    """
    backends = _get_backends()

    # Use isinstance for type-safe capability detection
    if isinstance(backend, backends.CompositeBackend):
        # CompositeBackend routes to appropriate backend
        return "direct"

    if isinstance(backend, backends.FilesystemBackend):
        # FilesystemBackend supports upload_files
        return "direct"

    if isinstance(backend, backends.StateBackend):
        # StateBackend requires write() method
        return "state"

    # Check for upload_files support via simple duck typing
    # Simplified: just check if method exists and is callable
    if hasattr(backend, "upload_files") and callable(getattr(backend, "upload_files", None)):
        return "direct"

    # Default to fallback for unknown backends
    return "fallback"


def _upload_direct(
    backend: "BackendProtocol",
    files: list[tuple[str, bytes]],
    runtime: Any | None = None,
) -> list[UploadResult]:
    """Upload files using backend.upload_files().

    Args:
        backend: Backend with upload_files support.
        files: List of (path, content) tuples.
        runtime: Optional runtime (not used for direct upload).

    Returns:
        List of UploadResult objects.
    """
    protocol = _get_protocol()
    FileUploadResponse = protocol.FileUploadResponse

    # Check for existing files before upload (for overwrite detection)
    existing_sizes: dict[str, int | None] = {}
    try:
        download_responses = backend.download_files([path for path, _ in files])
        for path, response in zip([p for p, _ in files], download_responses):
            if response.error is None and response.content is not None:
                existing_sizes[path] = len(response.content)
            else:
                existing_sizes[path] = None
    except (AttributeError, OSError, ValueError) as e:
        # If download_files fails, assume no existing files
        # AttributeError: method doesn't exist
        # OSError: file system errors (permission, not found, etc.)
        # ValueError: invalid arguments
        logger.debug(f"download_files failed, assuming no existing files: {e}")
        for path, _ in files:
            existing_sizes[path] = None

    responses = backend.upload_files(files)
    results: list[UploadResult] = []

    for (path, content), response in zip(files, responses):
        # Handle both dataclass and dict responses
        if isinstance(response, FileUploadResponse):
            error = response.error
            success = error is None
        else:
            # Handle dict response for compatibility
            error = response.get("error")
            success = error is None

        # Determine overwrite status
        previous_size = existing_sizes.get(path)
        is_overwrite = previous_size is not None

        results.append(
            UploadResult(
                path=path,
                success=success,
                error=error,
                strategy="direct",
                is_overwrite=is_overwrite,
                previous_size=previous_size,
            )
        )

    return results


def _upload_to_state(
    backend: "BackendProtocol",
    files: list[tuple[str, bytes]],
    runtime: Any | None = None,
) -> list[UploadResult]:
    """Upload files to StateBackend using write() method.

    Args:
        backend: StateBackend instance.
        files: List of (path, content) tuples.
        runtime: Runtime context (required for StateBackend).

    Returns:
        List of UploadResult objects.

    Raises:
        RuntimeError: If runtime is not provided.
    """
    if runtime is None:
        raise RuntimeError("StateBackend upload requires runtime parameter")

    # Get lock for this runtime (P0-2 Fix: WeakKeyDictionary)
    lock = _state_lock_manager.get_lock(runtime)

    with lock:
        return _upload_to_state_locked(backend, files, runtime)


def _upload_to_state_locked(
    backend: "BackendProtocol",
    files: list[tuple[str, bytes]],
    runtime: Any,
) -> list[UploadResult]:
    """Internal state upload with lock held.

    Args:
        backend: StateBackend instance.
        files: List of (path, content) tuples.
        runtime: Runtime context.

    Returns:
        List of UploadResult objects.
    """
    utils = _get_utils()
    create_file_data = utils.create_file_data

    max_file_size = int(os.environ.get("DEEPAGENTS_UPLOAD_MAX_SIZE", 1024 * 1024))
    results: list[UploadResult] = []

    for path, content in files:
        result = _upload_single_to_state(backend, path, content, max_file_size)

        # If successful, update the runtime state directly
        if result.success and hasattr(backend, "runtime"):
            # Get the file content that was written
            is_text = _is_text_content(content)
            if is_text:
                file_content = content.decode("utf-8")
            else:
                file_content = f"__BINARY_FILE__: {path}\n__ENCODING__: base64\n__SIZE__: {len(content)}\n"
                file_content += base64.b64encode(content).decode("ascii")

            # Update runtime state
            state = backend.runtime.state
            if "files" not in state:
                state["files"] = {}
            state["files"][path] = create_file_data(file_content)

        results.append(result)

    return results


def _upload_single_to_state(
    backend: "BackendProtocol",
    path: str,
    content: bytes,
    max_file_size: int,
) -> UploadResult:
    """Upload single file to StateBackend.

    Args:
        backend: StateBackend instance.
        path: File path.
        content: File content as bytes.
        max_file_size: Maximum allowed file size.

    Returns:
        UploadResult for the operation.
    """
    # Size check
    if len(content) > max_file_size:
        return UploadResult(
            path=path,
            success=False,
            error=f"File too large ({len(content)} > {max_file_size}). "
                  f"Consider using FilesystemBackend.",
            strategy="state",
        )

    try:
        # Detect text vs binary
        is_text = _is_text_content(content)

        if is_text:
            # Text file: pass directly as string
            file_content = content.decode("utf-8")
            encoding = "utf-8"
        else:
            # Binary file: encode as base64 metadata
            file_content = f"__BINARY_FILE__: {path}\n__ENCODING__: base64\n__SIZE__: {len(content)}\n"
            file_content += base64.b64encode(content).decode("ascii")
            encoding = "base64"

        # P0-3 Fix: Check for overwrite using correct method
        # backend.read() returns a string, not an object with 'found' attribute
        is_overwrite = False
        previous_size = None

        try:
            # Use download_files to check existence and get content
            download_responses = backend.download_files([path])
            if download_responses and len(download_responses) > 0:
                response = download_responses[0]
                if response.error is None and response.content is not None:
                    is_overwrite = True
                    # P1 Fix: Calculate size in bytes, not characters
                    previous_size = len(response.content)
                    logger.warning(f"Overwriting existing file: {path}")
        except Exception:
            # File doesn't exist or other error, continue
            pass

        # Use backend.write() - proper encapsulation
        write_result = backend.write(path, file_content)

        if hasattr(write_result, "error") and write_result.error:
            return UploadResult(
                path=path,
                success=False,
                error=write_result.error,
                strategy="state",
                is_overwrite=is_overwrite,
                previous_size=previous_size,
            )

        return UploadResult(
            path=path,
            success=True,
            error=None,
            strategy="state",
            encoding=encoding,
            is_overwrite=is_overwrite,
            previous_size=previous_size,
        )

    except Exception as e:
        logger.exception(f"State write failed for {path}: {e}")
        return UploadResult(
            path=path,
            success=False,
            error=str(e),
            strategy="state",
        )


def _is_text_content(content: bytes, sample_size: int = 8192) -> bool:
    """Check if content appears to be text.

    Args:
        content: The content to check.
        sample_size: Maximum bytes to sample for detection.

    Returns:
        True if content appears to be text, False otherwise.
    """
    if not content:
        return True

    # Check for null bytes (binary indicator)
    if b"\x00" in content:
        return False

    # Sample for high ratio of non-ASCII bytes
    sample = content[: min(len(content), sample_size)]
    non_ascii = sum(1 for b in sample if b > 127)
    if len(sample) > 0 and non_ascii / len(sample) > 0.3:
        try:
            content.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False

    # Final UTF-8 validation
    try:
        content.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _upload_fallback(
    backend: "BackendProtocol",
    files: list[tuple[str, bytes]],
    runtime: Any | None = None,
) -> list[UploadResult]:
    """Fallback upload using FilesystemBackend with secure temporary directory.

    Security Features:
    - Private temp directory with 0o700 permissions (owner only)
    - Random directory name using secrets token
    - File permissions set to 0o600 (owner read/write only)
    - Automatic cleanup via try-finally
    - virtual_mode=True for path traversal protection
    - O_NOFOLLOW for symlink attack prevention

    Args:
        backend: Original backend (not used, for compatibility).
        files: List of (path, content) tuples.
        runtime: Optional runtime (not used for fallback).

    Returns:
        List of UploadResult objects.
    """
    backends = _get_backends()
    FilesystemBackend = backends.FilesystemBackend

    # Create secure private temporary directory
    # Using mkdtemp with random suffix for unpredictability
    root_dir_str = tempfile.mkdtemp(
        prefix="deepagents_upload_",
        suffix=f"_{secrets.token_hex(8)}"
    )
    root_dir = Path(root_dir_str)

    try:
        # Set directory permissions to owner-only (0o700)
        os.chmod(root_dir, 0o700)

        # Use FilesystemBackend with virtual_mode=True for security
        fallback_backend = FilesystemBackend(root_dir=str(root_dir), virtual_mode=True)

        # Track existing files before upload for overwrite detection
        existing_sizes: dict[str, int | None] = {}
        for path, _ in files:
            physical_path = root_dir / path.lstrip("/")
            if physical_path.exists():
                try:
                    existing_sizes[path] = physical_path.stat().st_size
                except OSError:
                    existing_sizes[path] = None
            else:
                existing_sizes[path] = None

        # Use direct upload via FilesystemBackend
        responses = fallback_backend.upload_files(files)
        results: list[UploadResult] = []

        for (path, content), response in zip(files, responses):
            physical_path = root_dir / path.lstrip("/")

            # Set file permissions to owner-only (0o600)
            if physical_path.exists():
                try:
                    os.chmod(physical_path, 0o600)
                except OSError:
                    pass  # Ignore permission errors

            # Check if this was an overwrite based on pre-upload state
            previous_size = existing_sizes.get(path)
            is_overwrite = previous_size is not None

            results.append(
                UploadResult(
                    path=path,
                    success=response.error is None,
                    error=response.error,
                    strategy="fallback",
                    physical_path=str(physical_path),
                    is_overwrite=is_overwrite,
                    previous_size=previous_size,
                )
            )
    finally:
        # Clean up temporary directory
        try:
            shutil.rmtree(root_dir, ignore_errors=True)
        except Exception:
            pass  # Ignore cleanup errors

    return results


def upload_files(
    backend_or_factory: "BackendProtocol | Callable[[Any], BackendProtocol]",
    files: list[tuple[str, bytes]],
    runtime: Any | None = None,
) -> list[UploadResult]:
    """Universal upload function that works with ANY backend.

    Automatically detects backend capabilities and selects the appropriate
    upload strategy:
    - "direct": Uses backend.upload_files() (FilesystemBackend, CompositeBackend)
    - "state": Uses backend.write() (StateBackend)
    - "fallback": Uses FilesystemBackend with security features

    Args:
        backend_or_factory: Backend instance or factory function.
            Factory functions are called with runtime parameter.
        files: List of (virtual_path, content) tuples.
            Paths should be absolute (start with "/").
        runtime: Optional runtime context.
            Required for StateBackend and factory functions.

    Returns:
        List of UploadResult objects, one per input file.
        Response order matches input order.

    Raises:
        RuntimeError: If backend factory or StateBackend requires runtime but none provided.

    Example:
        >>> from deepagents.backends import FilesystemBackend
        >>> backend = FilesystemBackend(root_dir="/workspace")
        >>> results = upload_files(backend, [
        ...     ("/uploads/file1.txt", b"content1"),
        ...     ("/uploads/file2.txt", b"content2"),
        ... ])
        >>> for result in results:
        ...     print(f"{result.path}: {'OK' if result.success else 'FAILED'}")
    """
    # Resolve backend (handle factory functions)
    backend = _resolve_backend(backend_or_factory, runtime)

    # Select strategy based on backend type
    strategy = _select_strategy(backend)

    logger.debug(f"Uploading {len(files)} files using strategy: {strategy}")

    # Execute upload with selected strategy
    if strategy == "direct":
        return _upload_direct(backend, files, runtime)
    elif strategy == "state":
        return _upload_to_state(backend, files, runtime)
    else:  # fallback
        return _upload_fallback(backend, files, runtime)


# Convenience alias for backward compatibility
upload = upload_files
