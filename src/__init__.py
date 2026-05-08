"""Pacote src com módulos principais do code-solver-ai."""

from .classifier import (
    ClassificationType,
    ConfidenceLevel,
    ClassificationResult,
    ClassificationRequest,
    ClassificationStrategy,
    BaseClassificationStrategy,
    OllamaClassifierStrategy,
    RuleBasedClassifierStrategy,
    Classifier,
    create_classifier
)

from .repair_engine import (
    RepairStatus,
    RepairConfidence,
    ErrorContext,
    RepairProposal,
    RepairResult,
    RepairStrategy,
    BaseRepairStrategy,
    OllamaRepairStrategy,
    PatternBasedRepairStrategy,
    RepairEngine,
    create_repair_engine
)

__all__ = [
    # Classifier module
    "ClassificationType",
    "ConfidenceLevel",
    "ClassificationResult",
    "ClassificationRequest",
    "ClassificationStrategy",
    "BaseClassificationStrategy",
    "OllamaClassifierStrategy",
    "RuleBasedClassifierStrategy",
    "Classifier",
    "create_classifier",
    # Repair Engine module
    "RepairStatus",
    "RepairConfidence",
    "ErrorContext",
    "RepairProposal",
    "RepairResult",
    "RepairStrategy",
    "BaseRepairStrategy",
    "OllamaRepairStrategy",
    "PatternBasedRepairStrategy",
    "RepairEngine",
    "create_repair_engine"
]
