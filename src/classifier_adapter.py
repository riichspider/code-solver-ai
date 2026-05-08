"""Adapter: traduz entre o contrato dict do core/pipeline.py
e o ClassificationResult tipado do src/classifier.py.
"""
from __future__ import annotations
from typing import Any
from src.classifier import create_classifier, ClassificationRequest, ClassificationResult, ClassificationType


class ClassifierAdapter:
    """Wrapper que expõe a mesma interface do core/classifier.py antigo,
    mas delega para o src/classifier.py novo com type safety."""

    def __init__(self, ollama_client: Any = None) -> None:
        # Extrai o modelo com fallback para clientes que não têm default_model
        model = getattr(ollama_client, "default_model", "qwen2.5-coder:latest")
        self._classifier = create_classifier(
            ollama_client=ollama_client, model=model)

    def classify(
        self,
        problem: str,
        language_hint: str,
        context_text: str = "",
        similar_context: list[dict[str, Any]] | None = None,
        model: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Retorna dict compatível com o formato que o pipeline espera."""
        # Ignora context_text e similar_context pois o novo classifier não os usa
        request = ClassificationRequest(
            input_text=problem,
            language=language_hint or "",
        )
        result: ClassificationResult = self._classifier.classify(request)

        # Mapeamento para compatibilidade com o sistema antigo
        classification_map = {
            ClassificationType.BUG: "bug",
            ClassificationType.FEATURE: "enhancement",  # Mapeia FEATURE para enhancement
            ClassificationType.REFACTOR: "refactor",
            ClassificationType.UNKNOWN: "unknown"
        }

        # Mantém exatamente as chaves que o pipeline consome hoje
        return {
            "classification": classification_map.get(result.classification, "unknown"),
            # Converte 0.0-1.0 para 1-10
            "complexity": int(result.complexity_score * 10),
            # ClassificationResult não tem campo language
            "language": language_hint or "python",
            "understanding": result.reasoning,  # Mapeia reasoning para understanding
            "why": result.reasoning,
            "labels": result.tags,  # Mapeia tags para labels
            # Sugere repair para bugs
            "auto_repair": result.classification == ClassificationType.BUG,
        }
