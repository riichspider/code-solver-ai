"""Testes unitários para sistema de auto-repair.

Valida Strategy Pattern, classificação de erros e integração com executor.
"""

from __future__ import annotations

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from utils.auto_repair import (
    RepairStrategy,
    ErrorClassifier,
    ErrorType,
    RepairMetadata,
    RepairResult,
    PromptBasedRepairStrategy,
    PatternBasedRepairStrategy,
    AutoRepairManager,
    create_auto_repair_manager
)
from utils.executor_v2 import ExecutionResult, ExecutionStatus


class MockRepairStrategy:
    """Estratégia de reparo mock para testes."""
    
    def __init__(self, name: str = "mock_strategy", can_repair_result: bool = True):
        self.name = name
        self.can_repair_result = can_repair_result
        self.repair_called = False
    
    def can_repair(self, execution_result: ExecutionResult) -> bool:
        return self.can_repair_result
    
    def repair(
        self,
        execution_result: ExecutionResult,
        original_code: str,
        problem_context: str,
        language: str,
        **kwargs
    ) -> tuple[str, str, RepairMetadata]:
        self.repair_called = True
        
        if self.can_repair_result:
            repaired_code = original_code + "\n# Repaired by mock"
            explanation = "Mock repair applied"
            metadata = RepairMetadata(
                strategy_name=self.name,
                error_type=ErrorType.SYNTAX_ERROR,
                original_error=execution_result.stderr,
                repair_attempts=1,
                success=True,
                confidence=0.8,
                repair_time_seconds=0.1,
                applied_fixes=["mock_fix"],
                remaining_issues=[]
            )
        else:
            repaired_code = original_code
            explanation = "Mock repair failed"
            metadata = RepairMetadata(
                strategy_name=self.name,
                error_type=ErrorType.UNKNOWN_ERROR,
                original_error=execution_result.stderr,
                repair_attempts=1,
                success=False,
                confidence=0.0,
                repair_time_seconds=0.1,
                applied_fixes=[],
                remaining_issues=["mock_failure"]
            )
        
        return repaired_code, explanation, metadata
    
    def get_name(self) -> str:
        return self.name


class TestErrorClassifier:
    """Testes para ErrorClassifier."""
    
    def setup_method(self):
        """Setup para cada teste."""
        self.classifier = ErrorClassifier()
    
    def test_classify_syntax_error(self):
        """Testa classificação de erro de sintaxe."""
        execution_result = ExecutionResult(
            command=["python", "script.py"],
            returncode=1,
            stdout="",
            stderr="SyntaxError: invalid syntax",
            status=ExecutionStatus.ERROR,
            duration_seconds=0.1,
            timeout_seconds=10,
            working_directory=Path("."),
            security_violations=[],
            metadata={}
        )
        
        error_type = self.classifier.classify_error(execution_result)
        assert error_type == ErrorType.SYNTAX_ERROR
    
    def test_classify_import_error(self):
        """Testa classificação de erro de import."""
        execution_result = ExecutionResult(
            command=["python", "script.py"],
            returncode=1,
            stdout="",
            stderr="ModuleNotFoundError: No module named 'requests'",
            status=ExecutionStatus.ERROR,
            duration_seconds=0.1,
            timeout_seconds=10,
            working_directory=Path("."),
            security_violations=[],
            metadata={}
        )
        
        error_type = self.classifier.classify_error(execution_result)
        assert error_type == ErrorType.IMPORT_ERROR
    
    def test_classify_timeout_error(self):
        """Testa classificação de erro de timeout."""
        execution_result = ExecutionResult(
            command=["python", "script.py"],
            returncode=None,
            stdout="",
            stderr="Process timed out",
            status=ExecutionStatus.TIMEOUT,
            duration_seconds=30.0,
            timeout_seconds=10,
            working_directory=Path("."),
            security_violations=[],
            metadata={}
        )
        
        error_type = self.classifier.classify_error(execution_result)
        assert error_type == ErrorType.TIMEOUT_ERROR
    
    def test_classify_unknown_error(self):
        """Testa classificação de erro desconhecido."""
        execution_result = ExecutionResult(
            command=["python", "script.py"],
            returncode=1,
            stdout="",
            stderr="Some unknown error occurred",
            status=ExecutionStatus.ERROR,
            duration_seconds=0.1,
            timeout_seconds=10,
            working_directory=Path("."),
            security_violations=[],
            metadata={}
        )
        
        error_type = self.classifier.classify_error(execution_result)
        assert error_type == ErrorType.UNKNOWN_ERROR


