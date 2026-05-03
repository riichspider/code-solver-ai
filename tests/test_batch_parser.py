from core.solver import CodeSolver


class FakeOllamaClient:
    @staticmethod
    def list_models():
        return ["fake-model"]


def build_config():
    return {
        "default_model": "fake-model",
        "ollama": {
            "base_url": "http://localhost:11434/api",
            "timeout_seconds": 30,
            "keep_alive": "5m",
            "options": {"temperature": 0.1},
        },
        "profiles": {
            "fast": {"temperature": 0.05, "num_predict": 800},
            "deep": {"temperature": 0.15, "num_predict": 1600},
        },
        "cache": {"enabled": True, "directory": "db/cache"},
        "history": {"database_path": "db/history.db", "similar_results": 2},
        "export": {"directory": "exports"},
        "supported_languages": ["python", "javascript"],
        "preferred_models": ["fake-model"],
    }


def build_solver(tmp_path):
    return CodeSolver(base_dir=tmp_path, config=build_config(), client=FakeOllamaClient())


def test_parse_batch_text_supports_separator_blocks(tmp_path):
    solver = build_solver(tmp_path)
    text = "Primeiro problema\n---\nSegundo problema"

    assert solver.parse_batch_text(text) == ["Primeiro problema", "Segundo problema"]


def test_parse_batch_text_supports_bullet_lists(tmp_path):
    solver = build_solver(tmp_path)
    text = "- Corrija o bug A\n- Implemente a feature B\n- Refatore o módulo C"

    assert solver.parse_batch_text(text) == [
        "Corrija o bug A",
        "Implemente a feature B",
        "Refatore o módulo C",
    ]


def test_parse_batch_text_preserves_single_problem_blocks(tmp_path):
    solver = build_solver(tmp_path)
    text = "Corrija o parser atual.\nEle falha com espaços extras."

    assert solver.parse_batch_text(text) == ["Corrija o parser atual.\nEle falha com espaços extras."]
