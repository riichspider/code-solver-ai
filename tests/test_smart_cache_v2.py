"""Testes unitários para smart_cache_v2.

Valida Strategy Pattern, Inversão de Dependência e compatibilidade com TTL de 24h.
"""

from __future__ import annotations

import pytest
import tempfile
import json
import gzip
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime, timezone, timedelta

from utils.smart_cache_v2 import (
    SmartCacheV2,
    GzipCompressionStrategy,
    NoCompressionStrategy,
    JsonSerializationStrategy,
    PickleSerializationStrategy,
    LRUEvictionStrategy,
    LFUEvictionStrategy,
    SQLiteStorageStrategy,
    CacheEntry,
    CacheStats,
    create_smart_cache_v2
)


class TestCompressionStrategies:
    """Testes para estratégias de compressão."""

    def test_gzip_compression(self):
        """Testa compressão gzip."""
        strategy = GzipCompressionStrategy()
        data = b"Hello, World! " * 100  # Dados grandes o suficiente

        compressed = strategy.compress(data)
        decompressed = strategy.decompress(compressed)

        assert decompressed == data
        assert len(compressed) < len(data)
        assert strategy.is_beneficial(len(data))
        assert "gzip" in strategy.get_name()

    def test_gzip_not_beneficial_small_data(self):
        """Testa que gzip não é benéfico para dados pequenos."""
        strategy = GzipCompressionStrategy(min_size=1024)
        small_data = b"Hello"

        assert not strategy.is_beneficial(len(small_data))

    def test_no_compression(self):
        """Testa estratégia sem compressão."""
        strategy = NoCompressionStrategy()
        data = b"Hello, World!"

        compressed = strategy.compress(data)
        decompressed = strategy.decompress(compressed)

        assert compressed == data
        assert decompressed == data
        assert not strategy.is_beneficial(len(data))
        assert strategy.get_name() == "no_compression"


class TestSerializationStrategies:
    """Testes para estratégias de serialização."""

    def test_json_serialization(self):
        """Testa serialização JSON."""
        strategy = JsonSerializationStrategy()
        data = {"key": "value", "number": 42, "list": [1, 2, 3]}

        serialized = strategy.serialize(data)
        deserialized = strategy.deserialize(serialized)

        assert deserialized == data
        assert strategy.get_name() == "json"

    def test_json_serialization_invalid_data(self):
        """Testa falha na serialização JSON com dados inválidos."""
        strategy = JsonSerializationStrategy()

        # Dados não serializáveis em JSON
        invalid_data = {"key": object()}

        with pytest.raises(ValueError, match="JSON serialization failed"):
            strategy.serialize(invalid_data)

    def test_pickle_serialization(self):
        """Testa serialização Pickle."""
        strategy = PickleSerializationStrategy()
        # Pickle pode serializar objetos
        data = {"key": "value", "object": object()}

        serialized = strategy.serialize(data)
        deserialized = strategy.deserialize(serialized)

        assert deserialized["key"] == data["key"]
        assert strategy.get_name() == "pickle"


class TestEvictionStrategies:
    """Testes para estratégias de evicção."""

    def test_lru_eviction(self):
        """Testa evicção LRU."""
        strategy = LRUEvictionStrategy()

        now = datetime.now(timezone.utc)
        entries = {
            "old": CacheEntry(
                key="old",
                value="old_value",
                created_at=now - timedelta(hours=2),
                last_accessed=now - timedelta(hours=2),
                access_count=1,
                size_bytes=100,
                compressed=False,
                ttl_hours=24,
                problem_hash="hash1",
                language="python",
                model="model1",
                compression_strategy="none",
                serialization_strategy="json"
            ),
            "recent": CacheEntry(
                key="recent",
                value="recent_value",
                created_at=now - timedelta(hours=1),
                last_accessed=now - timedelta(hours=1),
                access_count=1,
                size_bytes=100,
                compressed=False,
                ttl_hours=24,
                problem_hash="hash2",
                language="python",
                model="model1",
                compression_strategy="none",
                serialization_strategy="json"
            )
        }

        # Converte para OrderedDict
        from collections import OrderedDict
        ordered_entries = OrderedDict(entries)

        # Precisa liberar 150 bytes (deve evictar ambas as entradas)
        keys_to_evict = strategy.select_for_eviction(ordered_entries, 150)

        assert "old" in keys_to_evict
        assert "recent" in keys_to_evict
        # A mais antiga deve vir primeiro
        assert keys_to_evict[0] == "old"
        assert strategy.get_name() == "lru"

    def test_lfu_eviction(self):
        """Testa evicção LFU."""
        strategy = LFUEvictionStrategy()

        now = datetime.now(timezone.utc)
        entries = {
            "rare": CacheEntry(
                key="rare",
                value="rare_value",
                created_at=now - timedelta(hours=2),
                last_accessed=now - timedelta(hours=1),
                access_count=1,
                size_bytes=100,
                compressed=False,
                ttl_hours=24,
                problem_hash="hash1",
                language="python",
                model="model1",
                compression_strategy="none",
                serialization_strategy="json"
            ),
            "frequent": CacheEntry(
                key="frequent",
                value="frequent_value",
                created_at=now - timedelta(hours=2),
                last_accessed=now - timedelta(hours=1),
                access_count=10,
                size_bytes=100,
                compressed=False,
                ttl_hours=24,
                problem_hash="hash2",
                language="python",
                model="model1",
                compression_strategy="none",
                serialization_strategy="json"
            )
        }

        from collections import OrderedDict
        ordered_entries = OrderedDict(entries)

        # Precisa liberar 150 bytes (deve evictar ambas as entradas)
        keys_to_evict = strategy.select_for_eviction(ordered_entries, 150)

        assert "rare" in keys_to_evict
        assert "frequent" in keys_to_evict
        # O menos usado deve vir primeiro
        assert keys_to_evict[0] == "rare"
        assert strategy.get_name() == "lfu"