class TestPatternBasedRepairStrategy:
    """Testes para PatternBasedRepairStrategy."""
    
    def setup_method(self):
        """Setup para cada teste."""
        self.strategy = PatternBasedRepairStrategy()
    
    def test_can_repair_syntax_error(self):
        """Testa se pode reparar erro de sintaxe."""
        execution_result = ExecutionResult(
            command=["python", "script.py"],
            returncode=1,
            stdout="",
            stderr="SyntaxError: invalid syntax",
            status=ExecutionStatus.ERROR,
            duration_seconds=0.1,
            timeout_seconds=10,
            working_directory=Path("."),
            security_violations=[],
            metadata={}
        )
        
        assert self.strategy.can_repair(execution_result) is True
    
    def test_cannot_repair_timeout_error(self):
        """Testa que não pode reparar erro de timeout."""
        execution_result = ExecutionResult(
            command=["python", "script.py"],
            returncode=None,
            stdout="",
            stderr="Process timed out",
            status=ExecutionStatus.TIMEOUT,
            duration_seconds=30.0,
            timeout_seconds=10,
            working_directory=Path("."),
            security_violations=[],
            metadata={}
        )
        
        assert self.strategy.can_repair(execution_result) is False
    
    def test_repair_missing_colon(self):
        """Testa reparo de dois-pontos faltando."""
        execution_result = ExecutionResult(
            command=["python", "script.py"],
            returncode=1,
            stdout="",
            stderr="SyntaxError: invalid syntax",
            status=ExecutionStatus.ERROR,
            duration_seconds=0.1,
            timeout_seconds=10,
            working_directory=Path("."),
            security_violations=[],
            metadata={}
        )
        
        original_code = "def my_function()\n    print('hello')"
        
        repaired_code, explanation, metadata = self.strategy.repair(
            execution_result=execution_result,
            original_code=original_code,
            problem_context="Simple function",
            language="python"
        )
        
        # Verifica que dois-pontos foram adicionados
        assert "def my_function():" in repaired_code
        assert metadata.success is True
        assert len(metadata.applied_fixes) > 0
    
    def test_repair_print_statement(self):
        """Testa reparo de statement print sem parênteses."""
        execution_result = ExecutionResult(
            command=["python", "script.py"],
            returncode=1,
            stdout="",
            stderr="SyntaxError: Missing parentheses",
            status=ExecutionStatus.ERROR,
            duration_seconds=0.1,
            timeout_seconds=10,
            working_directory=Path("."),
            security_violations=[],
            metadata={}
        )
        
        original_code = 'print "hello world"'
        
        repaired_code, explanation, metadata = self.strategy.repair(
            execution_result=execution_result,
            original_code=original_code,
            problem_context="Print statement",
            language="python"
        )
        
        # Verifica que parênteses foram adicionados
        assert "print(" in repaired_code
        assert metadata.success is True


