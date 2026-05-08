"""Sistema de Auto-Repair com Strategy Pattern.

Implementa diferentes estratégias de correção automática de código
baseado em erros de execução, seguindo princípios SOLID.
"""

from __future__ import annotations

import abc
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol, List, Dict, Any, Optional, Tuple

from utils.logger import get_logger
from utils.executor_v2 import ExecutionResult, ExecutionStatus


class RepairStrategy(Protocol):
    """Protocolo para estratégias de reparo automático."""
    
    def can_repair(self, execution_result: ExecutionResult) -> bool:
        """Verifica se pode reparar o erro."""
        ...
    
    def repair(
        self,
        execution_result: ExecutionResult,
        original_code: str,
        problem_context: str,
        language: str,
        **kwargs: Any
    ) -> Tuple[str, str, RepairMetadata]:
        """
        Tenta reparar o código.
        
        Args:
            execution_result: Resultado da execução com erro
            original_code: Código original que falhou
            problem_context: Contexto do problema
            language: Linguagem de programação
            **kwargs: Argumentos adicionais
            
        Returns:
            Tupla (código_reparado, explicação, metadados)
        """
        ...
    
    def get_name(self) -> str:
        """Nome da estratégia de reparo."""
        ...


class ErrorType(Enum):
    """Tipos de erro que podem ser reparados."""
    SYNTAX_ERROR = "syntax_error"
    RUNTIME_ERROR = "runtime_error"
    IMPORT_ERROR = "import_error"
    TYPE_ERROR = "type_error"
    NAME_ERROR = "name_error"
    ATTRIBUTE_ERROR = "attribute_error"
    INDEX_ERROR = "index_error"
    KEY_ERROR = "key_error"
    VALUE_ERROR = "value_error"
    TIMEOUT_ERROR = "timeout_error"
    MEMORY_ERROR = "memory_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class RepairMetadata:
    """Metadados do processo de reparo."""
    strategy_name: str
    error_type: ErrorType
    original_error: str
    repair_attempts: int
    success: bool
    confidence: float
    repair_time_seconds: float
    applied_fixes: List[str]
    remaining_issues: List[str]


@dataclass
class RepairResult:
    """Resultado do processo de reparo."""
    repaired_code: str
    explanation: str
    metadata: RepairMetadata
    success: bool
    
    @property
    def confidence(self) -> float:
        """Confiança no reparo."""
        return self.metadata.confidence


class ErrorClassifier:
    """Classificador de erros para identificar tipo de problema."""
    
    def __init__(self):
        self.logger = get_logger("error_classifier")
        
        # Padrões para diferentes tipos de erro
        self.error_patterns = {
            ErrorType.SYNTAX_ERROR: [
                r"SyntaxError:",
                r"Invalid syntax",
                r"unexpected EOF",
                r"unexpected indent",
                r"expected an indented block",
                r"'def' statement",
                r"missing parentheses",
                r"EOL while scanning string literal"
            ],
            ErrorType.IMPORT_ERROR: [
                r"ImportError:",
                r"ModuleNotFoundError:",
                r"No module named",
                r"cannot import name",
                r"No module named"
            ],
            ErrorType.TYPE_ERROR: [
                r"TypeError:",
                r"unsupported operand type",
                r"must be.*not",
                r"takes.*arguments",
                r"missing.*required positional argument"
            ],
            ErrorType.NAME_ERROR: [
                r"NameError:",
                r"name '.*' is not defined",
                r"global name '.*' is not defined"
            ],
            ErrorType.ATTRIBUTE_ERROR: [
                r"AttributeError:",
                r"has no attribute",
                r"object has no attribute"
            ],
            ErrorType.INDEX_ERROR: [
                r"IndexError:",
                r"list index out of range",
                r"string index out of range"
            ],
            ErrorType.KEY_ERROR: [
                r"KeyError:",
                r"not found in"
            ],
            ErrorType.VALUE_ERROR: [
                r"ValueError:",
                r"invalid literal",
                r"could not convert"
            ],
            ErrorType.MEMORY_ERROR: [
                r"MemoryError:",
                r"out of memory",
                r"cannot allocate"
            ],
            ErrorType.TIMEOUT_ERROR: [
                r"timeout",
                r"timed out"
            ]
        }
    
    def classify_error(self, execution_result: ExecutionResult) -> ErrorType:
        """
        Classifica o tipo de erro baseado na saída de erro.
        
        Args:
            execution_result: Resultado da execução com erro
            
        Returns:
            Tipo de erro identificado
        """
        error_output = execution_result.stderr.lower()
        
        # Verifica timeout primeiro
        if execution_result.timed_out:
            return ErrorType.TIMEOUT_ERROR
        
        # Procura padrões específicos
        import re
        for error_type, patterns in self.error_patterns.items():
            for pattern in patterns:
                if re.search(pattern, error_output, re.IGNORECASE):
                    self.logger.debug(f"Error classified as {error_type.value}")
                    return error_type
        
        # Se não encontrar padrão específico
        self.logger.warning("Could not classify error, treating as unknown")
        return ErrorType.UNKNOWN_ERROR


