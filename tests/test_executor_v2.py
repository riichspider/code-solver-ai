"""Testes unitários para executor_v2.

Valida Strategy Pattern, validação de segurança e type hints.
"""

from __future__ import annotations

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from utils.executor_v2 import (
    EnhancedExecutor,
    SandboxExecutionStrategy,
    DockerExecutionStrategy,
    SecurityValidator,
    ExecutionStatus,
    ExecutionResult,
    create_executor
)


class TestSecurityValidator:
    """Testes para SecurityValidator."""
    
    def setup_method(self):
        """Setup para cada teste."""
        self.validator = SecurityValidator()
    
    def test_validate_safe_command(self):
        """Testa validação de comando seguro."""
        safe_command = ["python", "script.py", "--verbose"]
        violations = self.validator.validate_command(safe_command)
        assert violations == []
    
    def test_validate_dangerous_command(self):
        """Testa validação de comando perigoso."""
        dangerous_command = ["rm", "-rf", "/"]
        violations = self.validator.validate_command(dangerous_command)
        assert len(violations) > 0
        assert any("perigoso" in v.lower() for v in violations)
    
    def test_validate_command_injection(self):
        """Testa detecção de injeção de comando."""
        injection_command = ["python", "script.py; rm -rf /"]
        violations = self.validator.validate_command(injection_command)
        assert len(violations) > 0
        assert any("injeção" in v.lower() for v in violations)
    
    def test_validate_working_directory_safe(self):
        """Testa validação de diretório seguro."""
        with tempfile.TemporaryDirectory() as temp_dir:
            safe_dir = Path(temp_dir)
            violations = self.validator.validate_working_directory(safe_dir)
            assert violations == []
    
    def test_validate_working_directory_nonexistent(self):
        """Testa validação de diretório inexistente."""
        nonexistent = Path("/nonexistent/path")
        violations = self.validator.validate_working_directory(nonexistent)
        assert len(violations) > 0
        assert any("não existe" in v for v in violations)
    
    def test_sanitize_command(self):
        """Testa sanitização de comando."""
        dirty_command = ["python", "script.py;rm", "-rf", "/tmp"]
        sanitized = self.validator.sanitize_command(dirty_command)
        assert ";" not in " ".join(sanitized)
        assert "python" in sanitized


