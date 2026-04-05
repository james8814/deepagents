"""Tests for SubAgent stream_writer progress extraction.

Verifies that _extract_stream_progress correctly extracts progress details
from SubAgent state chunks for real-time streaming via stream_writer.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from deepagents.middleware.subagents import _extract_stream_progress


class TestExtractStreamProgress:
    """Test _extract_stream_progress function."""

    def test_empty_messages(self) -> None:
        """Empty chunk produces minimal progress dict."""
        result = _extract_stream_progress({"messages": []}, "general-purpose")
        assert result["type"] == "subagent_progress"
        assert result["subagent_type"] == "general-purpose"
        assert result["message_count"] == 0
        assert "step_type" not in result

    def test_no_messages_key(self) -> None:
        """Chunk without messages key should not crash."""
        result = _extract_stream_progress({}, "test-agent")
        assert result["type"] == "subagent_progress"
        assert result["message_count"] == 0

    def test_tool_call_step(self) -> None:
        """AIMessage with tool_calls should produce tool_call step."""
        chunk = {
            "messages": [
                HumanMessage(content="do something"),
                AIMessage(
                    content="",
                    tool_calls=[{"id": "call_1", "name": "read_file", "args": {"path": "/secret.txt"}}],
                ),
            ]
        }
        result = _extract_stream_progress(chunk, "code-reviewer")
        assert result["step_type"] == "tool_call"
        assert result["tool_name"] == "read_file"
        assert result["message_count"] == 2
        # Tool arguments must NOT be exposed (security)
        assert "args" not in result
        assert "/secret.txt" not in str(result)

    def test_tool_result_step(self) -> None:
        """ToolMessage should produce tool_result step with content preview."""
        chunk = {
            "messages": [
                ToolMessage(content="File content: hello world", tool_call_id="call_1", name="read_file"),
            ]
        }
        result = _extract_stream_progress(chunk, "general-purpose")
        assert result["step_type"] == "tool_result"
        assert result["tool_name"] == "read_file"
        assert "content_preview" in result
        assert "hello world" in result["content_preview"]

    def test_thinking_step(self) -> None:
        """AIMessage without tool_calls should produce thinking step."""
        chunk = {
            "messages": [
                AIMessage(content="I'll analyze this file..."),
            ]
        }
        result = _extract_stream_progress(chunk, "researcher")
        assert result["step_type"] == "thinking"
        assert "analyze" in result["content_preview"]

    def test_thinking_step_empty_content(self) -> None:
        """AIMessage with empty content should not include content_preview."""
        chunk = {
            "messages": [
                AIMessage(content=""),
            ]
        }
        result = _extract_stream_progress(chunk, "researcher")
        assert result["step_type"] == "thinking"
        assert "content_preview" not in result

    def test_content_preview_truncation(self) -> None:
        """Long content should be truncated in preview."""
        long_content = "x" * 500
        chunk = {
            "messages": [
                ToolMessage(content=long_content, tool_call_id="call_1", name="execute"),
            ]
        }
        result = _extract_stream_progress(chunk, "general-purpose")
        assert len(result["content_preview"]) < len(long_content)
        assert "truncated" in result["content_preview"]

    def test_last_message_used(self) -> None:
        """Only the last message should determine step_type."""
        chunk = {
            "messages": [
                HumanMessage(content="do something"),
                AIMessage(content="", tool_calls=[{"id": "1", "name": "search", "args": {}}]),
                ToolMessage(content="result", tool_call_id="1", name="search"),
                AIMessage(content="Done analyzing."),
            ]
        }
        result = _extract_stream_progress(chunk, "general-purpose")
        assert result["step_type"] == "thinking"
        assert result["message_count"] == 4
