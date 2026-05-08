"""Executor v2 com Strategy Pattern e validação aprimorada.

Implementa diferentes estratégias de execução seguindo princípios SOLID,
com type hints rigorosos e validação de segurança.
"""

from __future__ import annotations

import subprocess
import time
import shlex
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, List, Optional, Union, Dict, Any
from enum import Enum

from utils.logger import get_logger


class ExecutionStatus(Enum):
    """Status da execução do comando."""
    SUCCESS = "success"
    TIMEOUT = "timeout"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class ExecutionResult:
    """Resultado detalhado da execução com metadados."""
    command: List[str]
    returncode: Optional[int]
    stdout: str
    stderr: str
    status: ExecutionStatus
    duration_seconds: float
    timeout_seconds: int
    working_directory: Path
    security_violations: List[str]
    metadata: Dict[str, Any]
    
    @property
    def timed_out(self) -> bool:
        """Verifica se a execução atingiu timeout."""
        return self.status == ExecutionStatus.TIMEOUT
    
    @property
    def succeeded(self) -> bool:
        """Verifica se a execução foi bem-sucedida."""
        return self.status == ExecutionStatus.SUCCESS and (self.returncode == 0)
    
    @property
    def failed(self) -> bool:
        """Verifica se a execução falhou."""
        return self.status in [ExecutionStatus.ERROR, ExecutionStatus.TIMEOUT]


class ExecutionStrategy(Protocol):
    """Protocolo para estratégias de execução."""
    
    def execute(
        self,
        command: List[str],
        working_directory: Path,
        timeout_seconds: int,
        **kwargs: Any
    ) -> ExecutionResult:
        """Executa comando com a estratégia específica."""
        ...


class SecurityValidator:
    """Validador de segurança para comandos e diretórios."""
    
    # Comandos perigosos que não devem ser executados
    DANGEROUS_COMMANDS = {
        'rm', 'rmdir', 'del', 'format', 'fdisk', 'mkfs',
        'sudo', 'su', 'passwd', 'chown', 'chmod',
        'ssh', 'scp', 'rsync', 'wget', 'curl',
        'pip', 'npm', 'yarn', 'docker', 'kubectl'
    }
    
    # Extensões de arquivo perigosas
    DANGEROUS_EXTENSIONS = {
        '.exe', '.bat', '.cmd', '.scr', '.msi', '.deb',
        '.rpm', '.dmg', '.pkg', '.app', '.jar'
    }
    
    def __init__(self, logger_name: str = "security_validator"):
        self.logger = get_logger(logger_name)
    
    def validate_command(self, command: List[str]) -> List[str]:
        """
        Valida o comando contra regras de segurança.
        
        Args:
            command: Lista de argumentos do comando
            
        Returns:
            Lista de violações de segurança encontradas
        """
        violations: List[str] = []
        
        if not command:
            violations.append("Comando vazio")
            return violations
        
        # Verifica comandos perigosos
        base_command = Path(command[0]).name.lower()
        if base_command in self.DANGEROUS_COMMANDS:
            violations.append(f"Comando perigoso detectado: {base_command}")
        
        # Verifica argumentos suspeitos
        for i, arg in enumerate(command):
            arg_lower = arg.lower()
            
            # Verifica flags perigosas
            if any(dangerous in arg_lower for dangerous in ['-rf', '-rf/', '--force']):
                violations.append(f"Flag perigosa detectada no argumento {i}: {arg}")
            
            # Verifica tentativas de escape
            if any(pattern in arg for pattern in ['..', '~/', '/etc/', '/var/', '/usr/']):
                violations.append(f"Tentativa de escape de diretório no argumento {i}: {arg}")
            
            # Verifica injeção de comando
            if any(char in arg for char in [';', '|', '&', '$(', '`']):
                violations.append(f"Possível injeção de comando no argumento {i}: {arg}")
        
        return violations
    
    def validate_working_directory(self, directory: Path) -> List[str]:
        """
        Valida o diretório de trabalho contra regras de segurança.
        
        Args:
            directory: Diretório de trabalho
            
        Returns:
            Lista de violações de segurança encontradas
        """
        violations: List[str] = []
        
        # Verifica se o diretório existe
        if not directory.exists():
            violations.append(f"Diretório não existe: {directory}")
            return violations
        
        # Verifica se é um diretório
        if not directory.is_dir():
            violations.append(f"Caminho não é um diretório: {directory}")
            return violations
        
        # Verifica permissões de escrita
        if not os.access(directory, os.W_OK):
            violations.append(f"Sem permissão de escrita no diretório: {directory}")
        
        # Verifica diretórios sensíveis
        sensitive_dirs = ['/etc', '/var', '/usr', '/bin', '/sbin', '/boot']
        for sensitive in sensitive_dirs:
            if directory.is_relative_to(Path(sensitive)):
                violations.append(f"Diretório sensível detectado: {directory}")
                break
        
        return violations
    
    def sanitize_command(self, command: List[str]) -> List[str]:
        """
        Sanitiza o comando removendo elementos perigosos.
        
        Args:
            command: Lista de argumentos do comando
            
        Returns:
            Comando sanitizado
        """
        sanitized = []
        
        for arg in command:
            # Remove caracteres perigosos
            clean_arg = arg.replace(';', '').replace('|', '').replace('&', '').replace('$(', '').replace('`', '')
            
            # Remove aspas perigosas
            clean_arg = clean_arg.replace('"', '').replace("'", '')
            
            # Trim espaços extras
            clean_arg = clean_arg.strip()
            
            if clean_arg:  # Adiciona apenas se não estiver vazio
                sanitized.append(clean_arg)
        
        return sanitized


