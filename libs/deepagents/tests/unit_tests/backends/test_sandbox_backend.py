"""Tests for BaseSandbox backend template formatting.

These tests verify that the command templates in BaseSandbox can be properly
formatted without raising KeyError due to unescaped curly braces.

Related issue: https://github.com/langchain-ai/deepagents/pull/872
The heredoc templates introduced in PR #872 contain {e} in exception handlers
that need to be escaped as {{e}} for Python's .format() method.
"""

import base64
import json

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.sandbox import (
    _EDIT_COMMAND_TEMPLATE,
    _GLOB_COMMAND_TEMPLATE,
    _READ_COMMAND_TEMPLATE,
    _WRITE_COMMAND_TEMPLATE,
    BaseSandbox,
)


class MockSandbox(BaseSandbox):
    """Minimal concrete implementation of BaseSandbox for testing."""

    def __init__(self) -> None:
        self.last_command = None
        self._next_output: str = "1"

    @property
    def id(self) -> str:
        return "mock-sandbox"

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        self.last_command = command
        output = self._next_output
        self._next_output = "1"
        return ExecuteResponse(output=output, exit_code=0, truncated=False)

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        return [FileUploadResponse(path=f[0], error=None) for f in files]

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        return [FileDownloadResponse(path=p, content=None, error="not_implemented") for p in paths]


def test_write_command_template_format() -> None:
    """Test that _WRITE_COMMAND_TEMPLATE can be formatted without KeyError."""
    content = "test content with special chars: {curly} and 'quotes'"
    content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
    payload = json.dumps({"path": "/test/file.txt", "content": content_b64})
    payload_b64 = base64.b64encode(payload.encode("utf-8")).decode("ascii")

    # This should not raise KeyError
    cmd = _WRITE_COMMAND_TEMPLATE.format(payload_b64=payload_b64)

    assert "python3 -c" in cmd
    assert payload_b64 in cmd


def test_edit_command_template_format() -> None:
    """Test that _EDIT_COMMAND_TEMPLATE can be formatted without KeyError."""
    payload = json.dumps({"path": "/test/file.txt", "old": "foo", "new": "bar"})
    payload_b64 = base64.b64encode(payload.encode("utf-8")).decode("ascii")

    # This should not raise KeyError
    cmd = _EDIT_COMMAND_TEMPLATE.format(payload_b64=payload_b64, replace_all=False)

    assert "python3 -c" in cmd
    assert payload_b64 in cmd


def test_glob_command_template_format() -> None:
    """Test that _GLOB_COMMAND_TEMPLATE can be formatted without KeyError."""
    path_b64 = base64.b64encode(b"/test").decode("ascii")
    pattern_b64 = base64.b64encode(b"*.py").decode("ascii")

    cmd = _GLOB_COMMAND_TEMPLATE.format(path_b64=path_b64, pattern_b64=pattern_b64)

    assert "python3 -c" in cmd
    assert path_b64 in cmd
    assert pattern_b64 in cmd


def test_read_command_template_format() -> None:
    """Test that _READ_COMMAND_TEMPLATE can be formatted without KeyError."""
    payload = json.dumps({"path": "/test/file.txt", "offset": 0, "limit": 100})
    payload_b64 = base64.b64encode(payload.encode("utf-8")).decode("ascii")
    cmd = _READ_COMMAND_TEMPLATE.format(payload_b64=payload_b64)

    assert "python3 -c" in cmd
    assert payload_b64 in cmd
    assert "__DEEPAGENTS_EOF__" in cmd


def test_heredoc_command_templates_end_with_newline() -> None:
    """Test that heredoc-based command templates terminate with a trailing newline."""
    payload = json.dumps({"path": "/test/file.txt", "offset": 0, "limit": 100})
    payload_b64 = base64.b64encode(payload.encode("utf-8")).decode("ascii")

    write_cmd = _WRITE_COMMAND_TEMPLATE.format(payload_b64=payload_b64)
    edit_cmd = _EDIT_COMMAND_TEMPLATE.format(payload_b64=payload_b64, replace_all=False)
    read_cmd = _READ_COMMAND_TEMPLATE.format(payload_b64=payload_b64)

    assert write_cmd.endswith("\n")
    assert edit_cmd.endswith("\n")
    assert read_cmd.endswith("\n")


