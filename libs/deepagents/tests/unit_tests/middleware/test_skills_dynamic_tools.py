"""Unit tests for SkillsMiddleware V2 dynamic tools feature.

These tests verify the load_skill and unload_skill tools behavior when expose_dynamic_tools is enabled/disdisabled.
"""

import pytest

from deepagents.middleware.skills import SkillsMiddleware
from deepagents.backends import FilesystemBackend


class TestExposeDynamicTools:
    """Test the expose_dynamic_tools parameter."""

    def test_default_expose_dynamic_tools_false(self):
        """When expose_dynamic_tools=False (default), tools should not be exposed."""
        m = SkillsMiddleware(
            backend=FilesystemBackend(),
            sources=["/skills/"],
        )
        assert len(m.tools) == 0

    def test_expose_dynamic_tools_true(self):
        """When expose_dynamic_tools=True, tools should be exposed."""
        m = SkillsMiddleware(
            backend=FilesystemBackend(),
            sources=["/skills/"],
            expose_dynamic_tools=True,
        )
        assert len(m.tools) == 2
        tool_names = {t.name for t in m.tools}
        assert "load_skill" in tool_names
        assert "unload_skill" in tool_names

    def test_max_loaded_skills_limit(self):
        """Test that max_loaded_skills limit is enforced."""
        m = SkillsMiddleware(
            backend=FilesystemBackend(),
            sources=["/skills/"],
            expose_dynamic_tools=True,
            max_loaded_skills=2,  # Small limit
        )
        assert m._max_loaded_skills == 2


class DummyRuntime:
    """Minimal runtime stub providing attributes accessed by SkillsMiddleware."""

    def __init__(self, state: dict | None = None, tool_call_id: str = "tc1") -> None:
        self.state = state or {}
        self.tool_call_id = tool_call_id


def _write_skill(tmp_path, name: str, body: str = "# Body\n", license: str | None = None, compatibility: str | None = None) -> str:
    """Create a simple skill directory with SKILL.md and return SKILL.md absolute path."""
    import os
    skill_dir = os.path.join(tmp_path, "skills", "user", name)
    os.makedirs(skill_dir, exist_ok=True)
    fm = ["---", f"name: {name}", "description: Test skill for unit testing"]
    if license is not None:
        fm.append(f"license: {license}")
    if compatibility is not None:
        fm.append(f"compatibility: {compatibility}")
    fm.append("---\n")
    with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(fm) + body)
    # add a resource file to test resource discovery
    scripts_dir = os.path.join(skill_dir, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)
    with open(os.path.join(scripts_dir, "helper.py"), "w", encoding="utf-8") as f:
        f.write("print('ok')\n")
    return os.path.join(skill_dir, "SKILL.md")


