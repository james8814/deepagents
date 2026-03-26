from __future__ import annotations

import importlib.util
import os

import pytest


def _has_module(name: str) -> bool:
    spec = importlib.util.find_spec(name)
    return spec is not None


def _has_env_var(name: str) -> bool:
    return bool(os.getenv(name))


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "requires(*dependencies): skip test unless required optional dependencies are available.",
    )


def pytest_runtest_setup(item: pytest.Item) -> None:
    marker = item.get_closest_marker("requires")
    if marker is None:
        return

    missing: list[str] = []
    for dependency in marker.args:
        if dependency == "langchain_anthropic":
            if not _has_module("langchain_anthropic") or not _has_env_var("ANTHROPIC_API_KEY"):
                missing.append("langchain_anthropic/ANTHROPIC_API_KEY")
        elif dependency == "langchain_openai":
            if not _has_module("langchain_openai") or not _has_env_var("OPENAI_API_KEY"):
                missing.append("langchain_openai/OPENAI_API_KEY")

    if missing:
        pytest.skip(f"Skipping because required dependencies are missing: {', '.join(missing)}")