class TestSQLiteStorageStrategy:
    """Testes para estratégia de armazenamento SQLite."""

    def setup_method(self):
        """Setup para cada teste."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.db_path = self.temp_dir / "test.db"
        self.storage = SQLiteStorageStrategy(self.db_path)

    def teardown_method(self):
        """Cleanup após cada teste."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_load(self):
        """Testa salvar e carregar dados."""
        key = "test_key"
        data = b"test_data"
        metadata = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_accessed": datetime.now(timezone.utc).isoformat(),
            "access_count": 1,
            "size_bytes": len(data),
            "compressed": False,
            "ttl_hours": 24,
            "problem_hash": "hash123",
            "language": "python",
            "model": "model1",
            "compression_strategy": "gzip",
            "serialization_strategy": "json"
        }

        # Salva
        self.storage.save(key, data, metadata)

        # Carrega
        result = self.storage.load(key)

        assert result is not None
        loaded_data, loaded_metadata = result
        assert loaded_data == data
        assert loaded_metadata["problem_hash"] == "hash123"

    def test_load_nonexistent(self):
        """Testa carregar chave inexistente."""
        result = self.storage.load("nonexistent_key")
        assert result is None

    def test_delete(self):
        """Testa remover dados."""
        key = "test_key"
        data = b"test_data"
        now = datetime.now(timezone.utc)
        metadata = {
            "test": "metadata",
            "created_at": now.isoformat(),
            "last_accessed": now.isoformat(),
            "access_count": 1,
            "size_bytes": len(data),
            "compressed": False,
            "ttl_hours": 24,
            "problem_hash": "hash123",
            "language": "python",
            "model": "model1",
            "compression_strategy": "none",
            "serialization_strategy": "json"
        }

        # Salva
        self.storage.save(key, data, metadata)

        # Verifica que existe
        assert self.storage.load(key) is not None

        # Remove
        self.storage.delete(key)

        # Verifica que não existe mais
        assert self.storage.load(key) is None

    def test_cleanup_expired(self):
        """Testa limpeza de entries expiradas."""
        key = "test_key"
        data = b"test_data"

        # Cria metadata expirado (2 horas atrás com TTL de 1 hora)
        expired_time = datetime.now(timezone.utc) - timedelta(hours=2)
        metadata = {
            "created_at": expired_time.isoformat(),
            "last_accessed": expired_time.isoformat(),
            "access_count": 1,
            "size_bytes": len(data),
            "compressed": False,
            "ttl_hours": 1,  # 1 hora TTL
            "problem_hash": "hash123",
            "language": "python",
            "model": "model1",
            "compression_strategy": "gzip",
            "serialization_strategy": "json"
        }

        # Salva entry expirada
        self.storage.save(key, data, metadata)

        # Limpa expiradas
        removed_count = self.storage.cleanup_expired(24)

        # Verifica que foi removida
        assert removed_count >= 1
        assert self.storage.load(key) is None


