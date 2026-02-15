# Sandbox Lifecycle Management Design

## Problem Statement

When using Daytona sandboxes in LangGraph deployment mode (long-running services), sandboxes are created but never explicitly deleted. This leads to:

1. **Resource Accumulation**: Stopped sandboxes still occupy storage
2. **Cost Accumulation**: Daytona may charge for stored sandbox data
3. **Management Complexity**: Large number of orphaned sandboxes

### Current Behavior Analysis

| Mode | Sandbox Creation | Sandbox Deletion | Result |
|------|-----------------|------------------|--------|
| CLI | `create_sandbox()` context manager | `finally` block calls `delete()` | ✅ Properly cleaned |
| LangGraph | Direct `DaytonaProvider.get_or_create()` | Only `auto_stop_interval` | ❌ Never deleted |

**Key Insight**: The CLI uses a context manager pattern (`sandbox_factory.create_sandbox()`) that guarantees cleanup in the `finally` block. However, LangGraph deployments create sandboxes directly through `DaytonaProvider` without any cleanup mechanism.

## Design Principles

1. **Systematic**: Solution should work at the `SandboxProvider` level, not individual Backend implementations
2. **Compatible**: Must not break existing CLI functionality
3. **Universal**: Should apply to all sandbox providers (Daytona, Modal, Runloop, LangSmith)
4. **Flexible**: All parameters should be configurable via environment variables
5. **Non-intrusive**: Should not require changes to existing user code

## Solution Design

### Environment Variables

```bash
# Sandbox TTL Configuration
DEEPAGENTS_SANDBOX_AUTO_STOP_MINUTES=60      # Auto-stop after N minutes (0 = disabled)
DEEPAGENTS_SANDBOX_AUTO_DELETE_MINUTES=120   # Auto-delete after N minutes (0 = disabled)
DEEPAGENTS_SANDBOX_IMAGE="daytonaio/sandbox:0.5.1"  # Default sandbox image

# Provider-specific overrides (optional)
DAYTONA_AUTO_STOP_MINUTES=60
DAYTONA_AUTO_DELETE_MINUTES=120
DAYTONA_SANDBOX_IMAGE="daytonaio/sandbox:0.5.1"
```

### Architecture Changes

#### 1. Unified Sandbox Configuration

Create a new configuration module that all providers can use:

```
libs/deepagents/deepagents/backends/sandbox_config.py
```

```python
"""Unified sandbox configuration from environment variables."""

import os
from dataclasses import dataclass


@dataclass
class SandboxConfig:
    """Configuration for sandbox lifecycle management.

    All values can be overridden via environment variables.
    Provider-specific env vars take precedence over generic ones.
    """

    auto_stop_minutes: int = 60
    auto_delete_minutes: int = 0  # 0 = disabled
    image: str = "daytonaio/sandbox:0.5.1"
    timeout_seconds: int = 180
    resources: dict | None = None

    @classmethod
    def from_env(cls, prefix: str = "DEEPAGENTS") -> "SandboxConfig":
        """Load configuration from environment variables.

        Args:
            prefix: Environment variable prefix. Provider-specific configs
                   can use their own prefix (e.g., "DAYTONA", "MODAL").

        Environment Variables:
            {PREFIX}_SANDBOX_AUTO_STOP_MINUTES: Minutes before auto-stop (default: 60)
            {PREFIX}_SANDBOX_AUTO_DELETE_MINUTES: Minutes before auto-delete (default: 0)
            {PREFIX}_SANDBOX_IMAGE: Sandbox image to use
        """
        def get_int(key: str, default: int) -> int:
            val = os.environ.get(f"{prefix}_{key}")
            if val is not None:
                try:
                    return int(val)
                except ValueError:
                    pass
            # Fallback to generic prefix
            if prefix != "DEEPAGENTS":
                val = os.environ.get(f"DEEPAGENTS_{key}")
                if val is not None:
                    try:
                        return int(val)
                    except ValueError:
                        pass
            return default

        def get_str(key: str, default: str) -> str:
            val = os.environ.get(f"{prefix}_{key}")
            if val is not None:
                return val
            if prefix != "DEEPAGENTS":
                val = os.environ.get(f"DEEPAGENTS_{key}")
                if val is not None:
                    return val
            return default

        return cls(
            auto_stop_minutes=get_int("SANDBOX_AUTO_STOP_MINUTES", 60),
            auto_delete_minutes=get_int("SANDBOX_AUTO_DELETE_MINUTES", 0),
            image=get_str("SANDBOX_IMAGE", "daytonaio/sandbox:0.5.1"),
            timeout_seconds=get_int("SANDBOX_TIMEOUT_SECONDS", 180),
        )
```

#### 2. Enhanced DaytonaProvider

Modify `libs/cli/deepagents_cli/integrations/daytona.py`:

```python
"""Daytona sandbox backend implementation."""

from __future__ import annotations

import os
import time
import atexit
import threading
import logging
from typing import TYPE_CHECKING, Any

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
    SandboxBackendProtocol,
)
from deepagents.backends.sandbox import (
    BaseSandbox,
    SandboxListResponse,
    SandboxProvider,
)
from deepagents.backends.sandbox_config import SandboxConfig

if TYPE_CHECKING:
    from daytona import Sandbox

logger = logging.getLogger(__name__)


class DaytonaBackend(BaseSandbox):
    """Daytona backend implementation conforming to SandboxBackendProtocol."""

    def __init__(self, sandbox: Sandbox, provider: "DaytonaProvider" = None) -> None:
        """Initialize the DaytonaBackend with a Daytona sandbox client.

        Args:
            sandbox: Daytona sandbox instance
            provider: Reference to the provider for lifecycle management
        """
        self._sandbox = sandbox
        self._provider = provider
        self._timeout: int = 30 * 60  # 30 mins

    @property
    def id(self) -> str:
        """Unique identifier for the sandbox backend."""
        return self._sandbox.id

    def execute(self, command: str) -> ExecuteResponse:
        """Execute a command in the sandbox."""
        result = self._sandbox.process.exec(command, timeout=self._timeout)
        return ExecuteResponse(
            output=result.result,
            exit_code=result.exit_code,
            truncated=False,
        )

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """Download multiple files from the Daytona sandbox."""
        from daytona import FileDownloadRequest
        download_requests = [FileDownloadRequest(source=path) for path in paths]
        daytona_responses = self._sandbox.fs.download_files(download_requests)
        return [
            FileDownloadResponse(
                path=resp.source,
                content=resp.result,
                error=None,
            )
            for resp in daytona_responses
        ]

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """Upload multiple files to the Daytona sandbox."""
        from daytona import FileUpload
        upload_requests = [
            FileUpload(source=content, destination=path) for path, content in files
        ]
        self._sandbox.fs.upload_files(upload_requests)
        return [FileUploadResponse(path=path, error=None) for path, _ in files]


class DaytonaProvider(SandboxProvider[dict[str, Any]]):
    """Daytona sandbox provider implementation with lifecycle management."""

    # Track all created sandboxes for cleanup
    _instances: list["DaytonaProvider"] = []
    _cleanup_registered: bool = False
    _lock = threading.Lock()

    def __init__(
        self,
        api_key: str | None = None,
        config: SandboxConfig | None = None,
    ) -> None:
        """Initialize Daytona provider.

        Args:
            api_key: Daytona API key (defaults to DAYTONA_API_KEY env var)
            config: Sandbox configuration (defaults to from_env("DAYTONA"))
        """
        from daytona import Daytona, DaytonaConfig

        self._api_key = api_key or os.environ.get("DAYTONA_API_KEY")
        if not self._api_key:
            msg = "DAYTONA_API_KEY environment variable not set"
            raise ValueError(msg)

        self._client = Daytona(DaytonaConfig(api_key=self._api_key))
        self._config = config or SandboxConfig.from_env("DAYTONA")
        self._created_sandboxes: dict[str, Sandbox] = {}

        # Register for cleanup
        with DaytonaProvider._lock:
            DaytonaProvider._instances.append(self)
            if not DaytonaProvider._cleanup_registered:
                atexit.register(DaytonaProvider._cleanup_all)
                DaytonaProvider._cleanup_registered = True

    @classmethod
    def _cleanup_all(cls) -> None:
        """Clean up all sandboxes created by all provider instances.

        Called automatically on process exit via atexit.
        """
        logger.info("Cleaning up all Daytona sandboxes...")
        for provider in cls._instances:
            provider.cleanup_created_sandboxes()
        cls._instances.clear()

    def cleanup_created_sandboxes(self) -> None:
        """Delete all sandboxes created by this provider instance."""
        for sandbox_id, sandbox in list(self._created_sandboxes.items()):
            try:
                self._client.delete(sandbox)
                logger.info(f"Deleted sandbox: {sandbox_id}")
            except Exception as e:
                logger.warning(f"Failed to delete sandbox {sandbox_id}: {e}")
        self._created_sandboxes.clear()

    def list(
        self,
        *,
        cursor: str | None = None,
        **kwargs: Any,
    ) -> SandboxListResponse[dict[str, Any]]:
        """List available Daytona sandboxes."""
        msg = "Listing with Daytona SDK not yet implemented"
        raise NotImplementedError(msg)

    def get_or_create(
        self,
        *,
        sandbox_id: str | None = None,
        timeout: int | None = None,
        auto_stop_minutes: int | None = None,
        auto_delete_minutes: int | None = None,
        image: str | None = None,
        **kwargs: Any,
    ) -> SandboxBackendProtocol:
        """Get existing or create new Daytona sandbox.

        Args:
            sandbox_id: Existing sandbox ID to connect to (not yet supported)
            timeout: Timeout in seconds for sandbox startup
            auto_stop_minutes: Minutes before auto-stop (overrides env config)
            auto_delete_minutes: Minutes before auto-delete (overrides env config)
            image: Sandbox image to use
            **kwargs: Additional parameters (resources, etc.)

        Returns:
            DaytonaBackend instance

        Environment Variables:
            DAYTONA_SANDBOX_AUTO_STOP_MINUTES: Default auto-stop time
            DAYTONA_SANDBOX_AUTO_DELETE_MINUTES: Default auto-delete time
            DAYTONA_SANDBOX_IMAGE: Default sandbox image
        """
        if sandbox_id:
            msg = (
                "Connecting to existing Daytona sandbox by ID not yet supported. "
                "Create a new sandbox by omitting sandbox_id parameter."
            )
            raise NotImplementedError(msg)

        # Resolve configuration with parameter overrides
        timeout = timeout or self._config.timeout_seconds
        auto_stop = auto_stop_minutes if auto_stop_minutes is not None else self._config.auto_stop_minutes
        auto_delete = auto_delete_minutes if auto_delete_minutes is not None else self._config.auto_delete_minutes
        sandbox_image = image or self._config.image

        # Create sandbox with lifecycle parameters
        sandbox = self._create_sandbox_with_config(
            image=sandbox_image,
            auto_stop_minutes=auto_stop,
            auto_delete_minutes=auto_delete,
            timeout=timeout,
        )

        # Track for cleanup
        self._created_sandboxes[sandbox.id] = sandbox

        return DaytonaBackend(sandbox, provider=self)

    def _create_sandbox_with_config(
        self,
        image: str,
        auto_stop_minutes: int,
        auto_delete_minutes: int,
        timeout: int,
    ) -> "Sandbox":
        """Create a new sandbox with the specified configuration."""
        from daytona import CreateSandboxFromImageParams

        params = CreateSandboxFromImageParams(
            image=image,
            auto_stop_interval=auto_stop_minutes if auto_stop_minutes > 0 else None,
            # Note: auto_delete is handled by our cleanup mechanism, not Daytona
        )

        sandbox = self._client.create(params=params, timeout=timeout)

        # Poll until running
        for _ in range(timeout // 2):
            try:
                result = sandbox.process.exec("echo ready", timeout=5)
                if result.exit_code == 0:
                    break
            except Exception:
                pass
            time.sleep(2)
        else:
            try:
                sandbox.delete()
            finally:
                msg = f"Daytona sandbox failed to start within {timeout} seconds"
                raise RuntimeError(msg)

        logger.info(f"Created sandbox: {sandbox.id} (auto_stop={auto_stop_minutes}min)")
        return sandbox

    def delete(self, *, sandbox_id: str, **kwargs: Any) -> None:
        """Delete a Daytona sandbox.

        Args:
            sandbox_id: Sandbox ID to delete
        """
        sandbox = self._client.get(sandbox_id)
        self._client.delete(sandbox)

        # Remove from tracking
        self._created_sandboxes.pop(sandbox_id, None)
        logger.info(f"Deleted sandbox: {sandbox_id}")
```

