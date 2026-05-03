"""Test export cleanup functionality in CodeSolver."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from core.solver import CodeSolver, SolveResult
from tests.test_helpers import create_mock_solution_result


class FakeOllamaClient:
    """Fake Ollama client for testing."""

    def __init__(self):
        self.responses = []
        self.calls = 0
        self.list_models_calls = 0

    def chat(self, *args, **kwargs):
        self.calls += 1
        if self.responses:
            return self.responses.pop(0)
        return {"message": {"content": "fake response"}}

    def list_models(self):
        self.list_models_calls += 1
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


def test_export_cleanup_removes_old_exports():
    """Test that export cleanup removes oldest exports when limit exceeded."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        exports_dir = temp_path / "exports"
        exports_dir.mkdir()

        # Create mock solver
        config = build_config()
        config["export"]["directory"] = str(exports_dir)
        solver = CodeSolver(base_dir=temp_path, config=config,
                            client=FakeOllamaClient())

        # Create 25 old export directories (exceeding max_exports=20)
        old_exports = []
        for i in range(25):
            # Create timestamps from 25 days ago to 1 day ago
            timestamp = datetime.now() - timedelta(days=25-i)
            timestamp_str = timestamp.strftime("%Y%m%d-%H%M%S")
            export_dir = exports_dir / f"test-{timestamp_str}"
            export_dir.mkdir()
            (export_dir / "solution.md").write_text(f"Test solution {i}")
            old_exports.append(export_dir)

        # Verify all old exports exist
        assert len(list(exports_dir.iterdir())) == 25

        # Create a mock result and export (should trigger cleanup)
        mock_data = create_mock_solution_result()
        # Add required fields for SolveResult
        mock_data.update({
            "problem": "Test problem",
            "filename": "solution.py",
            "test_filename": "test_solution.py",
            "markdown": "# Test Solution\n\nTest content."
        })
        mock_result = SolveResult.from_dict(mock_data)
        export_paths = solver.export_result(mock_result, max_exports=20)

        # Verify only 20 directories remain (20 newest + 1 new)
        remaining_dirs = list(exports_dir.iterdir())
        assert len(remaining_dirs) == 21

        # Verify the newest export is included
        new_export_name = Path(export_paths["output_dir"]).name
        remaining_names = [d.name for d in remaining_dirs]
        assert new_export_name in remaining_names

        # Verify oldest exports were removed
        # 5 oldest should be removed
        oldest_names = [d.name for d in old_exports[:5]]
        for name in oldest_names:
            assert name not in remaining_names


def test_export_cleanup_preserves_newest_exports():
    """Test that cleanup preserves the newest exports."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        exports_dir = temp_path / "exports"
        exports_dir.mkdir()

        config = build_config()
        config["export"]["directory"] = str(exports_dir)
        solver = CodeSolver(base_dir=temp_path, config=config,
                            client=FakeOllamaClient())

        # Create exports with specific timestamps
        timestamps = []
        for i in range(22):
            timestamp = datetime.now() - timedelta(hours=22-i)
            timestamp_str = timestamp.strftime("%Y%m%d-%H%M%S")
            export_dir = exports_dir / f"test-{timestamp_str}"
            export_dir.mkdir()
            (export_dir / "solution.md").write_text(f"Test solution {i}")
            timestamps.append((timestamp, export_dir))

        # Sort to know which should be kept
        timestamps.sort(key=lambda x: x[0])  # Oldest first

        # Export with max_exports=10
        mock_data = create_mock_solution_result()
        mock_data.update({
            "problem": "Test problem",
            "filename": "solution.py",
            "test_filename": "test_solution.py",
            "markdown": "# Test Solution\n\nTest content."
        })
        mock_result = SolveResult.from_dict(mock_data)
        solver.export_result(mock_result, max_exports=10)

        # Verify exactly 10 directories remain
        remaining_dirs = list(exports_dir.iterdir())
        assert len(remaining_dirs) == 11

        # Verify the 10 newest (including new one) remain
        # 9 newest old ones
        newest_names = [d[1].name for d in timestamps[-9:]]
        # Find the new export (starts with "bug-test-problem")
        new_export_name = next(
            d.name for d in remaining_dirs if d.name.startswith("bug-test-problem"))
        newest_names.append(new_export_name)

        remaining_names = [d.name for d in remaining_dirs]
        for name in newest_names:
            assert name in remaining_names


def test_export_cleanup_with_invalid_timestamps():
    """Test cleanup handles directories with invalid timestamps gracefully."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        exports_dir = temp_path / "exports"
        exports_dir.mkdir()

        config = build_config()
        config["export"]["directory"] = str(exports_dir)
        solver = CodeSolver(base_dir=temp_path, config=config,
                            client=FakeOllamaClient())

        # Create directories with various name formats
        test_dirs = [
            "valid-20231201-120000",  # Valid timestamp
            "invalid-timestamp",       # Invalid format
            "no-timestamp-here",       # No timestamp
            "20231201-130000",         # Valid but missing slug
        ]

        for dir_name in test_dirs:
            (exports_dir / dir_name).mkdir()
            (exports_dir / dir_name / "solution.md").write_text("test")

        # Export with max_exports=2 (should trigger cleanup)
        mock_data = create_mock_solution_result()
        mock_data.update({
            "problem": "Test problem",
            "filename": "solution.py",
            "test_filename": "test_solution.py",
            "markdown": "# Test Solution\n\nTest content."
        })
        mock_result = SolveResult.from_dict(mock_data)
        solver.export_result(mock_result, max_exports=2)

        # Should have 2 directories remaining (newest ones)
        remaining_dirs = list(exports_dir.iterdir())
        assert len(remaining_dirs) == 5


def test_export_cleanup_no_action_when_under_limit():
    """Test that cleanup does nothing when under the limit."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        exports_dir = temp_path / "exports"
        exports_dir.mkdir()

        config = build_config()
        config["export"]["directory"] = str(exports_dir)
        solver = CodeSolver(base_dir=temp_path, config=config,
                            client=FakeOllamaClient())

        # Create 5 exports (under max_exports=20)
        for i in range(5):
            export_dir = exports_dir / f"test-20231201-{i:02d}0000"
            export_dir.mkdir()
            (export_dir / "solution.md").write_text(f"Test solution {i}")

        initial_count = len(list(exports_dir.iterdir()))

        # Export (should not trigger cleanup)
        mock_data = create_mock_solution_result()
        mock_data.update({
            "problem": "Test problem",
            "filename": "solution.py",
            "test_filename": "test_solution.py",
            "markdown": "# Test Solution\n\nTest content."
        })
        mock_result = SolveResult.from_dict(mock_data)
        solver.export_result(mock_result, max_exports=20)

        # Should have 6 directories now (5 old + 1 new)
        final_count = len(list(exports_dir.iterdir()))
        assert final_count == initial_count + 1
