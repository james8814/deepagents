#!/usr/bin/env python3
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

import deepagents.graph as graph_mod
from deepagents.graph import create_deep_agent
from deepagents.middleware.skills import SkillsMiddleware

if TYPE_CHECKING:
    import pytest

    MonkeyPatch = pytest.MonkeyPatch


class _DummyCompiled:
    def __init__(self) -> None:
        self._config: dict[str, Any] = {}

    def with_config(self, cfg: dict[str, Any]) -> _DummyCompiled:
        self._config = cfg
        return self


def test_skills_expose_flag_wired_into_main_agent_middleware(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_create_agent(_model: Any, **kwargs: Any) -> _DummyCompiled:  # noqa: ANN401
        captured["middleware"] = kwargs.get("middleware", [])
        return _DummyCompiled()

    monkeypatch.setattr(graph_mod, "create_agent", _fake_create_agent)

    create_deep_agent(
        model=GenericFakeChatModel(messages=iter([])),
        skills=["/skills/user"],
        skills_expose_dynamic_tools=True,
    )

    mws = captured.get("middleware", [])
    assert any(isinstance(m, SkillsMiddleware) and getattr(m, "_expose_dynamic_tools", False) for m in mws)


def test_skills_expose_flag_defaults_false(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_create_agent(_model: Any, **kwargs: Any) -> _DummyCompiled:  # noqa: ANN401
        captured["middleware"] = kwargs.get("middleware", [])
        return _DummyCompiled()

    monkeypatch.setattr(graph_mod, "create_agent", _fake_create_agent)

    create_deep_agent(
        model=GenericFakeChatModel(messages=iter([])),
        skills=["/skills/user"],
    )

    mws = captured.get("middleware", [])
    assert any(isinstance(m, SkillsMiddleware) and getattr(m, "_expose_dynamic_tools", False) is False for m in mws)


def test_skills_expose_flag_wired_into_subagent_middleware(monkeypatch: MonkeyPatch) -> None:
    """Verify skills_expose_dynamic_tools is wired into SubAgent middleware specs."""
    captured_subagents: list[Any] = []

    def _fake_create_agent(_model: Any, **kwargs: Any) -> _DummyCompiled:  # noqa: ANN401
        # Capture subagents from SubAgentMiddleware
        middleware = kwargs.get("middleware", [])
        for mw in middleware:
            if hasattr(mw, "_subagents"):
                captured_subagents.extend(mw._subagents)
        return _DummyCompiled()

    monkeypatch.setattr(graph_mod, "create_agent", _fake_create_agent)

    create_deep_agent(
        model=GenericFakeChatModel(messages=iter([])),
        skills=["/skills/user"],
        skills_expose_dynamic_tools=True,
        subagents=[
            {
                "name": "researcher",
                "description": "Research agent",
                "system_prompt": "You research things.",
                "skills": ["/skills/research"],
            }
        ],
    )

    # Verify GP subagent has SkillsMiddleware with expose_dynamic_tools=True
    assert len(captured_subagents) >= 1, "Expected at least one subagent"

    for spec in captured_subagents:
        if "middleware" in spec:
            mws = spec["middleware"]
            skills_mws = [m for m in mws if isinstance(m, SkillsMiddleware)]
            for smw in skills_mws:
                assert getattr(smw, "_expose_dynamic_tools", False) is True, (
                    f"SubAgent '{spec.get('name', 'unknown')}' SkillsMiddleware should have expose_dynamic_tools=True"
                )


def test_main_agent_skips_default_skills_when_user_provided(monkeypatch: MonkeyPatch) -> None:
    """If user provides a SkillsMiddleware, default injection is skipped for main agent."""
    captured: dict[str, Any] = {}

    def _fake_create_agent(_model: Any, **kwargs: Any) -> _DummyCompiled:  # noqa: ANN401
        captured["middleware"] = kwargs.get("middleware", [])
        return _DummyCompiled()

    monkeypatch.setattr(graph_mod, "create_agent", _fake_create_agent)

    user_mw = SkillsMiddleware(backend=lambda rt: rt, sources=["/skills/user"])
    create_deep_agent(
        model=GenericFakeChatModel(messages=iter([])),
        skills=["/skills/user"],
        middleware=[user_mw],
        skills_expose_dynamic_tools=True,
    )

    mws = captured.get("middleware", [])
    skills_mws = [m for m in mws if isinstance(m, SkillsMiddleware)]
    assert len(skills_mws) == 1, "Expected exactly one SkillsMiddleware when user provides one"
    assert skills_mws[0] is user_mw


def test_subagent_skips_default_skills_when_user_provided(monkeypatch: MonkeyPatch) -> None:
    """If subagent provides a SkillsMiddleware, default injection is skipped for that subagent."""
    captured_subagents: list[Any] = []

    def _fake_create_agent(_model: Any, **kwargs: Any) -> _DummyCompiled:  # noqa: ANN401
        middleware = kwargs.get("middleware", [])
        for mw in middleware:
            if hasattr(mw, "_subagents"):
                captured_subagents.extend(mw._subagents)
        return _DummyCompiled()

    monkeypatch.setattr(graph_mod, "create_agent", _fake_create_agent)

    user_sub_mw = SkillsMiddleware(backend=lambda rt: rt, sources=["/skills/research"])
    create_deep_agent(
        model=GenericFakeChatModel(messages=iter([])),
        skills=["/skills/user"],
        skills_expose_dynamic_tools=True,
        subagents=[
            {
                "name": "researcher",
                "description": "Research agent",
                "system_prompt": "You research things.",
                "skills": ["/skills/research"],
                "middleware": [user_sub_mw],
            }
        ],
    )

    assert captured_subagents, "Expected captured subagents"
    specs_with_mw = [s for s in captured_subagents if s.get("name") == "researcher"]
    assert specs_with_mw, "Expected researcher subagent to be present"
    mws = specs_with_mw[0].get("middleware", [])
    skills_mws = [m for m in mws if isinstance(m, SkillsMiddleware)]
    assert len(skills_mws) == 1, "Expected exactly one SkillsMiddleware when user subagent provides one"
    assert skills_mws[0] is user_sub_mw


def test_subagent_skills_allowlist_is_wired(monkeypatch: MonkeyPatch) -> None:
    """Verify SubAgent.skills_allowlist is passed into SkillsMiddleware.allowed_skills."""
    captured_subagents: list[Any] = []

    def _fake_create_agent(_model: Any, **kwargs: Any) -> _DummyCompiled:  # noqa: ANN401
        middleware = kwargs.get("middleware", [])
        for mw in middleware:
            if hasattr(mw, "_subagents"):
                captured_subagents.extend(mw._subagents)
        return _DummyCompiled()

    monkeypatch.setattr(graph_mod, "create_agent", _fake_create_agent)

    allow = ["web-research", "code-review"]
    create_deep_agent(
        model=GenericFakeChatModel(messages=iter([])),
        skills=["/skills/user"],
        subagents=[
            {
                "name": "researcher",
                "description": "Research agent",
                "system_prompt": "You research things.",
                "skills": ["/skills/research", "/skills/user"],
                "skills_allowlist": allow,
            }
        ],
    )

    assert captured_subagents, "Expected captured subagents"
    spec = next(s for s in captured_subagents if s.get("name") == "researcher")
    mws = spec.get("middleware", [])
    skills_mws = [m for m in mws if isinstance(m, SkillsMiddleware)]
    assert skills_mws, "Expected SkillsMiddleware injected for researcher"
    allowed = getattr(skills_mws[0], "_allowed_skills", None)
    assert allowed is not None and set(allow) == set(allowed)