def test_sandbox_read_uses_payload() -> None:
    """Test that read() bundles all params into a single base64 payload."""
    sandbox = MockSandbox()
    sandbox._next_output = json.dumps({"content": "mock content", "encoding": "utf-8"})

    sandbox.read("/test/file.txt", offset=5, limit=50)

    assert sandbox.last_command is not None
    assert "__DEEPAGENTS_EOF__" in sandbox.last_command
    assert "/test/file.txt" not in sandbox.last_command


def test_sandbox_write_method() -> None:
    """Test that BaseSandbox.write() successfully formats the command."""
    sandbox = MockSandbox()

    # This should not raise KeyError
    sandbox.write("/test/file.txt", "test content")

    # The command should have been formatted and passed to execute()
    assert sandbox.last_command is not None
    assert "python3 -c" in sandbox.last_command


def test_sandbox_edit_method() -> None:
    """Test that BaseSandbox.edit() successfully formats the command."""
    sandbox = MockSandbox()

    # This should not raise KeyError
    sandbox.edit("/test/file.txt", "old", "new", replace_all=False)

    # The command should have been formatted and passed to execute()
    assert sandbox.last_command is not None
    assert "python3 -c" in sandbox.last_command


def test_sandbox_write_with_special_content() -> None:
    """Test write with content containing curly braces and special characters."""
    sandbox = MockSandbox()

    # Content with curly braces that could confuse format()
    content = "def foo(): return {key: value for key, value in items.items()}"

    sandbox.write("/test/code.py", content)

    assert sandbox.last_command is not None


def test_sandbox_edit_with_special_strings() -> None:
    """Test edit with strings containing curly braces."""
    sandbox = MockSandbox()

    old_string = "{old_key}"
    new_string = "{new_key}"

    sandbox.edit("/test/file.txt", old_string, new_string, replace_all=True)

    assert sandbox.last_command is not None
    assert large_old not in sandbox.last_command


def test_sandbox_edit_upload_cleans_up_temp_files() -> None:
    """Test that temp files are removed from the sandbox after a successful edit."""
    sandbox = MockSandbox()
    large_old = "x" * (_EDIT_INLINE_MAX_BYTES + 1)
    sandbox._file_store["/test/file.txt"] = f"prefix {large_old} suffix".encode()

    result = sandbox.edit("/test/file.txt", large_old, "new")

    assert result.error is None
    assert not any(k.startswith("/tmp/.deepagents_edit_") for k in sandbox._file_store)  # noqa: S108


def test_sandbox_edit_upload_string_not_found() -> None:
    """Test that upload-path edit returns error when old_string is absent."""
    sandbox = MockSandbox()
    large_old = "x" * (_EDIT_INLINE_MAX_BYTES + 1)
    sandbox._file_store["/test/file.txt"] = b"completely different content"

    result = sandbox.edit("/test/file.txt", large_old, "new")

    assert result.error is not None
    assert "not found" in result.error.lower()


def test_sandbox_edit_upload_multiple_occurrences_without_replace_all() -> None:
    """Test that upload-path edit errors on multiple matches without replace_all."""
    sandbox = MockSandbox()
    large_old = "x" * (_EDIT_INLINE_MAX_BYTES + 1)
    sandbox._file_store["/test/file.txt"] = f"a{large_old}b{large_old}c".encode()

    result = sandbox.edit("/test/file.txt", large_old, "y")

    assert result.error is not None
    assert "multiple times" in result.error.lower()


def test_sandbox_edit_upload_partial_upload_failure() -> None:
    """Test that upload-path edit surfaces error when one of two uploads fails."""
    sandbox = MockSandbox()
    large_old = "x" * (_EDIT_INLINE_MAX_BYTES + 1)
    sandbox._file_store["/test/file.txt"] = f"prefix {large_old} suffix".encode()

    def partial_failure(
        files: list[tuple[str, bytes]],
    ) -> list[FileUploadResponse]:
        return [
            FileUploadResponse(path=files[0][0], error=None),
            FileUploadResponse(path=files[1][0], error="disk_full"),
        ]

    sandbox.upload_files = partial_failure  # type: ignore[assignment]

    result = sandbox.edit("/test/file.txt", large_old, "new")

    assert result.error is not None
    assert "disk_full" in result.error


