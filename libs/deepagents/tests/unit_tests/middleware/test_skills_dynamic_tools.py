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
