"""Testes unitários para SmartCacheV3 com cache de falhas.

Valida chave otimizada, cache de falhas e integração com pipeline.
"""

from __future__ import annotations

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime, timezone, timedelta

from utils.smart_cache_v3 import (
    SmartCacheV3,
    ModelInfo,
    ValidationStatus,
    CacheEntryType,
    CacheEntryMetadata,
    DefaultCacheKeyBuilder,
    GzipCompressionStrategy,
    JsonSerializationStrategy,
    SQLiteStorageStrategy,
    create_smart_cache_v3
)
from utils.cache_validator import (
    CacheFailureValidator,
    CacheIntegrationHelper,
    FailureAnalysisResult,
    create_cache_validator
)


class TestModelInfo:
    """Testes para ModelInfo."""
    
    def test_model_info_creation(self):
        """Testa criação de ModelInfo."""
        model = ModelInfo(name="qwen2.5-coder", version="latest")
        
        assert model.name == "qwen2.5-coder"
        assert model.version == "latest"
        assert model.ollama_version is None
    
    def test_model_info_with_ollama_version(self):
        """Testa ModelInfo com versão Ollama."""
        model = ModelInfo(
            name="qwen2.5-coder", 
            version="latest", 
            ollama_version="1.1.0"
        )
        
        assert model.get_full_identifier() == "qwen2.5-coder:latest@1.1.0"
    
    def test_model_info_without_ollama_version(self):
        """Testa ModelInfo sem versão Ollama."""
        model = ModelInfo(name="qwen2.5-coder", version="latest")
        
        assert model.get_full_identifier() == "qwen2.5-coder:latest"


class TestDefaultCacheKeyBuilder:
    """Testes para DefaultCacheKeyBuilder."""
    
    def setup_method(self):
        """Setup para cada teste."""
        self.builder = DefaultCacheKeyBuilder()
    
    def test_build_success_key(self):
        """Testa construção de chave de sucesso."""
        key = self.builder.build_success_key(
            problem_hash="abc123",
            model_version="qwen2.5-coder:latest",
            language="python",
            mode="fast",
            context_hash="def456"
        )
        
        assert isinstance(key, str)
        assert len(key) == 64  # SHA256 hash length
        assert key != self.builder.build_success_key(
            problem_hash="different",
            model_version="qwen2.5-coder:latest",
            language="python",
            mode="fast",
            context_hash="def456"
        )
    
    def test_build_failure_key(self):
        """Testa construção de chave de falha."""
        key = self.builder.build_failure_key(
            problem_hash="abc123",
            model_version="qwen2.5-coder:latest",
            language="python",
            mode="fast",
            context_hash="def456",
            validation_error_hash="error789"
        )
        
        assert isinstance(key, str)
        assert len(key) == 64
        assert key != self.builder.build_success_key(
            problem_hash="abc123",
            model_version="qwen2.5-coder:latest",
            language="python",
            mode="fast",
            context_hash="def456"
        )
    
    def test_different_inputs_different_keys(self):
        """Testa que inputs diferentes geram chaves diferentes."""
        key1 = self.builder.build_success_key(
            problem_hash="abc123",
            model_version="qwen2.5-coder:latest",
            language="python",
            mode="fast",
            context_hash="def456"
        )
        
        key2 = self.builder.build_success_key(
            problem_hash="abc123",
            model_version="llama-3.3-70b:latest",
            language="python",
            mode="fast",
            context_hash="def456"
        )
        
        assert key1 != key2


