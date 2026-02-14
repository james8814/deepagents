"""StateSyncBackend: A wrapper that syncs sandbox file operations to LangGraph state.

This module provides a backend wrapper that enables UI visibility of files
created in external sandboxes (Daytona, Modal, etc.) by synchronizing file
metadata to LangGraph state while the actual files remain in the sandbox.

Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │                     StateSyncBackend                         │
    │  ┌─────────────────────┐    ┌─────────────────────────────┐ │
    │  │   Sandbox Backend   │    │     LangGraph State         │ │
    │  │   (Daytona/Modal)   │    │     (files metadata)        │ │
    │  │   - Actual files    │    │     - For UI visibility     │ │
    │  │   - Command exec    │    │     - Checkpointing         │ │
    │  └─────────────────────┘    └─────────────────────────────┘ │
    └─────────────────────────────────────────────────────────────┘

Usage:
    ```python
    from state_sync_backend import StateSyncBackend
    from deepagents_cli.integrations.daytona import DaytonaBackend

    # Wrap your sandbox backend
    sandbox = DaytonaBackend(daytona_sandbox)
    sync_backend = StateSyncBackend(sandbox)

    # Use in agent creation
    agent = create_deep_agent(
        model=model,
        backend=sync_backend,  # Files will sync to state for UI visibility
    )
    ```

This design:
- Preserves all sandbox capabilities (execution, real filesystem)
- Enables UI visibility via LangGraph state synchronization
- Maintains backward compatibility (no changes to deepagents core)
- Works with any SandboxBackendProtocol implementation
"""

from typing import Any

from deepagents.backends.protocol import (
    EditResult,
    ExecuteResponse,
    FileDownloadResponse,
    FileInfo,
    FileUploadResponse,
    GrepMatch,
    SandboxBackendProtocol,
    WriteResult,
)
from deepagents.backends.utils import create_file_data, update_file_data


