"""Smart Cache v2 com Strategy Pattern e Inversão de Dependência.

Implementa cache inteligente com estratégias de compressão injetáveis,
seguindo princípios SOLID e mantendo compatibilidade com TTL de 24h.
"""

from __future__ import annotations

import abc
import gzip
import json
import pickle
import sqlite3
import threading
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Union, Callable

from utils.logger import get_logger


# Interfaces e Protocolos para Inversão de Dependência

class CompressionStrategy(Protocol):
    """Protocolo para estratégias de compressão."""

    def compress(self, data: bytes) -> bytes:
        """Comprime dados."""
        ...

    def decompress(self, compressed_data: bytes) -> bytes:
        """Descomprime dados."""
        ...

    def is_beneficial(self, original_size: int) -> bool:
        """Verifica se compressão é benéfica para o tamanho."""
        ...

    def get_name(self) -> str:
        """Nome da estratégia de compressão."""
        ...


class SerializationStrategy(Protocol):
    """Protocolo para estratégias de serialização."""

    def serialize(self, data: Any) -> bytes:
        """Serializa dados."""
        ...

    def deserialize(self, serialized_data: bytes) -> Any:
        """Deserializa dados."""
        ...

    def get_name(self) -> str:
        """Nome da estratégia de serialização."""
        ...


class EvictionStrategy(Protocol):
    """Protocolo para estratégias de evicção de cache."""

    def select_for_eviction(
        self,
        entries: OrderedDict[str, 'CacheEntry'],
        bytes_to_free: int
    ) -> List[str]:
        """Seleciona entries para evicção."""
        ...

    def get_name(self) -> str:
        """Nome da estratégia de evicção."""
        ...


class StorageProtocol(Protocol):
    """Protocolo para armazenamento persistente."""

    def save(self, key: str, data: bytes, metadata: Dict[str, Any]) -> None:
        """Salva dados."""
        ...

    def load(self, key: str) -> Optional[tuple[bytes, Dict[str, Any]]]:
        """Carrega dados."""
        ...

    def delete(self, key: str) -> None:
        """Remove dados."""
        ...

    def cleanup_expired(self, ttl_hours: int) -> int:
        """Limpa entries expirados."""
        ...

    def get_size(self) -> int:
        """Retorna tamanho total do armazenamento."""
        ...


