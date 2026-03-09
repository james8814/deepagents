"""Test utilities for CLI tests.

This module provides common utilities for CLI tests, including:
- Skip decorators for tests requiring cloud services
- Fixtures for test isolation
"""

from __future__ import annotations

import os
from collections.abc import Callable

import pytest

__all__ = [
    "skip_if_no_anthropic",
    "skip_if_no_dashscope",
    "skip_if_no_daytona",
    "skip_if_no_key",
    "skip_if_no_langsmith",
    "skip_if_no_modal",
    "skip_if_no_openai",
    "skip_if_no_runloop",
]


def skip_if_no_key(*keys: str) -> pytest.MarkDecorator:
    """Create a pytest skip marker if any required environment keys are missing.

    This decorator allows tests to be skipped when required cloud service
    credentials are not available in the environment.

    Args:
        *keys: One or more environment variable names to check.

    Returns:
        A pytest.mark.skipif decorator that skips the test if any key is missing.

    Example:
        ```python
        @skip_if_no_key("DAYTONA_API_KEY")
        def test_daytona_integration():
            # This test will be skipped if DAYTONA_API_KEY is not set
            ...


        @skip_if_no_key("RUNLOOP_API_KEY", "MODAL_TOKEN")
        def test_multi_cloud():
            # Requires both keys
            ...
        ```
    """
    missing = [k for k in keys if not os.environ.get(k)]
    return pytest.mark.skipif(
        bool(missing),
        reason=f"Missing environment variable(s): {', '.join(missing)}",
    )


def skip_if_no_langsmith() -> pytest.MarkDecorator:
    """Create a pytest skip marker if LangSmith credentials are missing.

    Checks for LANGSMITH_API_KEY or LANGCHAIN_API_KEY.

    Returns:
        A pytest.mark.skipif decorator.
    """
    has_key = bool(
        os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")
    )
    return pytest.mark.skipif(
        not has_key,
        reason="Missing LangSmith credentials (LANGSMITH_API_KEY or LANGCHAIN_API_KEY)",
    )


# Pre-defined skip markers for common cloud services
skip_if_no_daytona: pytest.MarkDecorator = skip_if_no_key("DAYTONA_API_KEY")
skip_if_no_runloop: pytest.MarkDecorator = skip_if_no_key("RUNLOOP_API_KEY")
skip_if_no_modal: pytest.MarkDecorator = skip_if_no_key(
    "MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET"
)
skip_if_no_openai: pytest.MarkDecorator = skip_if_no_key("OPENAI_API_KEY")
skip_if_no_anthropic: pytest.MarkDecorator = skip_if_no_key("ANTHROPIC_API_KEY")
skip_if_no_dashscope: pytest.MarkDecorator = skip_if_no_key("DASHSCOPE_API_KEY")
