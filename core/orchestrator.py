"""Orquestrador de execução com auto-repair integrado.

Implementa fluxo completo de execução, validação e reparo automático
usando Strategy Pattern e seguindo princípios SOLID.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from utils.executor_v2 import (
    EnhancedExecutor, 
    ExecutionResult, 
    ExecutionStatus,
    create_executor
)
from utils.auto_repair import (
    AutoRepairManager,
    RepairResult,
    create_auto_repair_manager
)
from core.pipeline import CodeSolver, SolveRequest, SolveResult
from utils.logger import get_logger


class ValidationProtocol(Protocol):
    """Protocolo para estratégias de validação de solução."""
    
    def validate_solution(
        self,
        code: str,
        tests: str,
        language: str,
        working_directory: Path
    ) -> ValidationResult:
        """Valida se a solução está correta."""
        ...


@dataclass
class ValidationResult:
    """Resultado da validação da solução."""
    success: bool
    stdout: str
    stderr: str
    return_code: Optional[int]
    execution_time: float
    issues: List[str]
    suggestions: List[str]


class CodeValidationStrategy:
    """Estratégia de validação de código executável."""
    
    def __init__(self, executor: EnhancedExecutor, logger_name: str = "code_validator"):
        self.executor = executor
        self.logger = get_logger(logger_name)
    
    def validate_solution(
        self,
        code: str,
        tests: str,
        language: str,
        working_directory: Path
    ) -> ValidationResult:
        """
        Valida solução executando código e testes.
        
        Args:
            code: Código da solução
            tests: Código dos testes
            language: Linguagem de programação
            working_directory: Diretório de trabalho
            
        Returns:
            Resultado da validação
        """
        issues: List[str] = []
        suggestions: List[str] = []
        
        # Prepara arquivos para execução
        code_file = working_directory / f"solution.{self._get_extension(language)}"
        test_file = working_directory / f"test_solution.{self._get_extension(language)}"
        
        try:
            # Escreve arquivos
            code_file.write_text(code, encoding='utf-8')
            test_file.write_text(tests, encoding='utf-8')
            
            # Executa testes
            if language == "python":
                return self._validate_python(code_file, test_file, working_directory)
            else:
                return self._validate_generic(code_file, test_file, language, working_directory)
                
        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            return ValidationResult(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=None,
                execution_time=0.0,
                issues=[f"Validation error: {e}"],
                suggestions=[]
            )
    
    def _validate_python(
        self,
        code_file: Path,
        test_file: Path,
        working_directory: Path
    ) -> ValidationResult:
        """Validação específica para Python."""
        import time
        start_time = time.time()
        
        # Tenta executar testes com pytest primeiro
        try:
            result = self.executor.execute(
                command=["python", "-m", "pytest", str(test_file), "-v"],
                working_directory=working_directory,
                timeout_seconds=30
            )
            
            if result.succeeded:
                return ValidationResult(
                    success=True,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    return_code=result.returncode,
                    execution_time=time.time() - start_time,
                    issues=[],
                    suggestions=[]
                )
            else:
                return ValidationResult(
                    success=False,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    return_code=result.returncode,
                    execution_time=time.time() - start_time,
                    issues=["Test execution failed"],
                    suggestions=["Check test syntax and logic"]
                )
                
        except Exception:
            # Fallback para execução manual dos testes
            pass
        
        # Executa teste diretamente
        try:
            result = self.executor.execute(
                command=["python", str(test_file)],
                working_directory=working_directory,
                timeout_seconds=30
            )
            
            execution_time = time.time() - start_time
            
            if result.succeeded:
                return ValidationResult(
                    success=True,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    return_code=result.returncode,
                    execution_time=execution_time,
                    issues=[],
                    suggestions=[]
                )
            else:
                return ValidationResult(
                    success=False,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    return_code=result.returncode,
                    execution_time=execution_time,
                    issues=[f"Test failed: {result.stderr}"],
                    suggestions=["Fix test failures"]
                )
                
        except Exception as e:
            return ValidationResult(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=None,
                execution_time=time.time() - start_time,
                issues=[f"Execution error: {e}"],
                suggestions=["Check code syntax"]
            )
    
    def _validate_generic(
        self,
        code_file: Path,
        test_file: Path,
        language: str,
        working_directory: Path
    ) -> ValidationResult:
        """Validação genérica para outras linguagens."""
        import time
        start_time = time.time()
        
        # Tenta compilar/executar baseado na linguagem
        commands = self._get_execution_command(language, code_file, test_file)
        
        for command in commands:
            try:
                result = self.executor.execute(
                    command=command,
                    working_directory=working_directory,
                    timeout_seconds=30
                )
                
                if result.succeeded:
                    return ValidationResult(
                        success=True,
                        stdout=result.stdout,
                        stderr=result.stderr,
                        return_code=result.returncode,
                        execution_time=time.time() - start_time,
                        issues=[],
                        suggestions=[]
                    )
                    
            except Exception as e:
                continue  # Tenta próximo comando
        
        return ValidationResult(
            success=False,
            stdout="",
            stderr="Could not execute code",
            return_code=None,
            execution_time=time.time() - start_time,
            issues=["Execution failed for all commands"],
            suggestions=["Check language support"]
        )
    
    def _get_extension(self, language: str) -> str:
        """Retorna extensão de arquivo para linguagem."""
        extensions = {
            "python": "py",
            "javascript": "js",
            "typescript": "ts",
            "java": "java",
            "go": "go",
            "rust": "rs",
            "cpp": "cpp",
            "c": "c"
        }
        return extensions.get(language, "txt")
    
    def _get_execution_command(
        self, 
        language: str, 
        code_file: Path, 
        test_file: Path
    ) -> List[List[str]]:
        """Retorna comandos de execução para linguagem."""
        commands = []
        
        if language == "javascript":
            commands.extend([
                ["node", str(code_file)],
                ["node", str(test_file)]
            ])
        elif language == "typescript":
            commands.extend([
                ["ts-node", str(code_file)],
                ["ts-node", str(test_file)]
            ])
        elif language == "java":
            # Compila e executa
            class_name = code_file.stem
            commands.extend([
                ["javac", str(code_file)],
                ["java", "-cp", str(code_file.parent), class_name]
            ])
        elif language == "go":
            commands.extend([
                ["go", "run", str(code_file)],
                ["go", "test", str(test_file)]
            ])
        elif language == "rust":
            commands.extend([
                ["rustc", str(code_file), "-o", "program"],
                ["./program"]
            ])
        elif language in ["cpp", "c"]:
            executable = code_file.parent / "program"
            commands.extend([
                ["g++", str(code_file), "-o", str(executable)],
                [str(executable)]
            ])
        
        return commands


class ExecutionOrchestrator:
    """
    Orquestrador de execução com auto-repair integrado.
    
    Implementa fluxo completo: gerar código -> executar -> validar -> reparar
    usando Strategy Pattern e Inversão de Dependência.
    """
    
    def __init__(
        self,
        code_solver: CodeSolver,
        executor: Optional[EnhancedExecutor] = None,
        auto_repair_manager: Optional[AutoRepairManager] = None,
        validator: Optional[ValidationProtocol] = None,
        max_repair_attempts: int = 3,
        logger_name: str = "execution_orchestrator"
    ) -> None:
        """
        Inicializa orquestrador com dependências injetadas.
        
        Args:
            code_solver: Solver para gerar código
            executor: Executor para rodar código (opcional)
            auto_repair_manager: Gerenciador de auto-repair (opcional)
            validator: Validador de soluções (opcional)
            max_repair_attempts: Máximo de tentativas de reparo
            logger_name: Nome do logger
        """
        self.code_solver = code_solver
        self.executor = executor or create_executor("sandbox")
        self.auto_repair_manager = auto_repair_manager or create_auto_repair_manager(
            ai_client=code_solver.client if hasattr(code_solver, 'client') else None
        )
        self.validator = validator or CodeValidationStrategy(self.executor)
        self.max_repair_attempts = max_repair_attempts
        self.logger = get_logger(logger_name)
    
    def solve_with_auto_repair(
        self,
        problem: str,
        language: str = "python",
        mode: str = "fast",
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Resolve problema com ciclo completo de execução e auto-repair.
        
        Args:
            problem: Descrição do problema
            language: Linguagem de programação
            mode: Modo de resolução
            **kwargs: Argumentos adicionais
            
        Returns:
            Dicionário com resultado completo do processo
        """
        self.logger.info(f"Starting solve-with-auto-repair for {language}")
        
        # 1. Gera solução inicial
        solve_request = SolveRequest(
            problem=problem,
            language=language,
            mode=mode,
            auto_repair=True,  # Habilita auto-repair
            **kwargs
        )
        
        initial_result = self.code_solver.solve(solve_request)
        
        # 2. Valida solução inicial
        with tempfile.TemporaryDirectory() as temp_dir:
            working_dir = Path(temp_dir)
            
            validation_result = self.validator.validate_solution(
                code=initial_result.code,
                tests=initial_result.tests,
                language=language,
                working_directory=working_dir
            )
            
            self.logger.info(
                f"Initial validation: {'SUCCESS' if validation_result.success else 'FAILED'}"
            )
            
            # Se validação inicial falhar, tenta reparar
            if not validation_result.success:
                return self._attempt_repair_cycle(
                    initial_result=initial_result,
                    validation_result=validation_result,
                    problem=problem,
                    language=language,
                    working_directory=working_dir,
                    **kwargs
                )
            
            # Se validação inicial sucesso, retorna resultado
            return self._build_final_result(
                solve_result=initial_result,
                validation_result=validation_result,
                repair_attempts=0,
                repair_history=[]
            )
    
    def _attempt_repair_cycle(
        self,
        initial_result: SolveResult,
        validation_result: ValidationResult,
        problem: str,
        language: str,
        working_directory: Path,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Tenta ciclo de reparo automático.
        
        Args:
            initial_result: Resultado inicial da solução
            validation_result: Resultado da validação que falhou
            problem: Problema original
            language: Linguagem
            working_directory: Diretório de trabalho
            **kwargs: Argumentos adicionais
            
        Returns:
            Resultado final do processo
        """
        repair_history: List[Dict[str, Any]] = []
        current_code = initial_result.code
        current_tests = initial_result.tests
        
        # Simula resultado de execução para o reparo
        execution_result = ExecutionResult(
            command=["python", "solution.py"],
            returncode=validation_result.return_code,
            stdout=validation_result.stdout,
            stderr=validation_result.stderr,
            status=ExecutionStatus.ERROR,
            duration_seconds=validation_result.execution_time,
            timeout_seconds=30,
            working_directory=working_directory,
            security_violations=[],
            metadata={}
        )
        
        for attempt in range(self.max_repair_attempts):
            self.logger.info(f"Repair attempt {attempt + 1}/{self.max_repair_attempts}")
            
            # Tenta reparar o código
            repair_result = self.auto_repair_manager.attempt_repair(
                execution_result=execution_result,
                original_code=current_code,
                problem_context=problem,
                language=language,
                **kwargs
            )
            
            # Registra tentativa de reparo
            repair_history.append({
                "attempt": attempt + 1,
                "strategy": repair_result.metadata.strategy_name,
                "success": repair_result.success,
                "confidence": repair_result.confidence,
                "explanation": repair_result.explanation,
                "applied_fixes": repair_result.metadata.applied_fixes
            })
            
            if not repair_result.success:
                self.logger.warning(f"Repair attempt {attempt + 1} failed")
                continue
            
            # Atualiza código com versão reparada
            current_code = repair_result.repaired_code
            
            # Revalida código reparado
            new_validation = self.validator.validate_solution(
                code=current_code,
                tests=current_tests,
                language=language,
                working_directory=working_directory
            )
            
            if new_validation.success:
                self.logger.info(f"Repair successful on attempt {attempt + 1}")
                
                # Cria resultado final com código reparado
                final_result = initial_result
                final_result.code = current_code
                final_result.validation = {
                    "status": "passed",
                    "errors": [],
                    "details": {}
                }
                final_result.metadata["repair_applied"] = True
                final_result.metadata["repair_attempts"] = attempt + 1
                
                return self._build_final_result(
                    solve_result=final_result,
                    validation_result=new_validation,
                    repair_attempts=attempt + 1,
                    repair_history=repair_history
                )
            else:
                # Atualiza execution_result para próxima tentativa
                execution_result.stderr = new_validation.stderr
                execution_result.stdout = new_validation.stdout
                execution_result.return_code = new_validation.return_code
        
        # Todas as tentativas falharam
        self.logger.error("All repair attempts failed")
        
        return self._build_final_result(
            solve_result=initial_result,
            validation_result=validation_result,
            repair_attempts=self.max_repair_attempts,
            repair_history=repair_history
        )
    
    def _build_final_result(
        self,
        solve_result: SolveResult,
        validation_result: ValidationResult,
        repair_attempts: int,
        repair_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Constrói resultado final do processo.
        
        Args:
            solve_result: Resultado da solução
            validation_result: Resultado da validação
            repair_attempts: Número de tentativas de reparo
            repair_history: Histórico de reparos
            
        Returns:
            Dicionário com resultado completo
        """
        return {
            "problem": solve_result.problem,
            "language": solve_result.language,
            "code": solve_result.code,
            "tests": solve_result.tests,
            "filename": solve_result.filename,
            "test_filename": solve_result.test_filename,
            "explanation": solve_result.explanation,
            "validation": {
                "success": validation_result.success,
                "stdout": validation_result.stdout,
                "stderr": validation_result.stderr,
                "return_code": validation_result.return_code,
                "execution_time": validation_result.execution_time,
                "issues": validation_result.issues,
                "suggestions": validation_result.suggestions
            },
            "repair": {
                "attempts": repair_attempts,
                "success": validation_result.success,
                "history": repair_history
            },
            "metadata": {
                **solve_result.metadata,
                "auto_repair_enabled": True,
                "total_repair_attempts": repair_attempts
            }
        }


# Factory function para criação fácil

def create_execution_orchestrator(
    base_dir: Path,
    config: Dict[str, Any],
    **kwargs: Any
) -> ExecutionOrchestrator:
    """
    Factory function para criar ExecutionOrchestrator.
    
    Args:
        base_dir: Diretório base do projeto
        config: Configuração do CodeSolver
        **kwargs: Argumentos adicionais
        
    Returns:
        Instância do ExecutionOrchestrator
    """
    # Cria CodeSolver
    code_solver = CodeSolver.from_config(base_dir / "config.yaml")
    
    # Cria executor
    executor = create_executor("sandbox")
    
    # Cria auto-repair manager
    auto_repair_manager = create_auto_repair_manager(
        ai_client=getattr(code_solver, 'client', None),
        enable_pattern_based=True,
        enable_prompt_based=True
    )
    
    return ExecutionOrchestrator(
        code_solver=code_solver,
        executor=executor,
        auto_repair_manager=auto_repair_manager,
        **kwargs
    )