class TestSmartCacheV3:
    """Testes para SmartCacheV3."""
    
    def setup_method(self):
        """Setup para cada teste."""
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # Cria estratégias
        storage = SQLiteStorageStrategy(self.temp_dir / "test.db")
        compression = GzipCompressionStrategy()
        serialization = JsonSerializationStrategy()
        key_builder = DefaultCacheKeyBuilder()
        
        self.cache = SmartCacheV3(
            storage=storage,
            compression_strategy=compression,
            serialization_strategy=serialization,
            key_builder=key_builder,
            max_size_mb=1,
            max_entries=10,
            default_ttl_hours=24
        )
    
    def teardown_method(self):
        """Cleanup após cada teste."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_build_problem_hash(self):
        """Testa construção de hash do problema."""
        problem = "Create a function that calculates fibonacci"
        hash1 = self.cache.build_problem_hash(problem)
        hash2 = self.cache.build_problem_hash(problem)
        
        assert isinstance(hash1, str)
        assert len(hash1) == 64
        assert hash1 == hash2  # Same input should give same hash
    
    def test_build_context_hash(self):
        """Testa construção de hash do contexto."""
        context = "Some context information"
        hash1 = self.cache.build_context_hash(context)
        hash2 = self.cache.build_context_hash(context)
        
        assert isinstance(hash1, str)
        assert len(hash1) == 64
        assert hash1 == hash2
    
    def test_build_validation_error_hash(self):
        """Testa construção de hash de erro de validação."""
        error = "SyntaxError: invalid syntax"
        hash1 = self.cache.build_validation_error_hash(error)
        hash2 = self.cache.build_validation_error_hash(error)
        
        assert isinstance(hash1, str)
        assert len(hash1) == 64
        assert hash1 == hash2
    
    def test_set_and_get_success(self):
        """Testa definir e obter entrada de sucesso."""
        problem = "Test problem"
        model_info = ModelInfo(name="qwen2.5-coder", version="latest")
        language = "python"
        mode = "fast"
        context_text = "Some context"
        value = {"code": "print('hello')", "tests": "assert True"}
        
        # Define entrada
        self.cache.set_success(
            problem=problem,
            model_info=model_info,
            language=language,
            mode=mode,
            value=value,
            context_text=context_text
        )
        
        # Obtém entrada
        result = self.cache.get_success(
            problem=problem,
            model_info=model_info,
            language=language,
            mode=mode,
            context_text=context_text
        )
        
        assert result == value
    
    def test_set_and_get_failure(self):
        """Testa definir e obter entrada de falha."""
        problem = "Test problem"
        model_info = ModelInfo(name="qwen2.5-coder", version="latest")
        language = "python"
        mode = "fast"
        validation_error = "SyntaxError: invalid syntax"
        validation_status = ValidationStatus.FAILED
        context_text = "Some context"
        
        # Define falha
        self.cache.set_failure(
            problem=problem,
            model_info=model_info,
            language=language,
            mode=mode,
            validation_error=validation_error,
            validation_status=validation_status,
            context_text=context_text
        )
        
        # Obtém falha
        result = self.cache.get_failure(
            problem=problem,
            model_info=model_info,
            language=language,
            mode=mode,
            validation_error=validation_error,
            context_text=context_text
        )
        
        assert result is not None
        assert result.validation_status == ValidationStatus.FAILED
        assert result.validation_error_message == validation_error
    
    def test_has_recent_failures(self):
        """Testa verificação de falhas recentes."""
        problem = "Test problem"
        model_info = ModelInfo(name="qwen2.5-coder", version="latest")
        language = "python"
        mode = "fast"
        validation_error = "SyntaxError: invalid syntax"
        validation_status = ValidationStatus.FAILED
        context_text = "Some context"
        
        # Sem falhas inicialmente
        recent_failures = self.cache.has_recent_failure(
            problem=problem,
            model_info=model_info,
            language=language,
            mode=mode,
            context_text=context_text
        )
        assert len(recent_failures) == 0
        
        # Adiciona falha
        self.cache.set_failure(
            problem=problem,
            model_info=model_info,
            language=language,
            mode=mode,
            validation_error=validation_error,
            validation_status=validation_status,
            context_text=context_text
        )
        
        # Verifica falhas recentes
        recent_failures = self.cache.has_recent_failure(
            problem=problem,
            model_info=model_info,
            language=language,
            mode=mode,
            context_text=context_text
        )
        assert len(recent_failures) == 1
        assert recent_failures[0].validation_status == ValidationStatus.FAILED
    
    def test_cache_stats(self):
        """Testa obtenção de estatísticas."""
        stats = self.cache.get_stats()
        
        assert isinstance(stats, type(stats))  # CacheStats type
        assert hasattr(stats, 'total_entries')
        assert hasattr(stats, 'success_entries')
        assert hasattr(stats, 'failure_entries')
        assert hasattr(stats, 'hit_rate')
        assert hasattr(stats, 'miss_rate')
    
    def test_clear_all(self):
        """Testa limpar todas as entries."""
        problem = "Test problem"
        model_info = ModelInfo(name="qwen2.5-coder", version="latest")
        
        # Adiciona entrada
        self.cache.set_success(
            problem=problem,
            model_info=model_info,
            language="python",
            mode="fast",
            value={"test": "data"}
        )
        
        # Verifica que existe
        result = self.cache.get_success(
            problem=problem,
            model_info=model_info,
            language="python",
            mode="fast"
        )
        assert result is not None
        
        # Limpa
        self.cache.clear_all()
        
        # Verifica que não existe mais
        result = self.cache.get_success(
            problem=problem,
            model_info=model_info,
            language="python",
            mode="fast"
        )
        assert result is None


class TestCacheFailureValidator:
    """Testes para CacheFailureValidator."""
    
    def setup_method(self):
        """Setup para cada teste."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cache = create_smart_cache_v3(self.temp_dir)
        self.validator = CacheFailureValidator(self.cache)
    
    def teardown_method(self):
        """Cleanup após cada teste."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_validate_before_generation_no_failures(self):
        """Testa validação sem falhas anteriores."""
        problem = "Test problem"
        model_info = ModelInfo(name="qwen2.5-coder", version="latest")
        
        result = self.validator.validate_before_generation(
            problem=problem,
            model_info=model_info,
            language="python",
            mode="fast"
        )
        
        assert isinstance(result, FailureAnalysisResult)
        assert result.has_recent_failures is False
        assert result.failure_count == 0
        assert result.should_skip_generation is False
        assert result.confidence_to_succeed == 1.0
    
    def test_validate_before_generation_with_failures(self):
        """Testa validação com falhas anteriores."""
        problem = "Test problem"
        model_info = ModelInfo(name="qwen2.5-coder", version="latest")
        
        # Adiciona falha
        self.validator.cache_failure(
            problem=problem,
            model_info=model_info,
            language="python",
            mode="fast",
            validation_error="SyntaxError",
            validation_status=ValidationStatus.FAILED
        )
        
        result = self.validator.validate_before_generation(
            problem=problem,
            model_info=model_info,
            language="python",
            mode="fast"
        )
        
        assert result.has_recent_failures is True
        assert result.failure_count == 1
        assert result.confidence_to_succeed < 1.0
    
    def test_cache_failure(self):
        """Testa cache de falha."""
        problem = "Test problem"
        model_info = ModelInfo(name="qwen2.5-coder", version="latest")
        
        self.validator.cache_failure(
            problem=problem,
            model_info=model_info,
            language="python",
            mode="fast",
            validation_error="SyntaxError: invalid syntax",
            validation_status=ValidationStatus.FAILED,
            retry_count=1
        )
        
        # Verifica que foi cacheada
        result = self.validator.cache.get_failure(
            problem=problem,
            model_info=model_info,
            language="python",
            mode="fast",
            validation_error="SyntaxError: invalid syntax"
        )
        
        assert result is not None
        assert result.validation_status == ValidationStatus.FAILED
        assert result.retry_count == 1
    
    def test_get_failure_summary(self):
        """Testa obtenção de resumo de falhas."""
        problem = "Test problem"
        model_info = ModelInfo(name="qwen2.5-coder", version="latest")
        
        # Adiciona múltiplas falhas
        self.validator.cache_failure(
            problem=problem,
            model_info=model_info,
            language="python",
            mode="fast",
            validation_error="Error 1",
            validation_status=ValidationStatus.FAILED
        )
        
        self.validator.cache_failure(
            problem=problem,
            model_info=model_info,
            language="python",
            mode="fast",
            validation_error="Error 2",
            validation_status=ValidationStatus.FAILED
        )
        
        summary = self.validator.get_failure_summary(
            problem=problem,
            model_info=model_info,
            language="python",
            mode="fast"
        )
        
        assert summary["has_failures"] is True
        assert summary["failure_count"] == 2
        assert "failed" in summary["failure_types"]
        assert summary["average_retry_count"] == 0.0


class TestCacheIntegrationHelper:
    """Testes para CacheIntegrationHelper."""
    
    def setup_method(self):
        """Setup para cada teste."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cache = create_smart_cache_v3(self.temp_dir)
        self.helper = CacheIntegrationHelper(self.cache)
    
    def teardown_method(self):
        """Cleanup após cada teste."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_should_attempt_generation_no_failures(self):
        """Testa decisão de geração sem falhas."""
        problem = "Test problem"
        model_info = ModelInfo(name="qwen2.5-coder", version="latest")
        
        should_attempt, reason, analysis = self.helper.should_attempt_generation(
            problem=problem,
            model_info=model_info,
            language="python",
            mode="fast"
        )
        
        assert should_attempt is True
        assert reason == "proceed_with_generation"
        assert analysis.has_recent_failures is False
    
    def test_should_attempt_generation_with_failures(self):
        """Testa decisão de geração com falhas."""
        problem = "Test problem"
        model_info = ModelInfo(name="qwen2.5-coder", version="latest")
        
        # Adiciona falha
        self.helper.handle_generation_failure(
            problem=problem,
            model_info=model_info,
            language="python",
            mode="fast",
            validation_error="SyntaxError",
            validation_status=ValidationStatus.FAILED
        )
        
        should_attempt, reason, analysis = self.helper.should_attempt_generation(
            problem=problem,
            model_info=model_info,
            language="python",
            mode="fast"
        )
        
        # Ainda deve tentar com apenas uma falha
        assert should_attempt is True
        assert reason in ["proceed_with_caution", "proceed_with_generation"]
        assert analysis.has_recent_failures is True
    
    def test_handle_generation_failure(self):
        """Testa tratamento de falha de geração."""
        problem = "Test problem"
        model_info = ModelInfo(name="qwen2.5-coder", version="latest")
        
        self.helper.handle_generation_failure(
            problem=problem,
            model_info=model_info,
            language="python",
            mode="fast",
            validation_error="SyntaxError: invalid syntax",
            validation_status=ValidationStatus.FAILED,
            retry_count=2
        )
        
        # Verifica que foi cacheada
        result = self.cache.get_failure(
            problem=problem,
            model_info=model_info,
            language="python",
            mode="fast",
            validation_error="SyntaxError: invalid syntax"
        )
        
        assert result is not None
        assert result.validation_status == ValidationStatus.FAILED
        assert result.retry_count == 2
    
    def test_get_failure_insights(self):
        """Testa obtenção de insights sobre falhas."""
        problem = "Test problem"
        model_info = ModelInfo(name="qwen2.5-coder", version="latest")
        
        # Adiciona falha
        self.helper.handle_generation_failure(
            problem=problem,
            model_info=model_info,
            language="python",
            mode="fast",
            validation_error="SyntaxError",
            validation_status=ValidationStatus.FAILED
        )
        
        insights = self.helper.get_failure_insights(
            problem=problem,
            model_info=model_info,
            language="python",
            mode="fast"
        )
        
        assert insights["has_failures"] is True
        assert insights["failure_count"] == 1
        assert "recommendations" in insights
        assert isinstance(insights["recommendations"], list)


class TestFactoryFunctions:
    """Testes para factory functions."""
    
    def test_create_smart_cache_v3(self):
        """Testa criação do SmartCacheV3."""
        temp_dir = Path(tempfile.mkdtemp())
        
        try:
            cache = create_smart_cache_v3(
                directory=temp_dir,
                max_size_mb=512,
                max_entries=100,
                default_ttl_hours=24
            )
            
            assert isinstance(cache, SmartCacheV3)
            assert cache.max_size_bytes == 512 * 1024 * 1024
            assert cache.max_entries == 100
            
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_create_cache_validator(self):
        """Testa criação do CacheFailureValidator."""
        temp_dir = Path(tempfile.mkdtemp())
        
        try:
            cache = create_smart_cache_v3(temp_dir)
            validator = create_cache_validator(
                cache=cache,
                max_failure_hours=12,
                max_failure_count=5,
                min_confidence_threshold=0.4
            )
            
            assert isinstance(validator, CacheFailureValidator)
            assert validator.max_failure_hours == 12
            assert validator.max_failure_count == 5
            assert validator.min_confidence_threshold == 0.4
            
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestCacheEntryMetadata:
    """Testes para CacheEntryMetadata."""
    
    def test_metadata_creation(self):
        """Testa criação de metadados."""
        now = datetime.now(timezone.utc)
        model_info = ModelInfo(name="test", version="latest")
        
        metadata = CacheEntryMetadata(
            created_at=now,
            last_accessed=now,
            access_count=1,
            size_bytes=100,
            compressed=False,
            ttl_hours=24,
            entry_type=CacheEntryType.SUCCESS,
            problem_hash="abc123",
            model_info=model_info,
            language="python",
            mode="fast",
            context_hash="def456",
            compression_strategy="gzip",
            serialization_strategy="json"
        )
        
        assert metadata.entry_type == CacheEntryType.SUCCESS
        assert metadata.problem_hash == "abc123"
        assert metadata.model_info.name == "test"
    
    def test_metadata_serialization(self):
        """Testa serialização de metadados."""
        now = datetime.now(timezone.utc)
        model_info = ModelInfo(name="test", version="latest")
        
        metadata = CacheEntryMetadata(
            created_at=now,
            last_accessed=now,
            access_count=1,
            size_bytes=100,
            compressed=False,
            ttl_hours=24,
            entry_type=CacheEntryType.SUCCESS,
            problem_hash="abc123",
            model_info=model_info,
            language="python",
            mode="fast",
            context_hash="def456",
            compression_strategy="gzip",
            serialization_strategy="json"
        )
        
        # Serializa
        metadata_dict = metadata.to_dict()
        
        # Deserializa
        restored_metadata = CacheEntryMetadata.from_dict(metadata_dict)
        
        assert restored_metadata.created_at == metadata.created_at
        assert restored_metadata.entry_type == metadata.entry_type
        assert restored_metadata.model_info.name == metadata.model_info.name


if __name__ == "__main__":
    pytest.main([__file__])
