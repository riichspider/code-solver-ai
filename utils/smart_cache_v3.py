"""Smart Cache v3 com cache de falhas e chave otimizada.

Implementa cache inteligente com:
- Chave baseada em hash do problema + versão do modelo Ollama
- Cache de falhas de validação para evitar repetição de erros
- Arquitetura SOLID com type hints rigorosos
- TTL padrão de 24h mantido
"""

from __future__ import annotations

import abc
import json
import pickle
import sqlite3
import threading
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Union, Set, Tuple
from enum import Enum

from utils.logger import get_logger


# Enums para tipagem forte
class CacheEntryType(Enum):
    """Tipos de entries no cache."""
    SUCCESS = "success"
    FAILURE = "failure"


class ValidationStatus(Enum):
    """Status de validação."""
    PASSED = "passed"
    FAILED = "failed"
    UNKNOWN = "unknown"


# Protocolos para Inversão de Dependência

class CompressionStrategy(Protocol):
    """Protocolo para estratégias de compressão."""

    def compress(self, data: bytes) -> bytes:
        """Comprime dados."""
        ...

    def decompress(self, compressed_data: bytes) -> bytes:
        """Descomprime dados."""
        ...

    def is_beneficial(self, original_size: int) -> bool:
        """Verifica se compressão é benéfica."""
        ...

    def get_name(self) -> str:
        """Nome da estratégia."""
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
        """Nome da estratégia."""
        ...


class CacheKeyBuilder(Protocol):
    """Protocolo para construção de chaves de cache."""

    def build_success_key(
        self,
        problem_hash: str,
        model_version: str,
        language: str,
        mode: str,
        context_hash: str
    ) -> str:
        """Constrói chave para cache de sucesso."""
        ...

    def build_failure_key(
        self,
        problem_hash: str,
        model_version: str,
        language: str,
        mode: str,
        context_hash: str,
        validation_error_hash: str
    ) -> str:
        """Constrói chave para cache de falha."""
        ...


# Dataclasses com type hints rigorosos

@dataclass(frozen=True)
class ModelInfo:
    """Informações do modelo para construção de chave."""
    name: str
    version: str
    ollama_version: Optional[str] = None

    def get_full_identifier(self) -> str:
        """Retorna identificador completo do modelo."""
        if self.ollama_version:
            return f"{self.name}:{self.version}@{self.ollama_version}"
        return f"{self.name}:{self.version}"