class PromptBasedRepairStrategy:
    """Estratégia de reparo baseada em prompts para IA."""
    
    def __init__(self, ai_client, logger_name: str = "prompt_repair"):
        self.ai_client = ai_client
        self.logger = get_logger(logger_name)
    
    def can_repair(self, execution_result: ExecutionResult) -> bool:
        """Verifica se pode reparar usando IA."""
        # Pode reparar a maioria dos erros exceto problemas de sistema
        if execution_result.timed_out:
            return False  # Timeout geralmente requer mudança de abordagem
        
        error_classifier = ErrorClassifier()
        error_type = error_classifier.classify_error(execution_result)
        
        # Não tenta reparar erros muito complexos
        non_repairable = {
            ErrorType.MEMORY_ERROR,
            ErrorType.TIMEOUT_ERROR
        }
        
        return error_type not in non_repairable
    
    def repair(
        self,
        execution_result: ExecutionResult,
        original_code: str,
        problem_context: str,
        language: str,
        **kwargs: Any
    ) -> Tuple[str, str, RepairMetadata]:
        """
        Tenta reparar usando IA para analisar o erro.
        
        Args:
            execution_result: Resultado com erro
            original_code: Código original
            problem_context: Contexto do problema
            language: Linguagem
            **kwargs: Argumentos adicionais
            
        Returns:
            Código reparado, explicação e metadados
        """
        import time
        start_time = time.time()
        
        error_classifier = ErrorClassifier()
        error_type = error_classifier.classify_error(execution_result)
        
        # Constrói prompt de reparo
        repair_prompt = self._build_repair_prompt(
            original_code=original_code,
            error_output=execution_result.stderr,
            problem_context=problem_context,
            language=language,
            error_type=error_type
        )
        
        try:
            # Envia para IA
            response = self.ai_client.generate_text(
                system_prompt=self._get_system_prompt(language),
                user_prompt=repair_prompt,
                json_mode=True
            )
            
            # Processa resposta
            repair_data = response.get('content', '{}')
            if isinstance(repair_data, str):
                import json
                try:
                    repair_data = json.loads(repair_data)
                except json.JSONDecodeError:
                    # Se não for JSON, trata como texto simples
                    repair_data = {"repaired_code": repair_data, "explanation": "Reparo gerado"}
            
            repaired_code = repair_data.get('repaired_code', original_code)
            explanation = repair_data.get('explanation', 'Código reparado baseado no erro')
            applied_fixes = repair_data.get('applied_fixes', ['Correção automática'])
            confidence = repair_data.get('confidence', 0.7)
            
            # Validação básica
            if repaired_code == original_code:
                confidence = 0.3  # Baixa confiança se não mudou nada
            
            repair_time = time.time() - start_time
            
            metadata = RepairMetadata(
                strategy_name=self.get_name(),
                error_type=error_type,
                original_error=execution_result.stderr,
                repair_attempts=1,
                success=repaired_code != original_code,
                confidence=confidence,
                repair_time_seconds=repair_time,
                applied_fixes=applied_fixes,
                remaining_issues=[]
            )
            
            return repaired_code, explanation, metadata
            
        except Exception as e:
            self.logger.error(f"Failed to repair with AI: {e}")
            
            # Retorno fallback sem modificações
            repair_time = time.time() - start_time
            metadata = RepairMetadata(
                strategy_name=self.get_name(),
                error_type=error_type,
                original_error=execution_result.stderr,
                repair_attempts=1,
                success=False,
                confidence=0.0,
                repair_time_seconds=repair_time,
                applied_fixes=[],
                remaining_issues=[str(e)]
            )
            
            return original_code, f"Falha no reparo: {e}", metadata
    
    def _build_repair_prompt(
        self,
        original_code: str,
        error_output: str,
        problem_context: str,
        language: str,
        error_type: ErrorType
    ) -> str:
        """Constrói prompt para reparo."""
        
        return f"""Analise o erro a seguir e corrija o código {language}.

**Problema Original:**
{problem_context}

**Código com Erro:**
```{language}
{original_code}
```

**Erro de Execução:**
{error_output}

**Tipo de Erro Identificado:**
{error_type.value}

**Instruções:**
1. Analise cuidadosamente o erro e o código
2. Identifique a causa raiz do problema
3. Corrija apenas o necessário para resolver o erro
4. Mantenha a lógica original intacta
5. Não adicione funcionalidades extras
6. Preserve a estrutura e estilo do código

**Resposta esperada (formato JSON):**
{{
    "repaired_code": "Código corrigido",
    "explanation": "Explicação clara do que foi corrigido e por quê",
    "applied_fixes": ["lista", "das", "correções", "aplicadas"],
    "confidence": 0.9
}}"""
    
    def _get_system_prompt(self, language: str) -> str:
        """Retorna prompt de sistema específico para linguagem."""
        return f"""Você é um especialista em debugging e reparo de código {language}.

Sua missão é analisar erros de execução e fornecer correções precisas.
Foque em:
- Identificar a causa exata do erro
- Fazer o mínimo de alterações necessárias
- Manter a funcionalidade original
- Explicar claramente o que foi corrigido

Seja conciso e preciso nas suas correções."""
    
    def get_name(self) -> str:
        """Nome da estratégia."""
        return "prompt_based_repair"


