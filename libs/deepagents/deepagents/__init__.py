"""Deep Agents package."""

from deepagents._version import __version__
from deepagents.graph import create_deep_agent
from deepagents.middleware.async_subagents import AsyncSubAgent, AsyncSubAgentMiddleware
from deepagents.middleware.filesystem import FilesystemMiddleware
from deepagents.middleware.memory import MemoryMiddleware
from deepagents.middleware.permissions import FilesystemPermission
from deepagents.middleware.subagents import CompiledSubAgent, SubAgent, SubAgentMiddleware
from deepagents.profiles import (
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    HarnessProfileConfig,
    ProviderProfile,
    register_harness_profile,
    register_provider_profile,
)
from deepagents.upload_adapter import UploadResult, upload_files

# A14 alias: backward-compatible names for pmagent imports (Phase 2b cutover safety net)
# pmagent 11 处 _HarnessProfile import 通过此 alias 透明工作
# Path 3 fork-side patch — 与 #2892 cherry-pick 同 commit
_HarnessProfile = HarnessProfile

__all__ = [
    "AsyncSubAgent",
    "AsyncSubAgentMiddleware",
    "CompiledSubAgent",
    "FilesystemMiddleware",
    "FilesystemPermission",
    "GeneralPurposeSubagentProfile",
    "HarnessProfile",
    "HarnessProfileConfig",
    "MemoryMiddleware",
    "ProviderProfile",
    "SubAgent",
    "SubAgentMiddleware",
    "UploadResult",
    "_HarnessProfile",
    "__version__",
    "create_deep_agent",
    "register_harness_profile",
    "register_provider_profile",
    "upload_files",
]
