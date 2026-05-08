"""Módulo de reparo automático de código usando padrão Strategy.

Recebe código com erro e traceback, consulta Ollama via code-solver-engine 
para propor correção e valida com sandbox-validator seguindo princípios SOLID.
"""

from __future__ import annotations
import time

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Union

from models.ollama_client import OllamaClient, OllamaError
from utils.executor_v2 import EnhancedExecutor, ExecutionResult, ExecutionStatus, create_executor
from utils.logger import get_logger


class RepairStatus(Enum):
    """Status do processo de reparo."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    REPAIRING = "repairing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RepairConfidence(Enum):
    """Nível de confiança no reparo proposto."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass(frozen=True)
class ErrorContext:
    """Contexto do erro para análise."""
    code: str
    error_message: str
    traceback: str
    language: str
    file_path: Optional[Path] = None
    line_number: Optional[int] = None
    error_type: Optional[str] = None
    additional_context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário serializável."""
        result = asdict(self)
        if self.file_path:
            result['file_path'] = str(self.file_path)
        return result


@dataclass(frozen=True)
class RepairProposal:
    """Proposta de reparo gerada pela estratégia."""
    original_code: str
    repaired_code: str
    confidence: RepairConfidence
    reasoning: str
    changes_made: List[str]
    risk_assessment: str
    estimated_success_rate: float  # 0.0 a 1.0
    validation_strategy: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário serializável."""
        result = asdict(self)
        result['confidence'] = self.confidence.value
        return result


@dataclass(frozen=True)
class RepairResult:
    """Resultado final do processo de reparo."""
    status: RepairStatus
    original_code: str
    final_code: str
    proposal: Optional[RepairProposal]
    validation_result: Optional[ExecutionResult]
    error_message: Optional[str]
    execution_time_seconds: float
    attempts_made: int
    success: bool
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário serializável."""
        result = asdict(self)
        result['status'] = self.status.value
        if self.proposal:
            result['proposal'] = self.proposal.to_dict()
        if self.validation_result:
            result['validation_result'] = asdict(self.validation_result)
            result['validation_result']['status'] = self.validation_result.status.value
        return result


class RepairStrategy(Protocol):
    """Interface Strategy para diferentes estratégias de reparo."""

    def analyze_error(self, error_context: ErrorContext) -> RepairProposal:
        """Analisa o erro e propõe uma correção."""
        ...

    def validate_proposal(self, proposal: RepairProposal,
                          executor: EnhancedExecutor) -> ExecutionResult:
        """Valida se a proposta de reparo resolve o erro."""
        ...

    def can_handle(self, error_context: ErrorContext) -> bool:
        """Verifica se esta estratégia pode lidar com o erro."""
        ...


class BaseRepairStrategy(ABC):
    """Classe base abstrata para estratégias de reparo."""

    def __init__(self, name: str, logger_name: str = "repair_strategy") -> None:
        self.name = name
        self.logger = get_logger(logger_name)
        self._setup_patterns()

    @abstractmethod
    def _setup_patterns(self) -> None:
        """Configura padrões específicos da estratégia."""
        ...

    @abstractmethod
    def analyze_error(self, error_context: ErrorContext) -> RepairProposal:
        """Analisa o erro e propõe uma correção."""
        ...

    def validate_proposal(self, proposal: RepairProposal,
                          executor: EnhancedExecutor) -> ExecutionResult:
        """Validação padrão da proposta."""
        try:
            # Cria arquivo temporário com código reparado
            temp_file = Path("temp_repair.py")
            temp_file.write_text(proposal.repaired_code, encoding='utf-8')

            # Executa validação básica
            result = executor.execute(
                command=["python", str(temp_file)],
                working_directory=temp_file.parent,
                timeout_seconds=10
            )

            # Limpa arquivo temporário
            temp_file.unlink(missing_ok=True)

            return result

        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            return ExecutionResult(
                command=["python", str(temp_file)],
                returncode=1,
                stdout="",
                stderr=f"Validation error: {str(e)}",
                status=ExecutionStatus.ERROR,
                duration_seconds=0.0,
                timeout_seconds=10,
                working_directory=Path.cwd(),
                security_violations=[],
                metadata={"validation_error": str(e)}
            )

    def can_handle(self, error_context: ErrorContext) -> bool:
        """Validação base - pode ser sobrescrita."""
        return bool(error_context.error_message and error_context.code)


class OllamaRepairStrategy(BaseRepairStrategy):
    """Estratégia de reparo usando Ollama com IA."""

    def __init__(self, ollama_client: OllamaClient, model: Optional[str] = None,
                 max_attempts: int = 3) -> None:
        self.client = ollama_client
        self.model = model or ollama_client.default_model
        self.max_attempts = max_attempts
        super().__init__(name="ollama_repair", logger_name="ollama_repair")

    def _setup_patterns(self) -> None:
        """Configura prompts e padrões para análise."""
        self.system_prompt = """You are an expert code debugger and repair specialist. 
