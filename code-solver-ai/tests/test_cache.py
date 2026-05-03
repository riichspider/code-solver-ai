from core.cache import HistoryStore, SolverCache


def test_solver_cache_roundtrip(tmp_path):
    cache = SolverCache(tmp_path / "cache")
    key = cache.build_key(
        problem="Fix duplicate removal bug",
        language="python",
        model="fake-model",
        mode="fast",
        context_text="",
    )
    payload = {"classification": "bug", "code": "print('ok')"}
    cache.set(key, payload)
    assert cache.get(key) == payload


def test_history_store_finds_similar_items(tmp_path):
    store = HistoryStore(tmp_path / "history.db")
    store.save_result(
        {
            "problem": "Fix duplicate removal bug in Python list handling",
            "classification": "bug",
            "complexity": 4,
            "labels": ["bug", "python", "complexity-low"],
            "language": "python",
            "model": "fake-model",
            "mode": "fast",
            "markdown": "# report",
            "code": "def deduplicate(items):\n    return items\n",
            "tests": "",
            "explanation": ["Explanation"],
            "validation": {"status": "skipped"},
            "metadata": {"generated_at": "2026-05-03T00:00:00Z"},
        }
    )

    similar = store.find_similar("Fix duplicate removal bug in Python", language="python")
    assert similar
    assert similar[0]["classification"] == "bug"
