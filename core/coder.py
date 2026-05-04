from __future__ import annotations

import re
from typing import Any

from utils.logger import get_logger, log_error
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
        self.logger = get_logger("coder")

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
            log_error(
                self.logger,
                CodeGenerationError("No client available for code generation"),
                context="generate",
                details={"language": language, "model": model}
            )
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
                log_error(
                    self.logger,
                    exc,
                    context="generate",
                    details={
                        "language": language,
                        "model": model,
                        "retry_attempt": len(errors),
                        "error": str(exc)
                    }
                )

        final_error = CodeGenerationError(
            "O modelo não retornou uma solução utilizável após 2 tentativas. "
            f"Último erro: {errors[-1]}"
        )
        log_error(
            self.logger,
            final_error,
            context="generate",
            details={
                "language": language,
                "model": model,
                "total_retries": len(errors),
                "all_errors": errors
            }
        )
        raise final_error

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
        filename = str(payload.get("filename", default_filename)
                       ).strip() or default_filename
        test_filename = str(payload.get(
            "test_filename", default_test_filename)).strip() or default_test_filename

        explanation = payload.get("explanation", [])
        if isinstance(explanation, str):
            explanation = [explanation]
        explanation = [str(item).strip()
                       for item in explanation if str(item).strip()]

        notes = payload.get("notes", [])
        if isinstance(notes, str):
            notes = [notes]
        notes = [str(item).strip() for item in notes if str(item).strip()]

        code = self._normalize_generated_block(
            str(payload.get("code", "")).strip())
        tests = self._normalize_generated_block(
            str(payload.get("tests", "")).strip())
        if not code:
            raise CodeGenerationError(
                "O modelo não retornou código utilizável.")

        return {
            "filename": filename,
            "test_filename": test_filename,
            "code": code,
            "tests": tests,
            "explanation": explanation or ["Solução gerada com foco em correção, clareza e testabilidade."],
            "notes": notes,
        }

    def _normalize_generated_block(self, text: str) -> str:
        cleaned = self._strip_code_fences(text)
        cleaned = cleaned.replace("\r\n", "\n")
        if self._looks_escaped_multiline(cleaned):
            cleaned = (
                cleaned.replace("\\r\\n", "\n")
                .replace("\\n", "\n")
                .replace("\\t", "\t")
            )
        return cleaned.strip()

    def _strip_code_fences(self, text: str) -> str:
        cleaned = text.strip()
        fence_match = re.search(
            r"```(?:[\w.+-]+)?\s*\n?(.*?)```", cleaned, re.DOTALL)
        if fence_match:
            return fence_match.group(1).strip()

        cleaned = re.sub(r"^\s*```(?:[\w.+-]+)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
        return cleaned

    def _looks_escaped_multiline(self, text: str) -> bool:
        escaped_layout = text.count("\\n") + text.count("\\t")
        actual_newlines = text.count("\n")
        return escaped_layout >= 2 and escaped_layout > max(1, actual_newlines)
