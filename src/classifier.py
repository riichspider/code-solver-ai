"""Módulo de classificação inteligente usando padrão Strategy.

Analisa input e classifica em: BUG, FEATURE ou REFACTOR via Ollama,
retornando JSON estruturado com type hints rigorosos.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Union
from pathlib import Path

from models.ollama_client import OllamaClient, OllamaError

# Valor sentinel para distinguir entre não passado e explicitamente None
_SENTINEL = object()


class ClassificationType(Enum):
    """Tipos de classificação suportados."""
    BUG = "bug"
    FEATURE = "feature"
    REFACTOR = "refactor"
    UNKNOWN = "unknown"


class ConfidenceLevel(Enum):
    """Níveis de confiança da classificação."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass(frozen=True)
class ClassificationResult:
    """Resultado estruturado da classificação."""
    classification: ClassificationType
    confidence: ConfidenceLevel
    reasoning: str
    key_indicators: List[str]
    suggested_actions: List[str]
    complexity_score: float  # 0.0 a 1.0
    estimated_effort: str  # "low", "medium", "high"
    tags: List[str]
    raw_response: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário JSON serializável."""
        result = asdict(self)
        result['classification'] = self.classification.value
        result['confidence'] = self.confidence.value
        return result

    def to_json(self) -> str:
        """Converte para JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass(frozen=True)
class ClassificationRequest:
    """Request para classificação com metadados."""
    input_text: str
    context: Optional[str] = None
    language: Optional[str] = None
    file_path: Optional[str] = None
    additional_metadata: Optional[Dict[str, Any]] = None


class ClassificationStrategy(Protocol):
    """Interface Strategy para diferentes estratégias de classificação."""

    def classify(self, request: ClassificationRequest) -> ClassificationResult:
        """Executa a classificação do input."""
        ...

    def validate_request(self, request: ClassificationRequest) -> bool:
        """Valida se a request é adequada para esta estratégia."""
        ...


class BaseClassificationStrategy(ABC):
    """Classe base abstrata para estratégias de classificação."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._setup_prompts()

    @abstractmethod
    def _setup_prompts(self) -> None:
        """Configura os prompts específicos da estratégia."""
        ...

    @abstractmethod
    def classify(self, request: ClassificationRequest) -> ClassificationResult:
        """Executa a classificação usando a estratégia específica."""
        ...

    def validate_request(self, request: ClassificationRequest) -> bool:
        """Validação base da request."""
        if not request.input_text or not request.input_text.strip():
            return False

        # Verifica tamanho mínimo do texto
        if len(request.input_text.strip()) < 10:
            return False

        return True

    def _build_context_string(self, request: ClassificationRequest) -> str:
        """Constrói string de contexto a partir da request."""
        context_parts = []

        if request.context:
            context_parts.append(f"Context: {request.context}")

        if request.language:
            context_parts.append(f"Language: {request.language}")

        if request.file_path:
            context_parts.append(f"File: {request.file_path}")

        if request.additional_metadata:
            metadata_str = ", ".join(
                f"{k}: {v}" for k, v in request.additional_metadata.items())
            context_parts.append(f"Metadata: {metadata_str}")

        return "\n".join(context_parts) if context_parts else "No additional context provided."


class OllamaClassifierStrategy(BaseClassificationStrategy):
    """Estratégia de classificação usando Ollama com IA."""

    def __init__(self, ollama_client: OllamaClient, model: Optional[str] = None) -> None:
        self.client = ollama_client
        self.model = model or ollama_client.default_model
        super().__init__(name="ollama_classifier")

    def _setup_prompts(self) -> None:
        """Configura prompts para classificação via Ollama."""
        self.system_prompt = """You are an expert software development analyst. Your task is to classify code-related requests into one of three categories:

1. **BUG** - Issues, errors, problems, unexpected behavior, crashes, performance issues
2. **FEATURE** - New functionality, enhancements, additions, new capabilities
3. **REFACTOR** - Code improvements, optimizations, restructuring, cleanup without changing behavior

Analyze the input carefully and provide a structured JSON response with:
- classification: "bug", "feature", or "refactor"
- confidence: "low", "medium", "high", or "very_high"
- reasoning: Detailed explanation of your classification
- key_indicators: Array of specific phrases/patterns that led to your decision
- suggested_actions: Array of recommended next steps
- complexity_score: Float between 0.0 and 1.0
- estimated_effort: "low", "medium", or "high"
- tags: Array of relevant technical tags

Consider the context, language, and any additional metadata provided. Be precise and justify your reasoning."""

        self.user_prompt_template = """Classify the following request:

{context}

INPUT:
{input_text}

