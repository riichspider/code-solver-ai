"""Export functionality for Code Solver AI."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from core.models import SolveResult


class SolutionExporter:
    """Handles exporting solutions to various formats."""

    def __init__(self, base_dir: Path, export_directory: str = "exports"):
        self.base_dir = Path(base_dir)
        self.export_directory = export_directory

    def export_result(
        self,
        result: SolveResult,
        export_root: Path | None = None,
        slug: str | None = None,
        max_exports: int = 20,
    ) -> dict[str, str]:
        export_base = export_root or self._resolve_path(self.export_directory)
        export_base.mkdir(parents=True, exist_ok=True)

        # Cleanup old exports if needed
        self._cleanup_old_exports(export_base, max_exports)

        safe_slug = slug or self._slugify(
            result.classification + "-" + result.problem[:40])
        output_dir = export_base / \
            f"{safe_slug}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        output_dir.mkdir(parents=True, exist_ok=True)

        markdown_path = output_dir / "solution.md"
        code_path = output_dir / result.filename
        tests_path = output_dir / result.test_filename
        metadata_path = output_dir / "metadata.json"

        markdown_path.write_text(result.markdown, encoding="utf-8")
        code_path.write_text(result.code, encoding="utf-8")
        tests_path.write_text(result.tests, encoding="utf-8")
        metadata_path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return {
            "output_dir": str(output_dir),
            "markdown": str(markdown_path),
            "code": str(code_path),
            "tests": str(tests_path),
            "metadata": str(metadata_path),
        }

    def _cleanup_old_exports(self, export_base: Path, max_exports: int) -> None:
        """Remove oldest export directories if count exceeds max_exports."""
        if not export_base.exists():
            return

        # Get all subdirectories (exports) sorted by timestamp in name
        export_dirs = []
        for item in export_base.iterdir():
            if item.is_dir():
                # Extract timestamp from directory name format: slug-YYYYMMDD-HHMMSS
                parts = item.name.split('-')
                if len(parts) >= 3:
                    try:
                        # Try to parse timestamp from last parts
                        timestamp_str = '-'.join(parts[-2:])  # YYYYMMDD-HHMMSS
                        timestamp = datetime.strptime(
                            timestamp_str, "%Y%m%d-%H%M%S")
                        export_dirs.append((timestamp, item))
                    except (ValueError, IndexError):
                        # If timestamp parsing fails, use current time (will be considered newest)
                        export_dirs.append((datetime.now(), item))

        # Sort by timestamp (oldest first)
        export_dirs.sort(key=lambda x: x[0])

        # Remove oldest directories if count exceeds max_exports
        if len(export_dirs) > max_exports:
            # Keep the newest max_exports
            for timestamp, dir_path in export_dirs[:-max_exports]:
                try:
                    shutil.rmtree(dir_path)
                except (OSError, PermissionError) as e:
                    # Log warning but don't fail the export
                    print(
                        f"Warning: Could not remove old export {dir_path}: {e}")

    def _slugify(self, text: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
        return slug[:50] or "solution"

    def parse_batch_text(self, text: str) -> list[str]:
        raw = text.replace("\ufeff", "").replace("\r\n", "\n").strip()
        if not raw:
            return []

        parts = [
            self._clean_batch_item(part)
            for part in re.split(r"(?m)^\s*---\s*$", raw)
            if part.strip()
        ]
        if len(parts) > 1:
            return [part for part in parts if part]

        paragraphs = [
            self._clean_batch_item(part)
            for part in re.split(r"\n\s*\n", raw)
            if part.strip()
        ]
        return paragraphs

    def _clean_batch_item(self, item: str) -> str:
        # Remove leading/trailing whitespace and common prefixes
        lines = item.strip().split('\n')
        cleaned_lines = []

        for line in lines:
            stripped = line.strip()
            # Skip empty lines and common bullet points
            if not stripped:
                continue
            # Remove common bullet point patterns
            if stripped.startswith(('•', '-', '*', '1.', '2.', '3.', '4.', '5.',
                                   '6.', '7.', '8.', '9.', '10.', '11.', '12.',
                                    '13.', '14.', '15.', '16.', '17.', '18.', '19.', '20.')):
                # Remove the bullet and any following whitespace
                cleaned = re.sub(r'^[-*•\d+\.\s]+', '', stripped)
                if cleaned:
                    cleaned_lines.append(cleaned)
            else:
                cleaned_lines.append(stripped)

        return '\n'.join(cleaned_lines)

    def _resolve_path(self, relative_path: str) -> Path:
        return (self.base_dir / relative_path).resolve()