class TestSmartCacheV2:
    """Testes para SmartCacheV2."""

    def setup_method(self):
        """Setup para cada teste."""
        self.temp_dir = Path(tempfile.mkdtemp())

        # Cria estratégias mock para testes
        self.storage = Mock()
        self.storage.get_size.return_value = 0  # Retorna tamanho inicial como 0
        self.compression = NoCompressionStrategy()
        self.serialization = JsonSerializationStrategy()
        self.eviction = LRUEvictionStrategy()

        self.cache = SmartCacheV2(
            storage=self.storage,
            compression_strategy=self.compression,
            serialization_strategy=self.serialization,
            eviction_strategy=self.eviction,
            max_size_mb=1,
            max_entries=10,
            default_ttl_hours=24  # TTL padrão de 24h
        )

    def teardown_method(self):
        """Cleanup após cada teste."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_key(self):
        """Testa construção de chave de cache."""
        key = self.cache.build_key(
            problem="Test problem",
            language="python",
            model="gpt-4",
            mode="fast",
            context_text="Context"
        )

        assert isinstance(key, str)
        assert len(key) == 64  # SHA256 hash length

    def test_set_and_get(self):
        """Testa definir e obter valor."""
        key = "test_key"
        value = {"data": "test_value"}

        # Mock do storage
        self.storage.load.return_value = None

        # Define valor
        self.cache.set(key, value)

        # Mock para retornar os dados salvos
        self.storage.load.return_value = (
            self.serialization.serialize(value),
            {
                "compressed": False,
                "ttl_hours": 24,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        )

        # Obtém valor
        result = self.cache.get(key)

        assert result == value

    def test_get_nonexistent(self):
        """Testa obter valor inexistente."""
        self.storage.load.return_value = None

        result = self.cache.get("nonexistent_key")

        assert result is None

    def test_get_stats(self):
        """Testa obtenção de estatísticas."""
        # Mock para simular algumas estatísticas
        self.storage.get_size.return_value = 1024 * 100  # 100KB

        stats = self.cache.get_stats()

        assert isinstance(stats, CacheStats)
        assert hasattr(stats, 'hit_rate')
        assert hasattr(stats, 'miss_rate')
        assert hasattr(stats, 'total_size_mb')

    def test_ttl_default_24h(self):
        """Testa que TTL padrão é mantido em 24h."""
        key = "test_key"
        value = {"data": "test"}

        self.storage.load.return_value = None

        # Define sem TTL explícito
        self.cache.set(key, value)

        # Verifica se save foi chamado com TTL de 24h
        save_call = self.storage.save.call_args
        metadata = save_call[0][2]  # Terceiro argumento (metadata)

        assert metadata.get('ttl_hours') == 24

    def test_clear_all(self):
        """Testa limpar todos os entries."""
        # Adiciona alguns dados
        self.cache._memory_cache["key1"] = Mock()
        self.cache._memory_cache["key2"] = Mock()

        # Limpa
        self.cache.clear_all()

        # Verifica que cache em memória está vazio
        assert len(self.cache._memory_cache) == 0

        # Verifica que estatísticas foram resetadas
        assert self.cache._hits == 0
        assert self.cache._misses == 0


class TestFactoryFunction:
    """Testes para factory function."""

    def setup_method(self):
        """Setup para cada teste."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Cleanup após cada teste."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_with_defaults(self):
        """Testa criação com configurações padrão."""
        cache = create_smart_cache_v2(self.temp_dir)

        assert isinstance(cache.compression_strategy, GzipCompressionStrategy)
        assert isinstance(cache.serialization_strategy,
                          JsonSerializationStrategy)
        assert isinstance(cache.eviction_strategy, LRUEvictionStrategy)
        assert isinstance(cache.storage, SQLiteStorageStrategy)

    def test_create_no_compression(self):
        """Testa criação sem compressão."""
        cache = create_smart_cache_v2(
            self.temp_dir,
            compression_type="none"
        )

        assert isinstance(cache.compression_strategy, NoCompressionStrategy)

    def test_create_pickle_serialization(self):
        """Testa criação com serialização Pickle."""
        cache = create_smart_cache_v2(
            self.temp_dir,
            serialization_type="pickle"
        )

        assert isinstance(cache.serialization_strategy,
                          PickleSerializationStrategy)

    def test_create_lfu_eviction(self):
        """Testa criação com evicção LFU."""
        cache = create_smart_cache_v2(
            self.temp_dir,
            eviction_type="lfu"
        )

        assert isinstance(cache.eviction_strategy, LFUEvictionStrategy)

    def test_default_ttl_24h(self):
        """Testa que TTL padrão mantido em 24h."""
        cache = create_smart_cache_v2(self.temp_dir)

        # Verifica TTL em horas
        expected_ttl = int(timedelta(hours=24).total_seconds() / 3600)
        assert cache.default_ttl.total_seconds() / 3600 == expected_ttl


class TestCacheEntry:
    """Testes para CacheEntry."""

    def test_to_dict_and_from_dict(self):
        """Testa conversão para/dicionário."""
        now = datetime.now(timezone.utc)
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=now,
            last_accessed=now,
            access_count=1,
            size_bytes=100,
            compressed=False,
            ttl_hours=24,
            problem_hash="hash123",
            language="python",
            model="model1",
            compression_strategy="gzip",
            serialization_strategy="json"
        )

        # Converte para dict
        entry_dict = entry.to_dict()

        # Verifica campos
        assert entry_dict["key"] == "test_key"
        assert entry_dict["ttl_hours"] == 24

        # Converte de volta
        restored_entry = CacheEntry.from_dict(entry_dict)

        # Verifica que são iguais
        assert restored_entry.key == entry.key
        assert restored_entry.value == entry.value
        assert restored_entry.ttl_hours == entry.ttl_hours


if __name__ == "__main__":
    pytest.main([__file__])
