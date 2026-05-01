"""CSV file converter."""

import csv
from io import StringIO
from pathlib import Path

from deepagents.middleware.converters.base import BaseConverter


class CSVConverter(BaseConverter):
    """Converter for CSV files to Markdown tables.

    Supports standard CSV format with automatic delimiter detection.
    """

    def convert(self, path: Path, raw_content: str | bytes | None = None) -> str:
        """Convert a CSV file to Markdown table.

        Args:
            path: Path to the CSV file.
            raw_content: Pre-read content (str or bytes).

        Returns:
            Markdown table string.
        """
        if raw_content is None:
            raw_content = path.read_text(encoding="utf-8", errors="replace")
        elif isinstance(raw_content, bytes):
            raw_content = raw_content.decode("utf-8", errors="replace")

        # Parse CSV
        reader = csv.reader(StringIO(raw_content))
        rows = list(reader)

        if not rows:
            return "(Empty CSV file)"

        # Use first row as headers
        headers = rows[0]
        data_rows = rows[1:] if len(rows) > 1 else []

        # Limit output for large files
        max_rows = 100
        if len(data_rows) > max_rows:
            data_rows = data_rows[:max_rows]
            truncated = True
        else:
            truncated = False

        # Format as markdown table
        result = self._format_as_table(data_rows, headers)

        if truncated:
            result += f"\n\n*... ({len(rows) - 1 - max_rows} more rows truncated)*"

        return result
