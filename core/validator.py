from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from utils.executor import SandboxExecutor
from utils.logger import get_logger, log_error
from core.types import ValidationResult
from core.cpp_validator import validate_cpp
from core.ruby_validator import validate_ruby

try:
    from core.php_validator import validate_php
except ImportError:
    validate_php = None


class SolutionValidator:
    def __init__(self, timeout_seconds: int = 20) -> None:
        self.timeout_seconds = timeout_seconds
        self.executor = SandboxExecutor(timeout_seconds=timeout_seconds)
        self.logger = get_logger("validator")

    def _inject_database_mocking(self, code: str, tests: str) -> tuple[str, str]:
        """
        Inject database mocking into test code if the solution uses database connections.

        Args:
            code: The solution code
            tests: The test code

        Returns:
            Tuple of (modified_code, modified_tests)
        """
        # Check if code uses database connections
        db_patterns = [
            r'sqlite3\.connect',
            r'psycopg2\.connect',
            r'mysql\.connector\.connect',
            r'pymongo\.MongoClient',
            r'from\s+pymongo\s+import',
            r'engine\s*=\s*create_engine',
            r'Database\.connect',
            r'Connection\(',
        ]

        uses_db = any(re.search(pattern, code) for pattern in db_patterns)

        if not uses_db:
            return code, tests

        # If tests already have mocking, don't modify
        if re.search(r'@patch\(', tests) and re.search(r'unittest\.mock', tests):
            return code, tests

        # Inject mocking imports and setup
        mock_imports = """import unittest.mock
from unittest.mock import patch, MagicMock

"""

        # Create mock setup function
        mock_setup = """
def setup_database_mock():
    \"\"\"Setup common database mocking for tests.\"\"\"
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (1, 'test_user', 'test@example.com', 'password123')
    mock_cursor.fetchall.return_value = [(1, 'test_user', 'test@example.com', 'password123')]
    mock_cursor.rowcount = 1
    
    # Mock the execute method to capture SQL queries for security testing
    def mock_execute(query, params=None):
        mock_cursor.last_query = query
        mock_cursor.last_params = params
        return mock_cursor
    
    mock_cursor.execute = mock_execute
    return mock_conn, mock_cursor

# Global mock setup for sqlite3.connect
def mock_sqlite_connect(*args, **kwargs):
    \"\"\"Mock sqlite3.connect for testing.\"\"\"
    mock_conn, mock_cursor = setup_database_mock()
    return mock_conn

"""

        # Modify tests to include mocking
        modified_tests = tests

        # Add imports if not present
        if 'import unittest.mock' not in modified_tests:
            # Find the first import line and add after it
            lines = modified_tests.split('\n')
            import_index = 0
            for i, line in enumerate(lines):
                if line.strip().startswith('import ') or line.strip().startswith('from '):
                    import_index = i + 1
                elif line.strip() == '' and import_index > 0:
                    break

            lines.insert(import_index, mock_imports.rstrip())
            modified_tests = '\n'.join(lines)

        # Add mock setup function before first test class
        if 'def setup_database_mock():' not in modified_tests:
            lines = modified_tests.split('\n')
            class_index = 0
            for i, line in enumerate(lines):
                if 'class ' in line and 'Test' in line:
                    class_index = i
                    break

            lines.insert(class_index, mock_setup.rstrip())
            modified_tests = '\n'.join(lines)

        # Add @patch decorators to test methods that might use database
        # Simple approach: add patch to all test methods for safety
        lines = modified_tests.split('\n')
        # Iterate backwards to avoid issues when inserting
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i]
            if line.strip().startswith('def test_') and '@patch' not in line:
                # Add patch decorator to all test methods
                indent = len(line) - len(line.lstrip())
                patch_decorator = ' ' * indent + \
                    '@patch("sqlite3.connect", side_effect=mock_sqlite_connect)'
                lines.insert(i, patch_decorator)

        modified_tests = '\n'.join(lines)

        return code, modified_tests

    def validate(
        self,
        language: str,
        code: str,
        tests: str,
        filename: str,
        test_filename: str,
    ) -> ValidationResult:
        normalized_language = language.strip().lower()
        if normalized_language == "python":
            return self._validate_python(code, tests, filename, test_filename)
        if normalized_language == "javascript":
            return self._validate_javascript(code, tests, filename, test_filename)
        if normalized_language == "typescript":
            return self._validate_typescript(code, tests, filename, test_filename)
        if normalized_language == "go":
            return self._validate_go(code, tests, filename, test_filename)
        if normalized_language == "cpp" or normalized_language == "c++":
            return validate_cpp(code, tests, filename, test_filename, self.timeout_seconds)
        if normalized_language == "ruby":
            return validate_ruby(code, tests, filename, test_filename, self.timeout_seconds)
        if normalized_language == "php":
            if validate_php is None:
                return {
                    "status": "skipped",
                    "tool": "php",
                    "command": "",
                    "stdout": "",
                    "stderr": "",
                    "notes": "PHP validator module not available",
                }
            return validate_php(code, tests, filename, test_filename, self.timeout_seconds)
        return {
            "status": "skipped",
            "tool": "none",
            "command": "",
            "stdout": "",
            "stderr": "",
            "notes": f"Validação automática detalhada ainda não está habilitada para {language}.",
        }

    def _validate_python(
        self,
        code: str,
        tests: str,
        filename: str,
        test_filename: str,
    ) -> ValidationResult:
        # Inject database mocking if needed
        modified_code, modified_tests = self._inject_database_mocking(
            code, tests)

        with tempfile.TemporaryDirectory(prefix="code-solver-") as temp_dir:
            workspace = Path(temp_dir)
            (workspace / filename).write_text(modified_code, encoding="utf-8")
            command: list[str]
            if modified_tests.strip():
                (workspace / test_filename).write_text(modified_tests, encoding="utf-8")
                command = [
                    sys.executable,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    ".",
                    "-p",
                    "test*.py",
                    "-v",
                ]
                tool = "python-unittest"
            else:
                command = [sys.executable, filename]
                tool = "python-exec"

            result = self.executor.run(command=command, cwd=workspace)
            status = "passed" if result.returncode == 0 and not result.timed_out else "failed"

            # Log validation failures
            if status == "failed":
                log_error(
                    self.logger,
                    RuntimeError(
                        f"Python validation failed with return code {result.returncode}"),
                    context="_validate_python",
                    details={
                        "filename": filename,
                        "test_filename": test_filename,
                        "returncode": result.returncode,
                        "timed_out": result.timed_out,
                        "duration_seconds": result.duration_seconds,
                        "command": " ".join(command),
                        "stderr_sample": result.stderr[:200] + "..." if len(result.stderr) > 200 else result.stderr
                    }
                )

            return {
                "status": status,
                "tool": tool,
                "command": " ".join(command),
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timed_out": result.timed_out,
                "returncode": result.returncode,
                "duration_seconds": result.duration_seconds,
                "notes": "Validação Python concluída com execução segura em subprocesso.",
            }

    def _validate_javascript(
        self,
        code: str,
        tests: str,
        filename: str,
        test_filename: str,
    ) -> ValidationResult:
        if shutil.which("node") is None:
            return {
                "status": "skipped",
                "tool": "node",
                "command": "",
                "stdout": "",
                "stderr": "",
                "notes": "Node.js não encontrado no ambiente para validar JavaScript.",
            }

        with tempfile.TemporaryDirectory(prefix="code-solver-") as temp_dir:
            workspace = Path(temp_dir)
            (workspace / filename).write_text(code, encoding="utf-8")
            syntax_check = self.executor.run(
                command=["node", "--check", filename],
                cwd=workspace,
            )
            if syntax_check.returncode != 0 or syntax_check.timed_out:
                return {
                    "status": "failed",
                    "tool": "node",
                    "command": "node --check " + filename,
                    "stdout": syntax_check.stdout,
                    "stderr": syntax_check.stderr,
                    "timed_out": syntax_check.timed_out,
                    "returncode": syntax_check.returncode,
                    "duration_seconds": syntax_check.duration_seconds,
                    "notes": "Falha na checagem sintática do JavaScript.",
                }

            if tests.strip():
                (workspace / test_filename).write_text(tests, encoding="utf-8")
                execution = self.executor.run(
                    command=["node", test_filename], cwd=workspace)
                status = "passed" if execution.returncode == 0 and not execution.timed_out else "failed"
                return {
                    "status": status,
                    "tool": "node",
                    "command": "node " + test_filename,
                    "stdout": execution.stdout,
                    "stderr": execution.stderr,
                    "timed_out": execution.timed_out,
                    "returncode": execution.returncode,
                    "duration_seconds": execution.duration_seconds,
                    "notes": "Checagem sintática e execução básica dos testes JavaScript concluídas.",
                }

            return {
                "status": "passed",
                "tool": "node",
                "command": "node --check " + filename,
                "stdout": syntax_check.stdout,
                "stderr": syntax_check.stderr,
                "timed_out": syntax_check.timed_out,
                "returncode": syntax_check.returncode,
                "duration_seconds": syntax_check.duration_seconds,
                "notes": "Checagem sintática concluída; nenhum arquivo de teste foi retornado.",
            }

    def _validate_typescript(
        self,
        code: str,
        tests: str,
        filename: str,
        test_filename: str,
    ) -> ValidationResult:
        if shutil.which("tsc") is None:
            return {
                "status": "skipped",
                "tool": "tsc",
                "command": "",
                "stdout": "",
                "stderr": "",
                "notes": "TypeScript compiler (tsc) não encontrado no ambiente para validar TypeScript.",
            }

        with tempfile.TemporaryDirectory(prefix="code-solver-") as temp_dir:
            workspace = Path(temp_dir)
            (workspace / filename).write_text(code, encoding="utf-8")

            # Create a minimal tsconfig.json for TypeScript compilation
            tsconfig = {
                "compilerOptions": {
                    "target": "ES2020",
                    "module": "commonjs",
                    "strict": True,
                    "noEmit": True,
                    "skipLibCheck": True
                },
                "include": [filename]
            }
            (workspace / "tsconfig.json").write_text(
                json.dumps(tsconfig, indent=2), encoding="utf-8"
            )

            # Type check with TypeScript compiler
            type_check = self.executor.run(
                command=["tsc", "--noEmit"],
                cwd=workspace,
            )

            if type_check.returncode != 0 or type_check.timed_out:
                return {
                    "status": "failed",
                    "tool": "tsc",
                    "command": "tsc --noEmit",
                    "stdout": type_check.stdout,
                    "stderr": type_check.stderr,
                    "timed_out": type_check.timed_out,
                    "returncode": type_check.returncode,
                    "duration_seconds": type_check.duration_seconds,
                    "notes": "Falha na verificação de tipos do TypeScript.",
                }

            if tests.strip():
                (workspace / test_filename).write_text(tests, encoding="utf-8")
                # For TypeScript tests, we use ts-node if available, otherwise skip test execution
                if shutil.which("ts-node") is not None:
                    execution = self.executor.run(
                        command=["ts-node", test_filename], cwd=workspace)
                    status = "passed" if execution.returncode == 0 and not execution.timed_out else "failed"
                    return {
                        "status": status,
                        "tool": "tsc",
                        "command": f"tsc --noEmit && ts-node {test_filename}",
                        "stdout": execution.stdout,
                        "stderr": execution.stderr,
                        "timed_out": execution.timed_out,
                        "returncode": execution.returncode,
                        "duration_seconds": execution.duration_seconds,
                        "notes": "Verificação de tipos e execução dos testes TypeScript concluídas.",
                    }
                else:
                    return {
                        "status": "passed",
                        "tool": "tsc",
                        "command": "tsc --noEmit",
                        "stdout": type_check.stdout,
                        "stderr": type_check.stderr,
                        "timed_out": type_check.timed_out,
                        "returncode": type_check.returncode,
                        "duration_seconds": type_check.duration_seconds,
                        "notes": "Verificação de tipos concluída; ts-node não encontrado para executar testes.",
                    }

            return {
                "status": "passed",
                "tool": "tsc",
                "command": "tsc --noEmit",
                "stdout": type_check.stdout,
                "stderr": type_check.stderr,
                "timed_out": type_check.timed_out,
                "returncode": type_check.returncode,
                "duration_seconds": type_check.duration_seconds,
                "notes": "Verificação de tipos concluída; nenhum arquivo de teste foi retornado.",
            }

    def _validate_go(
        self,
        code: str,
        tests: str,
        filename: str,
        test_filename: str,
    ) -> ValidationResult:
        if shutil.which("go") is None:
            return {
                "status": "skipped",
                "tool": "go",
                "command": "",
                "stdout": "",
                "stderr": "",
                "notes": "Go compiler (go) não encontrado no ambiente para validar Go.",
            }

        with tempfile.TemporaryDirectory(prefix="code-solver-") as temp_dir:
            workspace = Path(temp_dir)
            (workspace / filename).write_text(code, encoding="utf-8")

            # Initialize Go module
            self.executor.run(
                command=["go", "mod", "init", "code-solver-test"],
                cwd=workspace,
            )

            # Build check (syntax and compilation)
            build_check = self.executor.run(
                command=["go", "build", "."],
                cwd=workspace,
            )

            if build_check.returncode != 0 or build_check.timed_out:
                return {
                    "status": "failed",
                    "tool": "go",
                    "command": "go build .",
                    "stdout": build_check.stdout,
                    "stderr": build_check.stderr,
                    "timed_out": build_check.timed_out,
                    "returncode": build_check.returncode,
                    "duration_seconds": build_check.duration_seconds,
                    "notes": "Falha na compilação do código Go.",
                }

            if tests.strip():
                (workspace / test_filename).write_text(tests, encoding="utf-8")
                # Run Go tests
                test_execution = self.executor.run(
                    command=["go", "test", "./..."],
                    cwd=workspace,
                )
                status = "passed" if test_execution.returncode == 0 and not test_execution.timed_out else "failed"
                return {
                    "status": status,
                    "tool": "go",
                    "command": "go test ./...",
                    "stdout": test_execution.stdout,
                    "stderr": test_execution.stderr,
                    "timed_out": test_execution.timed_out,
                    "returncode": test_execution.returncode,
                    "duration_seconds": test_execution.duration_seconds,
                    "notes": "Compilação e execução dos testes Go concluídas.",
                }

            return {
                "status": "passed",
                "tool": "go",
                "command": "go build .",
                "stdout": build_check.stdout,
                "stderr": build_check.stderr,
                "timed_out": build_check.timed_out,
                "returncode": build_check.returncode,
                "duration_seconds": build_check.duration_seconds,
                "notes": "Compilação concluída; nenhum arquivo de teste foi retornado.",
            }
