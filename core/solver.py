from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from core.cache import HistoryStore, SolverCache
from core.classifier import ProblemClassifier
from core.coder import CodeGenerationError, CodeGenerator
from core.reasoner import ProblemReasoner
from core.validator import SolutionValidator
from models.ollama_client import OllamaClient
from utils.markdown import render_solution_markdown


@dataclass
class ContextItem:
    name: str
    content: str


@dataclass
class SolveRequest:
    problem: str
    language: str = "python"
    model: str | None = None
    mode: str = "fast"
    context_items: list[ContextItem] = field(default_factory=list)
    use_cache: bool = True
    auto_repair: bool = True


@dataclass
class SolveResult:
    problem: str
    classification: str
    complexity: int
    labels: list[str]
    language: str
    model: str
    mode: str
    understanding: str
    plan_steps: list[str]
    constraints: list[str]
    risks: list[str]
    success_criteria: list[str]
    code: str
    tests: str
    filename: str
    test_filename: str
    explanation: list[str]
    validation: dict[str, Any]
    markdown: str
    similar_context: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    cached: bool = False
    history_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SolveResult":
        return cls(**payload)


class CodeSolver:
    def __init__(
        self,
        base_dir: Path,
        config: dict[str, Any],
        client: OllamaClient | None = None,
    ) -> None:
        self.base_dir = Path(base_dir)
        self.config = config
        self.default_model = config.get("default_model", "qwen2.5-coder:latest")
        self.supported_languages = config.get(
            "supported_languages",
            ["python", "javascript", "typescript", "java", "go", "rust"],
        )
        self.export_directory = config.get("export", {}).get("directory", "exports")

        ollama_config = config.get("ollama", {})
        self.client = client or OllamaClient(
            base_url=ollama_config.get("base_url", "http://localhost:11434/api"),
            default_model=self.default_model,
            timeout_seconds=ollama_config.get("timeout_seconds", 240),
            keep_alive=ollama_config.get("keep_alive", "10m"),
            default_options=ollama_config.get("options", {}),
        )

        cache_directory = self._resolve_path(config.get("cache", {}).get("directory", "db/cache"))
        history_path = self._resolve_path(config.get("history", {}).get("database_path", "db/history.db"))
        self.cache_enabled = bool(config.get("cache", {}).get("enabled", True))
        self.similar_results = int(config.get("history", {}).get("similar_results", 3))

        self.cache = SolverCache(cache_directory)
        self.history = HistoryStore(history_path)
        self.classifier = ProblemClassifier(self.client)
        self.reasoner = ProblemReasoner(self.client)
        self.coder = CodeGenerator(self.client)
        self.validator = SolutionValidator()
        self._installed_models_cache: list[str] | None = None

    @classmethod
    def from_config(cls, config_path: Path) -> "CodeSolver":
        config_file = Path(config_path)
        import yaml

        config = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        return cls(base_dir=config_file.parent, config=config)

    def available_models(self) -> list[str]:
        configured = list(dict.fromkeys(self.config.get("preferred_models", []) + [self.default_model]))
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

        context_text = self._render_context_items(request.context_items)
        cache_key = self.cache.build_key(problem, language, model, mode, context_text)
        if request.use_cache and self.cache_enabled:
            cached_payload = self.cache.get(cache_key)
            if cached_payload:
                cached_payload["cached"] = True
                return SolveResult.from_dict(cached_payload)

        similar_context = self.history.find_similar(
            problem=problem,
            language=language,
            limit=self.similar_results,
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
            raise RuntimeError(
                "Falha ao gerar uma solução executável. "
                "Tente usar um modelo maior, ativar `--mode deep` ou enviar mais contexto. "
                f"Detalhe: {exc}"
            ) from exc

        validation = self.validator.validate(
            language=language,
            code=solution["code"],
            tests=solution["tests"],
            filename=solution["filename"],
            test_filename=solution["test_filename"],
        )

        repair_applied = False
        if request.auto_repair and validation.get("status") == "failed":
            repaired_solution = self.coder.repair(
                problem=problem,
                language=language,
                previous_solution=solution,
                validation=validation,
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

        metadata = {
            "classification_reason": classification.get("why", ""),
            "generated_at": datetime.utcnow().isoformat() + "Z",
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

    def export_result(
        self,
        result: SolveResult,
        export_root: Path | None = None,
        slug: str | None = None,
    ) -> dict[str, str]:
        export_base = export_root or self._resolve_path(self.export_directory)
        export_base.mkdir(parents=True, exist_ok=True)
        safe_slug = slug or self._slugify(result.classification + "-" + result.problem[:40])
        output_dir = export_base / f"{safe_slug}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        output_dir.mkdir(parents=True, exist_ok=True)

        markdown_path = output_dir / "solution.md"
        code_path = output_dir / result.filename
        tests_path = output_dir / result.test_filename
        metadata_path = output_dir / "metadata.json"

        markdown_path.write_text(result.markdown, encoding="utf-8")
        code_path.write_text(result.code, encoding="utf-8")
        tests_path.write_text(result.tests, encoding="utf-8")
        metadata_path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return {
            "output_dir": str(output_dir),
            "markdown": str(markdown_path),
            "code": str(code_path),
            "tests": str(tests_path),
            "metadata": str(metadata_path),
        }

    def parse_batch_text(self, text: str) -> list[str]:
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
        bullet_pattern = re.compile(r"^(?:[-*•]|\d+[.)])\s+")
        if len(lines) > 1 and all(bullet_pattern.match(line) for line in lines):
            return [
                self._clean_batch_item(bullet_pattern.sub("", line, count=1))
                for line in lines
                if self._clean_batch_item(bullet_pattern.sub("", line, count=1))
            ]

        cleaned = self._clean_batch_item(raw)
        return [cleaned] if cleaned else []

    def _resolve_path(self, relative_path: str) -> Path:
        return (self.base_dir / relative_path).resolve()

    def _build_model_options(self, mode: str) -> dict[str, Any]:
        base_options = dict(self.config.get("ollama", {}).get("options", {}))
        profile = dict(self.config.get("profiles", {}).get(mode, {}))
        profile.pop("reasoning_style", None)
        base_options.update(profile)
        return base_options

    def _render_context_items(self, items: list[ContextItem]) -> str:
        if not items:
            return ""
        sections: list[str] = []
        for item in items:
            sections.append(f"### {item.name}\n{item.content.strip()}")
        return "\n\n".join(sections).strip()

    def _slugify(self, text: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
        return slug[:50] or "solution"

    def _resolve_model(self, requested_model: str | None) -> tuple[str, dict[str, Any]]:
        installed, lookup_error = self._get_installed_models()
        metadata = {
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
        if self.default_model in installed:
            metadata["resolved_model"] = self.default_model
            return self.default_model, metadata

        preferred = self.config.get("preferred_models", [])
        for candidate in preferred:
            if candidate in installed:
                metadata["resolved_model"] = candidate
                metadata["fallback_used"] = True
                return candidate, metadata

        metadata["resolved_model"] = installed[0]
        metadata["fallback_used"] = True
        return installed[0], metadata

    def _get_installed_models(self, refresh: bool = False) -> tuple[list[str], Exception | None]:
        if self._installed_models_cache is not None and not refresh:
            return self._installed_models_cache, None
        try:
            installed = self.client.list_models()
        except Exception as exc:
            return [], exc
        self._installed_models_cache = installed
        return installed, None

    def _clean_batch_item(self, text: str) -> str:
        return text.strip().strip("#").strip()
