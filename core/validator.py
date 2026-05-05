from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from utils.executor import SandboxExecutor
from utils.logger import get_logger, log_error


class SolutionValidator:
    def __init__(self, timeout_seconds: int = 20) -> None:
        self.timeout_seconds = timeout_seconds
        self.executor = SandboxExecutor(timeout_seconds=timeout_seconds)
        self.logger = get_logger("validator")

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
        if normalized_language == "typescript":
            return self._validate_typescript(code, tests, filename, test_filename)
        if normalized_language == "go":
            return self._validate_go(code, tests, filename, test_filename)
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
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
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
