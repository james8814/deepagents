"""Middleware for handling file attachments and context injection."""

import xml.etree.ElementTree as ET
from collections.abc import Awaitable, Callable
from typing import TypedDict

from langchain.agents.middleware.types import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
)
from langchain_core.messages import SystemMessage

from deepagents.backends import StateBackend
from deepagents.backends.protocol import BACKEND_TYPES, BackendProtocol

try:
    import tiktoken
except ImportError:
    tiktoken = None

# Threshold for switching between full context and metadata-only mode
TOKEN_LIMIT = 100000


class UploadedFileInfo(TypedDict):
    """Information about an uploaded file."""
    path: str
    size: int
    token_count: int
    status: str  # "cached" or "tool_access_only"
    content: str | None


class AttachmentMiddleware(AgentMiddleware):
    """Middleware that injects uploaded file content or metadata into the system prompt.

    Implements Adaptive Context Strategy:
    - Small files (< 100k tokens): Injected fully with Prompt Caching.
    - Large files (> 100k tokens): Injected as metadata with instructions to use tools.
    """

    def __init__(
        self,
        *,
        backend: BACKEND_TYPES | None = None,
        uploads_dir: str = "/uploads",
    ) -> None:
        """Initialize the attachment middleware.

        Args:
            backend: Backend for file storage.
            uploads_dir: Directory to scan for attachments.
        """
        self.backend = backend if backend is not None else (lambda rt: StateBackend(rt))
        self.uploads_dir = uploads_dir

    def _get_backend(self, runtime) -> BackendProtocol:
        if callable(self.backend):
            return self.backend(runtime)
        return self.backend

    def _estimate_tokens(self, text: str) -> int:
        if tiktoken:
            try:
                encoding = tiktoken.get_encoding("cl100k_base")
                return len(encoding.encode(text))
            except Exception:
                pass
        # Fallback: conservative estimate for mixed content
        # English ~4 chars/token, Chinese ~0.7 chars/token
        # Using len // 3 as a safe middle ground
        return len(text) // 3

    def _get_uploaded_files(self, backend: BackendProtocol) -> list[UploadedFileInfo]:
        files: list[UploadedFileInfo] = []
        try:
            # List files in uploads directory
            ls_result = backend.ls_info(self.uploads_dir)

            for item in ls_result:
                if item.get("is_dir"):
                    continue

                path = item["path"]
                # Read content to estimate tokens
                content = backend.read(path)

                # Check for read errors
                if content.startswith("Error:"):
                    continue

                token_count = self._estimate_tokens(content)

                status = "cached" if token_count <= TOKEN_LIMIT else "tool_access_only"

                files.append({
                    "path": path,
                    "size": item["size"],
                    "token_count": token_count,
                    "status": status,
                    "content": content if status == "cached" else None
                })

        except Exception:
            # Gracefully handle if uploads dir doesn't exist or other errors
            pass

        return files

    def _construct_system_message_content(self, files: list[UploadedFileInfo]) -> list[dict]:
        """Construct the system message content blocks with caching."""
        if not files:
            return []

        # Build XML
        root = ET.Element("uploaded_files")

        for file in files:
            file_elem = ET.SubElement(root, "file")
            file_elem.set("path", file["path"])
            file_elem.set("size", str(file["size"]))
            file_elem.set("token_count", str(file["token_count"]))
            file_elem.set("status", file["status"])

            if file["status"] == "cached":
                file_elem.text = file["content"]
            else:
                file_elem.text = (
                    "\n[SYSTEM NOTICE]\n"
                    "This file exceeds the context limit. Content is NOT loaded.\n"
                    "You MUST use tools to access it:\n"
                    "- Use `ls` to check file existence.\n"
                    "- Use `grep` to search for keywords.\n"
                    "- Use `read_file` with line limits to read specific sections.\n"
                )

        xml_str = ET.tostring(root, encoding="unicode")

        # Create content block with cache_control
        return [
            {
                "type": "text",
                "text": f"\n\n{xml_str}",
                "cache_control": {"type": "ephemeral"}
            }
        ]

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        backend = self._get_backend(request.runtime)
        files = self._get_uploaded_files(backend)

        if files:
            attachment_blocks = self._construct_system_message_content(files)

            original_content = request.system_message.content
            if isinstance(original_content, str):
                new_content = [{"type": "text", "text": original_content}] + attachment_blocks
            else:
                new_content = list(original_content) + attachment_blocks

            new_system_message = SystemMessage(content=new_content)
            request = request.override(system_message=new_system_message)

        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        # Reusing sync logic for simplicity as file reading is fast enough
        # In production, should use backend.aread
        backend = self._get_backend(request.runtime)

        # Using run_in_executor to avoid blocking event loop if file IO is heavy
        import asyncio
        files = await asyncio.to_thread(self._get_uploaded_files, backend)

        if files:
            attachment_blocks = self._construct_system_message_content(files)

            original_content = request.system_message.content
            if isinstance(original_content, str):
                new_content = [{"type": "text", "text": original_content}] + attachment_blocks
            else:
                new_content = list(original_content) + attachment_blocks

            new_system_message = SystemMessage(content=new_content)
            request = request.override(system_message=new_system_message)

        return await handler(request)
