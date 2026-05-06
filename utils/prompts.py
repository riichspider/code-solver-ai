from __future__ import annotations

import json
import re
import warnings
from typing import Any, Optional


def sanitize_input(text: Optional[str]) -> Optional[str]:
    """
    Sanitize input text to prevent prompt injection attacks.

    Removes or escapes suspicious patterns including:
    - "ignore previous instructions" variants
    - "you are now" / "act as" role-playing attempts
    - Simulated system blocks like [SYSTEM]
    - Control characters and null bytes

    Args:
        text: Input text to sanitize

    Returns:
        Sanitized text safe for LLM consumption
    """
    if not text:
        return text

    # Remove null bytes and control characters (except newlines and tabs)
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)

    # Escape or remove prompt injection patterns
    patterns_to_remove = [
        # Ignore previous instructions patterns
        r'(?i)(ignore\s+(?:previous|all|the)\s+instructions?)',
        r'(?i)(forget\s+(?:everything|all|previous|the)\s+(?:above|instructions)?)',
        r'(?i)(disregard\s+(?:previous|all|the)\s+instructions?)',

        # Role-playing attempts
        r'(?i)(you\s+are\s+now\s+(?:a|an))',
        r'(?i)(act\s+as\s+(?:a|an))',
        r'(?i)(pretend\s+to\s+be)',
        r'(?i)(roleplay\s+as)',

        # System block attempts
        r'\[SYSTEM\]',
        r'\[ADMIN\]',
        r'\[DEVELOPER\]',
        r'\[MODATOR\]',
        r'\[AI\]',

        # Instruction override attempts
        r'(?i)(override\s+(?:previous|all|the)\s+instructions?)',
        r'(?i)(new\s+(?:instructions|rules|directives))',
        r'(?i)(from\s+now\s+on)',

        # Jailbreak attempts
        r'(?i)(jailbreak)',
        r'(?i)(dan\s+\d+)',
        r'(?i)(developer\s+mode)',

        # Template injection
        r'\{\{.*?\}\}',
        r'\${.*?}',
    ]

    for pattern in patterns_to_remove:
        text = re.sub(pattern, '[REDACTED]', text)

    # Limit consecutive characters to prevent DoS
    text = re.sub(r'(.)\1{50,}', r'\1\1\1\1\1', text)

    # Trim whitespace
    text = text.strip()

    return text


def _serialize_similar_context(similar_context: list[dict[str, Any]]) -> str:
    if not similar_context:
        return "No similar history available."
    compact = []
    for item in similar_context:
        problem_text = item.get("problem", "")
        # TRUNCATION_LIMIT: 260 chars for problem context
        truncated_problem = problem_text[:260]
        if len(problem_text) > 260:
            warnings.warn(
                f"Problem text truncated from {len(problem_text)} to 260 characters for LLM context. "
                f"Original: '{problem_text[:50]}...'",
                UserWarning,
                stacklevel=3
            )
        compact.append(
            {
                "score": round(float(item.get("score", 0.0)), 3),
                "classification": item.get("classification", ""),
                "language": item.get("language", ""),
                "problem": truncated_problem,
                "labels": item.get("labels", []),
            }
        )
    return json.dumps(compact, ensure_ascii=False, indent=2)


def classification_system_prompt() -> str:
    return """
You are a senior staff engineer classifying software tasks for an offline code-solving pipeline.
Return valid JSON only.
Decide the dominant task type among: bug, enhancement, optimization, refactor, question.
Infer the best primary language when possible.
Rate complexity from 1 to 10.
Suggest concise GitHub-style labels.
Be precise, practical, and avoid filler.
""".strip()


def build_classification_user_prompt(
    problem: str,
    language_hint: str,
    context_text: str,
    similar_context: list[dict[str, Any]],
) -> str:
    # Sanitize inputs to prevent prompt injection
    safe_problem = sanitize_input(problem)
    safe_context = sanitize_input(context_text)

    return f"""
Return a JSON object with this schema:
{{
  "understanding": "short problem understanding",
  "classification": "bug|enhancement|optimization|refactor|question",
  "complexity": 1,
  "labels": ["bug", "python"],
  "language": "python",
  "why": "one sentence justification"
}}

Language hint: {language_hint or "unknown"}

Problem:
{safe_problem}

Additional context:
{safe_context or "None"}

Relevant memory from previous solutions:
{_serialize_similar_context(similar_context)}
""".strip()


def reasoning_system_prompt() -> str:
    return """
You are the reasoning stage of a deterministic coding pipeline.
Return valid JSON only.
Think like a senior engineer preparing a high-confidence implementation plan.
Do not write the final solution code yet.
Focus on constraints, risks, success criteria, and an execution plan that another coding stage can follow.
""".strip()


