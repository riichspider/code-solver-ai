from utils.markdown import render_solution_markdown


def test_render_solution_markdown_contains_expected_sections():
    markdown = render_solution_markdown(
        {
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
    )

    assert "## 7. Generated Code" in markdown
    assert "## 9. Validation" in markdown
    assert "```python" in markdown