class StateSyncBackend(SandboxBackendProtocol):
    """Wrapper that synchronizes sandbox file operations to LangGraph state.

    This backend wraps any SandboxBackendProtocol and adds state synchronization
    for write/edit operations, enabling UI visibility of files in external sandboxes.

    The actual file content is stored in the sandbox (for execution), while
    metadata is synced to LangGraph state (for UI display and checkpointing).

    Attributes:
        _backend: The underlying sandbox backend (Daytona, Modal, etc.)
        _state_files: In-memory cache of file data for state synchronization

    Example:
        ```python
        from daytona import Daytona
        from deepagents_cli.integrations.daytona import DaytonaBackend
        from state_sync_backend import StateSyncBackend

        # Create sandbox backend
        daytona = Daytona(config)
        sandbox = daytona.create(...)
        daytona_backend = DaytonaBackend(sandbox)

        # Wrap with state sync
        backend = StateSyncBackend(daytona_backend)

        # Now write_file will update both sandbox AND LangGraph state
        ```
    """

    def __init__(self, backend: SandboxBackendProtocol) -> None:
        """Initialize the state-syncing wrapper.

        Args:
            backend: The underlying sandbox backend to wrap.
                     Must implement SandboxBackendProtocol.
        """
        self._backend = backend
        # In-memory cache for state synchronization
        # Maps file_path -> FileData dict (with content, created_at, modified_at)
        self._state_files: dict[str, dict[str, Any]] = {}

    @property
    def id(self) -> str:
        """Unique identifier from the underlying sandbox."""
        return self._backend.id

    # ==================== File Operations ====================

    def ls_info(self, path: str) -> list[FileInfo]:
        """List files from sandbox, enriched with state metadata if available."""
        return self._backend.ls_info(path)

    async def als_info(self, path: str) -> list[FileInfo]:
        """Async version of ls_info."""
        return await self._backend.als_info(path)

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:
        """Read file content from sandbox."""
        return self._backend.read(file_path, offset=offset, limit=limit)

    async def aread(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:
        """Async version of read."""
        return await self._backend.aread(file_path, offset=offset, limit=limit)

    def write(self, file_path: str, content: str) -> WriteResult:
        """Write to sandbox AND sync metadata to state for UI visibility.

        This method:
        1. Writes the actual file to the sandbox
        2. Creates FileData metadata for state synchronization
        3. Returns WriteResult with files_update for LangGraph state

        The files_update enables the UI's ContextPanel to display the file,
        while the actual content remains in the sandbox for execution.
        """
        # First, write to the underlying sandbox
        result = self._backend.write(file_path, content)

        if result.error:
            return result

        # Create FileData for state synchronization
        file_data = create_file_data(content)

        # Update our in-memory cache
        self._state_files[file_path] = file_data

        # Return with files_update for LangGraph state synchronization
        return WriteResult(
            path=result.path,
            files_update={file_path: file_data},
        )

    async def awrite(self, file_path: str, content: str) -> WriteResult:
        """Async version of write."""
        result = await self._backend.awrite(file_path, content)

        if result.error:
            return result

        # Create FileData for state synchronization
        file_data = create_file_data(content)

        # Update our in-memory cache
        self._state_files[file_path] = file_data

        return WriteResult(
            path=result.path,
            files_update={file_path: file_data},
        )

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        """Edit file in sandbox AND sync metadata to state.

        Similar to write(), this updates both the sandbox file and
        LangGraph state metadata.
        """
        result = self._backend.edit(file_path, old_string, new_string, replace_all=replace_all)

        if result.error:
            return result

        # Get existing file data or read from sandbox
        if file_path in self._state_files:
            existing_data = self._state_files[file_path]
            # We need to compute the new content
            # Read from sandbox to get the updated content
            try:
                new_content = self._backend.read(file_path)
                # Remove line numbers from read output
                lines = []
                for line in new_content.split("\n"):
                    if "\t" in line:
                        lines.append(line.split("\t", 1)[1] if "\t" in line else line)
                    else:
                        lines.append(line)
                new_content_str = "\n".join(lines)

                updated_data = update_file_data(existing_data, new_content_str)
            except Exception:
                # Fallback: just update timestamp
                updated_data = existing_data.copy()
                from datetime import UTC, datetime

                updated_data["modified_at"] = datetime.now(UTC).isoformat()
        else:
            # No cached data, read from sandbox
            try:
                content = self._backend.read(file_path)
                # Remove line numbers
                lines = []
                for line in content.split("\n"):
                    if "\t" in line:
                        lines.append(line.split("\t", 1)[1] if "\t" in line else line)
                    else:
                        lines.append(line)
                content_str = "\n".join(lines)
                updated_data = create_file_data(content_str)
            except Exception:
                # Last resort: create minimal metadata
                updated_data = create_file_data("")

        # Update cache
        self._state_files[file_path] = updated_data

        return EditResult(
            path=result.path,
            files_update={file_path: updated_data},
            occurrences=result.occurrences,
        )

    async def aedit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        """Async version of edit."""
        result = await self._backend.aedit(file_path, old_string, new_string, replace_all=replace_all)

        if result.error:
            return result

        # Similar logic to sync edit
        if file_path in self._state_files:
            existing_data = self._state_files[file_path]
            try:
                new_content = await self._backend.aread(file_path)
                lines = []
                for line in new_content.split("\n"):
                    if "\t" in line:
                        lines.append(line.split("\t", 1)[1] if "\t" in line else line)
                    else:
                        lines.append(line)
                new_content_str = "\n".join(lines)
                updated_data = update_file_data(existing_data, new_content_str)
            except Exception:
                updated_data = existing_data.copy()
                from datetime import UTC, datetime

                updated_data["modified_at"] = datetime.now(UTC).isoformat()
        else:
            try:
                content = await self._backend.aread(file_path)
                lines = []
                for line in content.split("\n"):
                    if "\t" in line:
                        lines.append(line.split("\t", 1)[1] if "\t" in line else line)
                    else:
                        lines.append(line)
                content_str = "\n".join(lines)
                updated_data = create_file_data(content_str)
            except Exception:
                updated_data = create_file_data("")

        self._state_files[file_path] = updated_data

        return EditResult(
            path=result.path,
            files_update={file_path: updated_data},
            occurrences=result.occurrences,
        )

    # ==================== Search Operations ====================

    def grep_raw(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
    ) -> list[GrepMatch] | str:
        """Search files in sandbox."""
        return self._backend.grep_raw(pattern, path, glob)

    async def agrep_raw(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
    ) -> list[GrepMatch] | str:
        """Async version of grep_raw."""
        return await self._backend.agrep_raw(pattern, path, glob)

    def glob_info(self, pattern: str, path: str = "/") -> list[FileInfo]:
        """Find files matching glob pattern in sandbox."""
        return self._backend.glob_info(pattern, path)

    async def aglob_info(self, pattern: str, path: str = "/") -> list[FileInfo]:
        """Async version of glob_info."""
        return await self._backend.aglob_info(pattern, path)

    # ==================== Execution ====================

    def execute(self, command: str) -> ExecuteResponse:
        """Execute command in sandbox."""
        return self._backend.execute(command)

    async def aexecute(self, command: str) -> ExecuteResponse:
        """Async version of execute."""
        return await self._backend.aexecute(command)

    # ==================== Upload/Download ====================

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """Upload files to sandbox."""
        return self._backend.upload_files(files)

    async def aupload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """Async version of upload_files."""
        return await self._backend.aupload_files(files)

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """Download files from sandbox."""
        return self._backend.download_files(paths)

    async def adownload_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """Async version of download_files."""
        return await self._backend.adownload_files(paths)
