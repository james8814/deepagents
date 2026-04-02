from __future__ import annotations

import importlib.util
import os

import pytest


def _has_module(name: str) -> bool:
    spec = importlib.util.find_spec(name)
    return spec is not None


def _has_env_var(name: str) -> bool:
    return bool(os.getenv(name))


def _ensure_openai_compatible_env() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key

    if os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE"):
        return

    if os.getenv("DEEPSEEK_API_KEY"):
        base_url = os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1"
    elif os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY"):
        base_url = os.getenv("DASHSCOPE_BASE_URL") or os.getenv("QWEN_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    else:
        return

    os.environ.setdefault("OPENAI_BASE_URL", base_url)
    os.environ.setdefault("OPENAI_API_BASE", base_url)


def _has_any_llm_credentials() -> bool:
    if _has_module("langchain_anthropic") and _has_env_var("ANTHROPIC_API_KEY"):
        return True
    _ensure_openai_compatible_env()
    return _has_module("langchain_openai") and _has_env_var("OPENAI_API_KEY")


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
            _ensure_openai_compatible_env()
            if not _has_module("langchain_openai") or not _has_env_var("OPENAI_API_KEY"):
                missing.append("langchain_openai/OPENAI_API_KEY")
        elif dependency == "llm":
            if not _has_any_llm_credentials():
                missing.append("llm credentials (ANTHROPIC_API_KEY or OpenAI-compatible key)")

    if missing:
        pytest.skip(f"Skipping because required dependencies are missing: {', '.join(missing)}")