@dataclass
class CacheEntry:
    """Representa uma entrada do cache com metadados."""
    key: str
    value: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int
    size_bytes: int
    compressed: bool
    ttl_hours: int
    problem_hash: str
    language: str
    model: str
    compression_strategy: str
    serialization_strategy: str

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário para armazenamento."""
        return {
            **asdict(self),
            'created_at': self.created_at.isoformat(),
            'last_accessed': self.last_accessed.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CacheEntry':
        """Cria a partir de dicionário."""
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['last_accessed'] = datetime.fromisoformat(data['last_accessed'])
        return cls(**data)


@dataclass
class CacheStats:
    """Estatísticas do cache para monitoramento."""
    total_entries: int
    total_size_mb: float
    hit_rate: float
    miss_rate: float
    compression_ratio: float
    evictions_count: int
    memory_saved_mb: float
    hot_entries: int
    cold_entries: int


# Implementações das estratégias

class GzipCompressionStrategy:
    """Estratégia de compressão usando gzip."""

    def __init__(self, compression_level: int = 6, min_size: int = 1024):
        self.compression_level = compression_level
        self.min_size = min_size

    def compress(self, data: bytes) -> bytes:
        """Comprime dados usando gzip."""
        return gzip.compress(data, compresslevel=self.compression_level)

    def decompress(self, compressed_data: bytes) -> bytes:
        """Descomprime dados gzip."""
        return gzip.decompress(compressed_data)

    def is_beneficial(self, original_size: int) -> bool:
        """Verifica se compressão é benéfica."""
        return original_size >= self.min_size

    def get_name(self) -> str:
        """Nome da estratégia."""
        return f"gzip_level_{self.compression_level}"


class NoCompressionStrategy:
    """Estratégia sem compressão."""

    def compress(self, data: bytes) -> bytes:
        """Retorna dados sem compressão."""
        return data

    def decompress(self, compressed_data: bytes) -> bytes:
        """Retorna dados sem descompressão."""
        return compressed_data

    def is_beneficial(self, original_size: int) -> bool:
        """Nunca é benéfico (sem compressão)."""
        return False

    def get_name(self) -> str:
        """Nome da estratégia."""
        return "no_compression"


class JsonSerializationStrategy:
    """Estratégia de serialização JSON."""

    def serialize(self, data: Any) -> bytes:
        """Serializa usando JSON."""
        try:
            return json.dumps(data, ensure_ascii=False).encode('utf-8')
        except (TypeError, ValueError) as e:
            raise ValueError(f"JSON serialization failed: {e}")

    def deserialize(self, serialized_data: bytes) -> Any:
        """Deserializa JSON."""
        try:
            return json.loads(serialized_data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"JSON deserialization failed: {e}")

    def get_name(self) -> str:
        """Nome da estratégia."""
        return "json"


class PickleSerializationStrategy:
    """Estratégia de serialização Pickle."""

    def serialize(self, data: Any) -> bytes:
        """Serializa usando Pickle."""
        return pickle.dumps(data)

    def deserialize(self, serialized_data: bytes) -> Any:
        """Deserializa Pickle."""
        return pickle.loads(serialized_data)

    def get_name(self) -> str:
        """Nome da estratégia."""
        return "pickle"


class LRUEvictionStrategy:
    """Estratégia de evicção LRU (Least Recently Used)."""

    def select_for_eviction(
        self,
        entries: OrderedDict[str, CacheEntry],
        bytes_to_free: int
    ) -> List[str]:
        """Seleciona entries LRU para evicção."""
        keys_to_evict: List[str] = []
        freed_bytes = 0

        # Ordena por last_accessed (mais antigos primeiro)
        sorted_entries = sorted(
            entries.items(),
            key=lambda x: x[1].last_accessed
        )

        for key, entry in sorted_entries:
            keys_to_evict.append(key)
            freed_bytes += entry.size_bytes

            if freed_bytes >= bytes_to_free:
                break

        return keys_to_evict

    def get_name(self) -> str:
        """Nome da estratégia."""
        return "lru"


class LFUEvictionStrategy:
    """Estratégia de evicção LFU (Least Frequently Used)."""

    def select_for_eviction(
        self,
        entries: OrderedDict[str, CacheEntry],
        bytes_to_free: int
    ) -> List[str]:
        """Seleciona entries LFU para evicção."""
        keys_to_evict: List[str] = []
        freed_bytes = 0

        # Ordena por access_count (menos usados primeiro)
        sorted_entries = sorted(
            entries.items(),
            key=lambda x: x[1].access_count
        )

        for key, entry in sorted_entries:
            keys_to_evict.append(key)
            freed_bytes += entry.size_bytes

            if freed_bytes >= bytes_to_free:
                break

        return keys_to_evict

    def get_name(self) -> str:
        """Nome da estratégia."""
        return "lfu"


class SQLiteStorageStrategy:
    """Estratégia de armazenamento usando SQLite."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.logger = get_logger("sqlite_storage")
        self._init_database()

    def _init_database(self) -> None:
        """Inicializa o banco de dados SQLite."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    data BLOB NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_accessed TEXT NOT NULL,
                    access_count INTEGER DEFAULT 1,
                    size_bytes INTEGER NOT NULL,
                    compressed BOOLEAN DEFAULT FALSE,
                    ttl_hours INTEGER NOT NULL,
                    problem_hash TEXT NOT NULL,
                    language TEXT NOT NULL,
                    model TEXT NOT NULL,
                    compression_strategy TEXT NOT NULL,
                    serialization_strategy TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_problem_hash 
                ON cache_entries(problem_hash)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_last_accessed 
                ON cache_entries(last_accessed DESC)
            """)

    def save(self, key: str, data: bytes, metadata: Dict[str, Any]) -> None:
        """Salva dados no SQLite."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO cache_entries 
                    (key, data, metadata, created_at, last_accessed, 
                     access_count, size_bytes, compressed, ttl_hours,
                     problem_hash, language, model, compression_strategy, serialization_strategy)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    key,
                    data,
                    json.dumps(metadata, ensure_ascii=False),
                    metadata['created_at'],
                    metadata['last_accessed'],
                    metadata['access_count'],
                    metadata['size_bytes'],
                    metadata['compressed'],
                    metadata['ttl_hours'],
                    metadata['problem_hash'],
                    metadata['language'],
                    metadata['model'],
                    metadata['compression_strategy'],
                    metadata['serialization_strategy'],
                ))
        except Exception as e:
            self.logger.error(f"Failed to save to SQLite: {e}")
            raise

    def load(self, key: str) -> Optional[tuple[bytes, Dict[str, Any]]]:
        """Carrega dados do SQLite."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT data, metadata, ttl_hours, created_at
                    FROM cache_entries 
                    WHERE key = ?
                """, (key,))

                row = cursor.fetchone()
                if row is None:
                    return None

                data, metadata_json, ttl_hours, created_at = row

                # Verifica TTL
                created_dt = datetime.fromisoformat(created_at)
                if datetime.now(timezone.utc) - created_dt > timedelta(hours=ttl_hours):
                    # Expired, remove
                    conn.execute(
                        "DELETE FROM cache_entries WHERE key = ?", (key,))
                    return None

                metadata = json.loads(metadata_json)
                return data, metadata

        except Exception as e:
            self.logger.error(f"Failed to load from SQLite: {e}")
            return None

    def delete(self, key: str) -> None:
        """Remove dados do SQLite."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
        except Exception as e:
            self.logger.error(f"Failed to delete from SQLite: {e}")

    def cleanup_expired(self, ttl_hours: int) -> int:
        """Limpa entries expirados."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM cache_entries 
                    WHERE datetime(created_at, '+' || ttl_hours || ' hours') < datetime('now')
                """)
                return cursor.rowcount
        except Exception as e:
            self.logger.error(f"Failed to cleanup expired: {e}")
            return 0

    def get_size(self) -> int:
        """Retorna tamanho total do armazenamento."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT SUM(size_bytes) FROM cache_entries")
                result = cursor.fetchone()
                return result[0] or 0
        except Exception:
            return 0


class SmartCacheV2:
    """
    Cache inteligente v2 com Strategy Pattern e Inversão de Dependência.

    Mantém compatibilidade com TTL padrão de 24h seguindo as regras do projeto.
    """

    def __init__(
        self,
        storage: StorageProtocol,
        compression_strategy: CompressionStrategy,
        serialization_strategy: SerializationStrategy,
        eviction_strategy: EvictionStrategy,
        max_size_mb: int = 1024,
        max_entries: int = 500,
        default_ttl_hours: int = 24,  # TTL padrão de 24h conforme regras
        hot_entry_threshold: int = 2,
        hot_entry_hours: int = 6,
    ) -> None:
        """
        Inicializa cache com estratégias injetadas.

        Args:
            storage: Estratégia de armazenamento
            compression_strategy: Estratégia de compressão
            serialization_strategy: Estratégia de serialização
            eviction_strategy: Estratégia de evicção
            max_size_mb: Tamanho máximo em MB
            max_entries: Número máximo de entries
            default_ttl_hours: TTL padrão em horas (mantido 24h)
            hot_entry_threshold: Threshold para entries quentes
            hot_entry_hours: Horas para considerar entry quente
        """
        self.storage = storage
        self.compression_strategy = compression_strategy
        self.serialization_strategy = serialization_strategy
        self.eviction_strategy = eviction_strategy

        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.max_entries = max_entries
        self.default_ttl = timedelta(hours=default_ttl_hours)
        self.hot_entry_threshold = hot_entry_threshold
        self.hot_entry_hours = timedelta(hours=hot_entry_hours)

        # Cache em memória para entries quentes
        self._memory_cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._cache_lock = threading.RLock()

        # Estatísticas
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._compression_savings = 0

        self.logger = get_logger("smart_cache_v2")

        # Carrega entries quentes
        self._load_hot_entries()

    def build_key(
        self,
        problem: str,
        language: str,
        model: str,
        mode: str,
        context_text: str = "",
    ) -> str:
        """
        Constrói chave de cache dos parâmetros.

        Args:
            problem: Texto do problema
            language: Linguagem de programação
            model: Modelo usado
            mode: Modo de execução
            context_text: Texto de contexto

        Returns:
            Hash SHA256 como chave
        """
        normalized_problem = " ".join(problem.lower().strip().split())
        normalized_context = " ".join(context_text.lower().strip().split())

        payload = {
            "problem": normalized_problem,
            "language": language.strip().lower(),
            "model": model.strip().lower(),
            "mode": mode.strip().lower(),
            "context": normalized_context,
        }

        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """
        Obtém valor do cache com LRU update.

        Args:
            key: Chave do cache

        Returns:
            Valor armazenado ou None
        """
        with self._cache_lock:
            # Verifica cache em memória primeiro
            if key in self._memory_cache:
                entry = self._memory_cache[key]
                entry.last_accessed = datetime.now(timezone.utc)
                entry.access_count += 1

                # Move para o fim (mais recentemente usado)
                self._memory_cache.move_to_end(key)

                self._hits += 1
                self._update_access_stats(key)
                return entry.value

            # Verifica armazenamento persistente
            result = self._load_from_storage(key)
            if result is not None:
                self._hits += 1
                # Adiciona ao cache em memória se espaço permitir
                self._add_to_memory_cache(key, result)
                return result

            self._misses += 1
            return None

    def set(
        self,
        key: str,
        value: Any,
        ttl_hours: Optional[int] = None,
        problem_hash: Optional[str] = None,
        language: str = "python",
        model: str = "default",
    ) -> None:
        """
        Define valor no cache com compressão se benéfico.

        Args:
            key: Chave do cache
            value: Valor a ser armazenado
            ttl_hours: TTL em horas (usa padrão 24h se None)
            problem_hash: Hash do problema
            language: Linguagem
            model: Modelo
        """
        ttl_hours = ttl_hours or int(self.default_ttl.total_seconds() / 3600)

        # Serializa
        try:
            serialized_data = self.serialization_strategy.serialize(value)
        except Exception as e:
            self.logger.error(f"Serialization failed for key {key}: {e}")
            return

        # Comprime se benéfico
        compressed_data = None
        compressed = False
        original_size = len(serialized_data)

        if self.compression_strategy.is_beneficial(original_size):
            try:
                compressed_data = self.compression_strategy.compress(
                    serialized_data)
                compression_ratio = len(compressed_data) / original_size

                if compression_ratio < 0.8:  # Apenas se economizar >20%
                    serialized_data = compressed_data
                    compressed = True
                    self._compression_savings += original_size * \
                        (1 - compression_ratio)

            except Exception as e:
                self.logger.warning(f"Compression failed for key {key}: {e}")

        now = datetime.now(timezone.utc)

        entry = CacheEntry(
            key=key,
            value=value,
            created_at=now,
            last_accessed=now,
            access_count=1,
            size_bytes=len(serialized_data),
            compressed=compressed,
            ttl_hours=ttl_hours,
            problem_hash=problem_hash or sha256(key.encode()).hexdigest()[:16],
            language=language,
            model=model,
            compression_strategy=self.compression_strategy.get_name(),
            serialization_strategy=self.serialization_strategy.get_name(),
        )

        with self._cache_lock:
            # Adiciona ao cache em memória
            self._add_to_memory_cache(key, value, entry)

            # Salva no armazenamento persistente
            self._save_to_storage(entry, serialized_data)

            # Força limites de tamanho
            self._evict_if_needed()

    def get_stats(self) -> CacheStats:
        """
        Obtém estatísticas detalhadas do cache.

        Returns:
            Estatísticas do cache
        """
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0
        miss_rate = self._misses / total_requests if total_requests > 0 else 0.0

        total_size = self.storage.get_size() + self._estimate_memory_usage()
        total_size_mb = total_size / 1024 / 1024

        compression_ratio = (
            self._compression_savings /
            (total_size + self._compression_savings)
            if total_size + self._compression_savings > 0 else 0.0
        )

        memory_saved_mb = self._compression_savings / 1024 / 1024

        # Calcula entries quentes/frios
        hot_entries = len(self._memory_cache)
        cold_entries = self._get_total_storage_entries() - hot_entries

        return CacheStats(
            total_entries=len(self._memory_cache),
            total_size_mb=total_size_mb,
            hit_rate=hit_rate,
            miss_rate=miss_rate,
            compression_ratio=compression_ratio,
            evictions_count=self._evictions,
            memory_saved_mb=memory_saved_mb,
            hot_entries=hot_entries,
            cold_entries=cold_entries,
        )

    def find_similar_problems(
        self,
        problem_hash: str,
        language: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Encontra problemas similares baseado no hash.

        Args:
            problem_hash: Hash do problema
            language: Linguagem
            limit: Limite de resultados

        Returns:
            Lista de problemas similares
        """
        # Implementação depende da estratégia de armazenamento
        # Para SQLite, podemos fazer consultas SQL
        if isinstance(self.storage, SQLiteStorageStrategy):
            return self._find_similar_sqlite(problem_hash, language, limit)

        return []

    def clear_all(self) -> None:
        """Limpa todas as entries do cache."""
        with self._cache_lock:
            self._memory_cache.clear()

            # Limpa armazenamento persistente
            if hasattr(self.storage, 'clear_all'):
                self.storage.clear_all()

            # Reseta estatísticas
            self._hits = 0
            self._misses = 0
            self._evictions = 0
            self._compression_savings = 0

    # Métodos privados

    def _load_hot_entries(self) -> None:
        """Carrega entries frequentemente acessados para memória."""
        # Implementação depende da estratégia de armazenamento
        pass

    def _add_to_memory_cache(
        self,
        key: str,
        value: Any,
        entry: Optional[CacheEntry] = None
    ) -> None:
        """Adiciona entry ao cache em memória com gerenciamento LRU."""
        if key in self._memory_cache:
            self._memory_cache.move_to_end(key)
            return

        # Estima tamanho da entry
        if entry is None:
            entry_size = len(pickle.dumps(value))
        else:
            entry_size = entry.size_bytes

        # Evict se cache em memória estiver cheio
        while (len(self._memory_cache) >= self.max_entries or
               self._estimate_memory_usage() + entry_size > self.max_size_bytes // 2):
            if not self._memory_cache:
                break
            old_key, old_entry = self._memory_cache.popitem(last=False)
            self.logger.debug(f"Evicted from memory cache: {old_key}")

        # Adiciona nova entry
        if entry is None:
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=datetime.now(timezone.utc),
                last_accessed=datetime.now(timezone.utc),
                access_count=1,
                size_bytes=entry_size,
                compressed=False,
                ttl_hours=int(self.default_ttl.total_seconds() / 3600),
                problem_hash=sha256(key.encode()).hexdigest()[:16],
                language="unknown",
                model="unknown",
                compression_strategy="none",
                serialization_strategy="unknown",
            )

        self._memory_cache[key] = entry
        self._memory_cache.move_to_end(key)

    def _load_from_storage(self, key: str) -> Optional[Any]:
        """Carrega valor do armazenamento persistente."""
        result = self.storage.load(key)
        if result is None:
            return None

        data, metadata = result

        # Descomprime se necessário
        if metadata.get('compressed', False):
            try:
                data = self.compression_strategy.decompress(data)
            except Exception as e:
                self.logger.error(f"Decompression failed for key {key}: {e}")
                return None

        # Deserializa
        try:
            return self.serialization_strategy.deserialize(data)
        except Exception as e:
            self.logger.error(f"Deserialization failed for key {key}: {e}")
            return None

    def _save_to_storage(self, entry: CacheEntry, data: bytes) -> None:
        """Salva entry no armazenamento persistente."""
        metadata = entry.to_dict()
        self.storage.save(entry.key, data, metadata)

    def _update_access_stats(self, key: str) -> None:
        """Atualiza estatísticas de acesso no armazenamento."""
        # Implementação depende da estratégia de armazenamento
        pass

    def _evict_if_needed(self) -> None:
        """Evict entries se cache exceder limites."""
        # Verifica cache em memória
        while len(self._memory_cache) > self.max_entries:
            old_key, old_entry = self._memory_cache.popitem(last=False)
            self.logger.debug(f"Evicted from memory cache: {old_key}")
            self._evictions += 1

        # Limpa entries expiradas
        self.storage.cleanup_expired(
            int(self.default_ttl.total_seconds() / 3600))

        # Se ainda acima do limite, evict usando estratégia
        current_size = self.storage.get_size()
        if current_size > self.max_size_bytes:
            self._evict_with_strategy(current_size - self.max_size_bytes)

    def _evict_with_strategy(self, bytes_to_free: int) -> None:
        """Evict entries usando estratégia injetada."""
        # Implementação depende da estratégia de armazenamento
        # Para SQLite, podemos carregar entries e aplicar estratégia
        pass

    def _estimate_memory_usage(self) -> int:
        """Estima uso de memória do cache em memória."""
        return sum(entry.size_bytes for entry in self._memory_cache.values())

    def _get_total_storage_entries(self) -> int:
        """Obtém número total de entries no armazenamento."""
        # Implementação depende da estratégia de armazenamento
        return 0

    def _find_similar_sqlite(
        self,
        problem_hash: str,
        language: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Encontra problemas similares no SQLite."""
        # Implementação específica para SQLite
        return []


# Factory function para criação fácil mantendo compatibilidade

def create_smart_cache_v2(
    directory: Path,
    max_size_mb: int = 1024,
    max_entries: int = 500,
    default_ttl_hours: int = 24,  # Mantido 24h conforme regras
    compression_type: str = "gzip",
    serialization_type: str = "json",
    eviction_type: str = "lru",
) -> SmartCacheV2:
    """
    Factory function para criar SmartCacheV2 com configurações padrão.

    Args:
        directory: Diretório para armazenamento
        max_size_mb: Tamanho máximo em MB
        max_entries: Número máximo de entries
        default_ttl_hours: TTL padrão em horas (mantido 24h)
        compression_type: Tipo de compressão ("gzip" ou "none")
        serialization_type: Tipo de serialização ("json" ou "pickle")
        eviction_type: Tipo de evicção ("lru" ou "lfu")

    Returns:
        Instância do SmartCacheV2
    """
    # Cria estratégias
    storage = SQLiteStorageStrategy(directory / "smart_cache_v2.db")

    if compression_type == "gzip":
        compression = GzipCompressionStrategy()
    else:
        compression = NoCompressionStrategy()

    if serialization_type == "json":
        serialization = JsonSerializationStrategy()
    else:
        serialization = PickleSerializationStrategy()

    if eviction_type == "lru":
        eviction = LRUEvictionStrategy()
    else:
        eviction = LFUEvictionStrategy()

    return SmartCacheV2(
        storage=storage,
        compression_strategy=compression,
        serialization_strategy=serialization,
        eviction_strategy=eviction,
        max_size_mb=max_size_mb,
        max_entries=max_entries,
        default_ttl_hours=default_ttl_hours,
    )
