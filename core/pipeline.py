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
from models.fallback_client import FallbackClient
from utils.logger import get_logger, log_pipeline_stage, log_error
from utils.markdown import render_solution_markdown


__all__ = ["CodeSolver", "ContextItem", "SolveRequest", "SolveResult"]


class CodeSolver:
    """Main code solving pipeline orchestrator."""

    def __init__(
        self,
        base_dir: Path,
        config: dict[str, Any],
        client: FallbackClient | None = None,
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
        self.client = client or FallbackClient(
            ollama_base_url=ollama_config.get(
                "base_url", "http://localhost:11434/api"),
            ollama_default_model=self.default_model,
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
        if discovered:
            return discovered
        return configured

    def solve(self, request: SolveRequest) -> SolveResult:
        problem = request.problem.strip()
        if not problem:
            raise ValueError("O problema não pode estar vazio.")

        language = (request.language or "python").strip().lower()
        if language not in self.supported_languages:
            language = "python"
        mode = request.mode if request.mode in {"fast", "deep"} else "fast"
        model, model_resolution = self._resolve_model(request.model)

        log_pipeline_stage(
            self.logger, "solve", "started",
            details={
                "problem_length": len(problem),
                "language": language,
                "model": model,
                "mode": mode,
                "cache_enabled": request.use_cache and self.cache_enabled,
                "context_items": len(request.context_items),
            },
        )

        context_text = self._format_context_items(request.context_items)
        cache_key = self.cache.build_key(
            problem, language, model, mode, context_text)
        if request.use_cache and self.cache_enabled:
            cached_payload = self.cache.get(cache_key)
            if cached_payload:
                log_pipeline_stage(
                    self.logger, "solve", "cache_hit",
                    details={"cache_key": cache_key[:50] + "..."},
                )
                cached_payload["cached"] = True
                return SolveResult.from_dict(cached_payload)

        similar_context = self.history.find_similar(
            problem=problem, language=language, limit=self.similar_results,
        )
        options = self._build_model_options(mode)

        classification = self.classifier.classify(
            problem=problem,
            language_hint=language,
            context_text=context_text,
            similar_context=similar_context,
            model=model,
            options=options,
        )
        language = classification.get("language", language)

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
        except CodeGenerationError as exc:
            generation_error = exc
            solution = {
                "filename": "solution.py",
                "test_filename": "test_solution.py",
                "code": "",
                "tests": "",
                "explanation": [f"Generation failed: {str(exc)}"],
                "notes": ["Auto-repair will be attempted"],
            }

        validation = self.validator.validate(
            language=language,
            code=solution["code"],
            tests=solution["tests"],
            filename=solution["filename"],
            test_filename=solution["test_filename"],
        )

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

        metadata = {
            "classification_reason": classification.get("why", ""),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "repair_applied": repair_applied,
            "context_files": [item.name for item in request.context_items],
            "similar_context_count": len(similar_context),
            "default_model_requested": request.model is None,
            "configured_default_model": self.default_model,
            "model_resolution": model_resolution,
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

        payload = result.to_dict()
        history_id = self.history.save_result(payload)
        result.history_id = history_id
        payload["history_id"] = history_id
        if request.use_cache and self.cache_enabled:
            self.cache.set(cache_key, payload)
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

    def _get_installed_models(self, refresh: bool = False) -> tuple[list[str], Exception | None]:
        """Get list of installed models from Ollama."""
        if self._installed_models_cache is not None and not refresh:
            return self._installed_models_cache, None

        try:
            models = self.client.list_models()
            # Handle both string list and dict list formats
            if models and isinstance(models[0], str):
                # Fake client returns simple strings
                model_names = models
            else:
                # Real Ollama API returns objects with "name" field
                model_names = [model["name"] for model in models]
            self._installed_models_cache = model_names
            return model_names, None
        except Exception as e:
            self.logger.warning(f"Failed to get installed models: {e}")
            return [], e

    def _resolve_model(self, requested_model: str | None) -> tuple[str, dict[str, Any]]:
        """Resolve the model to use, falling back to available models."""
        installed, lookup_error = self._get_installed_models()
        metadata: dict[str, Any] = {
            "requested_model": requested_model,
            "configured_default_model": self.default_model,
            "resolved_model": None,
            "fallback_used": False,
            "lookup_error": str(lookup_error) if lookup_error else "",
            "available_models": installed,
        }

        if requested_model:
            if installed and requested_model not in installed:
                raise ValueError(
                    f"Modelo solicitado '{requested_model}' não está instalado no Ollama. "
                    f"Disponíveis: {', '.join(installed)}"
                )
            metadata["resolved_model"] = requested_model
            return requested_model, metadata

        if not installed:
            metadata["resolved_model"] = self.default_model
            return self.default_model, metadata

        # Check if default model is installed
        if self.default_model in installed:
            metadata["resolved_model"] = self.default_model
            return self.default_model, metadata

        # Try preferred models in order
        preferred = self.config.get("preferred_models", [])
        for candidate in preferred:
            if candidate in installed:
                metadata["resolved_model"] = candidate
                metadata["fallback_used"] = True
                return candidate, metadata

        # Fall back to first available model
        metadata["resolved_model"] = installed[0]
        metadata["fallback_used"] = True
        return installed[0], metadata

    def _resolve_path(self, relative_path: str) -> Path:
        return (self.base_dir / relative_path).resolve()

    def _build_model_options(self, mode: str) -> dict[str, Any]:
        base_options = dict(self.config.get("ollama", {}).get("options", {}))
        profile = dict(self.config.get("profiles", {}).get(mode, {}))
        profile.pop("reasoning_style", None)  # Handle separately
        return {**base_options, **profile}

    def _format_context_items(self, context_items: list[ContextItem]) -> str:
        """Format context items for prompt inclusion."""
        if not context_items:
            return ""
        sections: list[str] = []
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
        raw = text.replace("\ufeff", "").replace("\r\n", "\n").strip()
        if not raw:
            return []

        parts = [
            self._clean_batch_item(part)
            for part in re.split(r"(?m)^\s*---\s*$", raw)
            if part.strip()
        ]
        if len(parts) > 1:
            return [part for part in parts if part]

        paragraphs = [
            self._clean_batch_item(part)
            for part in re.split(r"\n\s*\n", raw)
            if part.strip()
        ]
        if len(paragraphs) > 1:
            return [part for part in paragraphs if part]

        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        bullet_pattern = re.compile(r"^(?:[-*•]|\d+[.)]) +")
        if len(lines) > 1 and all(bullet_pattern.match(line) for line in lines):
            return [
                self._clean_batch_item(bullet_pattern.sub("", line, count=1))
                for line in lines
                if self._clean_batch_item(bullet_pattern.sub("", line, count=1))
            ]

        cleaned = self._clean_batch_item(raw)
        return [cleaned] if cleaned else []

    def _clean_batch_item(self, text: str) -> str:
        """Clean individual batch item by removing extra markers."""
        return text.strip().strip("#").strip()

    def export_result(
        self,
        result: SolveResult,
        export_root: Path | None = None,
        slug: str | None = None,
        max_exports: int = 20,
    ) -> dict[str, str]:
        """Export solution result to files."""
        return self.exporter.export_result(result, export_root, slug, max_exports)
