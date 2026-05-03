from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from utils.executor import SandboxExecutor


class SolutionValidator:
    def __init__(self, timeout_seconds: int = 20) -> None:
        self.timeout_seconds = timeout_seconds
        self.executor = SandboxExecutor(timeout_seconds=timeout_seconds)

    def validate(
        self,
        language: str,
        code: str,
        tests: str,
        filename: str,
        test_filename: str,
    ) -> dict[str, Any]:
        normalized_language = language.strip().lower()
        if normalized_language == "python":
            return self._validate_python(code, tests, filename, test_filename)
        if normalized_language == "javascript":
            return self._validate_javascript(code, tests, filename, test_filename)
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
    ) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="code-solver-") as temp_dir:
            workspace = Path(temp_dir)
            (workspace / filename).write_text(code, encoding="utf-8")
            command: list[str]
            if tests.strip():
                (workspace / test_filename).write_text(tests, encoding="utf-8")
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
    ) -> dict[str, Any]:
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
                execution = self.executor.run(command=["node", test_filename], cwd=workspace)
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