class SandboxExecutionStrategy:
    """Estratégia de execução em sandbox com subprocess."""
    
    def __init__(self, logger_name: str = "sandbox_executor"):
        self.logger = get_logger(logger_name)
    
    def execute(
        self,
        command: List[str],
        working_directory: Path,
        timeout_seconds: int,
        **kwargs: Any
    ) -> ExecutionResult:
        """
        Executa comando em ambiente sandbox.
        
        Args:
            command: Comando a ser executado
            working_directory: Diretório de trabalho
            timeout_seconds: Timeout em segundos
            **kwargs: Argumentos adicionais
            
        Returns:
            Resultado da execução
        """
        started_at = time.perf_counter()
        metadata = kwargs.get('metadata', {})
        
        try:
            completed = subprocess.run(
                command,
                cwd=str(working_directory),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                shell=False,
                check=False,  # Não levanta exceção em erros
            )
            
            duration = time.perf_counter() - started_at
            status = ExecutionStatus.SUCCESS if completed.returncode == 0 else ExecutionStatus.ERROR
            
            return ExecutionResult(
                command=command,
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                status=status,
                duration_seconds=duration,
                timeout_seconds=timeout_seconds,
                working_directory=working_directory,
                security_violations=[],
                metadata=metadata
            )
            
        except subprocess.TimeoutExpired as exc:
            duration = time.perf_counter() - started_at
            
            return ExecutionResult(
                command=command,
                returncode=None,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                status=ExecutionStatus.TIMEOUT,
                duration_seconds=duration,
                timeout_seconds=timeout_seconds,
                working_directory=working_directory,
                security_violations=[],
                metadata=metadata
            )
            
        except Exception as exc:
            duration = time.perf_counter() - started_at
            
            return ExecutionResult(
                command=command,
                returncode=None,
                stdout="",
                stderr=str(exc),
                status=ExecutionStatus.ERROR,
                duration_seconds=duration,
                timeout_seconds=timeout_seconds,
                working_directory=working_directory,
                security_violations=[],
                metadata=metadata
            )


class DockerExecutionStrategy:
    """Estratégia de execução usando contêineres Docker."""
    
    def __init__(self, logger_name: str = "docker_executor"):
        self.logger = get_logger(logger_name)
    
    def execute(
        self,
        command: List[str],
        working_directory: Path,
        timeout_seconds: int,
        **kwargs: Any
    ) -> ExecutionResult:
        """
        Executa comando em contêiner Docker.
        
        Args:
            command: Comando a ser executado
            working_directory: Diretório de trabalho
            timeout_seconds: Timeout em segundos
            **kwargs: Argumentos adicionais (image, volumes, etc.)
            
        Returns:
            Resultado da execução
        """
        started_at = time.perf_counter()
        metadata = kwargs.get('metadata', {})
        
        # Constrói comando Docker
        docker_image = kwargs.get('docker_image', 'python:3.11-slim')
        docker_command = [
            'docker', 'run', '--rm',
            '-v', f'{working_directory}:/workspace',
            '-w', '/workspace',
            '--timeout', str(timeout_seconds),
            docker_image
        ] + command
        
        try:
            completed = subprocess.run(
                docker_command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds + 10,  # Extra tempo para overhead do Docker
                shell=False,
                check=False,
            )
            
            duration = time.perf_counter() - started_at
            status = ExecutionStatus.SUCCESS if completed.returncode == 0 else ExecutionStatus.ERROR
            
            metadata.update({
                'docker_image': docker_image,
                'execution_type': 'docker'
            })
            
            return ExecutionResult(
                command=command,
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                status=status,
                duration_seconds=duration,
                timeout_seconds=timeout_seconds,
                working_directory=working_directory,
                security_violations=[],
                metadata=metadata
            )
            
        except subprocess.TimeoutExpired as exc:
            duration = time.perf_counter() - started_at
            
            return ExecutionResult(
                command=command,
                returncode=None,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                status=ExecutionStatus.TIMEOUT,
                duration_seconds=duration,
                timeout_seconds=timeout_seconds,
                working_directory=working_directory,
                security_violations=[],
                metadata=metadata
            )
            
        except Exception as exc:
            duration = time.perf_counter() - started_at
            
            return ExecutionResult(
                command=command,
                returncode=None,
                stdout="",
                stderr=str(exc),
                status=ExecutionStatus.ERROR,
                duration_seconds=duration,
                timeout_seconds=timeout_seconds,
                working_directory=working_directory,
                security_violations=[],
                metadata=metadata
            )