class PatternBasedRepairStrategy:
    """Estratégia de reparo baseada em padrões conhecidos."""
    
    def __init__(self, logger_name: str = "pattern_repair"):
        self.logger = get_logger(logger_name)
        
        # Padrões de reparo comuns
        self.repair_patterns = {
            ErrorType.SYNTAX_ERROR: [
                # Correção de indentação
                (r'^(\s+)(def|class|if|for|while|try|with)', self._fix_indentation),
                # Correção de dois-pontos faltando
                (r'(def|class|if|for|while|try|with)([^\n:]+)\s*$', self._add_colon),
                # Correção de parênteses
                (r'print\s+[^(]', self._fix_print_statement),
            ],
            ErrorType.IMPORT_ERROR: [
                # Sugestão de imports alternativos
                (r'No module named \'(.*)\'', self._suggest_import_fix),
            ],
            ErrorType.NAME_ERROR: [
                # Variáveis não definidas comuns
                (r"name '(.*)' is not defined", self._fix_undefined_variable),
            ],
            ErrorType.TYPE_ERROR: [
                # Conversões de tipo
                (r"can't multiply sequence by non-int of type 'str'", self._fix_string_multiplication),
                (r"can only concatenate str", self._fix_string_concatenation),
            ],
            ErrorType.INDEX_ERROR: [
                # Verificação de limites
                (r"list index out of range", self._add_bounds_check),
            ]
        }
    
    def can_repair(self, execution_result: ExecutionResult) -> bool:
        """Verifica se pode reparar baseado em padrões."""
        error_classifier = ErrorClassifier()
        error_type = error_classifier.classify_error(execution_result)
        
        # Verifica se tem padrões para este tipo de erro
        return error_type in self.repair_patterns
    
    def repair(
        self,
        execution_result: ExecutionResult,
        original_code: str,
        problem_context: str,
        language: str,
        **kwargs: Any
    ) -> Tuple[str, str, RepairMetadata]:
        """
        Tenta reparar usando padrões conhecidos.
        
        Args:
            execution_result: Resultado com erro
            original_code: Código original
            problem_context: Contexto do problema
            language: Linguagem
            **kwargs: Argumentos adicionais
            
        Returns:
            Código reparado, explicação e metadados
        """
        import time
        start_time = time.time()
        
        error_classifier = ErrorClassifier()
        error_type = error_classifier.classify_error(execution_result)
        
        repaired_code = original_code
        applied_fixes = []
        
        # Aplica padrões de reparo
        if error_type in self.repair_patterns:
            for pattern, fix_function in self.repair_patterns[error_type]:
                import re
                if re.search(pattern, execution_result.stderr, re.IGNORECASE):
                    try:
                        new_code = fix_function(repaired_code, execution_result.stderr)
                        if new_code != repaired_code:
                            repaired_code = new_code
                            applied_fixes.append(f"Applied pattern: {pattern}")
                    except Exception as e:
                        self.logger.warning(f"Pattern fix failed: {e}")
        
        repair_time = time.time() - start_time
        success = repaired_code != original_code
        
        if success:
            explanation = f"Código reparado usando {len(applied_fixes)} padrões de correção"
            confidence = 0.6  # Confiança moderada para reparos baseados em padrões
        else:
            explanation = "Nenhum padrão de reparo aplicável encontrado"
            confidence = 0.0
        
        metadata = RepairMetadata(
            strategy_name=self.get_name(),
            error_type=error_type,
            original_error=execution_result.stderr,
            repair_attempts=1,
            success=success,
            confidence=confidence,
            repair_time_seconds=repair_time,
            applied_fixes=applied_fixes,
            remaining_issues=[] if success else ["No applicable patterns found"]
        )
        
        return repaired_code, explanation, metadata
    
    def _fix_indentation(self, code: str, error_output: str) -> str:
        """Corrige problemas de indentação."""
        lines = code.split('\n')
        fixed_lines = []
        
        for line in lines:
            # Corrige indentação inconsistente
            if line.strip() and not line.startswith('    ') and not line.startswith('\t'):
                # Adiciona indentação padrão para blocos
                if any(keyword in line.strip() for keyword in ['def', 'class', 'if', 'for', 'while', 'try', 'with']):
                    fixed_lines.append('    ' + line)
                else:
                    fixed_lines.append(line)
            else:
                fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    def _add_colon(self, code: str, error_output: str) -> str:
        """Adiciona dois-pontos faltando."""
        import re
        # Adiciona dois-pontos após definições de função/classe/condicionais
        return re.sub(r'(def|class|if|for|while|try|with)([^\n:]+)\s*$', r'\1\2:', code, flags=re.MULTILINE)
    
    def _fix_print_statement(self, code: str, error_output: str) -> str:
        """Corrige statement print sem parênteses (Python 2 vs 3)."""
        import re
        # Converte print "texto" para print("texto")
        return re.sub(r'print\s+([^(].*?)$', r'print(\1)', code, flags=re.MULTILINE)
    
    def _suggest_import_fix(self, code: str, error_output: str) -> str:
        """Sugere correção para import error."""
        import re
        match = re.search(r"No module named '(.*)'", error_output)
        if match:
            module_name = match.group(1)
            
            # Sugestões comuns
            suggestions = {
                'tkinter': 'try:\n    import tkinter\nexcept ImportError:\n    import Tkinter as tkinter',
                'configparser': 'try:\n    import configparser\nexcept ImportError:\n    import ConfigParser as configparser',
                'queue': 'try:\n    import queue\nexcept ImportError:\n    import Queue as queue'
            }
            
            if module_name in suggestions:
                return suggestions[module_name] + '\n\n' + code
        
        return code
    
    def _fix_undefined_variable(self, code: str, error_output: str) -> str:
        """Tenta corrigir variáveis não definidas."""
        import re
        match = re.search(r"name '(.*)' is not defined", error_output)
        if match:
            var_name = match.group(1)
            
            # Adiciona definição padrão para variáveis comuns
            if var_name in ['i', 'j', 'k']:
                return f"for {var_name} in range(len(data)):\n    pass\n\n" + code
            elif var_name in ['data', 'result', 'output']:
                return f"{var_name} = []\n" + code
        
        return code
    
    def _fix_string_multiplication(self, code: str, error_output: str) -> str:
        """Corrige multiplicação de string por string."""
        import re
        # Converte "a" * "b" para int("a") * "b" ou similar
        return re.sub(r'"([^"]*)"\s*\*\s*"([^"]*)"', r'int(\1) * "\2"', code)
    
    def _fix_string_concatenation(self, code: str, error_output: str) -> str:
        """Corrige concatenação de tipos incompatíveis."""
        import re
        # Converte str + number para str(number)
        return re.sub(r'(\w+)\s*\+\s*(\d+)', r'str(\1) + str(\2)', code)
    
    def _add_bounds_check(self, code: str, error_output: str) -> str:
        """Adiciona verificação de limites."""
        # Esta é uma correção mais complexa, por ora apenas adiciona comentário
        return "# TODO: Add bounds check for list access\n" + code
    
    def get_name(self) -> str:
        """Nome da estratégia."""
        return "pattern_based_repair"


