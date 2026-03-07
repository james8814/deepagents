"""Integration tests for SkillsMiddleware dynamic loading with a fake LLM.

These tests execute a compiled deep agent end-to-end with a fake chat model
that emits tool calls for load_skill/unload_skill, verifying the middleware
updates state and emits tool outputs properly.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from langchain_core.language_models import LanguageModelInput
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

from deepagents.backends import FilesystemBackend
from deepagents.graph import create_deep_agent
from deepagents.middleware.skills import SkillsMiddleware


def _write_skill(tmp_path: Path, name: str, body: str = "# Body\n") -> Path:
    """Create a simple skill directory with SKILL.md and a resource file."""
    skill_dir = tmp_path / "skills" / "user" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    fm = "\n".join(["---", f"name: {name}", "description: Integration test skill", "---", ""])
    (skill_dir / "SKILL.md").write_text(fm + body, encoding="utf-8")
    # Add a resource to validate resource listing in tool output
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    (scripts_dir / "helper.py").write_text("print('ok')\n", encoding="utf-8")
    return skill_dir / "SKILL.md"


class FixedGenericFakeChatModel(GenericFakeChatModel):
    """Fixed version that properly handles bind_tools by returning self."""

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        return self


def test_dynamic_load_and_unload_skill_end_to_end(tmp_path: Path) -> None:
    """End-to-end: load then unload a skill via tool calls and validate messages."""
    _ = _write_skill(tmp_path, "alpha", body="# Alpha\nHello\n")
    skills_root = str(tmp_path / "skills" / "user")

    # Fake model emits two tool calls: load then unload
    model = FixedGenericFakeChatModel(
        messages=iter(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "load_skill", "args": {"skill_name": "alpha"}, "id": "call_1", "type": "tool_call"},
                    ],
                ),
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "unload_skill", "args": {"skill_name": "alpha"}, "id": "call_2", "type": "tool_call"},
                    ],
                ),
                AIMessage(content="Done."),
            ]
        )
    )

    backend = FilesystemBackend(root_dir=str(tmp_path))
    skills_mw = SkillsMiddleware(
        backend=backend,
        sources=[skills_root],
        expose_dynamic_tools=True,
        max_loaded_skills=2,
    )
    agent = create_deep_agent(model=model, middleware=[skills_mw])

    result = agent.invoke({"messages": [HumanMessage(content="manage skills")]})
    tool_messages = [m for m in result["messages"] if m.type == "tool"]
    assert len(tool_messages) >= 2
    # First tool message should include SKILL.md content header and resources header
    assert "Alpha" in tool_messages[0].content
    assert "Skill Resources" in tool_messages[0].content
    # Second tool message should confirm unload
    assert "has been unloaded" in tool_messages[1].content


def test_dynamic_load_twice_reports_already_loaded(tmp_path: Path) -> None:
    """End-to-end: load same skill twice and verify 'already loaded' message appears."""
    _ = _write_skill(tmp_path, "beta", body="# Beta\n")
    skills_root = str(tmp_path / "skills" / "user")

    model = FixedGenericFakeChatModel(
        messages=iter(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "load_skill", "args": {"skill_name": "beta"}, "id": "call_1", "type": "tool_call"},
                    ],
                ),
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "load_skill", "args": {"skill_name": "beta"}, "id": "call_2", "type": "tool_call"},
                    ],
                ),
                AIMessage(content="ok"),
            ]
        )
    )
    backend = FilesystemBackend(root_dir=str(tmp_path))
    agent = create_deep_agent(
        model=model,
        middleware=[SkillsMiddleware(backend=backend, sources=[skills_root], expose_dynamic_tools=True, max_loaded_skills=2)],
    )
    result = agent.invoke({"messages": [HumanMessage(content="load twice")]})
    tool_messages = [m for m in result["messages"] if m.type == "tool"]
    assert len(tool_messages) >= 2
    assert "already loaded" in tool_messages[1].content.lower()