def build_reasoning_user_prompt(
    problem: str,
    classification: str,
    complexity: int,
    language: str,
    understanding: str,
    context_text: str,
    similar_context: list[dict[str, Any]],
) -> str:
    # Sanitize inputs to prevent prompt injection
    safe_problem = sanitize_input(problem)
    safe_context = sanitize_input(context_text)
    safe_understanding = sanitize_input(understanding)

    return f"""
Return a JSON object with this schema:
{{
  "understanding": "refined understanding",
  "constraints": ["constraint 1"],
  "risks": ["risk 1"],
  "success_criteria": ["criterion 1"],
  "plan_steps": ["step 1", "step 2", "step 3"]
}}

Problem classification: {classification}
Complexity: {complexity}/10
Target language: {language}
Current understanding:
{safe_understanding}

Problem:
{safe_problem}

Additional context:
{safe_context or "None"}

Relevant memory:
{_serialize_similar_context(similar_context)}
""".strip()


def coding_system_prompt(language: str, mode: str) -> str:
    style = "very concise and fast" if mode == "fast" else "deeply reasoned and robust"
    return f"""
You are the code-generation stage of an offline AI code solver.
Target language: {language}.
Working style: {style}.

Return valid JSON only with the exact keys:
{{
  "filename": "solution file name",
  "code": "raw source code with no markdown fences",
  "test_filename": "test file name",
  "tests": "raw test code with no markdown fences",
  "explanation": ["bullet 1", "bullet 2"],
  "notes": ["optional note"]
}}

Rules:
- Produce production-ready code.
- Keep dependencies minimal.
- Prefer standard library when possible.
- Tests must be runnable locally and cover the main flow plus edge cases.
- For Python, prefer unittest and code that can be imported from the generated file.
- For JavaScript, do not use chai, jest, mocha, vitest, or any third-party package; use only built-in `assert` and optionally `node:test`.
- Never wrap code in markdown fences.

Few-shot quality example:
{{
  "filename": "solution.py",
  "code": "def add(a, b):\\n    return a + b\\n",
  "test_filename": "test_solution.py",
  "tests": "import unittest\\nfrom solution import add\\n\\nclass AddTests(unittest.TestCase):\\n    def test_add(self):\\n        self.assertEqual(add(2, 3), 5)\\n\\nif __name__ == '__main__':\\n    unittest.main()\\n",
  "explanation": ["Implements the core function directly.", "Adds a regression test for the expected behavior."],
  "notes": ["Keep naming stable so the validator can execute the tests."]
}}
""".strip()


def build_coding_user_prompt(
    problem: str,
    classification: str,
    language: str,
    understanding: str,
    plan_steps: list[str],
    constraints: list[str],
    risks: list[str],
    success_criteria: list[str],
    context_text: str,
    similar_context: list[dict[str, Any]],
) -> str:
    # Sanitize inputs to prevent prompt injection
    safe_problem = sanitize_input(problem)
    safe_context = sanitize_input(context_text)
    safe_understanding = sanitize_input(understanding)

    return f"""
Generate the final solution package.

Problem:
{safe_problem}

Classification: {classification}
Target language: {language}
Understanding:
{safe_understanding}

Plan steps:
{json.dumps(plan_steps, ensure_ascii=False, indent=2)}

Constraints:
{json.dumps(constraints, ensure_ascii=False, indent=2)}

Risks:
{json.dumps(risks, ensure_ascii=False, indent=2)}

Success criteria:
{json.dumps(success_criteria, ensure_ascii=False, indent=2)}

Additional context:
{safe_context or "None"}

Relevant memory:
{_serialize_similar_context(similar_context)}
""".strip()


def repair_system_prompt(language: str) -> str:
    return f"""
You are the repair stage of an offline code-solving pipeline.
Target language: {language}.
Return valid JSON only with the same schema as the code-generation stage.
Use the validation feedback to fix the code or tests with the smallest reliable change.
If the validator reports missing packages or modules, rewrite the solution to avoid external dependencies.
Do not add markdown fences.
""".strip()


def build_repair_user_prompt(
    problem: str,
    language: str,
    previous_solution: dict[str, Any],
    validation: dict[str, Any],
) -> str:
    # Sanitize inputs to prevent prompt injection
    safe_problem = sanitize_input(problem)

    return f"""
Repair the generated solution using the validator feedback.

Problem:
{safe_problem}

Target language:
{language}

Previous solution:
{json.dumps(previous_solution, ensure_ascii=False, indent=2)}

Validation feedback:
{json.dumps(validation, ensure_ascii=False, indent=2)}
""".strip()


def final_format_system_prompt() -> str:
    return """
You are a technical writer formatting code-solving reports.
Return concise markdown with sections for classification, analysis, solution, tests, validation, and labels.
""".strip()
