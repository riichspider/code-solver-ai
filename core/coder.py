from __future__ import annotations

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


class CodeGenerator:
    def __init__(self, client) -> None:
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
            raise RuntimeError(
                "Nenhum cliente de modelo local foi configurado. Inicie o Ollama e defina um modelo válido."
            )

        payload = self.client.generate_json(
            system_prompt=coding_system_prompt(language=language, mode=mode),
            user_prompt=build_coding_user_prompt(
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
            ),
            model=model,
            options=options,
        )
        return self._normalize_payload(payload, language)

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

        code = self._strip_code_fences(str(payload.get("code", "")).strip())
        tests = self._strip_code_fences(str(payload.get("tests", "")).strip())
        if not code:
            raise RuntimeError("O modelo não retornou código utilizável.")

        return {
            "filename": filename,
            "test_filename": test_filename,
            "code": code,
            "tests": tests,
            "explanation": explanation or ["Solução gerada com foco em correção, clareza e testabilidade."],
            "notes": notes,
        }

    def _strip_code_fences(self, text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```") and cleaned.endswith("```"):
            lines = cleaned.splitlines()
            if len(lines) >= 3:
                cleaned = "\n".join(lines[1:-1]).strip()
        return cleaned