# -- remaining template tests --------------------------------------------------


def test_read_command_template_format() -> None:
    """Test that _READ_COMMAND_TEMPLATE can be formatted without KeyError."""
    path_b64 = base64.b64encode(b"/test/file.txt").decode("ascii")
    cmd = _READ_COMMAND_TEMPLATE.format(
        path_b64=path_b64,
        file_type="text",
        offset=0,
        limit=2000,
    )

    assert "python3 -c" in cmd
    assert path_b64 in cmd


def test_edit_command_template_format() -> None:
    """Test that _EDIT_COMMAND_TEMPLATE can be formatted without KeyError."""
    payload_b64 = base64.b64encode(b'{"path":"/f","old":"a","new":"b"}').decode("ascii")
    cmd = _EDIT_COMMAND_TEMPLATE.format(payload_b64=payload_b64)

    assert "python3 -c" in cmd
    assert payload_b64 in cmd
    assert "__DEEPAGENTS_EDIT_EOF__" in cmd


def test_edit_command_template_ends_with_newline() -> None:
    """Test that _EDIT_COMMAND_TEMPLATE preserves the trailing newline after EOF."""
    assert _EDIT_COMMAND_TEMPLATE.endswith("\n")


def test_edit_tmpfile_template_format() -> None:
    """Test that _EDIT_TMPFILE_TEMPLATE can be formatted without KeyError."""
    old_b64 = base64.b64encode(b"/tmp/old").decode("ascii")
    new_b64 = base64.b64encode(b"/tmp/new").decode("ascii")
    tgt_b64 = base64.b64encode(b"/test/file.txt").decode("ascii")

    cmd = _EDIT_TMPFILE_TEMPLATE.format(
        old_path_b64=old_b64,
        new_path_b64=new_b64,
        target_b64=tgt_b64,
        replace_all=False,
    )

    assert "python3 -c" in cmd
    assert old_b64 in cmd
    assert new_b64 in cmd
    assert tgt_b64 in cmd


def test_sandbox_read_embeds_b64_path_not_raw() -> None:
    """Test that read() uses base64-encoded path, not raw path in execute()."""
    sandbox = MockSandbox()
    sandbox._next_output = json.dumps({"encoding": "utf-8", "content": "content"})

    sandbox.read("/test/file.txt", offset=0, limit=50)

    # read() should call execute() with base64-encoded path
    assert sandbox.last_command is not None
    assert "/test/file.txt" not in sandbox.last_command



def test_sandbox_grep_literal_search() -> None:
    """Test that grep performs literal search using grep -F flag."""
    sandbox = MockSandbox()

    # Override execute to return mock grep results
    def mock_execute(command: str) -> ExecuteResponse:
        sandbox.last_command = command
        # Return mock grep output for literal search tests
        if "grep" in command:
            # Check that -F flag (fixed-strings/literal) is present in the flags
            # -F can appear as standalone "-F" or combined like "-rHnF"
            assert "-F" in command or "F" in command.split("grep", 1)[1].split(maxsplit=1)[0], "grep should use -F flag for literal search"
            return ExecuteResponse(
                output="/test/code.py:1:def __init__(self):\n/test/types.py:1:str | int",
                exit_code=0,
                truncated=False,
            )
        return ExecuteResponse(output="", exit_code=0, truncated=False)

    sandbox.execute = mock_execute

    # Test with parentheses (should be literal, not regex grouping)
    matches = sandbox.grep("def __init__(", path="/test").matches
    assert matches is not None
    assert len(matches) == 2

    # Test with pipe character (should be literal, not regex OR)
    matches = sandbox.grep("str | int", path="/test").matches
    assert matches is not None

    # Verify the command uses grep -rHnF for literal search (combined flags)
    assert sandbox.last_command is not None
    assert "grep -rHnF" in sandbox.last_command