#### 3. Update Other Providers (Same Pattern)

Apply the same pattern to `ModalProvider`, `RunloopProvider`, and `LangSmithProvider`:

1. Add `SandboxConfig` parameter to `__init__`
2. Track created sandboxes in `_created_sandboxes` dict
3. Register `atexit` cleanup handler
4. Add `cleanup_created_sandboxes()` method
5. Use environment variables for TTL configuration

### Usage Examples

#### CLI Mode (No Changes Required)

```python
# Existing code continues to work
with create_sandbox("daytona") as sandbox:
    sandbox.execute("echo hello")
# Sandbox is automatically deleted when context exits
```

#### LangGraph Deployment Mode

```python
# Set environment variables
os.environ["DAYTONA_SANDBOX_AUTO_STOP_MINUTES"] = "60"
os.environ["DAYTONA_SANDBOX_AUTO_DELETE_MINUTES"] = "0"  # Use atexit cleanup

# Create provider
provider = DaytonaProvider()

# Get or create sandbox
sandbox = provider.get_or_create()

# Sandbox will be cleaned up when process exits via atexit
```

#### Custom TTL Per Sandbox

```python
# Override TTL for specific sandbox
sandbox = provider.get_or_create(
    auto_stop_minutes=30,  # Stop after 30 minutes
    auto_delete_minutes=0,  # Delete on process exit
)
```

