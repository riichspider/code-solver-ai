from __future__ import annotations

from typing import Any

from utils.logger import get_logger, log_warning
from utils.prompts import build_classification_user_prompt, classification_system_prompt


ALLOWED_CLASSIFICATIONS = {"bug", "enhancement",
                           "optimization", "refactor", "question"}


class ProblemClassifier:
    def __init__(self, client: Any) -> None:
        self.client = client
        self.logger = get_logger("classifier")

    def classify(
        self,
        problem: str,
        language_hint: str,
        context_text: str,
        similar_context: list[dict[str, Any]],
        model: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        fallback = self._fallback(problem, language_hint, context_text)
        if self.client is None:
            log_warning(
                self.logger,
                "No client available, using fallback classification",
                context="classify",
                details={"language_hint": language_hint}
            )
            return fallback

        try:
            payload = self.client.generate_json(
                system_prompt=classification_system_prompt(),
                user_prompt=build_classification_user_prompt(
                    problem=problem,
                    language_hint=language_hint,
                    context_text=context_text,
                    similar_context=similar_context,
                ),
                model=model,
                options=options,
            )
        except Exception as e:
            log_warning(
                self.logger,
                f"Classification failed, using fallback: {str(e)}",
                context="classify",
                details={"model": model, "error_type": type(e).__name__}
            )
            return fallback

        classification = str(payload.get(
            "classification", fallback["classification"])).strip().lower()
        if classification not in ALLOWED_CLASSIFICATIONS:
            classification = fallback["classification"]

        complexity = payload.get("complexity", fallback["complexity"])
        try:
            complexity = int(complexity)
        except (TypeError, ValueError):
            complexity = fallback["complexity"]
        complexity = max(1, min(10, complexity))

        detected_language = str(payload.get(
            "language", language_hint or fallback["language"])).strip().lower()
        labels = payload.get("labels") or fallback["labels"]
        if not isinstance(labels, list):
            labels = fallback["labels"]

        understanding = str(payload.get(
            "understanding", fallback["understanding"])).strip() or fallback["understanding"]
        why = str(payload.get(
            "why", fallback["why"])).strip() or fallback["why"]

        return {
            "classification": classification,
            "complexity": complexity,
            "labels": self._normalize_labels(labels, classification, detected_language, complexity),
            "language": detected_language,
            "understanding": understanding,
            "why": why,
        }

    def _fallback(self, problem: str, language_hint: str, context_text: str) -> dict[str, Any]:
        combined = f"{problem}\n{context_text}".lower()
        if any(token in combined for token in ["traceback", "exception", "erro", "bug", "fails", "falha"]):
            classification = "bug"
        elif any(token in combined for token in ["optimiz", "performance", "slow", "lento"]):
            classification = "optimization"
        elif any(token in combined for token in ["refactor", "cleanup", "clean up", "reorganize"]):
            classification = "refactor"
        elif any(token in combined for token in ["feature", "add", "support", "implement", "crie"]):
            classification = "enhancement"
        else:
            classification = "question"

        detected_language = self._detect_language(language_hint, combined)
        complexity = min(10, max(2, len(problem.split()) //
                         12 + (2 if context_text else 0)))
        understanding = (
            "Resolver o problema descrito, considerando o contexto disponível, entregando código "
            "executável, testes e explicação clara."
        )
        why = "Classificação inferida por heurísticas locais porque a resposta estruturada do modelo não ficou disponível."

        return {
            "classification": classification,
            "complexity": complexity,
            "labels": self._normalize_labels([], classification, detected_language, complexity),
            "language": detected_language,
            "understanding": understanding,
            "why": why,
        }

    def _detect_language(self, language_hint: str, combined_text: str) -> str:
        if language_hint:
            return language_hint.strip().lower()
        if "typescript" in combined_text or ".ts" in combined_text:
            return "typescript"
        if "javascript" in combined_text or ".js" in combined_text:
            return "javascript"
        if "rust" in combined_text or ".rs" in combined_text:
            return "rust"
        if "golang" in combined_text or " go " in combined_text or ".go" in combined_text:
            return "go"
        if "java" in combined_text or ".java" in combined_text:
            return "java"
        return "python"

    def _normalize_labels(
        self,
        labels: list[Any],
        classification: str,
        language: str,
        complexity: int,
    ) -> list[str]:
        bucket = "complexity-high" if complexity >= 8 else "complexity-medium" if complexity >= 5 else "complexity-low"
        normalized: list[str] = []
        for label in labels:
            text = str(label).strip().lower().replace(" ", "-")
            if text and text not in normalized:
                normalized.append(text)
        for mandatory in [classification, language, bucket]:
            if mandatory not in normalized:
                normalized.append(mandatory)
        return normalized