class TestPromptBasedRepairStrategy:
    """Testes para PromptBasedRepairStrategy."""
    
    def setup_method(self):
        """Setup para cada teste."""
        self.mock_ai_client = Mock()
        self.strategy = PromptBasedRepairStrategy(self.mock_ai_client)
    
    def test_can_repair_syntax_error(self):
        """Testa se pode reparar erro de sintaxe."""
        execution_result = ExecutionResult(
            command=["python", "script.py"],
            returncode=1,
            stdout="",
            stderr="SyntaxError: invalid syntax",
            status=ExecutionStatus.ERROR,
            duration_seconds=0.1,
            timeout_seconds=10,
            working_directory=Path("."),
            security_violations=[],
            metadata={}
        )
        
        assert self.strategy.can_repair(execution_result) is True
    
    def test_cannot_repair_timeout_error(self):
        """Testa que não pode reparar erro de timeout."""
        execution_result = ExecutionResult(
            command=["python", "script.py"],
            returncode=None,
            stdout="",
            stderr="Process timed out",
            status=ExecutionStatus.TIMEOUT,
            duration_seconds=30.0,
            timeout_seconds=10,
            working_directory=Path("."),
            security_violations=[],
            metadata={}
        )
        
        assert self.strategy.can_repair(execution_result) is False
    
    @patch('utils.auto_repair.json.loads')
    def test_repair_with_ai_success(self, mock_json_loads):
        """Testa reparo bem-sucedido com IA."""
        # Mock da resposta da IA
        mock_response = {
            'content': '{"repaired_code": "def fixed_function():\\n    pass", "explanation": "Fixed syntax", "applied_fixes": ["added_colon"], "confidence": 0.9}'
        }
        self.mock_ai_client.generate_text.return_value = mock_response
        mock_json_loads.return_value = {
            "repaired_code": "def fixed_function():\n    pass",
            "explanation": "Fixed syntax",
            "applied_fixes": ["added_colon"],
            "confidence": 0.9
        }
        
        execution_result = ExecutionResult(
            command=["python", "script.py"],
            returncode=1,
            stdout="",
            stderr="SyntaxError: invalid syntax",
            status=ExecutionStatus.ERROR,
            duration_seconds=0.1,
            timeout_seconds=10,
            working_directory=Path("."),
            security_violations=[],
            metadata={}
        )
        
        original_code = "def broken_function()\n    pass"
        
        repaired_code, explanation, metadata = self.strategy.repair(
            execution_result=execution_result,
            original_code=original_code,
            problem_context="Function definition",
            language="python"
        )
        
        assert "def fixed_function():" in repaired_code
        assert metadata.success is True
        assert metadata.confidence == 0.9
        assert "added_colon" in metadata.applied_fixes
    
    def test_repair_with_ai_failure(self):
        """Testa falha no reparo com IA."""
        # Mock de falha na IA
        self.mock_ai_client.generate_text.side_effect = Exception("AI failed")
        
        execution_result = ExecutionResult(
            command=["python", "script.py"],
            returncode=1,
            stdout="",
            stderr="SyntaxError: invalid syntax",
            status=ExecutionStatus.ERROR,
            duration_seconds=0.1,
            timeout_seconds=10,
            working_directory=Path("."),
            security_violations=[],
            metadata={}
        )
        
        original_code = "def broken_function()\n    pass"
        
        repaired_code, explanation, metadata = self.strategy.repair(
            execution_result=execution_result,
            original_code=original_code,
            problem_context="Function definition",
            language="python"
        )
        
        # Retorna código original sem modificações
        assert repaired_code == original_code
        assert metadata.success is False
        assert metadata.confidence == 0.0


