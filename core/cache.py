from __future__ import annotations

import json
import sqlite3
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from hashlib import sha256
from pathlib import Path
from typing import Any


def normalize_text(text: str) -> str:
    return " ".join(text.lower().strip().split())


class SolverCache:
    def __init__(self, directory: Path, ttl_hours: int = 24) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)

    def build_key(
        self,
        problem: str,
        language: str,
        model: str,
        mode: str,
        context_text: str,
    ) -> str:
        payload = {
            "problem": normalize_text(problem),
            "language": language.strip().lower(),
            "model": model.strip().lower(),
            "mode": mode.strip().lower(),
            "context": normalize_text(context_text),
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return sha256(raw.encode("utf-8")).hexdigest()

    def _path_for_key(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        path = self._path_for_key(key)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))

            # Check if entry has TTL information
            if "cached_at" in data:
                cached_at = datetime.fromisoformat(data["cached_at"])
                if datetime.now(timezone.utc) - cached_at > self.ttl:
                    # Entry expired, remove it and return None
                    path.unlink(missing_ok=True)
                    return None

            # Return the actual payload (without metadata)
            return data.get("payload", data)
        except (json.JSONDecodeError, ValueError, KeyError):
            # Corrupted cache file, remove it
            path.unlink(missing_ok=True)
            return None

    def set(self, key: str, payload: dict[str, Any]) -> None:
        path = self._path_for_key(key)
        cache_data = {
            "payload": payload,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "ttl_hours": self.ttl.total_seconds() / 3600,
        }
        path.write_text(
            json.dumps(cache_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def cleanup_expired(self) -> int:
        """Remove expired cache entries and return count of removed items."""
        removed_count = 0
        current_time = datetime.now(timezone.utc)

        for cache_file in self.directory.glob("*.json"):
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                if "cached_at" in data:
                    cached_at = datetime.fromisoformat(data["cached_at"])
                    if current_time - cached_at > self.ttl:
                        cache_file.unlink()
                        removed_count += 1
            except (json.JSONDecodeError, ValueError, KeyError):
                # Remove corrupted cache files
                cache_file.unlink()
                removed_count += 1

        return removed_count


@dataclass
class SimilarSolution:
    score: float
    problem: str
    classification: str
    language: str
    solution_excerpt: str
    labels: list[str]


class HistoryStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS solutions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    problem_hash TEXT NOT NULL,
                    problem_text TEXT NOT NULL,
                    normalized_problem TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    complexity INTEGER NOT NULL,
                    labels_json TEXT NOT NULL,
                    language TEXT NOT NULL,
                    model TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    markdown TEXT NOT NULL,
                    code TEXT NOT NULL,
                    tests TEXT NOT NULL,
                    explanation TEXT NOT NULL,
                    validation_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_solutions_problem_hash
                ON solutions(problem_hash)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_solutions_created_at
                ON solutions(created_at DESC)
                """
            )

    def save_result(self, result_payload: dict[str, Any]) -> int:
        created_at = datetime.now(timezone.utc).isoformat()
        problem_text = result_payload["problem"]
        normalized_problem = normalize_text(problem_text)
        problem_hash = sha256(normalized_problem.encode("utf-8")).hexdigest()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO solutions (
                    created_at,
                    problem_hash,
                    problem_text,
                    normalized_problem,
                    classification,
                    complexity,
                    labels_json,
                    language,
                    model,
                    mode,
                    markdown,
                    code,
                    tests,
                    explanation,
                    validation_json,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    problem_hash,
                    problem_text,
                    normalized_problem,
                    result_payload["classification"],
                    result_payload["complexity"],
                    json.dumps(result_payload["labels"], ensure_ascii=False),
                    result_payload["language"],
                    result_payload["model"],
                    result_payload["mode"],
                    result_payload["markdown"],
                    result_payload["code"],
                    result_payload["tests"],
                    json.dumps(
                        result_payload["explanation"], ensure_ascii=False),
                    json.dumps(
                        result_payload["validation"], ensure_ascii=False),
                    json.dumps(result_payload["metadata"], ensure_ascii=False),
                ),
            )
            return int(cursor.lastrowid)

    def find_similar(
        self,
        problem: str,
        language: str | None = None,
        limit: int = 3,
        candidate_pool: int = 50,
    ) -> list[dict[str, Any]]:
        normalized_problem = normalize_text(problem)
        problem_words = set(normalized_problem.split())

        # Optimized query with language filter and recent items limit
        query = """
            SELECT problem_text, classification, language, markdown, labels_json, normalized_problem
            FROM solutions
        """
        params: list[Any] = []
        if language:
            query += " WHERE language = ?"
            params.append(language)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(candidate_pool)

        scored: list[SimilarSolution] = []
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()

        # Early exit if no rows
        if not rows:
            return []

        # Pre-filter with faster Jaccard similarity first, then compute expensive SequenceMatcher only on promising candidates
        promising_candidates = []
        for row in rows:
            row_words = set(row["normalized_problem"].split())

            # Fast Jaccard similarity filter
            shared_terms = problem_words & row_words
            if not shared_terms:
                continue  # No shared words, skip expensive comparison

            jaccard = len(shared_terms) / \
                max(1, len(problem_words | row_words))
            if jaccard < 0.1:  # Low threshold for initial filter
                continue

            promising_candidates.append((row, jaccard))

        # Sort by Jaccard and compute expensive SequenceMatcher only on top candidates
        promising_candidates.sort(key=lambda x: x[1], reverse=True)

        # Compute full similarity score only on top 20 candidates
        for row, jaccard in promising_candidates[:20]:
            sequence_score = SequenceMatcher(
                None,
                normalized_problem,
                row["normalized_problem"],
            ).ratio()
            score = (sequence_score + jaccard) / 2

            if score < 0.18:
                continue

            markdown_text = row["markdown"]
            # TRUNCATION_LIMIT: 900 chars for solution excerpt
            solution_excerpt = markdown_text[:900]
            if len(markdown_text) > 900:
                warnings.warn(
                    f"Markdown solution truncated from {len(markdown_text)} to 900 characters for similarity matching. "
                    f"Original starts with: '{markdown_text[:50]}...'",
                    UserWarning,
                    stacklevel=3
                )
            scored.append(
                SimilarSolution(
                    score=score,
                    problem=row["problem_text"],
                    classification=row["classification"],
                    language=row["language"],
                    solution_excerpt=solution_excerpt,
                    labels=json.loads(row["labels_json"]),
                )
            )

        scored.sort(key=lambda item: item.score, reverse=True)
        return [
            {
                "score": item.score,
                "problem": item.problem,
                "classification": item.classification,
                "language": item.language,
                "solution_excerpt": item.solution_excerpt,
                "labels": item.labels,
            }
            for item in scored[:limit]
        ]