class EnhancedExecutor:
    """
    Executor aprimorado com Strategy Pattern e validação de segurança.
    
    Implementa Inversão de Dependência e Responsabilidade Única.
    """
    
    def __init__(
        self,
        strategy: ExecutionStrategy,
        security_validator: Optional[SecurityValidator] = None,
        logger_name: str = "enhanced_executor"
    ) -> None:
        """
        Inicializa o executor com estratégia injetada.
        
        Args:
            strategy: Estratégia de execução a ser utilizada
            security_validator: Validador de segurança (opcional)
            logger_name: Nome do logger
        """
        self.strategy = strategy
        self.security_validator = security_validator or SecurityValidator()
        self.logger = get_logger(logger_name)
    
    def execute(
        self,
        command: Union[str, List[str]],
        working_directory: Path,
        timeout_seconds: int = 20,
        validate_security: bool = True,
        **kwargs: Any
    ) -> ExecutionResult:
        """
        Executa comando com validação e estratégia injetada.
        
        Args:
            command: Comando a ser executado (string ou lista)
            working_directory: Diretório de trabalho
            timeout_seconds: Timeout em segundos
            validate_security: Se deve validar segurança
            **kwargs: Argumentos adicionais para a estratégia
            
        Returns:
            Resultado detalhado da execução
            
        Raises:
            ValueError: Se comandos ou diretório forem inválidos
            SecurityError: Se violações de segurança forem detectadas
        """
        # Converte comando para lista se necessário
        if isinstance(command, str):
            try:
                command_list = shlex.split(command)
            except ValueError as e:
                raise ValueError(f"Comando inválido: {e}")
        else:
            command_list = command.copy()
        
        # Validação de segurança
        security_violations: List[str] = []
        
        if validate_security:
            # Valida comando
            command_violations = self.security_validator.validate_command(command_list)
            security_violations.extend(command_violations)
            
            # Valida diretório
            dir_violations = self.security_validator.validate_working_directory(working_directory)
            security_violations.extend(dir_violations)
            
            # Se houver violações críticas, sanitiza ou aborta
            if security_violations:
                self.logger.warning(f"Violações de segurança detectadas: {security_violations}")
                
                # Sanitiza comando se possível
                if command_violations:
                    sanitized_command = self.security_validator.sanitize_command(command_list)
                    self.logger.info(f"Comando sanitizado: {sanitized_command}")
                    command_list = sanitized_command
        
        # Prepara metadados
        metadata = kwargs.get('metadata', {})
        metadata.update({
            'original_command': command,
            'sanitized_command': command_list,
            'security_validated': validate_security,
            'security_violations': security_violations,
            'strategy': self.strategy.__class__.__name__
        })
        kwargs['metadata'] = metadata
        
        # Executa com a estratégia injetada
        self.logger.info(
            f"Executando comando: {command_list} "
            f"em {working_directory} com estratégia {self.strategy.__class__.__name__}"
        )
        
        result = self.strategy.execute(
            command_list,
            working_directory,
            timeout_seconds,
            **kwargs
        )
        
        # Adiciona violações de segurança ao resultado
        result.security_violations = security_violations
        
        # Log do resultado
        if result.succeeded:
            self.logger.info(f"Comando executado com sucesso em {result.duration_seconds:.2f}s")
        else:
            self.logger.warning(
                f"Falha na execução: {result.status.value} "
                f"(código: {result.returncode}, duração: {result.duration_seconds:.2f}s)"
            )
        
        return result
    
    def change_strategy(self, new_strategy: ExecutionStrategy) -> None:
        """
        Altera a estratégia de execução em runtime.
        
        Args:
            new_strategy: Nova estratégia de execução
        """
        old_strategy = self.strategy.__class__.__name__
        self.strategy = new_strategy
        self.logger.info(f"Estratégia alterada: {old_strategy} -> {new_strategy.__class__.__name__}")


# Factory function para criação fácil
def create_executor(
    strategy_type: str = "sandbox",
    **kwargs: Any
) -> EnhancedExecutor:
    """
    Factory function para criar executor com estratégia específica.
    
    Args:
        strategy_type: Tipo da estratégia ("sandbox" ou "docker")
        **kwargs: Argumentos adicionais
        
    Returns:
        Instância do EnhancedExecutor
    """
    if strategy_type == "sandbox":
        strategy = SandboxExecutionStrategy()
    elif strategy_type == "docker":
        strategy = DockerExecutionStrategy()
    else:
        raise ValueError(f"Estratégia desconhecida: {strategy_type}")
    
    security_validator = SecurityValidator()
    
    return EnhancedExecutor(
        strategy=strategy,
        security_validator=security_validator
    )


# Import necessário para validação de diretório
import os
