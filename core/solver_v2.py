"""Refactored CodeSolver with dependency injection.

This version implements loose coupling through dependency injection,
making the system more modular, testable, and maintainable.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Optional

from core.interfaces import (
    AIProtocol, CacheProtocol, HistoryProtocol, OptimizerProtocol,
    RouterProtocol, ValidatorProtocol, ExporterProtocol,
    ProblemClassifierInterface, ProblemReasonerInterface, 
    CodeGeneratorInterface, container
)
from core.models import ContextItem, SolveRequest, SolveResult
from utils.logger import get_logger, log_pipeline_stage
from utils.markdown import render_solution_markdown


class CodeSolverV2:
    """Dependency-injected version of CodeSolver."""
    
    def __init__(
        self,
        base_dir: Path,
        config: dict[str, Any],
        ai_client: Optional[AIProtocol] = None,
        cache: Optional[CacheProtocol] = None,
        history: Optional[HistoryProtocol] = None,
        classifier: Optional[ProblemClassifierInterface] = None,
        reasoner: Optional[ProblemReasonerInterface] = None,
        coder: Optional[CodeGeneratorInterface] = None,
        validator: Optional[ValidatorProtocol] = None,
        exporter: Optional[ExporterProtocol] = None,
        optimizer: Optional[OptimizerProtocol] = None,
        router: Optional[RouterProtocol] = None,
    ) -> None:
        self.base_dir = Path(base_dir)
        self.config = config
        self.logger = get_logger("code_solver_v2")
        
        # Dependency injection - use provided instances or get from container
        self.ai_client = ai_client or container.get('ai_client')
        self.cache = cache or container.get('cache')
        self.history = history or container.get('history')
        self.classifier = classifier or container.get('classifier')
        self.reasoner = reasoner or container.get('reasoner')
        self.coder = coder or container.get('coder')
        self.validator = validator or container.get('validator')
        self.exporter = exporter or container.get('exporter')
        self.optimizer = optimizer or container.get('optimizer')
        self.router = router or container.get('router')
        
        # Configuration
        self.default_model = config.get("default_model", "qwen2.5-coder:latest")
        self.supported_languages = config.get(
            "supported_languages",
            ["python", "javascript", "typescript", "java", "go", "rust"],
        )
        self.cache_enabled = bool(config.get("cache", {}).get("enabled", True))
        self.similar_results = int(config.get("history", {}).get("similar_results", 3))
    
    @classmethod
    def from_config(cls, config_path: Path) -> "CodeSolverV2":
        """Create instance from configuration file."""
        config_file = Path(config_path)
        import yaml
        config = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        return cls(base_dir=config_file.parent, config=config)
    
    def solve(self, request: SolveRequest) -> SolveResult:
        """Main solve method with dependency injection."""
        problem = request.problem.strip()
        if not problem:
            raise ValueError("O problema não pode estar vazio.")

        language = (request.language or "python").strip().lower()
        if language not in self.supported_languages:
            language = "python"
        mode = request.mode if request.mode in {"fast", "deep"} else "fast"
        
        # Intelligent model routing
        model, model_resolution = self._resolve_model(request.model, problem, language)

        log_pipeline_stage(
            self.logger, "solve", "started",
            details={
                "problem_length": len(problem),
                "language": language,
                "model": model,
                "mode": mode,
                "cache_enabled": request.use_cache and self.cache_enabled,
                "context_items": len(request.context_items),
                "routing_used": model_resolution.get("routing_used", False),
            },
        )

        # Optimize context
        context_text = self._format_context_items(request.context_items, language)
        cache_key = self.cache.build_key(problem, language, model, mode, context_text)
        
        # Check cache
        if request.use_cache and self.cache_enabled:
            cached_payload = self.cache.get(cache_key)
            if cached_payload:
                log_pipeline_stage(
                    self.logger, "solve", "cache_hit",
                    details={
                        "cache_key": cache_key[:50] + "...",
                        "cache_stats": getattr(self.cache, 'get_stats', lambda: {})(),
                    },
                )
                cached_payload["cached"] = True
                return SolveResult.from_dict(cached_payload)

        # Get similar context
        similar_context = self.history.find_similar(
            problem=problem, language=language, limit=self.similar_results,
        )
        options = self._build_model_options(mode)

        # Classification stage
        classification = self.classifier.classify(
            problem=problem,
            language_hint=language,
            context_text=context_text,
            similar_context=similar_context,
            model=model,
            options=options,
        )
        language = classification.get("language", language)

        # Reasoning stage
        reasoning = self.reasoner.analyze(
            problem=problem,
            classification=classification["classification"],
            complexity=classification["complexity"],
            language=language,
            understanding=classification["understanding"],
            context_text=context_text,
            similar_context=similar_context,
            model=model,
            options=options,
        )

        # Code generation stage
        solution = None
        generation_error = None
        try:
            solution = self.coder.generate(
                problem=problem,
                classification=classification["classification"],
                language=language,
                understanding=reasoning["understanding"],
                plan_steps=reasoning["plan_steps"],
                constraints=reasoning["constraints"],
                risks=reasoning["risks"],
                success_criteria=reasoning["success_criteria"],
                context_text=context_text,
                similar_context=similar_context,
                model=model,
                mode=mode,
                options=options,
            )
        except Exception as exc:
            generation_error = exc
            solution = {
                "filename": "solution.py",
                "test_filename": "test_solution.py",
                "code": "",
                "tests": "",
                "explanation": [f"Generation failed: {str(exc)}"],
                "notes": ["Auto-repair will be attempted"],
            }

        # Validation stage
        validation = self.validator.validate(
            language=language,
            code=solution["code"],
            tests=solution["tests"],
            filename=solution["filename"],
            test_filename=solution["test_filename"],
        )

        # Auto-repair if needed
        repair_applied = False
        should_attempt_repair = (
            request.auto_repair
            and (validation.get("status") == "failed" or generation_error is not None)
        )

        if should_attempt_repair:
            repair_validation = (
                {
                    "status": "failed",
                    "errors": [f"Code generation failed: {str(generation_error)}"],
                    "details": {"generation_error": True},
                }
                if generation_error is not None
                else validation
            )

            try:
                repaired_solution = self.coder.repair(
                    problem=problem,
                    language=language,
                    previous_solution=solution,
                    validation=repair_validation,
                    model=model,
                    options=options,
                )
                repaired_validation = self.validator.validate(
                    language=language,
                    code=repaired_solution["code"],
                    tests=repaired_solution["tests"],
                    filename=repaired_solution["filename"],
                    test_filename=repaired_solution["test_filename"],
                )
                if repaired_validation.get("status") == "passed":
                    solution = repaired_solution
                    validation = repaired_validation
                    repair_applied = True
                elif generation_error is not None:
                    raise RuntimeError(
                        "Falha ao gerar uma solução executável e a tentativa de reparo também falhou. "
                        "Tente usar um modelo maior, ativar `--mode deep` ou enviar mais contexto. "
                        f"Detalhe: {generation_error}"
                    ) from generation_error
            except Exception as repair_error:
                self.logger.warning(f"Auto-repair failed: {repair_error}")

        # Build result
        metadata = {
            "classification_reason": classification.get("why", ""),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "repair_applied": repair_applied,
            "context_files": [item.name for item in request.context_items],
            "similar_context_count": len(similar_context),
            "default_model_requested": request.model is None,
            "configured_default_model": self.default_model,
            "model_resolution": model_resolution,
            "tokens_saved": getattr(context_text, 'tokens_saved', 0),
        }

        result = SolveResult(
            problem=problem,
            classification=classification["classification"],
            complexity=classification["complexity"],
            labels=classification["labels"],
            language=language,
            model=model,
            mode=mode,
            understanding=reasoning["understanding"],
            plan_steps=reasoning["plan_steps"],
            constraints=reasoning["constraints"],
            risks=reasoning["risks"],
            success_criteria=reasoning["success_criteria"],
            code=solution["code"],
            tests=solution["tests"],
            filename=solution["filename"],
            test_filename=solution["test_filename"],
            explanation=solution["explanation"],
            validation=validation,
            markdown="",
            similar_context=similar_context,
            metadata=metadata,
        )
        result.markdown = render_solution_markdown(result.to_dict())

        # Save to cache and history
        self._save_result(cache_key, result.to_dict(), problem, language, model)

        return result
    
    def solve_batch(self, problems: list[str], template: SolveRequest) -> list[SolveResult]:
        """Solve multiple problems using the same template."""
        return [
            self.solve(
                SolveRequest(
                    problem=problem,
                    language=template.language,
                    model=template.model,
                    mode=template.mode,
                    context_items=template.context_items,
                    use_cache=template.use_cache,
                    auto_repair=template.auto_repair,
                )
            )
            for problem in problems
        ]
    
    def _resolve_model(
        self, 
        requested_model: Optional[str], 
        problem: str = "", 
        language: str = "python"
    ) -> tuple[str, dict[str, Any]]:
        """Resolve model using intelligent routing."""
        metadata: dict[str, Any] = {
            "requested_model": requested_model,
            "configured_default_model": self.default_model,
            "resolved_model": None,
            "fallback_used": False,
            "routing_used": False,
            "routing_reasoning": [],
        }

        # If specific model requested, use it
        if requested_model:
            metadata["resolved_model"] = requested_model
            return requested_model, metadata

        # Use intelligent routing
        try:
            available_models = self.ai_client.list_models()
            problem_analysis = self.router.analyze_problem(problem, language)
            recommendation = self.router.select_model(problem_analysis, available_models)
            
            metadata.update({
                "resolved_model": recommendation.model,
                "routing_used": True,
                "routing_category": getattr(recommendation, 'category', 'unknown'),
                "routing_confidence": getattr(recommendation, 'confidence', 0.0),
                "routing_reasoning": getattr(recommendation, 'reasoning', []),
                "problem_complexity": getattr(problem_analysis, 'complexity_score', 0.0),
                "problem_type": getattr(problem_analysis, 'problem_type', 'unknown'),
            })
            
            self.logger.info(
                f"Intelligent routing selected '{recommendation.model}' "
                f"(confidence: {getattr(recommendation, 'confidence', 0.0):.2f})"
            )
            
            return recommendation.model, metadata
            
        except Exception as e:
            self.logger.warning(f"Intelligent routing failed, using default: {e}")
            metadata["routing_error"] = str(e)
            metadata["resolved_model"] = self.default_model
            return self.default_model, metadata
    
    def _format_context_items(self, context_items: list[ContextItem], language: str = "python") -> str:
        """Format and optimize context items."""
        if not context_items:
            return ""
        
        sections: list[str] = []
        total_tokens_saved = 0
        
        for item in context_items:
            # Apply optimization
            optimization_result = self.optimizer.optimize_context(
                item.content.strip(), language
            )
            
            if hasattr(optimization_result, 'tokens_saved'):
                total_tokens_saved += optimization_result.tokens_saved
                if optimization_result.tokens_saved > 0:
                    self.logger.info(
                        f"Context item '{item.name}' optimized: "
                        f"{optimization_result.tokens_saved} tokens saved"
                    )
            
            content = optimization_result.content if hasattr(optimization_result, 'content') else optimization_result
            sections.append(f"### {item.name}\n{content}")
        
        # Apply final optimization
        combined_context = "\n\n".join(sections).strip()
        final_optimization = self.optimizer.optimize_context(combined_context, language)
        
        if hasattr(final_optimization, 'tokens_saved') and final_optimization.tokens_saved > 0:
            total_tokens_saved += final_optimization.tokens_saved
            self.logger.info(
                f"Combined context optimized: {final_optimization.tokens_saved} tokens saved"
            )
        
        # Add token savings to result for tracking
        result = final_optimization.content if hasattr(final_optimization, 'content') else final_optimization
        result.tokens_saved = total_tokens_saved  # type: ignore
        
        return result
    
    def _build_model_options(self, mode: str) -> dict[str, Any]:
        """Build model options based on mode."""
        base_options = dict(self.config.get("ollama", {}).get("options", {}))
        profile = dict(self.config.get("profiles", {}).get(mode, {}))
        profile.pop("reasoning_style", None)
        return {**base_options, **profile}
    
    def _save_result(
        self, 
        cache_key: str, 
        payload: dict[str, Any], 
        problem: str, 
        language: str, 
        model: str
    ) -> None:
        """Save result to cache and history."""
        # Save to history
        history_id = self.history.save_result(payload)
        payload["history_id"] = history_id
        
        # Save to cache
        if self.cache_enabled:
            problem_hash = sha256(problem.encode('utf-8')).hexdigest()[:16]
            self.cache.set(
                cache_key, 
                payload, 
                ttl_hours=int(self.config.get("cache", {}).get("ttl_hours", 24)),
                problem_hash=problem_hash,
                language=language,
                model=model
            )
    
    def export_result(
        self,
        result: SolveResult,
        export_root: Optional[Path] = None,
        slug: Optional[str] = None,
        max_exports: int = 20,
    ) -> dict[str, str]:
        """Export solution using injected exporter."""
        return self.exporter.export_result(result, export_root, slug, max_exports)
    
    def get_cache_stats(self) -> Any:
        """Get cache statistics."""
        if hasattr(self.cache, 'get_stats'):
            return self.cache.get_stats()
        return {}


# Factory function for easy setup
def create_solver_v2(base_dir: Path, config: dict[str, Any]) -> CodeSolverV2:
    """Factory function to create CodeSolverV2 with all dependencies."""
    
    # This would typically be replaced with proper dependency injection setup
    # For now, we'll use the existing implementations
    
    # Import implementations
    from models.fallback_client import FallbackClient
    from utils.smart_cache import SmartCodeCache
    from core.cache import HistoryStore
    from core.classifier import ProblemClassifier
    from core.reasoner import ProblemReasoner
    from core.coder import CodeGenerator
    from core.validator import SolutionValidator
    from core.exporter import SolutionExporter
    from utils.token_optimizer import TokenOptimizer
    from utils.model_router import IntelligentModelRouter
    
    # Create instances
    ollama_config = config.get("ollama", {})
    ai_client = FallbackClient(
        ollama_base_url=ollama_config.get("base_url", "http://localhost:11434/api"),
        ollama_default_model=config.get("default_model", "qwen2.5-coder:latest"),
        timeout_seconds=ollama_config.get("timeout_seconds", 240),
        keep_alive=ollama_config.get("keep_alive", "10m"),
        default_options=ollama_config.get("options", {}),
    )
    
    cache_directory = base_dir / config.get("cache", {}).get("directory", "db/cache")
    cache = SmartCodeCache(
        directory=cache_directory,
        max_size_mb=config.get("cache", {}).get("max_size_mb", 1024),
        max_entries=config.get("cache", {}).get("max_entries", 500),
        default_ttl_hours=int(config.get("cache", {}).get("ttl_hours", 24)),
        compression_threshold_bytes=config.get("cache", {}).get("compression_threshold", 1024),
        enable_compression=config.get("cache", {}).get("enable_compression", True),
    )
    
    history_path = base_dir / config.get("history", {}).get("database_path", "db/history.db")
    history = HistoryStore(history_path)
    
    classifier = ProblemClassifier(ai_client)
    reasoner = ProblemReasoner(ai_client)
    coder = CodeGenerator(ai_client)
    validator = SolutionValidator()
    
    export_directory = config.get("export", {}).get("directory", "exports")
    exporter = SolutionExporter(base_dir, export_directory)
    
    optimizer = TokenOptimizer(
        max_context_tokens=config.get("optimization", {}).get("max_context_tokens", 8000)
    )
    
    router = IntelligentModelRouter(config=config.get("model_routing", {}))
    
    return CodeSolverV2(
        base_dir=base_dir,
        config=config,
        ai_client=ai_client,
        cache=cache,
        history=history,
        classifier=classifier,
        reasoner=reasoner,
        coder=coder,
        validator=validator,
        exporter=exporter,
        optimizer=optimizer,
        router=router,
    )
