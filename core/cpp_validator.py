"""C++ language validator for Code Solver AI."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from utils.executor import SandboxExecutor
from utils.logger import get_logger, log_error


class CppValidator:
    """C++ solution validator with compilation and execution support."""

    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds
        self.executor = SandboxExecutor(timeout_seconds=timeout_seconds)
        self.logger = get_logger("cpp_validator")
        self._compiler_cache: dict[str, str | None] = {}

    def validate(
        self,
        code: str,
        tests: str,
        filename: str = "solution.cpp",
        test_filename: str = "test_solution.cpp",
    ) -> dict[str, Any]:
        """
        Validate C++ solution with compilation and test execution.

        Args:
            code: C++ solution code
            tests: C++ test code
            filename: Solution filename
            test_filename: Test filename

        Returns:
            Validation result with status, output, and details
        """
        with tempfile.TemporaryDirectory(prefix="code-solver-cpp-") as temp_dir:
            workspace = Path(temp_dir)

            # Write solution file
            solution_file = workspace / filename
            solution_file.write_text(code, encoding="utf-8")

            # Write test file
            test_file = workspace / test_filename
            test_file.write_text(tests, encoding="utf-8")

            try:
                # Step 1: Compile solution
                compilation_result = self._compile_cpp(
                    solution_file, workspace)
                if compilation_result["status"] != "passed":
                    return compilation_result

                # Step 2: Compile and run tests
                test_result = self._compile_and_run_tests(test_file, workspace)
                return test_result

            except Exception as e:
                log_error(
                    self.logger,
                    RuntimeError(f"C++ validation failed: {str(e)}"),
                    context="validate_cpp",
                    details={
                        "filename": filename,
                        "test_filename": test_filename,
                        "error": str(e)
                    }
                )
                return {
                    "status": "failed",
                    "tool": "cpp-validator",
                    "command": "",
                    "stdout": "",
                    "stderr": f"Validation error: {str(e)}",
                    "timed_out": False,
                    "returncode": -1,
                    "duration_seconds": 0,
                    "notes": "C++ validation encountered an unexpected error"
                }

    def _compile_cpp(self, source_file: Path, workspace: Path) -> dict[str, Any]:
        """Compile C++ source file."""
        try:
            # Check for C++ compiler
            compiler = self._find_cpp_compiler()
            if not compiler:
                return {
                    "status": "failed",
                    "tool": "cpp-compiler",
                    "command": compiler,
                    "stdout": "",
                    "stderr": "",
                    "timed_out": False,
                    "returncode": -1,
                    "duration_seconds": 0,
                    "notes": "C++ compiler (g++/clang++) not found in environment"
                }

            # Compile command
            executable_name = source_file.stem
            executable_path = workspace / executable_name

            compile_cmd = [
                compiler,
                str(source_file),
                "-o", str(executable_path),
                "-std=c++17",
                "-Wall",
                "-Wextra",
                "-O2"
            ]

            # Validate command security
            if not self._validate_command_security(compile_cmd):
                return {
                    "status": "failed",
                    "tool": "cpp-compiler",
                    "command": " ".join(compile_cmd),
                    "stdout": "",
                    "stderr": "",
                    "timed_out": False,
                    "returncode": -1,
                    "duration_seconds": 0,
                    "notes": "Invalid compilation command detected"
                }

            result = self.executor.run(
                command=compile_cmd,
                cwd=workspace
            )

            status = "passed" if result.returncode == 0 and not result.timed_out else "failed"

            return {
                "status": status,
                "tool": "cpp",
                "command": " ".join(compile_cmd),
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timed_out": result.timed_out,
                "returncode": result.returncode,
                "duration_seconds": result.duration_seconds,
                "notes": "C++ compilation successful" if status == "passed" else "C++ compilation failed"
            }

        except Exception as e:
            return {
                "status": "failed",
                "tool": "cpp",
                "command": "",
                "stdout": "",
                "stderr": str(e),
                "timed_out": False,
                "returncode": -1,
                "duration_seconds": 0,
                "notes": "C++ compilation error"
            }

    def _compile_and_run_tests(self, test_file: Path, workspace: Path) -> dict[str, Any]:
        """Compile and run C++ tests."""
        try:
            # Check for C++ compiler
            compiler = self._find_cpp_compiler()
            if not compiler:
                return {
                    "status": "failed",
                    "tool": "cpp-compiler",
                    "command": compiler,
                    "stdout": "",
                    "stderr": "",
                    "timed_out": False,
                    "returncode": -1,
                    "duration_seconds": 0,
                    "notes": "C++ compiler (g++/clang++) not found in environment"
                }

            # Compile tests
            executable_name = test_file.stem
            executable_path = workspace / executable_name

            compile_cmd = [
                compiler,
                str(test_file),
                "-o", str(executable_path),
                "-std=c++17",
                "-Wall",
                "-Wextra",
                "-O2"
            ]

            # Validate command security
            if not self._validate_command_security(compile_cmd):
                return {
                    "status": "failed",
                    "tool": "cpp-compiler",
                    "command": " ".join(compile_cmd),
                    "stdout": "",
                    "stderr": "",
                    "timed_out": False,
                    "returncode": -1,
                    "duration_seconds": 0,
                    "notes": "Invalid compilation command detected"
                }

            compile_result = self.executor.run(
                command=compile_cmd,
                cwd=workspace
            )

            if compile_result.returncode != 0:
                return {
                    "status": "failed",
                    "tool": "cpp",
                    "command": " ".join(compile_cmd),
                    "stdout": compile_result.stdout,
                    "stderr": compile_result.stderr,
                    "timed_out": compile_result.timed_out,
                    "returncode": compile_result.returncode,
                    "duration_seconds": compile_result.duration_seconds,
                    "notes": "C++ test compilation failed"
                }

            # Validate execution command security
            if not self._validate_command_security([str(executable_path)]):
                return {
                    "status": "failed",
                    "tool": "cpp-executor",
                    "command": str(executable_path),
                    "stdout": "",
                    "stderr": "",
                    "timed_out": False,
                    "returncode": -1,
                    "duration_seconds": 0,
                    "notes": "Invalid execution command detected"
                }

            # Run tests
            run_result = self.executor.run(
                command=[str(executable_path)],
                cwd=workspace
            )

            status = "passed" if run_result.returncode == 0 and not run_result.timed_out else "failed"

            return {
                "status": status,
                "tool": "cpp",
                "command": str(executable_path),
                "stdout": run_result.stdout,
                "stderr": run_result.stderr,
                "timed_out": run_result.timed_out,
                "returncode": run_result.returncode,
                "duration_seconds": run_result.duration_seconds,
                "notes": f"C++ tests {status}"
            }

        except Exception as e:
            return {
                "status": "failed",
                "tool": "cpp",
                "command": "",
                "stdout": "",
                "stderr": str(e),
                "timed_out": False,
                "returncode": -1,
                "duration_seconds": 0,
                "notes": "C++ test execution error"
            }

    def _find_cpp_compiler(self) -> str | None:
        """Find available C++ compiler (cached)."""
        if self._compiler_cache is not None:
            return self._compiler_cache

        compilers = ["g++", "clang++", "cpp"]

        for compiler in compilers:
            if shutil.which(compiler):
                self._compiler_cache = compiler
                return compiler

        self._compiler_cache = None
        return None

    def _validate_command_security(self, command: list[str]) -> bool:
        """Validate command for security before execution."""
        # List of allowed commands and paths
        allowed_commands = {
            "g++", "clang++", "cpp"
        }

        if not command:
            return False

        # Check main command
        main_cmd = command[0]
        if main_cmd not in allowed_commands:
            return False

        # Check for dangerous patterns in arguments
        dangerous_patterns = [
            ";", "&", "|", "`", "$(", "${",
            ">", "<", ">>", "<<", "2>", "2>>",
            "rm ", "del ", "format ", "mkfs ",
            "wget ", "curl ", "nc ", "netcat "
        ]

        for arg in command[1:]:
            arg_str = str(arg)
            for pattern in dangerous_patterns:
                if pattern in arg_str:
                    return False

        return True


def validate_cpp(
    code: str,
    tests: str,
    filename: str = "solution.cpp",
    test_filename: str = "test_solution.cpp",
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    """
    Convenience function for C++ validation.

    Args:
        code: C++ solution code
        tests: C++ test code
        filename: Solution filename
        test_filename: Test filename
        timeout_seconds: Validation timeout

    Returns:
        Validation result
    """
    validator = CppValidator(timeout_seconds=timeout_seconds)
    return validator.validate(code, tests, filename, test_filename)
