from __future__ import annotations

import re
from typing import Any

from utils.prompts import (
    build_coding_user_prompt,
    build_repair_user_prompt,
    coding_system_prompt,
    repair_system_prompt,
)


LANGUAGE_DEFAULTS = {
    "python": ("solution.py", "test_solution.py"),
    "javascript": ("solution.js", "test_solution.js"),
    "typescript": ("solution.ts", "test_solution.ts"),
    "java": ("Solution.java", "SolutionTest.java"),
    "go": ("solution.go", "solution_test.go"),
    "rust": ("solution.rs", "solution_test.rs"),
}


class CodeGenerationError(RuntimeError):
    pass


class CodeGenerator:
    def __init__(self, client: Any) -> None:
        self.client = client

    def generate(
        self,
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
        model: str,
        mode: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        if self.client is None:
            raise CodeGenerationError(
                "Nenhum cliente de modelo local foi configurado. Inicie o Ollama e defina um modelo válido."
            )

        system_prompt = coding_system_prompt(language=language, mode=mode)
        base_user_prompt = build_coding_user_prompt(
            problem=problem,
            classification=classification,
            language=language,
            understanding=understanding,
            plan_steps=plan_steps,
            constraints=constraints,
            risks=risks,
            success_criteria=success_criteria,
            context_text=context_text,
            similar_context=similar_context,
        )

        errors: list[str] = []
        retry_suffixes = [
            "",
            (
                "\n\nPrevious attempt failed. Return ONLY valid JSON with every required key populated. "
                "Do not omit `code` or `tests`. Do not wrap the source code in markdown fences. "
                "Do not emit literal escaped layout sequences like \\n or \\t inside the final generated source. "
                "Prefer minimal, standard-library-compatible tests."
            ),
        ]

        for retry_suffix in retry_suffixes:
            try:
                payload = self.client.generate_json(
                    system_prompt=system_prompt,
                    user_prompt=base_user_prompt + retry_suffix,
                    model=model,
                    options=options,
                )
                return self._normalize_payload(payload, language)
            except Exception as exc:
                errors.append(str(exc))

        raise CodeGenerationError(
            "O modelo não retornou uma solução utilizável após 2 tentativas. "
            f"Último erro: {errors[-1]}"
        )

    def repair(
        self,
        problem: str,
        language: str,
        previous_solution: dict[str, Any],
        validation: dict[str, Any],
        model: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        if self.client is None:
            return previous_solution

        try:
            payload = self.client.generate_json(
                system_prompt=repair_system_prompt(language),
                user_prompt=build_repair_user_prompt(
                    problem=problem,
                    language=language,
                    previous_solution=previous_solution,
                    validation=validation,
                ),
                model=model,
                options=options,
            )
            return self._normalize_payload(payload, language)
        except Exception:
            return previous_solution

    def _normalize_payload(self, payload: dict[str, Any], language: str) -> dict[str, Any]:
        default_filename, default_test_filename = LANGUAGE_DEFAULTS.get(
            language,
            ("solution.txt", "test_solution.txt"),
        )
        filename = str(payload.get("filename", default_filename)).strip() or default_filename
        test_filename = str(payload.get("test_filename", default_test_filename)).strip() or default_test_filename

        explanation = payload.get("explanation", [])
        if isinstance(explanation, str):
            explanation = [explanation]
        explanation = [str(item).strip() for item in explanation if str(item).strip()]

        notes = payload.get("notes", [])
        if isinstance(notes, str):
            notes = [notes]
        notes = [str(item).strip() for item in notes if str(item).strip()]

    ```(?:[\w.+-]+)?\s*\n?(.*?)
