from __future__ import annotations

from typing import Any


LANGUAGE_ALIASES = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "java": "java",
    "go": "go",
    "rust": "rust",
}


def render_solution_markdown(result: dict[str, Any]) -> str:
    language = LANGUAGE_ALIASES.get(result.get("language", "python"), "text")
    explanation = result.get("explanation", [])
    validation = result.get("validation", {})
    similar_context = result.get("similar_context", [])
    metadata = result.get("metadata", {})

    lines: list[str] = [
        "# Code Solver AI Report",
        "",
        "## 1. Classification",
        f"- **Type:** {result['classification']}",
        f"- **Complexity:** {result['complexity']}/10",
        f"- **Labels:** {', '.join(result['labels'])}",
        f"- **Model:** {result['model']}",
        f"- **Mode:** {result['mode']}",
        "",
        "## 2. Understanding",
        result["understanding"],
        "",
        "## 3. Step-by-step Plan",
    ]

    for step in result.get("plan_steps", []):
        lines.append(f"1. {step}")

    lines.extend(
        [
            "",
            "## 4. Constraints",
            *[f"- {item}" for item in result.get("constraints", [])],
            "",
            "## 5. Risks",
            *[f"- {item}" for item in result.get("risks", [])],
            "",
            "## 6. Solution Explanation",
            *[f"- {item}" for item in explanation],
            "",
            "## 7. Generated Code",
            f"```{language}",
            result["code"].rstrip(),
            "```",
            "",
            "## 8. Generated Tests",
            f"```{language}",
            result["tests"].rstrip() or "# No tests generated",
            "```",
            "",
            "## 9. Validation",
            f"- **Status:** {validation.get('status', 'unknown')}",
            f"- **Tool:** {validation.get('tool', 'n/a')}",
            f"- **Command:** `{validation.get('command', '')}`" if validation.get("command") else "- **Command:** n/a",
            f"- **Notes:** {validation.get('notes', '')}",
        ]
    )

    stdout = str(validation.get("stdout", "")).strip()
    stderr = str(validation.get("stderr", "")).strip()
    if stdout:
        lines.extend(["", "### Stdout", "```text", stdout, "```"])
    if stderr:
        lines.extend(["", "### Stderr", "```text", stderr, "```"])

    lines.extend(["", "## 10. Success Criteria", *[f"- {item}" for item in result.get("success_criteria", [])]])

    if similar_context:
        lines.append("")
        lines.append("## 11. Related History")
        for item in similar_context:
            lines.append(
                f"- Score {item['score']:.2f} · {item['classification']} · {item['language']} · {item['problem']}"
            )

    if metadata:
        lines.extend(
            [
                "",
                "## 12. Metadata",
                f"- **Generated at:** {metadata.get('generated_at', 'n/a')}",
                f"- **Repair applied:** {'yes' if metadata.get('repair_applied') else 'no'}",
                f"- **Context files:** {', '.join(metadata.get('context_files', [])) or 'none'}",
            ]
        )

    return "\n".join(lines).strip() + "\n"