class AutoRepairManager:
    """
    Gerenciador de auto-repair com múltiplas estratégias.
    
    Implementa Strategy Pattern para selecionar melhor abordagem.
    """
    
    def __init__(
        self,
        strategies: List[RepairStrategy],
        max_attempts: int = 3,
        logger_name: str = "auto_repair_manager"
    ) -> None:
        """
        Inicializa gerenciador com estratégias injetadas.
        
        Args:
            strategies: Lista de estratégias de reparo
            max_attempts: Número máximo de tentativas
            logger_name: Nome do logger
        """
        self.strategies = strategies
        self.max_attempts = max_attempts
        self.logger = get_logger(logger_name)
        self.error_classifier = ErrorClassifier()
    
    def attempt_repair(
        self,
        execution_result: ExecutionResult,
        original_code: str,
        problem_context: str,
        language: str,
        **kwargs: Any
    ) -> RepairResult:
        """
        Tenta reparar o código usando múltiplas estratégias.
        
        Args:
            execution_result: Resultado da execução com erro
            original_code: Código original que falhou
            problem_context: Contexto do problema
            language: Linguagem de programação
            **kwargs: Argumentos adicionais
            
        Returns:
            Resultado do processo de reparo
        """
        if not execution_result.failed:
            self.logger.warning("No repair needed - execution succeeded")
            return RepairResult(
                repaired_code=original_code,
                explanation="No repair needed",
                metadata=RepairMetadata(
                    strategy_name="none",
                    error_type=ErrorType.UNKNOWN_ERROR,
                    original_error="",
                    repair_attempts=0,
                    success=True,
                    confidence=1.0,
                    repair_time_seconds=0.0,
                    applied_fixes=[],
                    remaining_issues=[]
                ),
                success=True
            )
        
        error_type = self.error_classifier.classify_error(execution_result)
        self.logger.info(f"Attempting repair for {error_type.value}")
        
        best_result = None
        best_confidence = 0.0
        
        # Tenta cada estratégia em ordem
        for strategy in self.strategies:
            if not strategy.can_repair(execution_result):
                self.logger.debug(f"Strategy {strategy.get_name()} cannot repair this error")
                continue
            
            try:
                self.logger.info(f"Trying strategy: {strategy.get_name()}")
                
                repaired_code, explanation, metadata = strategy.repair(
                    execution_result=execution_result,
                    original_code=original_code,
                    problem_context=problem_context,
                    language=language,
                    **kwargs
                )
                
                # Atualiza melhor resultado
                if metadata.confidence > best_confidence:
                    best_confidence = metadata.confidence
                    best_result = RepairResult(
                        repaired_code=repaid_code,
                        explanation=explanation,
                        metadata=metadata,
                        success=metadata.success
                    )
                
                self.logger.info(
                    f"Strategy {strategy.get_name()} completed with "
                    f"confidence: {metadata.confidence:.2f}"
                )
                
                # Se encontrou solução com alta confiança, para
                if metadata.confidence >= 0.8:
                    break
                    
            except Exception as e:
                self.logger.error(f"Strategy {strategy.get_name()} failed: {e}")
                continue
        
        if best_result is None:
            # Nenhuma estratégia funcionou
            self.logger.error("All repair strategies failed")
            
            metadata = RepairMetadata(
                strategy_name="none",
                error_type=error_type,
                original_error=execution_result.stderr,
                repair_attempts=len(self.strategies),
                success=False,
                confidence=0.0,
                repair_time_seconds=0.0,
                applied_fixes=[],
                remaining_issues=["All strategies failed"]
            )
            
            return RepairResult(
                repaired_code=original_code,
                explanation="Nenhuma estratégia de reparo disponível para este erro",
                metadata=metadata,
                success=False
            )
        
        self.logger.info(
            f"Best repair result: {best_result.metadata.strategy_name} "
            f"(confidence: {best_result.confidence:.2f})"
        )
        
        return best_result


# Factory function para criação fácil

def create_auto_repair_manager(
    ai_client=None,
    enable_pattern_based: bool = True,
    enable_prompt_based: bool = True,
    max_attempts: int = 3
) -> AutoRepairManager:
    """
    Factory function para criar AutoRepairManager com estratégias padrão.
    
    Args:
        ai_client: Cliente IA para estratégia baseada em prompt
        enable_pattern_based: Se deve incluir estratégia baseada em padrões
        enable_prompt_based: Se deve incluir estratégia baseada em prompts
        max_attempts: Número máximo de tentativas
        
    Returns:
        Instância do AutoRepairManager
    """
    strategies: List[RepairStrategy] = []
    
    if enable_pattern_based:
        strategies.append(PatternBasedRepairStrategy())
    
    if enable_prompt_based and ai_client is not None:
        strategies.append(PromptBasedRepairStrategy(ai_client))
    
    return AutoRepairManager(
        strategies=strategies,
        max_attempts=max_attempts
    )
