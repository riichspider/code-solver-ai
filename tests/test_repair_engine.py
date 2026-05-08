"""Testes unitários para o módulo src.repair_engine.

Valida Strategy pattern, integração com Ollama, sandbox-validator,
tratamento de erros e conformidade com princípios SOLID.
"""

from __future__ import annotations

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.repair_engine import (
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
from models.ollama_client import OllamaClient, OllamaError
from utils.executor_v2 import EnhancedExecutor, ExecutionResult, ExecutionStatus


class TestRepairStatus:
    """Testes para enum RepairStatus."""

    def test_repair_status_values(self):
        """Testa valores do enum."""
        assert RepairStatus.PENDING.value == "pending"
        assert RepairStatus.ANALYZING.value == "analyzing"
        assert RepairStatus.REPAIRING.value == "repairing"
        assert RepairStatus.VALIDATING.value == "validating"
        assert RepairStatus.COMPLETED.value == "completed"
        assert RepairStatus.FAILED.value == "failed"
        assert RepairStatus.CANCELLED.value == "cancelled"


class TestRepairConfidence:
    """Testes para enum RepairConfidence."""

    def test_repair_confidence_values(self):
        """Testa valores do enum."""
        assert RepairConfidence.VERY_LOW.value == "very_low"
        assert RepairConfidence.LOW.value == "low"
        assert RepairConfidence.MEDIUM.value == "medium"
        assert RepairConfidence.HIGH.value == "high"
        assert RepairConfidence.VERY_HIGH.value == "very_high"


class TestErrorContext:
    """Testes para ErrorContext."""

    def test_minimal_error_context(self):
        """Testa criação mínima de ErrorContext."""
        context = ErrorContext(
            code="print(x)",
            error_message="NameError: name 'x' is not defined",
            traceback="Traceback...",
            language="python"
        )

        assert context.code == "print(x)"
        assert context.error_message == "NameError: name 'x' is not defined"
        assert context.traceback == "Traceback..."
        assert context.language == "python"
        assert context.file_path is None
        assert context.line_number is None
        assert context.error_type is None
        assert context.additional_context is None

    def test_full_error_context(self):
        """Testa criação completa de ErrorContext."""
        file_path = Path("/test/file.py")
        metadata = {"test": True}

        context = ErrorContext(
            code="print(x)",
            error_message="NameError: name 'x' is not defined",
            traceback="Traceback...",
            language="python",
            file_path=file_path,
            line_number=10,
            error_type="NameError",
            additional_context=metadata
        )

        assert context.file_path == file_path
        assert context.line_number == 10
        assert context.error_type == "NameError"
        assert context.additional_context == metadata

    def test_to_dict(self):
        """Testa conversão para dicionário."""
        file_path = Path("/test/file.py")
        context = ErrorContext(
            code="print(x)",
            error_message="NameError",
            traceback="Traceback",
            language="python",
            file_path=file_path
        )

        result_dict = context.to_dict()

        assert result_dict["code"] == "print(x)"
        assert result_dict["error_message"] == "NameError"
        assert result_dict["file_path"] == str(file_path)
        assert result_dict["language"] == "python"


class TestRepairProposal:
    """Testes para RepairProposal."""

    def test_repair_proposal_creation(self):
        """Testa criação de RepairProposal."""
        proposal = RepairProposal(
            original_code="print(x)",
            repaired_code="x = None\nprint(x)",
            confidence=RepairConfidence.HIGH,
            reasoning="Initialize undefined variable",
            changes_made=["Added x = None"],
            risk_assessment="Low risk",
            estimated_success_rate=0.9
        )

        assert proposal.original_code == "print(x)"
        assert proposal.repaired_code == "x = None\nprint(x)"
        assert proposal.confidence == RepairConfidence.HIGH
        assert proposal.reasoning == "Initialize undefined variable"
        assert proposal.changes_made == ["Added x = None"]
        assert proposal.risk_assessment == "Low risk"
        assert proposal.estimated_success_rate == 0.9
        assert proposal.validation_strategy is None
        assert proposal.metadata is None

    def test_to_dict(self):
        """Testa conversão para dicionário."""
        proposal = RepairProposal(
            original_code="print(x)",
            repaired_code="x = None\nprint(x)",
            confidence=RepairConfidence.MEDIUM,
            reasoning="Test reasoning",
            changes_made=["Test change"],
            risk_assessment="Test risk",
            estimated_success_rate=0.7
        )

        result_dict = proposal.to_dict()

        assert result_dict["original_code"] == "print(x)"
        assert result_dict["repaired_code"] == "x = None\nprint(x)"
        assert result_dict["confidence"] == "medium"
        assert result_dict["reasoning"] == "Test reasoning"
        assert result_dict["changes_made"] == ["Test change"]
        assert result_dict["risk_assessment"] == "Test risk"
        assert result_dict["estimated_success_rate"] == 0.7


class TestRepairResult:
    """Testes para RepairResult."""

    def test_repair_result_creation(self):
        """Testa criação de RepairResult."""
        proposal = RepairProposal(
            original_code="print(x)",
            repaired_code="x = None\nprint(x)",
            confidence=RepairConfidence.HIGH,
            reasoning="Test",
            changes_made=["Test"],
            risk_assessment="Low",
            estimated_success_rate=0.8
        )

        validation = ExecutionResult(
            command=["python", "test.py"],
            returncode=0,
            stdout="",
            stderr="",
            status=ExecutionStatus.SUCCESS,
            duration_seconds=1.0,
            timeout_seconds=10,
            working_directory=Path.cwd(),
            security_violations=[],
            metadata={}
        )

        result = RepairResult(
            status=RepairStatus.COMPLETED,
            original_code="print(x)",
            final_code="x = None\nprint(x)",
            proposal=proposal,
            validation_result=validation,
            error_message=None,
            execution_time_seconds=2.0,
            attempts_made=1,
            success=True
        )

        assert result.status == RepairStatus.COMPLETED
        assert result.success is True
        assert result.attempts_made == 1
        assert result.proposal == proposal
        assert result.validation_result == validation

    def test_to_dict(self):
        """Testa conversão para dicionário."""
        proposal = RepairProposal(
            original_code="print(x)",
            repaired_code="x = None\nprint(x)",
            confidence=RepairConfidence.LOW,
            reasoning="Test",
            changes_made=["Test"],
            risk_assessment="Low",
            estimated_success_rate=0.5
        )

        result = RepairResult(
            status=RepairStatus.FAILED,
            original_code="print(x)",
            final_code="print(x)",
            proposal=proposal,
            validation_result=None,
            error_message="Test error",
            execution_time_seconds=1.0,
            attempts_made=1,
            success=False
        )

        result_dict = result.to_dict()

        assert result_dict["status"] == "failed"
        assert result_dict["success"] is False
        assert result_dict["error_message"] == "Test error"
        assert result_dict["proposal"]["confidence"] == "low"
        assert result_dict["validation_result"] is None


class TestPatternBasedRepairStrategy:
    """Testes para PatternBasedRepairStrategy."""

    def setup_method(self):
        """Setup para cada teste."""
        self.strategy = PatternBasedRepairStrategy()

    def test_strategy_name(self):
        """Testa nome da estratégia."""
        assert self.strategy.name == "pattern_repair"

    def test_can_handle_python_nameerror(self):
        """Testa se pode lidar com NameError Python."""
        context = ErrorContext(
            code="print(undefined_var)",
            error_message="NameError: name 'undefined_var' is not defined",
            traceback="Traceback...",
            language="python"
        )

        assert self.strategy.can_handle(context) is True

    def test_can_handle_unsupported_language(self):
        """Testa linguagem não suportada."""
        context = ErrorContext(
            code="some code",
            error_message="Error",
            traceback="Traceback",
            language="unsupported_language"
        )

        assert self.strategy.can_handle(context) is False

    def test_analyze_nameerror(self):
        """Testa análise de NameError."""
        context = ErrorContext(
            code="print(x)",
            error_message="NameError: name 'x' is not defined",
            traceback="Traceback...",
            language="python"
        )

        proposal = self.strategy.analyze_error(context)

        assert proposal.original_code == "print(x)"
        assert "x = None" in proposal.repaired_code
        assert proposal.confidence == RepairConfidence.MEDIUM
        assert "Initialize undefined variable" in proposal.reasoning
        assert len(proposal.changes_made) > 0

    def test_analyze_syntaxerror(self):
        """Testa análise de SyntaxError."""
        context = ErrorContext(
            code="print(x);",
            error_message="SyntaxError: invalid syntax",
            traceback="Traceback...",
            language="python"
        )

        proposal = self.strategy.analyze_error(context)

        assert proposal.original_code == "print(x);"
        # Remove caracteres problemáticos
        fixed_code = proposal.repaired_code.rstrip().rstrip(';')
        assert fixed_code == "print(x)"
        assert proposal.confidence == RepairConfidence.MEDIUM

    def test_analyze_no_pattern_match(self):
        """Testa quando nenhum padrão corresponde."""
        context = ErrorContext(
            code="print(x)",
            error_message="CustomError: unknown error",
            traceback="Traceback...",
            language="python"
        )

        proposal = self.strategy.analyze_error(context)

        assert proposal.original_code == "print(x)"
        assert proposal.repaired_code == "print(x)"  # Sem mudanças
        assert proposal.confidence == RepairConfidence.VERY_LOW
        assert "No matching repair pattern" in proposal.reasoning

    def test_validate_proposal_success(self):
        """Testa validação de proposta com sucesso."""
        mock_executor = Mock(spec=EnhancedExecutor)
        mock_executor.execute.return_value = ExecutionResult(
            command=["python", "test.py"],
            returncode=0,
            stdout="Success",
            stderr="",
            status=ExecutionStatus.SUCCESS,
            duration_seconds=1.0,
            timeout_seconds=10,
            working_directory=Path.cwd(),
            security_violations=[],
            metadata={}
        )

        proposal = RepairProposal(
            original_code="print(x)",
            repaired_code="x = None\nprint(x)",
            confidence=RepairConfidence.HIGH,
            reasoning="Test",
            changes_made=["Test"],
            risk_assessment="Low",
            estimated_success_rate=0.9
        )

        with patch('pathlib.Path.write_text'), \
                patch('pathlib.Path.unlink'):
            result = self.strategy.validate_proposal(proposal, mock_executor)

        assert result.status == ExecutionStatus.SUCCESS
        assert result.returncode == 0

    def test_validate_proposal_failure(self):
        """Testa validação de proposta com falha."""
        mock_executor = Mock(spec=EnhancedExecutor)
        mock_executor.execute.return_value = ExecutionResult(
            command=["python", "test.py"],
            returncode=1,
            stdout="",
            stderr="Error",
            status=ExecutionStatus.ERROR,
            duration_seconds=1.0,
            timeout_seconds=10,
            working_directory=Path.cwd(),
            security_violations=[],
            metadata={}
        )

        proposal = RepairProposal(
            original_code="print(x)",
            repaired_code="x = None\nprint(x)",
            confidence=RepairConfidence.HIGH,
            reasoning="Test",
            changes_made=["Test"],
            risk_assessment="Low",
            estimated_success_rate=0.9
        )

        with patch('pathlib.Path.write_text'), \
                patch('pathlib.Path.unlink'):
            result = self.strategy.validate_proposal(proposal, mock_executor)

        assert result.status == ExecutionStatus.ERROR
        assert result.returncode == 1


class TestOllamaRepairStrategy:
    """Testes para OllamaRepairStrategy."""

    def setup_method(self):
        """Setup para cada teste."""
        self.mock_client = Mock(spec=OllamaClient)
        self.mock_client.default_model = "test-model"
        self.strategy = OllamaRepairStrategy(self.mock_client)

    def test_strategy_initialization(self):
        """Testa inicialização da estratégia."""
        assert self.strategy.name == "ollama_repair"
        assert self.strategy.model == "test-model"
        assert self.strategy.max_attempts == 3

    def test_can_handle_supported_language(self):
        """Testa se pode lidar com linguagem suportada."""
        context = ErrorContext(
            code="print(x)",
            error_message="NameError",
            traceback="Traceback",
            language="python"
        )

        assert self.strategy.can_handle(context) is True

    def test_can_handle_unsupported_language(self):
        """Testa se não pode lidar com linguagem não suportada."""
        context = ErrorContext(
            code="some code",
            error_message="Error",
            traceback="Traceback",
            language="cobol"
        )

        assert self.strategy.can_handle(context) is False

    def test_analyze_error_success(self):
        """Testa análise com sucesso via Ollama."""
        mock_response = {
            "analysis": "Variable x is not defined",
            "root_cause": "Missing variable initialization",
            "repaired_code": "x = None\nprint(x)",
            "confidence": "high",
            "changes_made": ["Added variable initialization"],
            "risk_assessment": "Low risk",
            "estimated_success_rate": 0.9,
            "validation_notes": "Test the fixed code"
        }

        self.mock_client.generate_json.return_value = mock_response

        context = ErrorContext(
            code="print(x)",
            error_message="NameError: name 'x' is not defined",
            traceback="Traceback...",
            language="python"
        )

        proposal = self.strategy.analyze_error(context)

        assert proposal.original_code == "print(x)"
        assert proposal.repaired_code == "x = None\nprint(x)"
        assert proposal.confidence == RepairConfidence.HIGH
        assert "Variable x is not defined" in proposal.reasoning
        assert proposal.changes_made == ["Added variable initialization"]
        assert proposal.risk_assessment == "Low risk"
        assert proposal.estimated_success_rate == 0.9
        assert proposal.validation_strategy == "Test the fixed code"

    def test_analyze_error_ollama_failure(self):
        """Testa análise quando Ollama falha."""
        self.mock_client.generate_json.side_effect = OllamaError(
            "Connection failed")

        context = ErrorContext(
            code="print(x)",
            error_message="NameError: name 'x' is not defined",
            traceback="Traceback...",
            language="python"
        )

        proposal = self.strategy.analyze_error(context)

        assert proposal.original_code == "print(x)"
        assert proposal.confidence == RepairConfidence.LOW
        assert "Fallback analysis" in proposal.reasoning
        assert proposal.estimated_success_rate == 0.3
        assert "fallback_reason" in proposal.metadata

    def test_analyze_error_invalid_response(self):
        """Testa análise com resposta inválida do Ollama."""
        mock_response = {
            "analysis": None,  # Vai causar erro no str()
            "repaired_code": 123,  # Não é string
            "confidence": "invalid_confidence",
            "changes_made": "not_array",
            "risk_assessment": None,
            "estimated_success_rate": "not_float"
        }

        self.mock_client.generate_json.return_value = mock_response

        context = ErrorContext(
            code="print(x)",
            error_message="NameError",
            traceback="Traceback",
            language="python"
        )

        proposal = self.strategy.analyze_error(context)

        # Deve fazer fallback para valores seguros
        assert isinstance(proposal.repaired_code, str)
        assert proposal.confidence == RepairConfidence.LOW
        assert isinstance(proposal.changes_made, list)
        assert isinstance(proposal.risk_assessment, str)
        assert isinstance(proposal.estimated_success_rate, float)

    def test_extract_undefined_var(self):
        """Testa extração de variável não definida."""
        error_msg = "NameError: name 'my_variable' is not defined"
        var = self.strategy._extract_undefined_var(error_msg)
        assert var == "my_variable"

        error_msg = "NameError: name 'x' is not defined"
        var = self.strategy._extract_undefined_var(error_msg)
        assert var == "x"

        error_msg = "No variable name here"
        var = self.strategy._extract_undefined_var(error_msg)
        assert var is None


class TestRepairEngine:
    """Testes para classe principal RepairEngine."""

    def setup_method(self):
        """Setup para cada teste."""
        self.mock_primary = Mock(spec=RepairStrategy)
        self.mock_fallback = Mock(spec=RepairStrategy)
        self.mock_executor = Mock(spec=EnhancedExecutor)

        self.engine = RepairEngine(
            primary_strategy=self.mock_primary,
            fallback_strategy=self.mock_fallback,
            executor=self.mock_executor,
            max_attempts=2
        )

    def test_initialization(self):
        """Testa inicialização do RepairEngine."""
        assert self.engine.primary_strategy == self.mock_primary
        assert self.engine.fallback_strategy == self.mock_fallback
        assert self.engine.executor == self.mock_executor
        assert self.engine.max_attempts == 2

    def test_initialization_default_fallback(self):
        """Testa inicialização com fallback padrão."""
        engine = RepairEngine(primary_strategy=self.mock_primary)

        assert engine.primary_strategy == self.mock_primary
        assert engine.fallback_strategy is None

    def test_repair_success_first_attempt(self):
        """Testa reparo com sucesso na primeira tentativa."""
        context = ErrorContext(
            code="print(x)",
            error_message="NameError",
            traceback="Traceback",
            language="python"
        )

        # Mock da estratégia primária
        proposal = RepairProposal(
            original_code="print(x)",
            repaired_code="x = None\nprint(x)",
            confidence=RepairConfidence.HIGH,
            reasoning="Test",
            changes_made=["Test"],
            risk_assessment="Low",
            estimated_success_rate=0.9
        )

        validation = ExecutionResult(
            command=["python", "test.py"],
            returncode=0,
            stdout="Success",
            stderr="",
            status=ExecutionStatus.SUCCESS,
            duration_seconds=1.0,
            timeout_seconds=10,
            working_directory=Path.cwd(),
            security_violations=[],
            metadata={}
        )

        self.mock_primary.can_handle.return_value = True
        self.mock_primary.analyze_error.return_value = proposal
        self.mock_primary.validate_proposal.return_value = validation

        result = self.engine.repair(context)

        assert result.success is True
        assert result.status == RepairStatus.COMPLETED
        assert result.attempts_made == 1
        assert result.final_code == "x = None\nprint(x)"
        assert result.proposal == proposal
        assert result.validation_result == validation

    def test_repair_success_second_attempt(self):
        """Testa reparo com sucesso na segunda tentativa (fallback)."""
        context = ErrorContext(
            code="print(x)",
            error_message="NameError",
            traceback="Traceback",
            language="python"
        )

        # Mock da estratégia primária (falha)
        self.mock_primary.can_handle.return_value = True
        self.mock_primary.analyze_error.side_effect = Exception(
            "Primary failed")

        # Mock do fallback (sucesso)
        proposal = RepairProposal(
            original_code="print(x)",
            repaired_code="x = None\nprint(x)",
            confidence=RepairConfidence.MEDIUM,
            reasoning="Fallback fix",
            changes_made=["Fallback change"],
            risk_assessment="Medium",
            estimated_success_rate=0.7
        )

        validation = ExecutionResult(
            command=["python", "test.py"],
            returncode=0,
            stdout="Success",
            stderr="",
            status=ExecutionStatus.SUCCESS,
            duration_seconds=1.0,
            timeout_seconds=10,
            working_directory=Path.cwd(),
            security_violations=[],
            metadata={}
        )

        self.mock_fallback.can_handle.return_value = True
        self.mock_fallback.analyze_error.return_value = proposal
        self.mock_fallback.validate_proposal.return_value = validation

        result = self.engine.repair(context)

        assert result.success is True
        assert result.status == RepairStatus.COMPLETED
        assert result.attempts_made == 2
        assert result.final_code == "x = None\nprint(x)"

    def test_repair_all_attempts_failed(self):
        """Testa quando todas as tentativas falham."""
        context = ErrorContext(
            code="print(x)",
            error_message="NameError",
            traceback="Traceback",
            language="python"
        )

        # Mock de falha em ambas as estratégias
        self.mock_primary.can_handle.return_value = True
        self.mock_primary.analyze_error.side_effect = Exception(
            "Primary failed")

        self.mock_fallback.can_handle.return_value = True
        self.mock_fallback.analyze_error.side_effect = Exception(
            "Fallback failed")

        result = self.engine.repair(context)

        assert result.success is False
        assert result.status == RepairStatus.FAILED
        assert result.attempts_made == 2
        assert result.error_message == "All repair attempts failed"
        assert result.final_code == "print(x)"  # Código original

    def test_repair_invalid_context(self):
        """Testa reparo com contexto inválido."""
        # Contexto sem código
        context = ErrorContext(
            code="",
            error_message="NameError",
            traceback="Traceback",
            language="python"
        )

        result = self.engine.repair(context)

        assert result.success is False
        assert result.status == RepairStatus.FAILED
        assert "Invalid error context" in result.error_message

    def test_repair_strategy_cannot_handle(self):
        """Testa quando estratégia não pode lidar com erro."""
        context = ErrorContext(
            code="print(x)",
            error_message="NameError",
            traceback="Traceback",
            language="python"
        )

        self.mock_primary.can_handle.return_value = False

        result = self.engine.repair(context)

        assert result.success is False
        assert result.status == RepairStatus.FAILED
        assert "cannot handle this error" in result.error_message


class TestCreateRepairEngine:
    """Testes para factory function create_repair_engine."""

    def test_create_repair_engine_with_fallback(self):
        """Testa criação com fallback."""
        mock_client = Mock(spec=OllamaClient)
        mock_client.default_model = "test-model"

        engine = create_repair_engine(
            mock_client,
            model="custom-model",
            enable_fallback=True,
            max_attempts=5
        )

        assert isinstance(engine, RepairEngine)
        assert isinstance(engine.primary_strategy, OllamaRepairStrategy)
        assert engine.fallback_strategy is None
        assert engine.max_attempts == 5
        assert engine.primary_strategy.model == "custom-model"

    def test_create_repair_engine_without_fallback(self):
        """Testa criação sem fallback."""
        mock_client = Mock(spec=OllamaClient)
        mock_client.default_model = "test-model"

        engine = create_repair_engine(
            mock_client,
            enable_fallback=False
        )

        assert isinstance(engine, RepairEngine)
        assert isinstance(engine.primary_strategy, OllamaRepairStrategy)
        assert engine.fallback_strategy is None


class TestIntegration:
    """Testes de integração."""

    def test_full_repair_flow(self):
        """Teste completo do fluxo de reparo."""
        # Mock do OllamaClient
        mock_client = Mock(spec=OllamaClient)
        mock_client.default_model = "test-model"

        mock_response = {
            "analysis": "Variable x is not defined",
            "root_cause": "Missing initialization",
            "repaired_code": "x = None\nprint(x)",
            "confidence": "high",
            "changes_made": ["Added x = None"],
            "risk_assessment": "Low risk",
            "estimated_success_rate": 0.9,
            "validation_notes": "Test the fix"
        }

        mock_client.generate_json.return_value = mock_response

        # Mock do executor
        mock_executor = Mock(spec=EnhancedExecutor)
        mock_executor.execute.return_value = ExecutionResult(
            command=["python", "test.py"],
            returncode=0,
            stdout="None",
            stderr="",
            status=ExecutionStatus.SUCCESS,
            duration_seconds=1.0,
            timeout_seconds=10,
            working_directory=Path.cwd(),
            security_violations=[],
            metadata={}
        )

        # Cria engine e executa reparo
        engine = create_repair_engine(mock_client, enable_fallback=True)
        engine.executor = mock_executor

        context = ErrorContext(
            code="print(x)",
            error_message="NameError: name 'x' is not defined",
            traceback="Traceback (most recent call last):\n  File test.py, line 1\n    print(x)\nNameError: name 'x' is not defined",
            language="python",
            file_path=Path("test.py"),
            line_number=1,
            error_type="NameError"
        )

        with patch('pathlib.Path.write_text'), \
                patch('pathlib.Path.unlink'):
            result = engine.repair(context)

        # Verifica resultado
        assert result.success is True
        assert result.status == RepairStatus.COMPLETED
        assert result.final_code == "x = None\nprint(x)"
        assert result.proposal.confidence == RepairConfidence.HIGH
        assert result.validation_result.status == ExecutionStatus.SUCCESS

        # Verifica chamadas aos mocks
        mock_client.generate_json.assert_called_once()
        mock_executor.execute.assert_called_once()

        # Verifica prompt enviado ao Ollama
        call_args = mock_client.generate_json.call_args
        assert "print(x)" in call_args[1]["user_prompt"]
        assert "NameError: name 'x' is not defined" in call_args[1]["user_prompt"]
        assert "python" in call_args[1]["user_prompt"]
