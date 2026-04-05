from types import SimpleNamespace
from typing import cast

from langchain.tools import ToolRuntime

from deepagents.middleware.filesystem import FilesystemMiddleware
from deepagents.middleware.memory import MemoryMiddleware, MemoryState
from deepagents.middleware.skills import SkillsMiddleware, SkillsState
from deepagents.middleware.summarization import SummarizationMiddleware
from tests.unit_tests.chat_model import GenericFakeChatModel


class _FakeDownloadResponse:
    def __init__(self, *, content: bytes | None = None, error: str | None = None) -> None:
        self.content = content
        self.error = error


class _FakeBackend:
    def download_files(self, paths: list[str]) -> list[_FakeDownloadResponse]:
        return [_FakeDownloadResponse(error="file_not_found") for _ in paths]


def _assert_stream_writer(tool_runtime: ToolRuntime, stream_writer: object) -> None:
    assert tool_runtime.stream_writer is stream_writer


def test_memory_middleware_passes_stream_writer_to_backend_factory() -> None:
    def stream_writer(_: object) -> None:
        return None

    seen: dict[str, bool] = {"called": False}

    def backend_factory(tool_runtime: object) -> _FakeBackend:
        seen["called"] = True
        _assert_stream_writer(tool_runtime, stream_writer)
        return _FakeBackend()

    middleware = MemoryMiddleware(backend=backend_factory, sources=[])
    runtime = SimpleNamespace(context=None, stream_writer=stream_writer, store=None)
    config: dict[str, object] = {}

    middleware.before_agent(cast("MemoryState", {}), runtime, config)
    assert seen["called"]


def test_skills_middleware_passes_stream_writer_to_backend_factory() -> None:
    def stream_writer(_: object) -> None:
        return None

    seen: dict[str, bool] = {"called": False}

    def backend_factory(tool_runtime: object) -> object:
        seen["called"] = True
        _assert_stream_writer(tool_runtime, stream_writer)
        return object()

    middleware = SkillsMiddleware(backend=backend_factory, sources=[])
    runtime = SimpleNamespace(context=None, stream_writer=stream_writer, store=None)
    config: dict[str, object] = {}

    assert middleware._get_backend(cast("SkillsState", {}), runtime, config) is not None
    assert seen["called"]


def test_summarization_middleware_passes_stream_writer_to_backend_factory() -> None:
    def stream_writer(_: object) -> None:
        return None

    seen: dict[str, bool] = {"called": False}

    def backend_factory(tool_runtime: object) -> object:
        seen["called"] = True
        _assert_stream_writer(tool_runtime, stream_writer)
        return object()

    model = GenericFakeChatModel(messages=iter(["ok"]))
    middleware = SummarizationMiddleware(model=model, backend=backend_factory)
    runtime = SimpleNamespace(context=None, stream_writer=stream_writer, store=None, config={})

    assert middleware._get_backend({}, runtime) is not None
    assert seen["called"]


def test_filesystem_middleware_passes_stream_writer_to_backend_factory() -> None:
    def stream_writer(_: object) -> None:
        return None

    seen: dict[str, bool] = {"called": False}

    def backend_factory(tool_runtime: object) -> object:
        seen["called"] = True
        _assert_stream_writer(tool_runtime, stream_writer)
        return object()

    middleware = FilesystemMiddleware(backend=backend_factory)
    runtime = SimpleNamespace(context=None, stream_writer=stream_writer, store=None, config={})

    assert middleware._get_backend_from_runtime({}, runtime) is not None
    assert seen["called"]
