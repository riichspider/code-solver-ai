"""Data models for Code Solver AI."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.types import SolveMetadata, ValidationResult


@dataclass
class ContextItem:
    name: str
    content: str


@dataclass
class SolveRequest:
    problem: str
    language: str = "python"
    model: str | None = None
    mode: str = "fast"
    context_items: list[Any] = field(default_factory=list)
    use_cache: bool = True
    auto_repair: bool = True


@dataclass
class SolveResult:
    problem: str
    classification: str
    complexity: int
    labels: list[str]
    language: str
    model: str
    mode: str
    understanding: str
    plan_steps: list[str]
    constraints: list[str]
    risks: list[str]
    success_criteria: list[str]
    code: str
    tests: str
    filename: str
    test_filename: str
    explanation: list[str]
    validation: ValidationResult
    markdown: str
    similar_context: list[dict[str, Any]] = field(default_factory=list)
    metadata: SolveMetadata = field(default_factory=dict)
    cached: bool = False
    history_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SolveResult":
        return cls(**payload)