Provide your analysis as a structured JSON response following the exact format specified in the system prompt."""

    def classify(self, request: ClassificationRequest) -> ClassificationResult:
        """Executa classificação usando Ollama."""
        if not self.validate_request(request):
            raise ValueError("Invalid classification request")

        try:
            # Constrói o prompt
            context_str = self._build_context_string(request)
            user_prompt = self.user_prompt_template.format(
                context=context_str,
                input_text=request.input_text.strip()
            )

            # Chama Ollama em modo JSON
            response = self.client.generate_json(
                system_prompt=self.system_prompt,
                user_prompt=user_prompt,
                model=self.model
            )

            # Processa resposta
            return self._parse_ollama_response(response)

        except OllamaError as e:
            # Fallback para classificação desconhecida
            return ClassificationResult(
                classification=ClassificationType.UNKNOWN,
                confidence=ConfidenceLevel.LOW,
                reasoning=f"Ollama classification failed: {str(e)}",
                key_indicators=["ollama_error"],
                suggested_actions=["manual_classification"],
                complexity_score=0.0,
                estimated_effort="unknown",
                tags=["error", "fallback"],
                raw_response={"error": str(e)}
            )
        except Exception as e:
            raise RuntimeError(f"Classification failed: {str(e)}") from e

    def _parse_ollama_response(self, response: Dict[str, Any]) -> ClassificationResult:
        """Parse e valida resposta do Ollama."""
        try:
            # Mapeamento de tipos
            classification_map = {
                "bug": ClassificationType.BUG,
                "feature": ClassificationType.FEATURE,
                "refactor": ClassificationType.REFACTOR,
                "unknown": ClassificationType.UNKNOWN
            }

            confidence_map = {
                "low": ConfidenceLevel.LOW,
                "medium": ConfidenceLevel.MEDIUM,
                "high": ConfidenceLevel.HIGH,
                "very_high": ConfidenceLevel.VERY_HIGH
            }

            # Extrai valores com defaults seguros
            classification_str = response.get(
                "classification", "unknown").lower()
            confidence_str = response.get("confidence", "low").lower()

            classification = classification_map.get(
                classification_str, ClassificationType.UNKNOWN)
            confidence = confidence_map.get(
                confidence_str, ConfidenceLevel.LOW)

            # Validações de tipo
            reasoning = str(response.get("reasoning", ""))
            key_indicators = response.get("key_indicators", [])
            suggested_actions = response.get("suggested_actions", [])
            complexity_score = float(response.get("complexity_score", 0.0))
            estimated_effort = str(response.get("estimated_effort", "unknown"))
            tags = response.get("tags", [])

            # Validações de arrays
            if not isinstance(key_indicators, list):
                key_indicators = [str(key_indicators)]

            if not isinstance(suggested_actions, list):
                suggested_actions = [str(suggested_actions)]

            if not isinstance(tags, list):
                tags = [str(tags)]

            # Normalização de valores
            complexity_score = max(0.0, min(1.0, complexity_score))

            if estimated_effort not in ["low", "medium", "high", "unknown"]:
                estimated_effort = "unknown"

            return ClassificationResult(
                classification=classification,
                confidence=confidence,
                reasoning=reasoning,
                key_indicators=key_indicators,
                suggested_actions=suggested_actions,
                complexity_score=complexity_score,
                estimated_effort=estimated_effort,
                tags=tags,
                raw_response=response
            )

        except Exception as e:
            # Fallback em caso de erro no parsing
            return ClassificationResult(
                classification=ClassificationType.UNKNOWN,
                confidence=ConfidenceLevel.LOW,
                reasoning=f"Failed to parse Ollama response: {str(e)}",
                key_indicators=["parsing_error"],
                suggested_actions=["manual_review"],
                complexity_score=0.0,
                estimated_effort="unknown",
                tags=["error", "parsing"],
                raw_response=response
            )


class RuleBasedClassifierStrategy(BaseClassificationStrategy):
    """Estratégia de classificação baseada em regras (fallback)."""

    def __init__(self) -> None:
        super().__init__(name="rule_based_classifier")

    def _setup_prompts(self) -> None:
        """Configura regras para classificação baseada em padrões."""
        self.bug_keywords = [
            "error", "bug", "issue", "problem", "crash", "fail", "broken",
            "not working", "incorrect", "wrong", "exception", "fix", "debug"
        ]

        self.feature_keywords = [
            "add", "new", "implement", "create", "feature", "enhancement",
            "support", "ability", "functionality", "capability", "extend"
        ]

        self.refactor_keywords = [
            "refactor", "improve", "optimize", "clean", "restructure",
            "simplify", "better", "performance", "efficiency", "maintain"
        ]

    def classify(self, request: ClassificationRequest) -> ClassificationResult:
        """Executa classificação baseada em regras."""
        if not self.validate_request(request):
            raise ValueError("Invalid classification request")

        text = request.input_text.lower()

        # Conta palavras-chave
        bug_score = sum(1 for keyword in self.bug_keywords if keyword in text)
        feature_score = sum(
            1 for keyword in self.feature_keywords if keyword in text)
        refactor_score = sum(
            1 for keyword in self.refactor_keywords if keyword in text)

        # Determina classificação
        scores = {
            ClassificationType.BUG: bug_score,
            ClassificationType.FEATURE: feature_score,
            ClassificationType.REFACTOR: refactor_score
        }

        classification = max(scores, key=scores.get)
        max_score = scores[classification]

        # Se todos os scores são baixos, classifica como unknown
        if max_score == 0:
            classification = ClassificationType.UNKNOWN
            confidence = ConfidenceLevel.LOW
        elif max_score >= 2:
            confidence = ConfidenceLevel.HIGH
        elif max_score == 1:
            confidence = ConfidenceLevel.MEDIUM
        else:
            confidence = ConfidenceLevel.LOW

        # Constrói resultado
        return ClassificationResult(
            classification=classification,
            confidence=confidence,
            reasoning=f"Rule-based classification: {classification.value} (score: {max_score})",
            key_indicators=[f"{k}_score: {v}" for k, v in scores.items()],
            suggested_actions=[
                "review_classification"] if confidence == ConfidenceLevel.LOW else ["proceed"],
            complexity_score=0.5,
            estimated_effort="medium",
            tags=["rule_based", classification.value],
            raw_response={"scores": scores, "max_score": max_score}
        )


class Classifier:
    """Classe principal que gerencia diferentes estratégias de classificação."""

    _SENTINEL = object()

    def __init__(self, primary_strategy: ClassificationStrategy,
                 fallback_strategy: Optional[ClassificationStrategy] = _SENTINEL) -> None:
        self.primary_strategy = primary_strategy
        # Cria fallback padrão apenas se não for passado (sentinel)
        if fallback_strategy is self._SENTINEL:
            self.fallback_strategy = RuleBasedClassifierStrategy()
        else:
            self.fallback_strategy = fallback_strategy

    def classify(self, request: Union[str, ClassificationRequest]) -> ClassificationResult:
        # Converte string para request se necessário
        if isinstance(request, str):
            request = ClassificationRequest(input_text=request)

        # Valida request
        if not self.primary_strategy.validate_request(request):
            raise ValueError("Invalid classification request")

        try:
            # Tenta estratégia primária
            result = self.primary_strategy.classify(request)

            # Se confiança muito baixa, tenta fallback
            if result.confidence == ConfidenceLevel.LOW and self.fallback_strategy:
                fallback_result = self.fallback_strategy.classify(request)

                # Usa fallback se tiver confiança melhor
                if (fallback_result.confidence.value in ["medium", "high", "very_high"] and
                        fallback_result.classification != ClassificationType.UNKNOWN):
                    return fallback_result

            return result

        except Exception as e:
            # Fallback em caso de erro
            if self.fallback_strategy:
                try:
                    return self.fallback_strategy.classify(request)
                except Exception:
                    pass

            # Último recurso - retorna erro
            raise RuntimeError(
                f"All classification strategies failed: {str(e)}") from e

    def get_strategy_info(self) -> Dict[str, Any]:
        """Retorna informações sobre as estratégias configuradas."""
        return {
            "primary_strategy": getattr(self.primary_strategy, 'name', 'unknown'),
            "fallback_strategy": getattr(self.fallback_strategy, 'name', 'unknown'),
            "has_fallback": self.fallback_strategy is not None
        }


# Factory function para facilitar criação
def create_classifier(ollama_client: OllamaClient,
                      model: Optional[str] = None,
                      enable_fallback: bool = True) -> Classifier:
    """Factory function para criar classifier com configurações padrão."""
    primary = OllamaClassifierStrategy(ollama_client, model)

    if enable_fallback:
        return Classifier(primary_strategy=primary)  # Usa fallback padrão
    else:
        # Sem fallback
        return Classifier(primary_strategy=primary, fallback_strategy=Classifier._SENTINEL)


# Exportações públicas
__all__ = [
    "ClassificationType",
    "ConfidenceLevel",
    "ClassificationResult",
    "ClassificationRequest",
    "ClassificationStrategy",
    "BaseClassificationStrategy",
    "OllamaClassifierStrategy",
    "RuleBasedClassifierStrategy",
    "Classifier",
    "create_classifier"
]