@dataclass
class CacheEntryMetadata:
    """Metadados de uma entrada de cache."""
    created_at: datetime
    last_accessed: datetime
    access_count: int
    size_bytes: int
    compressed: bool
    ttl_hours: int
    entry_type: CacheEntryType
    problem_hash: str
    model_info: ModelInfo
    language: str
    mode: str
    context_hash: str
    compression_strategy: str
    serialization_strategy: str

    # Metadados específicos para falhas
    validation_status: Optional[ValidationStatus] = None
    validation_error_hash: Optional[str] = None
    validation_error_message: Optional[str] = None
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário serializável."""
        return {
            **asdict(self),
            'created_at': self.created_at.isoformat(),
            'last_accessed': self.last_accessed.isoformat(),
            'model_info': asdict(self.model_info),
            'entry_type': self.entry_type.value,
            'validation_status': self.validation_status.value if self.validation_status else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CacheEntryMetadata':
        """Cria a partir de dicionário."""
        data = data.copy()
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['last_accessed'] = datetime.fromisoformat(data['last_accessed'])
        data['model_info'] = ModelInfo(**data['model_info'])
        data['entry_type'] = CacheEntryType(data['entry_type'])

        if data['validation_status']:
            data['validation_status'] = ValidationStatus(
                data['validation_status'])

        return cls(**data)


@dataclass
class CacheEntry:
    """Entrada de cache com valor e metadados."""
    key: str
    value: Any
    metadata: CacheEntryMetadata

    @property
    def is_expired(self) -> bool:
        """Verifica se entry está expirada."""
        return datetime.now(timezone.utc) - self.metadata.created_at > timedelta(
            hours=self.metadata.ttl_hours
        )

    @property
    def is_success(self) -> bool:
        """Verifica se é uma entrada de sucesso."""
        return self.metadata.entry_type == CacheEntryType.SUCCESS

    @property
    def is_failure(self) -> bool:
        """Verifica se é uma entrada de falha."""
        return self.metadata.entry_type == CacheEntryType.FAILURE


@dataclass
class CacheStats:
    """Estatísticas detalhadas do cache."""
    total_entries: int
    success_entries: int
    failure_entries: int
    total_size_mb: float
    hit_rate: float
    miss_rate: float
    compression_ratio: float
    evictions_count: int
    memory_saved_mb: float
    hot_entries: int
    cold_entries: int

    @property
    def failure_rate(self) -> float:
        """Taxa de falhas no cache."""
        total = self.total_entries
        return self.failure_entries / total if total > 0 else 0.0


# Implementações concretas

class DefaultCacheKeyBuilder:
    """Construtor padrão de chaves de cache."""

    def build_success_key(
        self,
        problem_hash: str,
        model_version: str,
        language: str,
        mode: str,
        context_hash: str
    ) -> str:
        """Constrói chave para cache de sucesso."""
        payload = {
            "type": "success",
            "problem": problem_hash,
            "model": model_version,
            "language": language,
            "mode": mode,
            "context": context_hash
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return sha256(raw.encode("utf-8")).hexdigest()

    def build_failure_key(
        self,
        problem_hash: str,
        model_version: str,
        language: str,
        mode: str,
        context_hash: str,
        validation_error_hash: str
    ) -> str:
        """Constrói chave para cache de falha."""
        payload = {
            "type": "failure",
            "problem": problem_hash,
            "model": model_version,
            "language": language,
            "mode": mode,
            "context": context_hash,
            "error": validation_error_hash
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return sha256(raw.encode("utf-8")).hexdigest()


class GzipCompressionStrategy:
    """Estratégia de compressão gzip."""

    def __init__(self, compression_level: int = 6, min_size: int = 1024):
        self.compression_level = compression_level
        self.min_size = min_size

    def compress(self, data: bytes) -> bytes:
        """Comprime dados usando gzip."""
        import gzip
        return gzip.compress(data, compresslevel=self.compression_level)

    def decompress(self, compressed_data: bytes) -> bytes:
        """Descomprime dados gzip."""
        import gzip
        return gzip.decompress(compressed_data)

    def is_beneficial(self, original_size: int) -> bool:
        """Verifica se compressão é benéfica."""
        return original_size >= self.min_size

    def get_name(self) -> str:
        """Nome da estratégia."""
        return f"gzip_level_{self.compression_level}"


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


class SQLiteStorageStrategy:
    """Estratégia de armazenamento SQLite otimizada."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.logger = get_logger("sqlite_storage_v3")
        self._init_database()

    def _init_database(self) -> None:
        """Inicializa banco de dados SQLite."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            # Tabela principal de cache
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    data BLOB NOT NULL,
                    metadata TEXT NOT NULL,
                    entry_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_accessed TEXT NOT NULL,
                    ttl_hours INTEGER NOT NULL
                )
            """)

            # Índices para performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_entry_type 
                ON cache_entries(entry_type)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at 
                ON cache_entries(created_at DESC)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_problem_hash 
                ON cache_entries((json_extract(metadata, '$.problem_hash')))
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_model_info 
                ON cache_entries((json_extract(metadata, '$.model_info.name')))
            """)

    def save(self, key: str, data: bytes, metadata: CacheEntryMetadata) -> None:
        """Salva entrada no cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO cache_entries 
                    (key, data, metadata, entry_type, created_at, last_accessed, ttl_hours)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    key,
                    data,
                    json.dumps(metadata.to_dict(), ensure_ascii=False),
                    metadata.entry_type.value,
                    metadata.created_at.isoformat(),
                    metadata.last_accessed.isoformat(),
                    metadata.ttl_hours
                ))
        except Exception as e:
            self.logger.error(f"Failed to save to SQLite: {e}")
            raise

    def load(self, key: str) -> Optional[Tuple[bytes, CacheEntryMetadata]]:
        """Carrega entrada do cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT data, metadata, ttl_hours, created_at, entry_type
                    FROM cache_entries 
                    WHERE key = ?
                """, (key,))

                row = cursor.fetchone()
                if row is None:
                    return None

                data, metadata_json, ttl_hours, created_at, entry_type = row

                # Verifica TTL
                created_dt = datetime.fromisoformat(created_at)
                if datetime.now(timezone.utc) - created_dt > timedelta(hours=ttl_hours):
                    # Expired, remove
                    conn.execute(
                        "DELETE FROM cache_entries WHERE key = ?", (key,))
                    return None

                metadata_dict = json.loads(metadata_json)
                metadata = CacheEntryMetadata.from_dict(metadata_dict)

                return data, metadata

        except Exception as e:
            self.logger.error(f"Failed to load from SQLite: {e}")
            return None

    def delete(self, key: str) -> None:
        """Remove entrada do cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
        except Exception as e:
            self.logger.error(f"Failed to delete from SQLite: {e}")

    def cleanup_expired(self, ttl_hours: int) -> int:
        """Limpa entries expiradas."""
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
                    "SELECT SUM(LENGTH(data)) FROM cache_entries")
                result = cursor.fetchone()
                return result[0] or 0
        except Exception:
            return 0

    def find_failure_entries(
        self,
        problem_hash: str,
        model_name: str,
        language: str,
        mode: str,
        context_hash: str,
        limit: int = 10
    ) -> List[Tuple[str, CacheEntryMetadata]]:
        """Encontra entries de falha similares."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT key, metadata
                    FROM cache_entries 
                    WHERE entry_type = 'failure'
                    AND json_extract(metadata, '$.problem_hash') = ?
                    AND json_extract(metadata, '$.model_info.name') = ?
                    AND json_extract(metadata, '$.language') = ?
                    AND json_extract(metadata, '$.mode') = ?
                    AND json_extract(metadata, '$.context_hash') = ?
                    ORDER BY json_extract(metadata, '$.created_at') DESC
                    LIMIT ?
                """, (problem_hash, model_name, language, mode, context_hash, limit))

                results = []
                for key, metadata_json in cursor.fetchall():
                    metadata_dict = json.loads(metadata_json)
                    metadata = CacheEntryMetadata.from_dict(metadata_dict)
                    results.append((key, metadata))

                return results

        except Exception as e:
            self.logger.error(f"Failed to find failure entries: {e}")
            return []


class SmartCacheV3:
    """
    Cache inteligente v3 com cache de falhas e chave otimizada.

    Implementa SOLID principles com type hints rigorosos.
    """

    def __init__(
        self,
        storage: SQLiteStorageStrategy,
        compression_strategy: CompressionStrategy,
        serialization_strategy: SerializationStrategy,
        key_builder: CacheKeyBuilder,
        max_size_mb: int = 1024,
        max_entries: int = 500,
        default_ttl_hours: int = 24,  # Mantido 24h conforme regras
        hot_entry_threshold: int = 2,
        hot_entry_hours: int = 6,
    ) -> None:
        """
        Inicializa cache com dependências injetadas.

        Args:
            storage: Estratégia de armazenamento
            compression_strategy: Estratégia de compressão
            serialization_strategy: Estratégia de serialização
            key_builder: Construtor de chaves
            max_size_mb: Tamanho máximo em MB
            max_entries: Número máximo de entries
            default_ttl_hours: TTL padrão em horas (mantido 24h)
            hot_entry_threshold: Threshold para entries quentes
            hot_entry_hours: Horas para considerar entry quente
        """
        self.storage = storage
        self.compression_strategy = compression_strategy
        self.serialization_strategy = serialization_strategy
        self.key_builder = key_builder

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

        self.logger = get_logger("smart_cache_v3")

        # Carrega entries quentes
        self._load_hot_entries()

    def build_problem_hash(self, problem: str) -> str:
        """
        Constrói hash do problema normalizado.

        Args:
            problem: Texto do problema

        Returns:
            Hash SHA256 do problema
        """
        normalized_problem = " ".join(problem.lower().strip().split())
        return sha256(normalized_problem.encode("utf-8")).hexdigest()

    def build_context_hash(self, context_text: str) -> str:
        """
        Constrói hash do contexto.

        Args:
            context_text: Texto do contexto

        Returns:
            Hash SHA256 do contexto
        """
        normalized_context = " ".join(context_text.lower().strip().split())
        return sha256(normalized_context.encode("utf-8")).hexdigest()

    def build_validation_error_hash(self, validation_error: str) -> str:
        """
        Constrói hash do erro de validação.

        Args:
            validation_error: Mensagem de erro de validação

        Returns:
            Hash SHA256 do erro
        """
        normalized_error = " ".join(validation_error.lower().strip().split())
        return sha256(normalized_error.encode("utf-8")).hexdigest()

    def get_success(
        self,
        problem: str,
        model_info: ModelInfo,
        language: str,
        mode: str,
        context_text: str = ""
    ) -> Optional[Any]:
        """
        Obtém entrada de sucesso do cache.

        Args:
            problem: Texto do problema
            model_info: Informações do modelo
            language: Linguagem
            mode: Modo de execução
            context_text: Texto de contexto

        Returns:
            Valor cacheado ou None
        """
        problem_hash = self.build_problem_hash(problem)
        context_hash = self.build_context_hash(context_text)

        key = self.key_builder.build_success_key(
            problem_hash=problem_hash,
            model_version=model_info.get_full_identifier(),
            language=language,
            mode=mode,
            context_hash=context_hash
        )

        return self._get_from_cache(key)

    def set_success(
        self,
        problem: str,
        model_info: ModelInfo,
        language: str,
        mode: str,
        value: Any,
        context_text: str = "",
        ttl_hours: Optional[int] = None
    ) -> None:
        """
        Define entrada de sucesso no cache.

        Args:
            problem: Texto do problema
            model_info: Informações do modelo
            language: Linguagem
            mode: Modo de execução
            value: Valor a ser cacheado
            context_text: Texto de contexto
            ttl_hours: TTL em horas (usa padrão 24h se None)
        """
        problem_hash = self.build_problem_hash(problem)
        context_hash = self.build_context_hash(context_text)

        key = self.key_builder.build_success_key(
            problem_hash=problem_hash,
            model_version=model_info.get_full_identifier(),
            language=language,
            mode=mode,
            context_hash=context_hash
        )

        metadata = CacheEntryMetadata(
            created_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc),
            access_count=1,
            size_bytes=0,  # Será calculado após serialização
            compressed=False,
            ttl_hours=ttl_hours or int(
                self.default_ttl.total_seconds() / 3600),
            entry_type=CacheEntryType.SUCCESS,
            problem_hash=problem_hash,
            model_info=model_info,
            language=language,
            mode=mode,
            context_hash=context_hash,
            compression_strategy=self.compression_strategy.get_name(),
            serialization_strategy=self.serialization_strategy.get_name(),
        )

        self._set_in_cache(key, value, metadata)

    def get_failure(
        self,
        problem: str,
        model_info: ModelInfo,
        language: str,
        mode: str,
        validation_error: str,
        context_text: str = ""
    ) -> Optional[CacheEntryMetadata]:
        """
        Obtém entrada de falha do cache.

        Args:
            problem: Texto do problema
            model_info: Informações do modelo
            language: Linguagem
            mode: Modo de execução
            validation_error: Erro de validação
            context_text: Texto de contexto

        Returns:
            Metadados da falha cacheada ou None
        """
        problem_hash = self.build_problem_hash(problem)
        context_hash = self.build_context_hash(context_text)
        error_hash = self.build_validation_error_hash(validation_error)

        key = self.key_builder.build_failure_key(
            problem_hash=problem_hash,
            model_version=model_info.get_full_identifier(),
            language=language,
            mode=mode,
            context_hash=context_hash,
            validation_error_hash=error_hash
        )

        result = self._get_from_cache(key)
        if result is not None:
            # Para falhas, retornamos apenas os metadados
            if isinstance(result, CacheEntry):
                return result.metadata
            elif isinstance(result, dict) and 'validation_status' in result:
                # Se for um dicionário direto (do cache em memória),
                # precisamos reconstruir os metadados
                # Para simplificar, vamos buscar do storage diretamente
                storage_result = self._load_from_storage(key)
                if storage_result is not None and isinstance(storage_result, CacheEntry):
                    return storage_result.metadata

        return None

    def set_failure(
        self,
        problem: str,
        model_info: ModelInfo,
        language: str,
        mode: str,
        validation_error: str,
        validation_status: ValidationStatus,
        context_text: str = "",
        ttl_hours: Optional[int] = None,
        retry_count: int = 0
    ) -> None:
        """
        Define entrada de falha no cache.

        Args:
            problem: Texto do problema
            model_info: Informações do modelo
            language: Linguagem
            mode: Modo de execução
            validation_error: Erro de validação
            validation_status: Status da validação
            context_text: Texto de contexto
            ttl_hours: TTL em horas (usa padrão 24h se None)
            retry_count: Número de tentativas
        """
        problem_hash = self.build_problem_hash(problem)
        context_hash = self.build_context_hash(context_text)
        error_hash = self.build_validation_error_hash(validation_error)

        key = self.key_builder.build_failure_key(
            problem_hash=problem_hash,
            model_version=model_info.get_full_identifier(),
            language=language,
            mode=mode,
            context_hash=context_hash,
            validation_error_hash=error_hash
        )

        # Valor para falhas é o erro de validação
        failure_value = {
            "validation_error": validation_error,
            "validation_status": validation_status.value,
            "retry_count": retry_count
        }

        metadata = CacheEntryMetadata(
            created_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc),
            access_count=1,
            size_bytes=0,  # Será calculado após serialização
            compressed=False,
            ttl_hours=ttl_hours or int(
                self.default_ttl.total_seconds() / 3600),
            entry_type=CacheEntryType.FAILURE,
            problem_hash=problem_hash,
            model_info=model_info,
            language=language,
            mode=mode,
            context_hash=context_hash,
            compression_strategy=self.compression_strategy.get_name(),
            serialization_strategy=self.serialization_strategy.get_name(),
            validation_status=validation_status,
            validation_error_hash=error_hash,
            validation_error_message=validation_error,
            retry_count=retry_count
        )

        self._set_in_cache(key, failure_value, metadata)

    def has_recent_failure(
        self,
        problem: str,
        model_info: ModelInfo,
        language: str,
        mode: str,
        context_text: str = "",
        hours: int = 24
    ) -> List[CacheEntryMetadata]:
        """
        Verifica se há falhas recentes para o mesmo problema.

        Args:
            problem: Texto do problema
            model_info: Informações do modelo
            language: Linguagem
            mode: Modo de execução
            context_text: Texto de contexto
            hours: Horas para considerar como recente

        Returns:
            Lista de falhas recentes
        """
        problem_hash = self.build_problem_hash(problem)
        context_hash = self.build_context_hash(context_text)

        # Busca falhas similares no storage
        failure_entries = self.storage.find_failure_entries(
            problem_hash=problem_hash,
            model_name=model_info.name,
            language=language,
            mode=mode,
            context_hash=context_hash,
            limit=10
        )

        # Filtra por tempo
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        recent_failures = []

        for _, metadata in failure_entries:
            if metadata.created_at > cutoff_time:
                recent_failures.append(metadata)

        return recent_failures

    def get_stats(self) -> CacheStats:
        """
        Obtém estatísticas detalhadas do cache.

        Returns:
            Estatísticas completas do cache
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

        # Conta entries por tipo
        success_count = sum(
            1 for entry in self._memory_cache.values() if entry.is_success)
        failure_count = sum(
            1 for entry in self._memory_cache.values() if entry.is_failure)

        return CacheStats(
            total_entries=len(self._memory_cache),
            success_entries=success_count,
            failure_entries=failure_count,
            total_size_mb=total_size_mb,
            hit_rate=hit_rate,
            miss_rate=miss_rate,
            compression_ratio=compression_ratio,
            evictions_count=self._evictions,
            memory_saved_mb=memory_saved_mb,
            hot_entries=len(self._memory_cache),
            cold_entries=0  # Implementar se necessário
        )

    def clear_all(self) -> None:
        """Limpa todas as entries do cache."""
        with self._cache_lock:
            self._memory_cache.clear()

            # Limpa armazenamento persistente
            try:
                with sqlite3.connect(self.storage.db_path) as conn:
                    conn.execute("DELETE FROM cache_entries")
                self.logger.info("Cleared all cache entries")
            except Exception as e:
                self.logger.error(f"Failed to clear cache: {e}")

            # Reseta estatísticas
            self._hits = 0
            self._misses = 0
            self._evictions = 0
            self._compression_savings = 0

    # Métodos privados

    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Obtém valor do cache com LRU update."""
        with self._cache_lock:
            # Verifica cache em memória primeiro
            if key in self._memory_cache:
                entry = self._memory_cache[key]
                entry.metadata.last_accessed = datetime.now(timezone.utc)
                entry.metadata.access_count += 1

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

    def _set_in_cache(
        self,
        key: str,
        value: Any,
        metadata: CacheEntryMetadata
    ) -> None:
        """Define valor no cache com compressão se benéfico."""
        # Serializa
        try:
            serialized_data = self.serialization_strategy.serialize(value)
        except Exception as e:
            self.logger.error(f"Serialization failed for key {key}: {e}")
            return

        original_size = len(serialized_data)
        metadata.size_bytes = original_size

        # Comprime se benéfico
        compressed_data = None
        compressed = False

        if self.compression_strategy.is_beneficial(original_size):
            try:
                compressed_data = self.compression_strategy.compress(
                    serialized_data)
                compression_ratio = len(compressed_data) / original_size

                if compression_ratio < 0.8:  # Apenas se economizar >20%
                    serialized_data = compressed_data
                    compressed = True
                    metadata.compressed = True
                    self._compression_savings += original_size * \
                        (1 - compression_ratio)

            except Exception as e:
                self.logger.warning(f"Compression failed for key {key}: {e}")

        # Cria entry
        entry = CacheEntry(key=key, value=value, metadata=metadata)

        with self._cache_lock:
            # Adiciona ao cache em memória
            self._add_to_memory_cache(key, entry)

            # Salva no armazenamento persistente
            self._save_to_storage(entry, serialized_data)

            # Força limites de tamanho
            self._evict_if_needed()

    def _load_from_storage(self, key: str) -> Optional[Any]:
        """Carrega valor do armazenamento persistente."""
        result = self.storage.load(key)
        if result is None:
            return None

        data, metadata = result

        # Descomprime se necessário
        if metadata.compressed:
            try:
                data = self.compression_strategy.decompress(data)
            except Exception as e:
                self.logger.error(f"Decompression failed for key {key}: {e}")
                return None

        # Deserializa
        try:
            value = self.serialization_strategy.deserialize(data)

            # Cria entry para cache em memória
            entry = CacheEntry(key=key, value=value, metadata=metadata)
            return entry

        except Exception as e:
            self.logger.error(f"Deserialization failed for key {key}: {e}")
            return None

    def _save_to_storage(self, entry: CacheEntry, data: bytes) -> None:
        """Salva entry no armazenamento persistente."""
        try:
            self.storage.save(entry.key, data, entry.metadata)
        except Exception as e:
            self.logger.error(f"Failed to save to storage: {e}")

    def _update_access_stats(self, key: str) -> None:
        """Atualiza estatísticas de acesso no armazenamento."""
        # Implementação futura se necessário
        pass

    def _add_to_memory_cache(self, key: str, entry: Any) -> None:
        """Adiciona entry ao cache em memória com gerenciamento LRU."""
        if key in self._memory_cache:
            self._memory_cache.move_to_end(key)
            return

        # Estima tamanho da entry
        entry_size = entry.metadata.size_bytes

        # Evict se cache em memória estiver cheio
        while (len(self._memory_cache) >= self.max_entries or
               self._estimate_memory_usage() + entry_size > self.max_size_bytes // 2):
            if not self._memory_cache:
                break
            old_key, old_entry = self._memory_cache.popitem(last=False)
            self.logger.debug(f"Evicted from memory cache: {old_key}")

        # Adiciona nova entry
        self._memory_cache[key] = entry
        self._memory_cache.move_to_end(key)

    def _load_hot_entries(self) -> None:
        """Carrega entries frequentemente acessados para memória."""
        # Implementação futura baseada em access_count e last_accessed
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

        # Se ainda acima do limite, evict mais antigos
        current_size = self.storage.get_size()
        if current_size > self.max_size_bytes:
            self._evict_oldest_entries(current_size - self.max_size_bytes)

    def _evict_oldest_entries(self, bytes_to_free: int) -> None:
        """Evict entries mais antigos para liberar espaço."""
        # Implementação futura
        pass

    def _estimate_memory_usage(self) -> int:
        """Estima uso de memória do cache em memória."""
        return sum(entry.metadata.size_bytes for entry in self._memory_cache.values())


# Factory function mantendo compatibilidade

def create_smart_cache_v3(
    directory: Path,
    max_size_mb: int = 1024,
    max_entries: int = 500,
    default_ttl_hours: int = 24,  # Mantido 24h conforme regras
    compression_level: int = 6,
    min_compression_size: int = 1024
) -> SmartCacheV3:
    """
    Factory function para criar SmartCacheV3 com configurações padrão.

    Args:
        directory: Diretório para armazenamento
        max_size_mb: Tamanho máximo em MB
        max_entries: Número máximo de entries
        default_ttl_hours: TTL padrão em horas (mantido 24h)
        compression_level: Nível de compressão gzip
        min_compression_size: Tamanho mínimo para compressão

    Returns:
        Instância do SmartCacheV3
    """
    # Cria estratégias
    storage = SQLiteStorageStrategy(directory / "smart_cache_v3.db")
    compression = GzipCompressionStrategy(
        compression_level, min_compression_size)
    serialization = JsonSerializationStrategy()
    key_builder = DefaultCacheKeyBuilder()

    return SmartCacheV3(
        storage=storage,
        compression_strategy=compression,
        serialization_strategy=serialization,
        key_builder=key_builder,
        max_size_mb=max_size_mb,
        max_entries=max_entries,
        default_ttl_hours=default_ttl_hours
    )
