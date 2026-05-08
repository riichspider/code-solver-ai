"""Validador de cache para evitar repetição de falhas.

Implementa verificação inteligente de cache de falhas antes de gerar soluções,
seguindo SOLID principles com type hints rigorosos.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from pathlib import Path

from utils.smart_cache_v3 import (
    SmartCacheV3, 
    ModelInfo, 
    ValidationStatus, 
    CacheEntryMetadata,
    CacheEntryType
)
from utils.logger import get_logger


@dataclass
class FailureAnalysisResult:
    """Resultado da análise de falhas cacheadas."""
    has_recent_failures: bool
    failure_count: int
    failure_entries: List[CacheEntryMetadata]
    recommended_action: str
    confidence_to_succeed: float
    
    @property
    def should_skip_generation(self) -> bool:
        """Verifica se deve pular geração devido a falhas recentes."""
        return self.has_recent_failures and self.confidence_to_succeed < 0.3


class CacheFailureValidator:
    """
    Validador de cache de falhas para evitar repetição de erros.
    
    Implementa Single Responsibility Principle com type hints rigorosos.
    """
    
    def __init__(
        self,
        cache: SmartCacheV3,
        max_failure_hours: int = 24,
        max_failure_count: int = 3,
        min_confidence_threshold: float = 0.3,
        logger_name: str = "cache_failure_validator"
    ) -> None:
        """
        Inicializa validador de falhas.
        
        Args:
            cache: Instância do cache inteligente
            max_failure_hours: Horas para considerar falha como recente
            max_failure_count: Número máximo de falhas permitidas
            min_confidence_threshold: Confiança mínima para tentar novamente
            logger_name: Nome do logger
        """
        self.cache = cache
        self.max_failure_hours = max_failure_hours
        self.max_failure_count = max_failure_count
        self.min_confidence_threshold = min_confidence_threshold
        self.logger = get_logger(logger_name)
    
    def validate_before_generation(
        self,
        problem: str,
        model_info: ModelInfo,
        language: str,
        mode: str,
        context_text: str = ""
    ) -> FailureAnalysisResult:
        """
        Valida se deve gerar solução baseado em falhas cacheadas.
        
        Args:
            problem: Texto do problema
            model_info: Informações do modelo
            language: Linguagem de programação
            mode: Modo de execução
            context_text: Texto de contexto
            
        Returns:
            Análise de falhas com recomendação
        """
        self.logger.info(
            f"Validating cache failures for problem with model {model_info.get_full_identifier()}"
        )
        
        # Busca falhas recentes
        recent_failures = self.cache.has_recent_failure(
            problem=problem,
            model_info=model_info,
            language=language,
            mode=mode,
            context_text=context_text,
            hours=self.max_failure_hours
        )
        
        failure_count = len(recent_failures)
        
        self.logger.info(f"Found {failure_count} recent failures in last {self.max_failure_hours}h")
        
        if failure_count == 0:
            return FailureAnalysisResult(
                has_recent_failures=False,
                failure_count=0,
                failure_entries=[],
                recommended_action="proceed_with_generation",
                confidence_to_succeed=1.0
            )
        
        # Analisa padrões das falhas
        analysis = self._analyze_failure_patterns(recent_failures)
        
        # Calcula confiança baseada no histórico
        confidence = self._calculate_success_confidence(recent_failures)
        
        # Determina ação recomendada
        recommended_action = self._determine_recommended_action(
            failure_count, confidence, analysis
        )
        
        return FailureAnalysisResult(
            has_recent_failures=True,
            failure_count=failure_count,
            failure_entries=recent_failures,
            recommended_action=recommended_action,
            confidence_to_succeed=confidence
        )
    
    def cache_failure(
        self,
        problem: str,
        model_info: ModelInfo,
        language: str,
        mode: str,
        validation_error: str,
        validation_status: ValidationStatus,
        context_text: str = "",
        retry_count: int = 0
    ) -> None:
        """
        Cacheia uma falha de validação.
        
        Args:
            problem: Texto do problema
            model_info: Informações do modelo
            language: Linguagem de programação
            mode: Modo de execução
            validation_error: Erro de validação
            validation_status: Status da validação
            context_text: Texto de contexto
            retry_count: Número de tentativas
        """
        self.logger.info(
            f"Caching failure for {model_info.get_full_identifier()} "
            f"with status: {validation_status.value}"
        )
        
        self.cache.set_failure(
            problem=problem,
            model_info=model_info,
            language=language,
            mode=mode,
            validation_error=validation_error,
            validation_status=validation_status,
            context_text=context_text,
            retry_count=retry_count
        )
    
    def get_failure_summary(
        self,
        problem: str,
        model_info: ModelInfo,
        language: str,
        mode: str,
        context_text: str = ""
    ) -> Dict[str, Any]:
        """
        Obtém resumo das falhas para análise.
        
        Args:
            problem: Texto do problema
            model_info: Informações do modelo
            language: Linguagem de programação
            mode: Modo de execução
            context_text: Texto de contexto
            
        Returns:
            Dicionário com resumo das falhas
        """
        recent_failures = self.cache.has_recent_failure(
            problem=problem,
            model_info=model_info,
            language=language,
            mode=mode,
            context_text=context_text,
            hours=self.max_failure_hours
        )
        
        if not recent_failures:
            return {
                "has_failures": False,
                "failure_count": 0,
                "failure_types": [],
                "most_common_error": None,
                "retry_counts": []
            }
        
        # Analisa tipos de falha
        failure_types = list(set(f.validation_status.value for f in recent_failures))
        
        # Erro mais comum
        error_messages = [f.validation_error_message for f in recent_failures if f.validation_error_message]
        most_common_error = max(set(error_messages), key=error_messages.count) if error_messages else None
        
        # Contagens de retry
        retry_counts = [f.retry_count for f in recent_failures]
        
        return {
            "has_failures": True,
            "failure_count": len(recent_failures),
            "failure_types": failure_types,
            "most_common_error": most_common_error,
            "retry_counts": retry_counts,
            "average_retry_count": sum(retry_counts) / len(retry_counts) if retry_counts else 0,
            "oldest_failure": min(f.created_at for f in recent_failures).isoformat(),
            "newest_failure": max(f.created_at for f in recent_failures).isoformat()
        }
    
    def _analyze_failure_patterns(self, failures: List[CacheEntryMetadata]) -> Dict[str, Any]:
        """Analisa padrões nas falhas cacheadas."""
        patterns = {
            "validation_statuses": list(set(f.validation_status.value for f in failures if f.validation_status)),
            "error_types": [],
            "retry_distribution": {},
            "time_distribution": {}
        }
        
        # Analisa distribuição de retry
        retry_counts = [f.retry_count for f in failures]
        for count in set(retry_counts):
            patterns["retry_distribution"][str(count)] = retry_counts.count(count)
        
        # Analisa distribuição temporal
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        
        for hours in [1, 6, 12, 24]:
            cutoff = now - timedelta(hours=hours)
            count = sum(1 for f in failures if f.created_at > cutoff)
            patterns["time_distribution"][f"last_{hours}h"] = count
        
        return patterns
    
    def _calculate_success_confidence(self, failures: List[CacheEntryMetadata]) -> float:
        """Calcula confiança de sucesso baseada no histórico de falhas."""
        if not failures:
            return 1.0
        
        # Fatores que reduzem confiança
        failure_count = len(failures)
        avg_retry_count = sum(f.retry_count for f in failures) / failure_count
        
        # Penalidade baseada no número de falhas
        failure_penalty = min(failure_count * 0.2, 0.6)
        
        # Penalidade baseada em retry count
        retry_penalty = min(avg_retry_count * 0.1, 0.3)
        
        # Verifica se há falhas recentes (últimas 6 horas)
        from datetime import datetime, timezone, timedelta
        recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
        recent_failures = sum(1 for f in failures if f.created_at > recent_cutoff)
        
        if recent_failures > 0:
            recent_penalty = min(recent_failures * 0.15, 0.4)
        else:
            recent_penalty = 0.0
        
        # Confiança base = 1.0 - penalidades
        confidence = 1.0 - failure_penalty - retry_penalty - recent_penalty
        return max(0.0, confidence)
    
    def _determine_recommended_action(
        self,
        failure_count: int,
        confidence: float,
        analysis: Dict[str, Any]
    ) -> str:
        """Determina ação recomendada baseada na análise."""
        
        if failure_count >= self.max_failure_count:
            return "skip_generation_too_many_failures"
        
        if confidence < self.min_confidence_threshold:
            return "skip_generation_low_confidence"
        
        if failure_count >= 2 and confidence < 0.5:
            return "try_different_model"
        
        if failure_count == 1 and confidence >= 0.6:
            return "proceed_with_caution"
        
        return "proceed_with_generation"


class CacheIntegrationHelper:
    """
    Helper para integração do cache de falhas com o pipeline.
    
    Facilita o uso do CacheFailureValidator no fluxo principal.
    """
    
    def __init__(
        self,
        cache: SmartCacheV3,
        validator: Optional[CacheFailureValidator] = None,
        logger_name: str = "cache_integration_helper"
    ) -> None:
        """
        Inicializa helper de integração.
        
        Args:
            cache: Instância do cache inteligente
            validator: Validador de falhas (opcional)
            logger_name: Nome do logger
        """
        self.cache = cache
        self.validator = validator or CacheFailureValidator(cache)
        self.logger = get_logger(logger_name)
    
    def should_attempt_generation(
        self,
        problem: str,
        model_info: ModelInfo,
        language: str,
        mode: str,
        context_text: str = ""
    ) -> tuple[bool, str, Optional[FailureAnalysisResult]]:
        """
        Verifica se deve tentar gerar solução.
        
        Args:
            problem: Texto do problema
            model_info: Informações do modelo
            language: Linguagem
            mode: Modo
            context_text: Texto de contexto
            
        Returns:
            Tuple (deve_tentar, razão, análise)
        """
        analysis = self.validator.validate_before_generation(
            problem=problem,
            model_info=model_info,
            language=language,
            mode=mode,
            context_text=context_text
        )
        
        should_attempt = not analysis.should_skip_generation
        reason = analysis.recommended_action
        
        self.logger.info(
            f"Generation decision: {should_attempt} (reason: {reason}, "
            f"confidence: {analysis.confidence_to_succeed:.2f})"
        )
        
        return should_attempt, reason, analysis
    
    def handle_generation_failure(
        self,
        problem: str,
        model_info: ModelInfo,
        language: str,
        mode: str,
        validation_error: str,
        validation_status: ValidationStatus,
        context_text: str = "",
        retry_count: int = 0
    ) -> None:
        """
        Lida com falha na geração, cacheando para evitar repetição.
        
        Args:
            problem: Texto do problema
            model_info: Informações do modelo
            language: Linguagem
            mode: Modo
            validation_error: Erro de validação
            validation_status: Status da validação
            context_text: Texto de contexto
            retry_count: Número de tentativas
        """
        self.validator.cache_failure(
            problem=problem,
            model_info=model_info,
            language=language,
            mode=mode,
            validation_error=validation_error,
            validation_status=validation_status,
            context_text=context_text,
            retry_count=retry_count
        )
        
        self.logger.warning(
            f"Cached failure for {model_info.get_full_identifier()}: "
            f"{validation_status.value} - {validation_error[:100]}"
        )
    
    def get_failure_insights(
        self,
        problem: str,
        model_info: ModelInfo,
        language: str,
        mode: str,
        context_text: str = ""
    ) -> Dict[str, Any]:
        """
        Obtém insights sobre falhas para debugging.
        
        Args:
            problem: Texto do problema
            model_info: Informações do modelo
            language: Linguagem
            mode: Modo
            context_text: Texto de contexto
            
        Returns:
            Insights detalhados sobre as falhas
        """
        summary = self.validator.get_failure_summary(
            problem=problem,
            model_info=model_info,
            language=language,
            mode=mode,
            context_text=context_text
        )
        
        # Adiciona recomendações
        recommendations = []
        
        if summary["has_failures"]:
            if summary["failure_count"] >= 3:
                recommendations.append("Consider using a different model")
            
            if summary["average_retry_count"] > 1:
                recommendations.append("Problem may be too complex for current model")
            
            if "failed" in summary.get("failure_types", []):
                recommendations.append("Review problem requirements and constraints")
        
        summary["recommendations"] = recommendations
        
        return summary


# Factory function

def create_cache_validator(
    cache: SmartCacheV3,
    max_failure_hours: int = 24,
    max_failure_count: int = 3,
    min_confidence_threshold: float = 0.3
) -> CacheFailureValidator:
    """
    Factory function para criar CacheFailureValidator.
    
    Args:
        cache: Instância do cache inteligente
        max_failure_hours: Horas para considerar falha como recente
        max_failure_count: Número máximo de falhas permitidas
        min_confidence_threshold: Confiança mínima para tentar novamente
        
    Returns:
        Instância do CacheFailureValidator
    """
    return CacheFailureValidator(
        cache=cache,
        max_failure_hours=max_failure_hours,
        max_failure_count=max_failure_count,
        min_confidence_threshold=min_confidence_threshold
    )
