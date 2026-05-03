from __future__ import annotations

from typing import Any


def create_mock_solution_result() -> dict[str, Any]:
    """Creates a mock solution result for testing purposes."""
    return {
        "classification": "bug",
        "complexity": 3,
        "labels": ["bug", "python"],
        "model": "fake-model",
        "mode": "fast",
        "understanding": "Understand and repair the function.",
        "plan_steps": ["Inspect the failure", "Patch the code", "Run tests"],
        "constraints": ["Use standard library only"],
        "risks": ["Missing edge cases"],
        "explanation": ["Applies a direct fix."],
        "code": "def add(a, b):\n    return a + b\n",
        "tests": "print('ok')\n",
        "validation": {"status": "passed", "tool": "python-unittest", "notes": "All good."},
        "success_criteria": ["Tests pass"],
        "similar_context": [],
        "metadata": {"generated_at": "2026-05-03T00:00:00Z", "repair_applied": False, "context_files": []},
        "language": "python",
    }


def create_mock_solve_request() -> dict[str, Any]:
    """Creates a mock solve request for testing purposes."""
    return {
        "problem": "Fix the broken function",
        "language": "python",
        "model": "fake-model",
        "mode": "fast",
        "context_items": [],
        "use_cache": True,
        "auto_repair": True,
    }
