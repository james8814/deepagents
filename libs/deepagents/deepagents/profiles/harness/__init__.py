"""Harness profile package: `HarnessProfile` API and built-in registrations.

Individual built-in modules expose a zero-arg `register()` callable; the lazy
`_builtin_profiles` bootstrap invokes them once on first profile-registry
access. Built-ins must not register at module import time — registration runs
under the bootstrap mutex, so a top-level call would race with concurrent
lookups and bypass the additive-merge semantics.
"""

from deepagents.profiles.harness.harness_profiles import (
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    HarnessProfileConfig,
    register_harness_profile,
)

# A14 alias: backward-compat name for pmagent imports (Phase 2b cutover safety net).
# 防御性 alias — 与 profiles/__init__.py 同模式, 应对未来 pmagent 可能扩展 import path.
_HarnessProfile = HarnessProfile

__all__ = [
    "GeneralPurposeSubagentProfile",
    "HarnessProfile",
    "HarnessProfileConfig",
    "_HarnessProfile",
    "register_harness_profile",
]
