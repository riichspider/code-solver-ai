"""Type definitions for Code Solver AI."""

from __future__ import annotations

from typing import TypedDict


class ValidationResult(TypedDict, total=False):
    """Type definition for validation results."""
    status: str
    tool: str
    command: str
    stdout: str
    stderr: str
    notes: str


class SolveMetadata(TypedDict, total=False):
    """Type definition for solve metadata."""
    started_at: str
    finished_at: str
    duration_seconds: float
    ollama_url: str
    cache_hit: bool