Your task is to analyze code with errors and propose precise fixes.

Analyze the provided error context and generate a repair proposal with:
1. **Root Cause Analysis**: Identify the exact cause of the error
2. **Precise Fix**: Provide corrected code that resolves the issue
3. **Confidence Assessment**: Rate your confidence (very_low, low, medium, high, very_high)
4. **Risk Assessment**: Evaluate potential side effects of the fix
5. **Success Estimation**: Provide estimated success rate (0.0-1.0)

Guidelines:
- Preserve the original code structure and logic
- Fix only the identified error, don't over-engineer
- Explain your reasoning clearly
- Consider edge cases and potential side effects
- Return ONLY the fixed code, no explanations in the code block

Respond in JSON format with:
{
  "analysis": "detailed error analysis",
  "root_cause": "specific cause of error",
  "repaired_code": "complete fixed code",
  "confidence": "confidence_level",
  "changes_made": ["list", "of", "changes"],
  "risk_assessment": "risk evaluation",
  "estimated_success_rate": 0.85,
  "validation_notes": "how to validate the fix"
}"""

        self.user_prompt_template = """Analyze and repair this code error:

**Language**: {language}
**File**: {file_path}
**Error**: {error_message}
**Error Type**: {error_type}
**Line**: {line_number}

**Traceback**:
```
{traceback}
```

**Original Code**:
```{language}
{code}
```

**Additional Context**:
{additional_context}

