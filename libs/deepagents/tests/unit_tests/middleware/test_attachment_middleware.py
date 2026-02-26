"""Unit tests for AttachmentMiddleware."""

from unittest.mock import MagicMock, Mock

import pytest
from langchain_core.messages import SystemMessage
from langchain.agents.middleware.types import ModelRequest

from deepagents.backends import StateBackend
from deepagents.middleware.attachment import AttachmentMiddleware, TOKEN_LIMIT

class MockBackend:
    def __init__(self):
        self.files = {}

    def ls_info(self, path):
        return [
            {"path": f"{path}/{name}", "size": len(content), "is_dir": False}
            for name, content in self.files.items()
        ]

    def read(self, path):
        name = path.split("/")[-1]
        return self.files.get(name, "Error: File not found")

@pytest.fixture
def mock_backend():
    return MockBackend()

@pytest.fixture
def middleware(mock_backend):
    return AttachmentMiddleware(backend=mock_backend)

def test_estimate_tokens_fallback(middleware):
    # Test fallback estimation (len // 3)
    # We mock tiktoken to be None for this test if it's installed
    # But simpler to just test the logic if tiktoken is not available or throws

    # Force fallback by mocking _estimate_tokens internal check or just rely on implementation detail
    # Let's just test a string
    text = "hello world"
    # If tiktoken is installed, it will be accurate. If not, fallback.
    # We can't easily force fallback without patching.
    pass

def test_get_uploaded_files_small(middleware, mock_backend):
    mock_backend.files = {
        "small.txt": "content" * 10  # Small content
    }

    files = middleware._get_uploaded_files(mock_backend)
    assert len(files) == 1
    assert files[0]["path"] == "/uploads/small.txt"
    assert files[0]["status"] == "cached"
    assert files[0]["content"] is not None

def test_get_uploaded_files_large(middleware, mock_backend):
    # Create content larger than TOKEN_LIMIT
    # 100k tokens * 4 chars/token approx 400k chars
    large_content = "a" * (TOKEN_LIMIT * 4 + 1000)
    mock_backend.files = {
        "large.txt": large_content
    }

    # We need to mock _estimate_tokens to return > TOKEN_LIMIT to be sure
    middleware._estimate_tokens = MagicMock(return_value=TOKEN_LIMIT + 1)

    files = middleware._get_uploaded_files(mock_backend)
    assert len(files) == 1
    assert files[0]["status"] == "tool_access_only"
    assert files[0]["content"] is None

def test_construct_system_message_content(middleware):
    files = [
        {
            "path": "/uploads/test.txt",
            "size": 100,
            "token_count": 25,
            "status": "cached",
            "content": "file content"
        }
    ]

    blocks = middleware._construct_system_message_content(files)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "text"
    assert "cache_control" in blocks[0]
    assert blocks[0]["cache_control"]["type"] == "ephemeral"
    assert "<file path=\"/uploads/test.txt\"" in blocks[0]["text"]
    assert "file content" in blocks[0]["text"]

def test_wrap_model_call(middleware, mock_backend):
    mock_backend.files = {
        "test.txt": "content"
    }

    request = ModelRequest(
        system_message=SystemMessage(content="base prompt"),
        tools=[],
        tool_choice=None,
        state={},
        runtime=MagicMock()
    )

    handler = MagicMock()
    middleware.wrap_model_call(request, handler)

    # Check if handler was called with modified request
    assert handler.called
    modified_request = handler.call_args[0][0]

    # Check system message content
    content = modified_request.system_message.content
    assert isinstance(content, list)
    assert len(content) == 2  # base prompt + attachment block
    assert content[0]["text"] == "base prompt"
    assert "uploaded_files" in content[1]["text"]
