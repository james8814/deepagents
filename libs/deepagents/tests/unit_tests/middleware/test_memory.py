import pytest

from deepagents.backends.protocol import FileDownloadResponse
from deepagents.middleware.memory import MemoryMiddleware


class _FakeBackendSyncAdownload:
    def __init__(self, data: dict[str, bytes]) -> None:
        self._data = data

    # Intentionally synchronous "async" API to simulate buggy/legacy backends
    def adownload_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        responses: list[FileDownloadResponse] = []
        for p in paths:
            if p in self._data:
                responses.append(FileDownloadResponse(path=p, content=self._data[p], error=None))
            else:
                responses.append(FileDownloadResponse(path=p, content=None, error="file_not_found"))
        return responses


@pytest.mark.asyncio
async def test_abefore_agent_tolerates_sync_adownload_files() -> None:
    backend = _FakeBackendSyncAdownload(
        {"/mem/A.md": b"A content", "/mem/B.md": b"B content"},
    )
    mw = MemoryMiddleware(backend=backend, sources=["/mem/A.md", "/mem/B.md"])

    update = await mw.abefore_agent(state={}, runtime=None, config=None)
    assert update is not None
    assert update["memory_contents"]["/mem/A.md"] == "A content"
    assert update["memory_contents"]["/mem/B.md"] == "B content"