class TestDynamicToolsBehavior:
    """Behavior tests for load_skill/unload_skill core execution and errors."""

    def test_load_skill_exec_success_and_resources(self, tmp_path) -> None:
        import os

        # Arrange: create a real skill on filesystem
        skill_name = "alpha"
        md_path = _write_skill(tmp_path, skill_name, body="# Alpha Skill\nDo things.\n")
        skills_root = os.path.join(tmp_path, "skills", "user")
        backend = FilesystemBackend(root_dir=str(tmp_path))
        m = SkillsMiddleware(
            backend=backend,
            sources=[skills_root],
            expose_dynamic_tools=True,
            max_loaded_skills=10,
        )
        # Prime skills metadata like before_agent would
        skills = [{"name": skill_name, "description": "desc", "path": str(md_path), "license": None, "compatibility": None, "metadata": {}, "allowed_tools": []}]  # type: ignore[typeddict-item]
        state = {"skills_metadata": skills, "skills_loaded": [], "skill_resources": {}}
        rt = DummyRuntime(state)

        # Act
        cmd = m._execute_load_skill(backend, skill_name, rt)

        # Assert: command updates loaded list, resources and produces a ToolMessage
        assert hasattr(cmd, "update")
        update = cmd.update  # type: ignore[attr-defined]
        assert skill_name in update["skills_loaded"]
        # Has resource cache populated for the skill
        assert skill_name in update["skill_resources"]
        # Tool message includes file content and resource header
        assert update["messages"][0].type == "tool"
        assert "Alpha Skill" in update["messages"][0].content
        assert "Skill Resources" in update["messages"][0].content

    def test_unload_skill_exec_success_and_updates_state(self, tmp_path) -> None:
        import os

        skill_name = "beta"
        _ = _write_skill(tmp_path, skill_name, body="# Beta\n")
        skills_root = os.path.join(tmp_path, "skills", "user")
        backend = FilesystemBackend(root_dir=str(tmp_path))
        m = SkillsMiddleware(backend=backend, sources=[skills_root], expose_dynamic_tools=True, max_loaded_skills=10)
        # Preloaded state
        state = {"skills_metadata": [{"name": skill_name, "description": "d", "path": os.path.join(skills_root, skill_name, "SKILL.md"), "license": None, "compatibility": None, "metadata": {}, "allowed_tools": []}], "skills_loaded": [skill_name], "skill_resources": {skill_name: []}}  # type: ignore[typeddict-item]
        rt = DummyRuntime(state)

        cmd = m._execute_unload_skill(skill_name, rt)
        update = cmd.update  # type: ignore[attr-defined]
        assert skill_name not in update["skills_loaded"]
        assert skill_name not in update["skill_resources"]
        assert "has been unloaded" in update["messages"][0].content

    def test_load_skill_error_paths(self, tmp_path) -> None:
        import os

        skills_root = os.path.join(tmp_path, "skills", "user")
        os.makedirs(skills_root, exist_ok=True)
        backend = FilesystemBackend(root_dir=str(tmp_path))
        m = SkillsMiddleware(backend=backend, sources=[skills_root], expose_dynamic_tools=True, max_loaded_skills=1)

        # State with no matching skill -> not found
        state = {"skills_metadata": [], "skills_loaded": [], "skill_resources": {}}
        rt = DummyRuntime(state)
        err = m._execute_load_skill(backend, "missing", rt)
        assert isinstance(err, str)
        assert "not found" in err

        # Add one skill and load to hit duplicate and limit
        name = "gamma"
        _ = _write_skill(tmp_path, name, body="# G\n")
        md_path = os.path.join(skills_root, name, "SKILL.md")
        state["skills_metadata"] = [{"name": name, "description": "d", "path": md_path, "license": None, "compatibility": None, "metadata": {}, "allowed_tools": []}]  # type: ignore[typeddict-item]
        # First load succeeds
        first = m._execute_load_skill(backend, name, rt)
        assert hasattr(first, "update")
        # Apply update to runtime state to simulate graph behavior
        rt.state.update(first.update)  # type: ignore[attr-defined]
        # Second load reports already loaded
        dup = m._execute_load_skill(backend, name, rt)
        assert isinstance(dup, str)
        assert "already loaded" in dup
        # Reinitialize state to loaded and try loading another to hit limit
        state["skills_loaded"] = [name]
        state["skills_metadata"].append({"name": "delta", "description": "d", "path": md_path, "license": None, "compatibility": None, "metadata": {}, "allowed_tools": []})  # type: ignore[typeddict-item]
        over = m._execute_load_skill(backend, "delta", rt)
        assert isinstance(over, str)
        assert "Maximum number of simultaneously loaded skills" in over

    async def test_async_load_skill_exec_success(self, tmp_path) -> None:
        import os

        skill_name = "omega"
        _ = _write_skill(tmp_path, skill_name, body="# Omega\n")
        skills_root = os.path.join(tmp_path, "skills", "user")
        backend = FilesystemBackend(root_dir=str(tmp_path))
        m = SkillsMiddleware(backend=backend, sources=[skills_root], expose_dynamic_tools=True, max_loaded_skills=10)
        skills = [{"name": skill_name, "description": "d", "path": os.path.join(skills_root, skill_name, "SKILL.md"), "license": None, "compatibility": None, "metadata": {}, "allowed_tools": []}]  # type: ignore[typeddict-item]
        rt = DummyRuntime({"skills_metadata": skills, "skills_loaded": [], "skill_resources": {}})

        cmd = await m._aexecute_load_skill(backend, skill_name, rt)
        update = cmd.update  # type: ignore[attr-defined]
        assert skill_name in update["skills_loaded"]

    def test_format_skills_list_loaded_marker(self, tmp_path) -> None:
        import os

        name = "phi"
        md_path = _write_skill(tmp_path, name)
        backend = FilesystemBackend(root_dir=str(tmp_path))
        m = SkillsMiddleware(backend=backend, sources=[os.path.join(tmp_path, "skills", "user")])
        skills = [{"name": name, "description": "desc", "path": md_path, "license": None, "compatibility": None, "metadata": {}, "allowed_tools": []}]  # type: ignore[typeddict-item]
        out = m._format_skills_list(skills, loaded=[name], resources={})
        assert "[Loaded]" in out
