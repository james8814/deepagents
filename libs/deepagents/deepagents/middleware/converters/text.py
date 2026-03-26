"""Text file converter (pass-through with line formatting)."""

from pathlib import Path

from deepagents.middleware.converters.base import BaseConverter


class TextConverter(BaseConverter):
    """Converter for plain text files.

    This is a pass-through converter that returns text content as-is,
    with optional formatting for better readability.
    """

    def convert(self, path: Path, raw_content: str | bytes | None = None) -> str:
        """Convert a text file to Markdown.

        Args:
            path: Path to the text file.
            raw_content: Pre-read content (str for text files).

        Returns:
            The text content, optionally wrapped in a code block
            if the file type suggests it should be formatted.
        """
        if raw_content is None:
            raw_content = path.read_text(encoding="utf-8", errors="replace")
        elif isinstance(raw_content, bytes):
            raw_content = raw_content.decode("utf-8", errors="replace")

        # Determine if we should wrap in a code block based on extension
        ext = path.suffix.lower()
        code_extensions = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".rs": "rust",
            ".go": "go",
            ".rb": "ruby",
            ".php": "php",
            ".sh": "bash",
            ".bash": "bash",
            ".sql": "sql",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".xml": "xml",
            ".html": "html",
            ".htm": "html",
            ".css": "css",
        }

        if ext in code_extensions:
            lang = code_extensions[ext]
            return f"```{lang}\n{raw_content}\n```"

        # Check if content looks like it should be a code block
        # (e.g., contains code-like patterns)
        if self._looks_like_code(raw_content):
            # Try to infer language from shebang or content
            lang = self._infer_language(raw_content)
            return f"```{lang}\n{raw_content}\n```"

        return raw_content

    def _looks_like_code(self, content: str) -> bool:
        """Check if content looks like code.

        Args:
            content: The content to check.

        Returns:
            True if the content appears to be code.
        """
        lines = content.splitlines()
        if not lines:
            return False

        # Check for common code patterns
        code_indicators = 0
        for line in lines[: min(20, len(lines))]:
            # Skip empty lines
            if not line.strip():
                continue

            # Check for code patterns
            stripped = line.strip()
            if (
                stripped.startswith(("def ", "function ", "class ", "import ", "from ", "const ", "let ", "var "))
                or stripped.endswith((":", ";", "{", "}"))
                or "()" in stripped
                or "={" in stripped
                or "= {" in stripped
            ):
                code_indicators += 1

        # If more than 30% of lines look like code, treat as code
        return code_indicators > 0 and code_indicators / min(20, len(lines)) > 0.3

    def _infer_language(self, content: str) -> str:
        """Infer programming language from content.

        Args:
            content: The content to analyze.

        Returns:
            Language identifier for syntax highlighting.
        """
        first_lines = content.splitlines()[:5]

        # Check shebang
        for line in first_lines:
            if line.startswith("#!"):
                if "python" in line:
                    return "python"
                if "bash" in line or "sh" in line:
                    return "bash"
                if "node" in line:
                    return "javascript"
                if "ruby" in line:
                    return "ruby"

        # Check for language-specific patterns
        content_lower = content.lower()
        if "def " in content or ("import " in content and "from " in content):
            return "python"
        if "function " in content or "const " in content or "let " in content:
            if "=>" in content or "async " in content:
                return "javascript"

        return ""  # No language specified
