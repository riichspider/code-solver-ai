from pathlib import Path

import pytest

from core.solver import CodeSolver, SolveRequest


class FakeOllamaClient:
    def __init__(self):
        self.calls = 0
        self.list_models_calls = 0
        self.responses = [
            {
                "understanding": "Create a simple add helper with tests.",
                "classification": "enhancement",
                "complexity": 2,
                "labels": ["enhancement", "python"],
                "language": "python",
                "why": "The request asks for a new capability.",
            },
            {
                "understanding": "Build a tiny helper and validate it.",
                "constraints": ["Keep it simple", "Use standard library only"],
                "risks": ["Overengineering a trivial helper"],
                "success_criteria": ["Function works", "Tests pass"],
                "plan_steps": ["Write add", "Add unit tests", "Run validation"],
            },
            {
                "filename": "solution.py",
                "code": "def add(a, b):\n    return a + b\n",
                "test_filename": "test_solution.py",
                "tests": (
                    "import unittest\n"
                    "from solution import add\n\n"
                    "class AddTests(unittest.TestCase):\n"
                    "    def test_add(self):\n"
                    "        self.assertEqual(add(2, 3), 5)\n\n"
                    "if __name__ == '__main__':\n"
                    "    unittest.main()\n"
                ),
                "explanation": ["Implements the helper.", "Adds a regression test."],
                "notes": [],
            },
        ]

    def list_models(self):
        self.list_models_calls += 1
        return ["fake-model"]

    def generate_json(self, **kwargs):
        response = self.responses[self.calls]
        self.calls += 1
        return response


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


def test_solver_pipeline_runs_end_to_end_with_fake_client(tmp_path):
    solver = CodeSolver(base_dir=tmp_path, config=build_config(), client=FakeOllamaClient())
    request = SolveRequest(problem="Create an add function in Python", language="python")

    result = solver.solve(request)

    assert result.classification == "enhancement"
    assert result.validation["status"] == "passed"
    assert result.history_id is not None
    assert "def add" in result.code

    exported = solver.export_result(result, tmp_path / "exports", slug="smoke")
    assert Path(exported["markdown"]).exists()
    assert Path(exported["code"]).exists()


def test_solver_uses_cache_on_second_call(tmp_path):
    fake_client = FakeOllamaClient()
    solver = CodeSolver(base_dir=tmp_path, config=build_config(), client=fake_client)
    request = SolveRequest(problem="Create an add function in Python", language="python")

    first = solver.solve(request)
    second = solver.solve(request)

    assert first.cached is False
    assert second.cached is True
    assert fake_client.calls == 3


def test_solver_falls_back_to_installed_model_when_default_is_missing(tmp_path):
    fake_client = FakeOllamaClient()
    config = build_config()
    config["default_model"] = "missing-model"
    config["preferred_models"] = ["missing-model", "fake-model"]
    solver = CodeSolver(base_dir=tmp_path, config=config, client=fake_client)

    result = solver.solve(SolveRequest(problem="Create an add function in Python", language="python"))

    assert result.model == "fake-model"
    assert fake_client.list_models_calls >= 1


def test_solver_rejects_explicit_missing_model_when_list_is_available(tmp_path):
    fake_client = FakeOllamaClient()
    solver = CodeSolver(base_dir=tmp_path, config=build_config(), client=fake_client)

    with pytest.raises(ValueError, match="não está instalado"):
        solver.solve(
            SolveRequest(
                problem="Create an add function in Python",
                language="python",
                model="missing-model",
            )
        )