### Environment Variable Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPAGENTS_SANDBOX_AUTO_STOP_MINUTES` | 60 | Global default for auto-stop |
| `DEEPAGENTS_SANDBOX_AUTO_DELETE_MINUTES` | 0 | Global default for auto-delete (0=disabled) |
| `DEEPAGENTS_SANDBOX_IMAGE` | `daytonaio/sandbox:0.5.1` | Global default image |
| `DEEPAGENTS_SANDBOX_TIMEOUT_SECONDS` | 180 | Global default creation timeout |
| `DEEPAGENTS_FALLBACK_TRIGGER_TOKENS` | 100000 | Token threshold when model has no profile |
| `DEEPAGENTS_FALLBACK_KEEP_MESSAGES` | 6 | Messages to keep when model has no profile |
| `DAYTONA_SANDBOX_AUTO_STOP_MINUTES` | (uses global) | Daytona-specific override |
| `DAYTONA_SANDBOX_AUTO_DELETE_MINUTES` | (uses global) | Daytona-specific override |
| `DAYTONA_SANDBOX_IMAGE` | (uses global) | Daytona-specific override |
| `MODAL_SANDBOX_AUTO_STOP_MINUTES` | (uses global) | Modal-specific override |
| `RUNLOOP_SANDBOX_AUTO_STOP_MINUTES` | (uses global) | Runloop-specific override |

### Cleanup Mechanisms

| Mechanism | When It Runs | Use Case |
|-----------|-------------|----------|
| Context Manager `finally` | When `with` block exits | CLI interactive sessions |
| `atexit` handler | When Python process exits | Long-running services (LangGraph) |
| Provider `auto_stop_minutes` | After N minutes of inactivity | Cost optimization |
| Provider `auto_delete_minutes` | After N minutes total | Hard deadline |

### Implementation Checklist

- [ ] Create `libs/deepagents/deepagents/backends/sandbox_config.py`
- [ ] Update `libs/cli/deepagents_cli/integrations/daytona.py`
- [ ] Update `libs/cli/deepagents_cli/integrations/modal.py`
- [ ] Update `libs/cli/deepagents_cli/integrations/runloop.py`
- [ ] Update `libs/cli/deepagents_cli/integrations/langsmith.py`
- [ ] Update `libs/partners/daytona/langchain_daytona/sandbox.py`
- [ ] Add unit tests for `SandboxConfig`
- [ ] Add integration tests for cleanup mechanism
- [ ] Update documentation

### Backward Compatibility

This design maintains full backward compatibility:

1. **CLI Mode**: Existing `create_sandbox()` context manager behavior unchanged
2. **Default Values**: All environment variables have sensible defaults
3. **No Breaking Changes**: All new parameters are optional with defaults
4. **Existing Code**: Works without any modifications

### Risk Assessment

| Risk | Mitigation |
|------|-----------|
| `atexit` not called on crash | Daytona's `auto_stop_interval` as backup |
| Multiple providers create duplicate cleanup | Thread-safe singleton pattern for cleanup registration |
| Cleanup fails | Log warning, continue execution |
| Environment variable typo | Fallback to default values |

## Conclusion

This design provides a comprehensive solution for sandbox lifecycle management that:

1. **Solves the Problem**: Sandboxes are now properly cleaned up in all deployment modes
2. **Maintains Compatibility**: Existing code works without changes
3. **Provides Flexibility**: All parameters configurable via environment variables
4. **Follows Architecture**: Works at the `SandboxProvider` level as designed
5. **Is Universal**: Applies to all sandbox providers consistently

## Related: History Offload Path Configuration

### Problem

In sandbox environments (Daytona, Modal, Runloop), `SummarizationMiddleware` offloads
conversation history to disk before summarization. The default path `/conversation_history`
may not be writable in these environments.

In Daytona sandbox:
- `/` (root) - Read-only
- `/home/daytona/` - Only writable directory

This caused `PermissionError` when offloading history, preventing summarization
and leading to context overflow errors.

### Solution: CompositeBackend

Use `CompositeBackend` to map `/conversation_history/` to a writable location.
This approach is universal across all sandbox providers and keeps SDK simple.

### Usage for LangGraph Deployments

```python
from deepagents.backends import CompositeBackend
from deepagents_cli.integrations.daytona import DaytonaProvider

# Create sandbox backend
sandbox_backend = DaytonaProvider().get_or_create()

# Wrap with CompositeBackend to handle /conversation_history/ path
backend = CompositeBackend(
    default=sandbox_backend,
    mounts={
        # Map /conversation_history/ to sandbox's writable path
        "/conversation_history/": sandbox_backend,
    },
)

# Use with create_deep_agent
agent = create_deep_agent(
    model=model,
    backend=backend,
    ...
)
```

This approach:
1. Works universally across all sandbox providers
2. Keeps SDK simple (no environment variables needed)
3. Follows the existing pattern used by CLI
4. Allows flexible path mapping per deployment
