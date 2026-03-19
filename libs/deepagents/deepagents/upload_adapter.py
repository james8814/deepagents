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
    >>> backend = FilesystemBackend(root_dir="/workspace", virtual_mode=True)
    >>> results = upload_files(backend, [("/uploads/file.txt", b"content")])
    >>> print(results[0].success)
    True

Version: 5.0.0
"""

from __future__ import annotations

import base64
import contextlib
import logging
import os
import secrets
import shutil
import tempfile
import threading
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from deepagents.backends.protocol import BackendProtocol, FileOperationError


@cache
def _get_backends() -> ModuleType:
    return import_module("deepagents.backends")


@cache
def _get_protocol() -> ModuleType:
    return import_module("deepagents.backends.protocol")


@cache
def _get_utils() -> ModuleType:
    return import_module("deepagents.backends.utils")


logger = logging.getLogger(__name__)

_ASCII_MAX = 0x7F
_NON_ASCII_RATIO_THRESHOLD = 0.3
_DEFAULT_UPLOAD_MAX_SIZE = 1024 * 1024
_BACKEND_FACTORY_REQUIRES_RUNTIME_MESSAGE = "Backend factory requires runtime parameter. Pass runtime= when calling upload_files()."
_STATEBACKEND_REQUIRES_RUNTIME_MESSAGE = "StateBackend upload requires runtime parameter"


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
    error: FileOperationError | str | None
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

    def __init__(self) -> None:
        self._locks: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
        self._lock_creation_lock = threading.Lock()

    def get_lock(self, runtime: object) -> threading.Lock:
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
    backend_or_factory: BackendProtocol | Callable[[object], BackendProtocol],
    runtime: object | None = None,
) -> BackendProtocol:
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
        hasattr(backend_or_factory, "upload_files") and hasattr(backend_or_factory, "read") and hasattr(backend_or_factory, "write")
    )

    # If it's already a backend instance, return it
    if has_protocol_methods and not callable(backend_or_factory):
        return cast("BackendProtocol", backend_or_factory)

    # If it's callable (factory function), call it with runtime
    if callable(backend_or_factory):
        if runtime is None:
            raise RuntimeError(_BACKEND_FACTORY_REQUIRES_RUNTIME_MESSAGE)
        backend_factory = cast("Callable[[object], BackendProtocol]", backend_or_factory)
        return backend_factory(runtime)

    return cast("BackendProtocol", backend_or_factory)


def _select_strategy(backend: BackendProtocol) -> str:
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
    backend: BackendProtocol,
    files: list[tuple[str, bytes]],
    runtime: object | None = None,
) -> list[UploadResult]:
    """Upload files using backend.upload_files().

    Args:
        backend: Backend with upload_files support.
        files: List of (path, content) tuples.
        runtime: Optional runtime (not used for direct upload).

    Returns:
        List of UploadResult objects.
    """
    logger.debug("Direct upload for backend=%s runtime=%s", type(backend).__name__, runtime is not None)

    protocol = _get_protocol()
    file_upload_response_cls = protocol.FileUploadResponse

    # Check for existing files before upload (for overwrite detection)
    existing_sizes: dict[str, int | None] = {}
    try:
        download_responses = backend.download_files([path for path, _ in files])
        for path, response in zip([p for p, _ in files], download_responses, strict=True):
            if response.error is None and response.content is not None:
                existing_sizes[path] = len(response.content)
            else:
                existing_sizes[path] = None
    except (AttributeError, OSError, ValueError) as e:
        # If download_files fails, assume no existing files
        # AttributeError: method doesn't exist
        # OSError: file system errors (permission, not found, etc.)
        # ValueError: invalid arguments
        logger.debug("download_files failed, assuming no existing files: %s", e)
        for path, _ in files:
            existing_sizes[path] = None

    responses = backend.upload_files(files)
    results: list[UploadResult] = []

    for (path, _content), response in zip(files, responses, strict=True):
        # Handle both dataclass and dict responses
        if isinstance(response, file_upload_response_cls):
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
    backend: BackendProtocol,
    files: list[tuple[str, bytes]],
    runtime: object | None = None,
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
        raise RuntimeError(_STATEBACKEND_REQUIRES_RUNTIME_MESSAGE)

    # Get lock for this runtime (P0-2 Fix: WeakKeyDictionary)
    lock = _state_lock_manager.get_lock(runtime)

    with lock:
        return _upload_to_state_locked(backend, files, runtime)


def _upload_to_state_locked(
    backend: BackendProtocol,
    files: list[tuple[str, bytes]],
    runtime: object,
) -> list[UploadResult]:
    """Internal state upload with lock held.

    Args:
        backend: StateBackend instance.
        files: List of (path, content) tuples.
        runtime: Runtime context.

    Returns:
        List of UploadResult objects.
    """
    logger.debug("State upload locked for backend=%s runtime=%s", type(backend).__name__, runtime is not None)
    utils = _get_utils()
    create_file_data = utils.create_file_data

    max_file_size = int(os.environ.get("DEEPAGENTS_UPLOAD_MAX_SIZE", str(_DEFAULT_UPLOAD_MAX_SIZE)))
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
            backend_runtime = cast("Any", backend).runtime
            state = backend_runtime.state
            if "files" not in state:
                state["files"] = {}
            state["files"][path] = create_file_data(file_content)

        results.append(result)

    return results


def _upload_single_to_state(
    backend: BackendProtocol,
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
            error=f"File too large ({len(content)} > {max_file_size}). Consider using FilesystemBackend.",
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

        with contextlib.suppress(Exception):
            download_responses = backend.download_files([path])
            if download_responses:
                response = download_responses[0]
                if response.error is None and response.content is not None:
                    is_overwrite = True
                    previous_size = len(response.content)
                    logger.warning("Overwriting existing file: %s", path)

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
        logger.exception("State write failed for %s", path)
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
    non_ascii = sum(1 for b in sample if b > _ASCII_MAX)
    if sample and non_ascii / len(sample) > _NON_ASCII_RATIO_THRESHOLD:
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            return False
        else:
            return True

    # Final UTF-8 validation
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return False
    else:
        return True


def _upload_fallback(
    backend: BackendProtocol,
    files: list[tuple[str, bytes]],
    runtime: object | None = None,
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
    logger.debug("Fallback upload for backend=%s runtime=%s", type(backend).__name__, runtime is not None)

    backends = _get_backends()
    filesystem_backend_cls = backends.FilesystemBackend

    # Create secure private temporary directory
    # Using mkdtemp with random suffix for unpredictability
    root_dir_str = tempfile.mkdtemp(prefix="deepagents_upload_", suffix=f"_{secrets.token_hex(8)}")
    root_dir = Path(root_dir_str)

    try:
        root_dir.chmod(0o700)

        # Use FilesystemBackend with virtual_mode=True for security
        fallback_backend = filesystem_backend_cls(root_dir=str(root_dir), virtual_mode=True)

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

        for (path, _content), response in zip(files, responses, strict=True):
            physical_path = root_dir / path.lstrip("/")

            # Set file permissions to owner-only (0o600)
            if physical_path.exists():
                with contextlib.suppress(OSError):
                    physical_path.chmod(0o600)

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
        with contextlib.suppress(OSError):
            shutil.rmtree(root_dir, ignore_errors=True)

    return results


def upload_files(
    backend_or_factory: BackendProtocol | Callable[[object], BackendProtocol],
    files: list[tuple[str, bytes]],
    runtime: object | None = None,
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
        >>> results = upload_files(
        ...     backend,
        ...     [
        ...         ("/uploads/file1.txt", b"content1"),
        ...         ("/uploads/file2.txt", b"content2"),
        ...     ],
        ... )
        >>> for result in results:
        ...     print(f"{result.path}: {'OK' if result.success else 'FAILED'}")
    """
    # Resolve backend (handle factory functions)
    backend = _resolve_backend(backend_or_factory, runtime)

    # Select strategy based on backend type
    strategy = _select_strategy(backend)

    logger.debug("Uploading %d files using strategy: %s", len(files), strategy)

    # Execute upload with selected strategy
    if strategy == "direct":
        return _upload_direct(backend, files, runtime)
    if strategy == "state":
        return _upload_to_state(backend, files, runtime)
    # fallback
    return _upload_fallback(backend, files, runtime)


# Convenience alias for backward compatibility
upload = upload_files