class TestSandboxExecutionStrategy:
    """Testes para SandboxExecutionStrategy."""
    
    def setup_method(self):
        """Setup para cada teste."""
        self.strategy = SandboxExecutionStrategy()
        self.temp_dir = Path(tempfile.mkdtemp())
    
    def teardown_method(self):
        """Cleanup após cada teste."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_execute_simple_command(self):
        """Testa execução de comando simples."""
        command = ["python", "-c", "print('Hello, World!')"]
        
        result = self.strategy.execute(
            command=command,
            working_directory=self.temp_dir,
            timeout_seconds=10
        )
        
        assert result.command == command
        assert result.returncode == 0
        assert "Hello, World!" in result.stdout
        assert result.status == ExecutionStatus.SUCCESS
        assert result.succeeded is True
        assert result.timed_out is False
    
    def test_execute_failing_command(self):
        """Testa execução de comando que falha."""
        command = ["python", "-c", "exit(1)"]
        
        result = self.strategy.execute(
            command=command,
            working_directory=self.temp_dir,
            timeout_seconds=10
        )
        
        assert result.returncode == 1
        assert result.status == ExecutionStatus.ERROR
        assert result.succeeded is False
        assert result.failed is True
    
    def test_execute_timeout_command(self):
        """Testa execução com timeout."""
        command = ["python", "-c", "import time; time.sleep(30)"]
        
        result = self.strategy.execute(
            command=command,
            working_directory=self.temp_dir,
            timeout_seconds=2
        )
        
        assert result.timed_out is True
        assert result.status == ExecutionStatus.TIMEOUT
        assert result.succeeded is False
        assert result.failed is True


class TestDockerExecutionStrategy:
    """Testes para DockerExecutionStrategy."""
    
    def setup_method(self):
        """Setup para cada teste."""
        self.strategy = DockerExecutionStrategy()
        self.temp_dir = Path(tempfile.mkdtemp())
    
    def teardown_method(self):
        """Cleanup após cada teste."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('subprocess.run')
    def test_docker_command_construction(self, mock_run):
        """Testa construção de comando Docker."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Hello from Docker",
            stderr=""
        )
        
        command = ["python", "script.py"]
        
        self.strategy.execute(
            command=command,
            working_directory=self.temp_dir,
            timeout_seconds=10,
            docker_image="python:3.11-slim"
        )
        
        # Verifica se subprocess.run foi chamado com comando Docker
        called_args = mock_run.call_args[0][0]
        assert called_args[0] == "docker"
        assert "run" in called_args
        assert "python:3.11-slim" in called_args


class TestEnhancedExecutor:
    """Testes para EnhancedExecutor."""
    
    def setup_method(self):
        """Setup para cada teste."""
        self.strategy = Mock()
        self.validator = SecurityValidator()
        self.executor = EnhancedExecutor(
            strategy=self.strategy,
            security_validator=self.validator
        )
        self.temp_dir = Path(tempfile.mkdtemp())
    
    def teardown_method(self):
        """Cleanup após cada teste."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_execute_with_string_command(self):
        """Testa execução com comando em string."""
        mock_result = ExecutionResult(
            command=["python", "script.py"],
            returncode=0,
            stdout="Hello",
            stderr="",
            status=ExecutionStatus.SUCCESS,
            duration_seconds=0.1,
            timeout_seconds=10,
            working_directory=self.temp_dir,
            security_violations=[],
            metadata={}
        )
        
        self.strategy.execute.return_value = mock_result
        
        result = self.executor.execute(
            command="python script.py",
            working_directory=self.temp_dir
        )
        
        assert result.command == ["python", "script.py"]
        assert result.succeeded is True
    
    def test_execute_with_list_command(self):
        """Testa execução com comando em lista."""
        mock_result = ExecutionResult(
            command=["python", "script.py"],
            returncode=0,
            stdout="Hello",
            stderr="",
            status=ExecutionStatus.SUCCESS,
            duration_seconds=0.1,
            timeout_seconds=10,
            working_directory=self.temp_dir,
            security_violations=[],
            metadata={}
        )
        
        self.strategy.execute.return_value = mock_result
        
        result = self.executor.execute(
            command=["python", "script.py"],
            working_directory=self.temp_dir
        )
        
        assert result.command == ["python", "script.py"]
        assert result.succeeded is True
    
    def test_execute_with_security_validation(self):
        """Testa execução com validação de segurança."""
        mock_result = ExecutionResult(
            command=["python", "script.py"],
            returncode=0,
            stdout="Hello",
            stderr="",
            status=ExecutionStatus.SUCCESS,
            duration_seconds=0.1,
            timeout_seconds=10,
            working_directory=self.temp_dir,
            security_violations=["Comando sanitizado"],
            metadata={}
        )
        
        self.strategy.execute.return_value = mock_result
        
        result = self.executor.execute(
            command=["python", "script.py;rm", "-rf"],
            working_directory=self.temp_dir,
            validate_security=True
        )
        
        assert len(result.security_violations) > 0
        assert result.succeeded is True
    
    def test_change_strategy(self):
        """Testa mudança de estratégia em runtime."""
        new_strategy = Mock()
        
        self.executor.change_strategy(new_strategy)
        
        assert self.executor.strategy == new_strategy
    
    def test_execute_with_metadata(self):
        """Testa execução com metadados customizados."""
        mock_result = ExecutionResult(
            command=["python", "script.py"],
            returncode=0,
            stdout="Hello",
            stderr="",
            status=ExecutionStatus.SUCCESS,
            duration_seconds=0.1,
            timeout_seconds=10,
            working_directory=self.temp_dir,
            security_violations=[],
            metadata={"custom": "value"}
        )
        
        self.strategy.execute.return_value = mock_result
        
        result = self.executor.execute(
            command=["python", "script.py"],
            working_directory=self.temp_dir,
            metadata={"custom": "value"}
        )
        
        assert result.metadata["custom"] == "value"


class TestFactoryFunction:
    """Testes para factory function."""
    
    def test_create_sandbox_executor(self):
        """Testa criação de executor sandbox."""
        executor = create_executor(strategy_type="sandbox")
        
        assert isinstance(executor.strategy, SandboxExecutionStrategy)
        assert isinstance(executor.security_validator, SecurityValidator)
    
    def test_create_docker_executor(self):
        """Testa criação de executor Docker."""
        executor = create_executor(strategy_type="docker")
        
        assert isinstance(executor.strategy, DockerExecutionStrategy)
        assert isinstance(executor.security_validator, SecurityValidator)
    
    def test_create_invalid_strategy(self):
        """Testa criação com estratégia inválida."""
        with pytest.raises(ValueError, match="Estratégia desconhecida"):
            create_executor(strategy_type="invalid")


class TestExecutionResult:
    """Testes para ExecutionResult."""
    
    def test_success_property(self):
        """Testa propriedade succeeded."""
        result = ExecutionResult(
            command=["test"],
            returncode=0,
            stdout="",
            stderr="",
            status=ExecutionStatus.SUCCESS,
            duration_seconds=0.1,
            timeout_seconds=10,
            working_directory=Path("."),
            security_violations=[],
            metadata={}
        )
        
        assert result.succeeded is True
        assert result.failed is False
    
    def test_failed_property(self):
        """Testa propriedade failed."""
        result = ExecutionResult(
            command=["test"],
            returncode=1,
            stdout="",
            stderr="Error",
            status=ExecutionStatus.ERROR,
            duration_seconds=0.1,
            timeout_seconds=10,
            working_directory=Path("."),
            security_violations=[],
            metadata={}
        )
        
        assert result.succeeded is False
        assert result.failed is True
    
    def test_timed_out_property(self):
        """Testa propriedade timed_out."""
        result = ExecutionResult(
            command=["test"],
            returncode=None,
            stdout="",
            stderr="Timeout",
            status=ExecutionStatus.TIMEOUT,
            duration_seconds=30.0,
            timeout_seconds=10,
            working_directory=Path("."),
            security_violations=[],
            metadata={}
        )
        
        assert result.timed_out is True
        assert result.failed is True


if __name__ == "__main__":
    pytest.main([__file__])
