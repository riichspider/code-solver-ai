"""Core interfaces and protocols for dependency injection.

Defines abstract interfaces for all major components to enable loose coupling
and improve testability and modularity.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol
from pathlib import Path


class AIProtocol(Protocol):
    """Protocol for all AI/LLM clients."""
    
    def list_models(self) -> List[str]:
        """List available models."""
        ...
    
    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        json_mode: bool = False,
    ) -> Dict[str, Any]:
        """Generate text response."""
        ...
    
    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate JSON response."""
        ...


class CacheProtocol(Protocol):
    """Protocol for caching implementations."""
    
    def build_key(
        self,
        problem: str,
        language: str,
        model: str,
        mode: str,
        context_text: str,
    ) -> str:
        """Build cache key from parameters."""
        ...
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        ...
    
    def set(
        self,
        key: str,
        value: Any,
        ttl_hours: Optional[int] = None,
        problem_hash: Optional[str] = None,
        language: str = "python",
        model: str = "default",
    ) -> None:
        """Set value in cache."""
        ...
    
    def get_stats(self) -> Any:
        """Get cache statistics."""
        ...


class HistoryProtocol(Protocol):
    """Protocol for history storage."""
    
    def save_result(self, result_payload: Dict[str, Any]) -> int:
        """Save result to history."""
        ...
    
    def find_similar(
        self,
        problem: str,
        language: Optional[str] = None,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """Find similar problems."""
        ...


class OptimizerProtocol(Protocol):
    """Protocol for context optimization."""
    
    def optimize_context(self, problem_text: str, language: str = "python") -> Any:
        """Optimize context for token reduction."""
        ...


class RouterProtocol(Protocol):
    """Protocol for model routing."""
    
    def analyze_problem(self, problem_text: str, language: str = "python") -> Any:
        """Analyze problem characteristics."""
        ...
    
    def select_model(self, analysis: Any, available_models: List[str]) -> Any:
        """Select optimal model based on analysis."""
        ...


class ValidatorProtocol(Protocol):
    """Protocol for solution validation."""
    
    def validate(
        self,
        language: str,
        code: str,
        tests: str,
        filename: str,
        test_filename: str,
    ) -> Dict[str, Any]:
        """Validate solution code and tests."""
        ...


class ExporterProtocol(Protocol):
    """Protocol for solution export."""
    
    def export_result(
        self,
        result: Any,
        export_root: Optional[Path] = None,
        slug: Optional[str] = None,
        max_exports: int = 20,
    ) -> Dict[str, str]:
        """Export solution to files."""
        ...


# Abstract base classes for more complex interfaces

class ProblemClassifierInterface(ABC):
    """Abstract interface for problem classification."""
    
    @abstractmethod
    def classify(
        self,
        problem: str,
        language_hint: str,
        context_text: str,
        similar_context: List[Dict[str, Any]],
        model: str,
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Classify problem type and complexity."""
        pass


class ProblemReasonerInterface(ABC):
    """Abstract interface for problem reasoning."""
    
    @abstractmethod
    def analyze(
        self,
        problem: str,
        classification: str,
        complexity: str,
        language: str,
        understanding: str,
        context_text: str,
        similar_context: List[Dict[str, Any]],
        model: str,
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze problem and create solution plan."""
        pass


class CodeGeneratorInterface(ABC):
    """Abstract interface for code generation."""
    
    @abstractmethod
    def generate(
        self,
        problem: str,
        classification: str,
        language: str,
        understanding: str,
        plan_steps: List[str],
        constraints: List[str],
        risks: List[str],
        success_criteria: List[str],
        context_text: str,
        similar_context: List[Dict[str, Any]],
        model: str,
        mode: str,
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate solution code."""
        pass
    
    @abstractmethod
    def repair(
        self,
        problem: str,
        language: str,
        previous_solution: Dict[str, Any],
        validation: Dict[str, Any],
        model: str,
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Repair failed solution."""
        pass


class DependencyContainer:
    """Container for managing dependencies."""
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._singletons: Dict[str, Any] = {}
    
    def register(self, name: str, factory, singleton: bool = False):
        """Register a service factory."""
        self._services[name] = (factory, singleton)
    
    def get(self, name: str):
        """Get a service instance."""
        if name not in self._services:
            raise ValueError(f"Service '{name}' not registered")
        
        factory, is_singleton = self._services[name]
        
        if is_singleton:
            if name not in self._singletons:
                self._singletons[name] = factory()
            return self._singletons[name]
        
        return factory()
    
    def register_instance(self, name: str, instance):
        """Register a specific instance."""
        self._singletons[name] = instance
    
    def has(self, name: str) -> bool:
        """Check if service is registered."""
        return name in self._services or name in self._singletons


# Global dependency container
container = DependencyContainer()
