"""Pipeline implementation for Code Solver AI.

Fonte canônica da classe CodeSolver.
Dataclasses vivem em core.models e são re-exportadas aqui por conveniência.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.cache import HistoryStore, SolverCache
from core.classifier import ProblemClassifier
from core.coder import CodeGenerationError, CodeGenerator
from core.reasoner import ProblemReasoner
from core.exporter import SolutionExporter
from core.models import ContextItem, SolveRequest, SolveResult
from core.types import SolveMetadata, ValidationResult
from core.validator import SolutionValidator
from models.ollama_client import OllamaClient
from utils.logger import get_logger, log_pipeline_stage, log_error
from utils.markdown import render_solution_markdown


__all__ = ["CodeSolver", "ContextItem", "SolveRequest", "SolveResult"]


class CodeSolver:
    """Main code solving pipeline orchestrator."""

    def __init__(
        self,
        base_dir: Path,
        config: dict[str, Any],
        client: OllamaClient | None = None,
    ) -> None:
        self.base_dir = Path(base_dir)
        self.config = config
        self.default_model = config.get(
            "default_model", "qwen2.5-coder:latest")
        self.supported_languages = config.get(
            "supported_languages",
            ["python", "javascript", "typescript", "java", "go", "rust"],
        )
        self.export_directory = config.get(
            "export", {}).get("directory", "exports")

        ollama_config = config.get("ollama", {})
        self.client = client or OllamaClient(
            base_url=ollama_config.get(
                "base_url", "http://localhost:11434/api"),
            default_model=self.default_model,
            timeout_seconds=ollama_config.get("timeout_seconds", 240),
            keep_alive=ollama_config.get("keep_alive", "10m"),
            default_options=ollama_config.get("options", {}),
        )

        cache_directory = self._resolve_path(
            config.get("cache", {}).get("directory", "db/cache"))
        history_path = self._resolve_path(config.get(
            "history", {}).get("database_path", "db/history.db"))
        self.cache_enabled = bool(config.get("cache", {}).get("enabled", True))
        self.similar_results = int(config.get(
            "history", {}).get("similar_results", 3))
        cache_ttl_hours = int(config.get("cache", {}).get("ttl_hours", 24))

        self.cache = SolverCache(cache_directory, ttl_hours=cache_ttl_hours)
        self.history = HistoryStore(history_path)
        self.classifier = ProblemClassifier(self.client)
        self.reasoner = ProblemReasoner(self.client)
        self.coder = CodeGenerator(self.client)
        self.validator = SolutionValidator()
        self.exporter = SolutionExporter(self.base_dir, self.export_directory)
        self._installed_models_cache: list[str] | None = None
        self.logger = get_logger("code_solver")

    @classmethod
    def from_config(cls, config_path: Path) -> "CodeSolver":
        config_file = Path(config_path)
        import yaml

        config = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        return cls(base_dir=config_file.parent, config=config)

    def available_models(self) -> list[str]:
        configured = list(dict.fromkeys(self.config.get(
            "preferred_models", []) + [self.default_model]))
        discovered, _ = self._get_installed_models(refresh=True)
        return discovered or configured

    def solve(self, request: SolveRequest) -> SolveResult:
        problem = request.problem.strip()
        if not problem:
            raise ValueError("O problema não pode estar vazio.")

        # Check cache first
        cache_key = None
        if request.use_cache and self.cache_enabled:
            cache_key = self.cache.build_key(
                problem=problem,
                language=request.language,
                model=request.model or self.default_model,
                mode=request.mode,
                context_text=self._format_context_items(request.context_items),
            )
            cached_result = self.cache.get(cache_key)
            if cached_result:
                self.logger.info(f"Cache hit for problem: {problem[:50]}...")
                return SolveResult.from_dict(cached_result)

        # Start pipeline
        started_at = datetime.now(timezone.utc)
        log_pipeline_stage(self.logger, "classify", problem,
                           {"language": request.language})

        # Step 1: Classify problem
        classification_result = self.classifier.classify(
            problem=problem,
            language_hint=request.language,
            context_text=self._format_context_items(request.context_items),
            similar_context=self.history.find_similar(
                problem, limit=self.similar_results),
            model=request.model or self.default_model,
            options=self._build_model_options(request.mode),
        )
        classification = classification_result.get("classification", "")
        complexity = classification_result.get("complexity", 1)
        labels = classification_result.get("labels", [])

        # Step 2: Generate reasoning
        log_pipeline_stage(self.logger, "reason", problem,
                           {"language": request.language})
        # Generate basic understanding first
        basic_understanding = f"Problem: {problem}\nClassification: {classification}\nComplexity: {complexity}"
        reasoning_result = self.reasoner.analyze(
            problem=problem,
            classification=classification,
            complexity=complexity,
            language=request.language,
            understanding=basic_understanding,
            context_text=self._format_context_items(request.context_items),
            similar_context=self.history.find_similar(
                problem, limit=self.similar_results),
            model=request.model or self.default_model,
            options=self._build_model_options(request.mode),
        )
        understanding = reasoning_result.get("understanding", "")
        plan_steps = reasoning_result.get("plan_steps", [])
        constraints = reasoning_result.get("constraints", [])
        risks = reasoning_result.get("risks", [])
        success_criteria = reasoning_result.get("success_criteria", [])

        # Step 3: Generate code
        log_pipeline_stage(self.logger, "generate", problem,
                           {"language": request.language})
        try:
            generation_result = self.coder.generate(
                problem=problem,
                classification=classification,
                language=request.language,
                understanding=understanding,
                plan_steps=plan_steps,
                constraints=constraints,
                risks=risks,
                success_criteria=success_criteria,
                context_text=self._format_context_items(request.context_items),
                similar_context=self.history.find_similar(
                    problem, limit=self.similar_results),
                model=request.model or self._resolve_model(request.model)[0],
                mode=request.mode,
                options=self._build_model_options(request.mode),
            )
            code = generation_result.get("code", "")
            tests = generation_result.get("tests", "")
            filename = generation_result.get(
                "filename", f"solution.{self._get_file_extension(request.language)}")
            test_filename = generation_result.get(
                "test_filename", f"test_solution.{self._get_file_extension(request.language)}")
        except CodeGenerationError as e:
            self.logger.error(f"Code generation failed: {e}")
            raise

        # Step 4: Validate solution
        log_pipeline_stage(self.logger, "validate", problem,
                           {"language": request.language})
        validation = self.validator.validate(
            language=request.language,
            code=code,
            tests=tests,
            filename=filename,
            test_filename=test_filename,
        )

        # Step 5: Generate explanation and markdown
        explanation = self._generate_explanation(
            problem, classification, understanding, plan_steps, constraints,
            risks, success_criteria, code, tests, validation, request.language
        )

        # Prepare result dict for markdown rendering
        result_dict = {
            "problem": problem,
            "classification": classification,
            "complexity": complexity,
            "labels": labels,
            "model": request.model or self.default_model,
            "mode": request.mode,
            "understanding": understanding,
            "plan_steps": plan_steps,
            "constraints": constraints,
            "risks": risks,
            "success_criteria": success_criteria,
            "code": code,
            "tests": tests,
            "explanation": explanation,
            "validation": validation,
            "language": request.language,
            "filename": filename,
            "test_filename": test_filename,
            "similar_context": [],
            "metadata": {},
        }
        markdown = render_solution_markdown(result_dict)

        # Create result
        finished_at = datetime.now(timezone.utc)
        metadata: SolveMetadata = {
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": (finished_at - started_at).total_seconds(),
            "ollama_url": getattr(self.client, 'base_url', 'http://localhost:11434/api'),
            "cache_hit": False,
        }

        result = SolveResult(
            problem=problem,
            classification=classification,
            complexity=complexity,
            labels=labels,
            language=request.language,
            model=request.model or self.default_model,
            mode=request.mode,
            understanding=understanding,
            plan_steps=plan_steps,
            constraints=constraints,
            risks=risks,
            success_criteria=success_criteria,
            code=code,
            tests=tests,
            filename=filename,
            test_filename=test_filename,
            explanation=explanation,
            validation=validation,
            markdown=markdown,
            similar_context=self.history.find_similar(
                problem, limit=self.similar_results),
            metadata=metadata,
            cached=False,
        )

        # Store in cache
        if request.use_cache and self.cache_enabled:
            self.cache.set(cache_key, result.to_dict())

        # Store in history
        history_payload = {
            "problem": problem,
            "classification": classification,
            "complexity": complexity,
            "labels": labels,
            "understanding": understanding,
            "plan_steps": plan_steps,
            "constraints": constraints,
            "risks": risks,
            "success_criteria": success_criteria,
            "code": code,
            "tests": tests,
            "language": request.language,
            "validation": validation,
            "explanation": explanation,
            "model": request.model or self.default_model,
            "mode": request.mode,
            "markdown": markdown,
            "metadata": metadata,
        }
        history_id = self.history.save_result(history_payload)
        result.history_id = history_id

        # Auto-repair if needed
        if request.auto_repair and validation["status"] == "failed":
            self.logger.info("Attempting auto-repair...")
            try:
                repaired_result = self._auto_repair(result, request)
                if repaired_result.validation["status"] == "passed":
                    self.logger.info("Auto-repair successful!")
                    result = repaired_result
                    if request.use_cache and self.cache_enabled:
                        self.cache.set(cache_key, result.to_dict())
                else:
                    self.logger.warning(
                        "Auto-repair failed, returning original result")
            except Exception as e:
                self.logger.error(f"Auto-repair failed: {e}")

        return result

    def solve_batch(self, problems: list[str], template: SolveRequest) -> list[SolveResult]:
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

    def _generate_explanation(
        self,
        problem: str,
        classification: str,
        understanding: str,
        plan_steps: list[str],
        constraints: list[str],
        risks: list[str],
        success_criteria: list[str],
        code: str,
        tests: str,
        validation: ValidationResult,
        language: str,
    ) -> list[str]:
        """Generate explanation for the solution."""
        explanation = []

        explanation.append(f"## Problema")
        explanation.append(f"{problem}")

        explanation.append(f"## Classificação")
        explanation.append(f"**Tipo:** {classification}")
        explanation.append(f"**Complexidade:** {len(classification.split())}")

        explanation.append(f"## Entendimento")
        explanation.append(f"{understanding}")

        if plan_steps:
            explanation.append(f"## Plano de Solução")
            for i, step in enumerate(plan_steps, 1):
                explanation.append(f"{i}. {step}")

        if constraints:
            explanation.append(f"## Restrições")
            for constraint in constraints:
                explanation.append(f"- {constraint}")

        if risks:
            explanation.append(f"## Riscos")
            for risk in risks:
                explanation.append(f"- {risk}")

        if success_criteria:
            explanation.append(f"## Critérios de Sucesso")
            for criterion in success_criteria:
                explanation.append(f"- {criterion}")

        explanation.append(f"## Implementação em {language.title()}")
        explanation.append(
            f"O código foi implementado seguindo as boas práticas para {language}.")

        if validation["status"] == "passed":
            explanation.append(f"## Validação")
            explanation.append(f"✅ A solução foi validada com sucesso.")
        else:
            explanation.append(f"## Validação")
            explanation.append(
                f"❌ A solução apresentou problemas na validação:")
            explanation.append(f"{validation['notes']}")

        return explanation

    def _auto_repair(self, result: SolveResult, request: SolveRequest) -> SolveRequest:
        """Attempt to automatically repair a failed solution."""
        try:
            repair_prompt = f"""
            A seguinte solução para o problema "{result.problem}" falhou na validação.
            
            Erros encontrados:
            {result.validation['notes']}
            
            Por favor, corrija o código para resolver esses problemas mantendo a mesma estrutura.
            
            Código atual:
            ```{result.language}
            {result.code}
            ```
            
            Testes atuais:
            ```{result.language}
            {result.tests}
            ```
            """

            repaired_code, repaired_tests, _, _ = self.coder.generate(
                problem=repair_prompt,
                language=result.language,
                classification=result.classification,
                complexity=result.complexity,
                understanding=result.understanding,
                plan_steps=result.plan_steps,
                constraints=result.constraints,
                risks=result.risks,
                success_criteria=result.success_criteria,
                mode="repair",
                context_items=request.context_items,
                model=request.model or self._resolve_model(request.model)[0],
            )

            # Validate repaired solution
            repaired_validation = self.validator.validate(
                language=result.language,
                code=repaired_code,
                tests=repaired_tests,
                filename=result.filename,
                test_filename=result.test_filename,
            )

            # Create repaired result
            repaired_result = SolveResult(
                problem=result.problem,
                classification=result.classification,
                complexity=result.complexity,
                labels=result.labels,
                language=result.language,
                model=result.model,
                mode="repair",
                understanding=result.understanding,
                plan_steps=result.plan_steps,
                constraints=result.constraints,
                risks=result.risks,
                success_criteria=result.success_criteria,
                code=repaired_code,
                tests=repaired_tests,
                filename=result.filename,
                test_filename=result.test_filename,
                explanation=result.explanation,
                validation=repaired_validation,
                markdown=render_solution_markdown(
                    problem=result.problem,
                    classification=result.classification,
                    complexity=result.complexity,
                    understanding=result.understanding,
                    plan_steps=result.plan_steps,
                    constraints=result.constraints,
                    risks=result.risks,
                    success_criteria=result.success_criteria,
                    code=repaired_code,
                    tests=repaired_tests,
                    explanation=result.explanation,
                    validation=repaired_validation,
                    language=result.language,
                    filename=result.filename,
                    test_filename=result.test_filename,
                ),
                similar_context=result.similar_context,
                metadata=result.metadata,
                cached=False,
            )

            return repaired_result

        except Exception as e:
            self.logger.error(f"Auto-repair failed: {e}")
            return result

    def _get_installed_models(self, refresh: bool = False) -> tuple[list[str], str | None]:
        """Get list of installed models from Ollama."""
        if self._installed_models_cache is not None and not refresh:
            return self._installed_models_cache, None

        try:
            models = self.client.list_models()
            model_names = [model["name"] for model in models]
            self._installed_models_cache = model_names
            return model_names, None
        except Exception as e:
            self.logger.warning(f"Failed to get installed models: {e}")
            return [], str(e)

    def _resolve_model(self, requested_model: str | None) -> tuple[str, dict[str, Any]]:
        """Resolve the model to use, falling back to available models."""
        installed, lookup_error = self._get_installed_models()
        metadata = {
            "requested_model": requested_model,
            "default_model": self.default_model,
            "installed_models": installed,
            "lookup_error": lookup_error,
        }

        if requested_model:
            if requested_model in installed:
                return requested_model, metadata
            else:
                self.logger.warning(
                    f"Requested model '{requested_model}' not found in installed models: {installed}"
                )

        # Try default model
        if self.default_model in installed:
            return self.default_model, metadata

        # Fall back to first available model
        if installed:
            fallback = installed[0]
            self.logger.warning(
                f"Default model '{self.default_model}' not found, using fallback: {fallback}"
            )
            return fallback, metadata

        # No models available
        error_msg = f"No models available. Requested: {requested_model}, Default: {self.default_model}"
        if lookup_error:
            error_msg += f", Lookup error: {lookup_error}"
        raise ValueError(error_msg)

    def _resolve_path(self, relative_path: str) -> Path:
        return (self.base_dir / relative_path).resolve()

    def _build_model_options(self, mode: str) -> dict[str, Any]:
        base_options = dict(self.config.get("ollama", {}).get("options", {}))
        profile = dict(self.config.get("profiles", {}).get(mode, {}))
        profile.pop("reasoning_style", None)  # Handle separately
        return {**base_options, **profile}

    def _format_context_items(self, context_items: list[Any]) -> list[str]:
        """Format context items for prompt inclusion."""
        sections = []
        for item in context_items:
            sections.append(f"### {item.name}\n{item.content.strip()}")
        return "\n\n".join(sections).strip()

    def _get_file_extension(self, language: str) -> str:
        """Get file extension for programming language."""
        extensions = {
            "python": "py",
            "javascript": "js",
            "typescript": "ts",
            "java": "java",
            "go": "go",
            "rust": "rs",
            "cpp": "cpp",
            "c++": "cpp",
            "ruby": "rb",
            "php": "php",
        }
        return extensions.get(language.lower(), "txt")

    def parse_batch_text(self, text: str) -> list[str]:
        """Parse batch text into individual problems."""
        return self.exporter.parse_batch_text(text)

    def export_result(
        self,
        result: SolveResult,
        export_root: Path | None = None,
        slug: str | None = None,
        max_exports: int = 20,
    ) -> dict[str, str]:
        """Export solution result to files."""
        return self.exporter.export_result(result, export_root, slug, max_exports)