class TestAutoRepairManager:
    """Testes para AutoRepairManager."""
    
    def setup_method(self):
        """Setup para cada teste."""
        self.mock_strategy1 = MockRepairStrategy("strategy1", can_repair_result=True)
        self.mock_strategy2 = MockRepairStrategy("strategy2", can_repair_result=False)
        self.manager = AutoRepairManager([self.mock_strategy1, self.mock_strategy2])
    
    def test_successful_repair(self):
        """Testa reparo bem-sucedido."""
        execution_result = ExecutionResult(
            command=["python", "script.py"],
            returncode=1,
            stdout="",
            stderr="SyntaxError: invalid syntax",
            status=ExecutionStatus.ERROR,
            duration_seconds=0.1,
            timeout_seconds=10,
            working_directory=Path("."),
            security_violations=[],
            metadata={}
        )
        
        result = self.manager.attempt_repair(
            execution_result=execution_result,
            original_code="broken code",
            problem_context="Test problem",
            language="python"
        )
        
        assert result.success is True
        assert result.metadata.strategy_name == "strategy1"
        assert self.mock_strategy1.repair_called is True
    
    def test_all_strategies_fail(self):
        """Testa quando todas as estratégias falham."""
        # Configura ambas as estratégias para falhar
        self.mock_strategy1.can_repair_result = False
        self.mock_strategy2.can_repair_result = False
        
        execution_result = ExecutionResult(
            command=["python", "script.py"],
            returncode=1,
            stdout="",
            stderr="Unknown error",
            status=ExecutionStatus.ERROR,
            duration_seconds=0.1,
            timeout_seconds=10,
            working_directory=Path("."),
            security_violations=[],
            metadata={}
        )
        
        result = self.manager.attempt_repair(
            execution_result=execution_result,
            original_code="broken code",
            problem_context="Test problem",
            language="python"
        )
        
        assert result.success is False
        assert result.metadata.strategy_name == "none"
    
    def test_no_repair_needed(self):
        """Testa quando não há necessidade de reparo."""
        execution_result = ExecutionResult(
            command=["python", "script.py"],
            returncode=0,
            stdout="Success",
            stderr="",
            status=ExecutionStatus.SUCCESS,
            duration_seconds=0.1,
            timeout_seconds=10,
            working_directory=Path("."),
            security_violations=[],
            metadata={}
        )
        
        result = self.manager.attempt_repair(
            execution_result=execution_result,
            original_code="working code",
            problem_context="Test problem",
            language="python"
        )
        
        assert result.success is True
        assert result.metadata.strategy_name == "none"
        assert result.repaired_code == "working code"


class TestFactoryFunction:
    """Testes para factory function."""
    
    def test_create_with_ai_client(self):
        """Testa criação com cliente IA."""
        mock_ai_client = Mock()
        
        manager = create_auto_repair_manager(
            ai_client=mock_ai_client,
            enable_pattern_based=True,
            enable_prompt_based=True
        )
        
        assert len(manager.strategies) == 2
        assert any(isinstance(s, PatternBasedRepairStrategy) for s in manager.strategies)
        assert any(isinstance(s, PromptBasedRepairStrategy) for s in manager.strategies)
    
    def test_create_pattern_based_only(self):
        """Testa criação apenas com estratégia baseada em padrões."""
        manager = create_auto_repair_manager(
            ai_client=None,
            enable_pattern_based=True,
            enable_prompt_based=False
        )
        
        assert len(manager.strategies) == 1
        assert isinstance(manager.strategies[0], PatternBasedRepairStrategy)
    
    def test_create_prompt_based_only(self):
        """Testa criação apenas com estratégia baseada em prompts."""
        mock_ai_client = Mock()
        
        manager = create_auto_repair_manager(
            ai_client=mock_ai_client,
            enable_pattern_based=False,
            enable_prompt_based=True
        )
        
        assert len(manager.strategies) == 1
        assert isinstance(manager.strategies[0], PromptBasedRepairStrategy)
    
    def test_create_no_strategies(self):
        """Testa criação sem estratégias."""
        manager = create_auto_repair_manager(
            ai_client=None,
            enable_pattern_based=False,
            enable_prompt_based=False
        )
        
        assert len(manager.strategies) == 0


class TestRepairResult:
    """Testes para RepairResult."""
    
    def test_repair_result_properties(self):
        """Testa propriedades do RepairResult."""
        metadata = RepairMetadata(
            strategy_name="test",
            error_type=ErrorType.SYNTAX_ERROR,
            original_error="test error",
            repair_attempts=1,
            success=True,
            confidence=0.8,
            repair_time_seconds=0.1,
            applied_fixes=["fix1"],
            remaining_issues=[]
        )
        
        result = RepairResult(
            repaired_code="fixed code",
            explanation="Fixed",
            metadata=metadata,
            success=True
        )
        
        assert result.confidence == 0.8
        assert result.success is True
        assert result.repaired_code == "fixed code"


if __name__ == "__main__":
    pytest.main([__file__])