Provide a repair proposal following the JSON format specified in the system prompt."""

    def can_handle(self, error_context: ErrorContext) -> bool:
        """Verifica se pode lidar com o erro."""
        if not super().can_handle(error_context):
            return False

        # Verifica se há suporte para a linguagem
        supported_languages = ["python", "javascript", "java", "cpp", "c"]
        return error_context.language.lower() in supported_languages

    def analyze_error(self, error_context: ErrorContext) -> RepairProposal:
        """Analisa erro usando Ollama e propõe reparo."""
        try:
            # Constrói prompt
            user_prompt = self._build_prompt(error_context)

            # Chama Ollama em modo JSON
            response = self.client.generate_json(
                system_prompt=self.system_prompt,
                user_prompt=user_prompt,
                model=self.model
            )

            # Processa resposta
            return self._parse_ollama_response(error_context, response)

        except OllamaError as e:
            self.logger.error(f"Ollama analysis failed: {e}")
            # Fallback para análise básica
            return self._fallback_analysis(error_context, str(e))
        except Exception as e:
            self.logger.error(f"Repair analysis failed: {e}")
            raise RuntimeError(f"Failed to analyze error: {str(e)}") from e

    def _build_prompt(self, error_context: ErrorContext) -> str:
        """Constrói prompt para Ollama."""
        return self.user_prompt_template.format(
            language=error_context.language,
            file_path=str(error_context.file_path or "unknown"),
            error_message=error_context.error_message,
            error_type=error_context.error_type or "unknown",
            line_number=error_context.line_number or "unknown",
            traceback=error_context.traceback,
            code=error_context.code,
            additional_context=json.dumps(
                error_context.additional_context or {}, indent=2)
        )

    def _parse_ollama_response(self, error_context: ErrorContext,
                               response: Dict[str, Any]) -> RepairProposal:
        """Processa resposta do Ollama."""
        try:
            # Mapeamento de confiança
            confidence_map = {
                "very_low": RepairConfidence.VERY_LOW,
                "low": RepairConfidence.LOW,
                "medium": RepairConfidence.MEDIUM,
                "high": RepairConfidence.HIGH,
                "very_high": RepairConfidence.VERY_HIGH
            }

            # Extrai campos com defaults seguros
            confidence_str = response.get("confidence", "low").lower()
            confidence = confidence_map.get(
                confidence_str, RepairConfidence.LOW)

            repaired_code = str(response.get(
                "repaired_code", error_context.code))
            reasoning = str(response.get("analysis", "No analysis provided"))
            changes_made = response.get("changes_made", [])
            risk_assessment = str(response.get(
                "risk_assessment", "Unknown risk"))
            success_rate = float(response.get("estimated_success_rate", 0.5))
            validation_notes = response.get("validation_notes")

            # Validações de arrays
            if not isinstance(changes_made, list):
                changes_made = [str(changes_made)]

            # Normalização de valores
            success_rate = max(0.0, min(1.0, success_rate))

            return RepairProposal(
                original_code=error_context.code,
                repaired_code=repaired_code,
                confidence=confidence,
                reasoning=reasoning,
                changes_made=changes_made,
                risk_assessment=risk_assessment,
                estimated_success_rate=success_rate,
                validation_strategy=validation_notes,
                metadata={"ollama_response": response}
            )

        except Exception as e:
            self.logger.error(f"Failed to parse Ollama response: {e}")
            return self._fallback_analysis(error_context, f"Parse error: {str(e)}")

    def _fallback_analysis(self, error_context: ErrorContext,
                           error_reason: str) -> RepairProposal:
        """Análise de fallback quando Ollama falha."""
        # Análise básica baseada em padrões comuns
        common_fixes = self._get_common_fixes(error_context)

        return RepairProposal(
            original_code=error_context.code,
            repaired_code=common_fixes.get("fixed_code", error_context.code),
            confidence=RepairConfidence.LOW,
            reasoning=f"Fallback analysis due to: {error_reason}",
            changes_made=common_fixes.get("changes", ["Basic fix attempt"]),
            risk_assessment="High risk - fallback repair",
            estimated_success_rate=0.3,
            validation_strategy="Manual review required",
            metadata={"fallback_reason": error_reason}
        )

    def _get_common_fixes(self, error_context: ErrorContext) -> Dict[str, Any]:
        """Aplica correções comuns baseadas em padrões."""
        error_msg = error_context.error_message.lower()
        code = error_context.code

        # Fix comuns para Python
        if "nameerror" in error_msg:
            # Procura por variáveis não definidas
            undefined_var = self._extract_undefined_var(error_msg)
            if undefined_var:
                fixed_code = f"{undefined_var} = None\n{code}"
                return {"fixed_code": fixed_code, "changes": [f"Added {undefined_var} = None"]}

        elif "syntaxerror" in error_msg:
            # Remove caracteres problemáticos
            fixed_code = code.rstrip().rstrip(';')
            return {"fixed_code": fixed_code, "changes": ["Fixed syntax"]}

        elif "indentationerror" in error_msg:
            # Corrige indentação básica
            lines = code.split('\n')
            fixed_lines = []
            indent_level = 0

            for line in lines:
                if line.strip():
                    fixed_lines.append(' ' * (indent_level * 4) + line.strip())
                else:
                    fixed_lines.append('')

            return {"fixed_code": '\n'.join(fixed_lines), "changes": ["Fixed indentation"]}

        return {"fixed_code": code, "changes": ["No changes made"]}

    def _extract_undefined_var(self, error_message: str) -> Optional[str]:
        """Extrai nome da variável não definida do erro."""
        match = re.search(r"name '(\w+)' is not defined",
                          error_message, re.IGNORECASE)
        return match.group(1) if match else None


class PatternBasedRepairStrategy(BaseRepairStrategy):
    """Estratégia de reparo baseada em padrões (fallback)."""

    def __init__(self) -> None:
        super().__init__(name="pattern_repair", logger_name="pattern_repair")

    def _setup_patterns(self) -> None:
        """Configura padrões de reparo conhecidos."""
        self.repair_patterns = {
            "python": [
                {
                    "error_pattern": r"NameError.*name '(\w+)' is not defined",
                    "fix_template": "{var} = None\n{code}",
                    "description": "Initialize undefined variable"
                },
                {
                    "error_pattern": r"SyntaxError.*invalid syntax",
                    "fix_template": lambda code: code.rstrip(";"),
                    "description": "Remove trailing semicolon"
                },
                {
                    "error_pattern": r"IndentationError",
                    "fix_template": self._fix_indentation,
                    "description": "Fix indentation"
                }
            ]
        }

    def can_handle(self, error_context: ErrorContext) -> bool:
        """Verifica se há padrões para o erro."""
        if not super().can_handle(error_context):
            return False

        language = error_context.language.lower()
        patterns = self.repair_patterns.get(language, [])

        for pattern_info in patterns:
            if re.search(pattern_info["error_pattern"],
                         error_context.error_message, re.IGNORECASE):
                return True

        return False

    def analyze_error(self, error_context: ErrorContext) -> RepairProposal:
        """Aplica padrões de reparo conhecidos."""
        language = error_context.language.lower()
        patterns = self.repair_patterns.get(language, [])

        for pattern_info in patterns:
            if re.search(pattern_info["error_pattern"],
                         error_context.error_message, re.IGNORECASE):

                fix_template = pattern_info["fix_template"]

                if callable(fix_template):
                    fixed_code = fix_template(error_context.code)
                else:
                    match = re.search(pattern_info["error_pattern"],
                                      error_context.error_message, re.IGNORECASE)
                    if match:
                        fixed_code = fix_template.format(
                            code=error_context.code,
                            var=match.group(1) if match.groups() else ""
                        )
                    else:
                        fixed_code = error_context.code

                return RepairProposal(
                    original_code=error_context.code,
                    repaired_code=fixed_code,
                    confidence=RepairConfidence.MEDIUM,
                    reasoning=f"Applied pattern: {pattern_info['description']}",
                    changes_made=[pattern_info["description"]],
                    risk_assessment="Low risk - pattern-based fix",
                    estimated_success_rate=0.7,
                    validation_strategy="Basic syntax check"
                )

        # Nenhum padrão encontrado
        return RepairProposal(
            original_code=error_context.code,
            repaired_code=error_context.code,
            confidence=RepairConfidence.VERY_LOW,
            reasoning="No matching repair pattern found",
            changes_made=[],
            risk_assessment="Unknown - no pattern matched",
            estimated_success_rate=0.1,
            validation_strategy="Manual review required"
        )

    def _fix_indentation(self, code: str) -> str:
        """Corrige indentação básica do Python."""
        lines = code.split('\n')
        fixed_lines = []
        indent_level = 0

        for line in lines:
            stripped = line.strip()
            if stripped:
                # Detecta mudança de escopo
                if stripped.startswith(('def ', 'class ', 'if ', 'for ', 'while ', 'try:', 'with ')):
                    fixed_lines.append(' ' * (indent_level * 4) + stripped)
                    if not stripped.endswith(':'):
                        indent_level += 1
                elif stripped in ('else:', 'elif ', 'except:', 'finally:'):
                    indent_level = max(0, indent_level - 1)
                    fixed_lines.append(' ' * (indent_level * 4) + stripped)
                else:
                    fixed_lines.append(' ' * (indent_level * 4) + stripped)
            else:
                fixed_lines.append('')

        return '\n'.join(fixed_lines)


class RepairEngine:
    """Motor principal de reparo seguindo princípios SOLID."""

    def __init__(self,
                 primary_strategy: RepairStrategy,
                 fallback_strategy: Optional[RepairStrategy] = None,
                 executor: Optional[EnhancedExecutor] = None,
                 max_attempts: int = 3) -> None:
        self.primary_strategy = primary_strategy
        self.fallback_strategy = fallback_strategy
        self.executor = executor or create_executor("sandbox")
        self.max_attempts = max_attempts
        self.logger = get_logger("repair_engine")

    def repair(self, error_context: ErrorContext) -> RepairResult:
        """Executa processo completo de reparo."""
        start_time = time.perf_counter()
        attempts_made = 0

        try:
            self.logger.info(
                f"Starting repair for {error_context.error_type or 'unknown'}")

            # Validação inicial
            if not self._validate_error_context(error_context):
                return self._create_error_result(
                    error_context, "Invalid error context", start_time, attempts_made
                )

            # Tenta estratégia primária
            for attempt in range(self.max_attempts):
                attempts_made += 1

                try:
                    result = self._attempt_repair(error_context, attempt)
                    if result.success:
                        self.logger.info(
                            f"Repair successful on attempt {attempt + 1}")
                        return result
                    # Se a estratégia não pode lidar com o erro, retorna imediatamente
                    if "cannot handle this error" in result.error_message:
                        return result

                except Exception as e:
                    self.logger.warning(
                        f"Repair attempt {attempt + 1} failed: {e}")
                    continue

            # Todas as tentativas falharam
            return self._create_error_result(
                error_context, "All repair attempts failed", start_time, attempts_made
            )

        except Exception as e:
            self.logger.error(f"Repair process failed: {e}")
            return self._create_error_result(
                error_context, str(e), start_time, attempts_made
            )

    def _attempt_repair(self, error_context: ErrorContext,
                        attempt_number: int) -> RepairResult:
        """Tenta reparo usando estratégias disponíveis."""
        strategy = self.primary_strategy if attempt_number == 0 else self.fallback_strategy

        # Verifica se estratégia pode lidar com o erro
        if not strategy or not strategy.can_handle(error_context):
            return self._create_error_result(
                error_context, f"cannot handle this error: {error_context.error_type}",
                time.perf_counter(), attempt_number + 1
            )

        # Gera proposta de reparo
        proposal = strategy.analyze_error(error_context)

        # Valida proposta
        validation_result = strategy.validate_proposal(proposal, self.executor)

        # Determina sucesso
        success = (
            validation_result.status == ExecutionStatus.SUCCESS and
            validation_result.returncode == 0
        )

        execution_time = time.perf_counter()

        return RepairResult(
            status=RepairStatus.COMPLETED if success else RepairStatus.FAILED,
            original_code=error_context.code,
            final_code=proposal.repaired_code,
            proposal=proposal,
            validation_result=validation_result,
            error_message=None if success else f"Validation failed: {validation_result.stderr}",
            execution_time_seconds=execution_time,
            attempts_made=attempt_number + 1,
            success=success,
            metadata={"strategy": getattr(
                strategy, 'name', 'mock_strategy'), "attempt": attempt_number + 1}
        )

    def _validate_error_context(self, error_context: ErrorContext) -> bool:
        """Valida contexto do erro."""
        if not error_context.code or not error_context.error_message:
            return False

        if not error_context.language:
            return False

        return True

    def _create_error_result(self, error_context: ErrorContext,
                             error_message: str, start_time: float,
                             attempts_made: int) -> RepairResult:
        """Cria resultado de erro."""
        execution_time = time.perf_counter() - start_time

        return RepairResult(
            status=RepairStatus.FAILED,
            original_code=error_context.code,
            final_code=error_context.code,
            proposal=None,
            validation_result=None,
            error_message=error_message,
            execution_time_seconds=execution_time,
            attempts_made=attempts_made,
            success=False,
            metadata={"failed_reason": error_message}
        )


# Factory functions para facilitar criação
def create_repair_engine(ollama_client: OllamaClient,
                         model: Optional[str] = None,
                         enable_fallback: bool = True,
                         max_attempts: int = 3) -> RepairEngine:
    """Factory function para criar RepairEngine com configurações padrão."""
    primary = OllamaRepairStrategy(ollama_client, model, max_attempts)

    if enable_fallback:
        return RepairEngine(
            primary_strategy=primary,
            max_attempts=max_attempts
        )  # Usa fallback padrão
    else:
        return RepairEngine(
            primary_strategy=primary,
            fallback_strategy=None,  # Sem fallback
            max_attempts=max_attempts
        )


# Import necessário para time.perf_counter()

# Exportações públicas
__all__ = [
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
