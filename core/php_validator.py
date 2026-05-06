"""PHP language validator for Code Solver AI."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from utils.executor import SandboxExecutor
from utils.logger import get_logger, log_error


class PhpValidator:
    """PHP solution validator with execution and testing support."""

    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds
        self.executor = SandboxExecutor(timeout_seconds=timeout_seconds)
        self.logger = get_logger("php_validator")
        self._php_interpreter_cache: str | None = None

    def validate(
        self,
        code: str,
        tests: str,
        filename: str = "solution.php",
        test_filename: str = "test_solution.php",
    ) -> dict[str, Any]:
        """
        Validate PHP solution with execution and test running.

        Args:
            code: PHP solution code
            tests: PHP test code
            filename: Solution filename
            test_filename: Test filename

        Returns:
            Validation result with status, output, and details
        """
        with tempfile.TemporaryDirectory(prefix="code-solver-php-") as temp_dir:
            workspace = Path(temp_dir)

            # Write solution file
            solution_file = workspace / filename
            solution_file.write_text(code, encoding="utf-8")

            # Write test file
            test_file = workspace / test_filename
            test_file.write_text(tests, encoding="utf-8")

            try:
                # Step 1: Check PHP syntax
                syntax_result = self._check_php_syntax(solution_file)
                if syntax_result["status"] != "passed":
                    return syntax_result

                # Step 2: Run tests if provided
                if tests.strip():
                    test_result = self._run_php_tests(test_file, workspace)
                    return test_result
                else:
                    # Just run the solution
                    run_result = self._run_php_script(solution_file, workspace)
                    return run_result

            except Exception as e:
                log_error(
                    self.logger,
                    RuntimeError(f"PHP validation failed: {str(e)}"),
                    context="validate_php",
                    details={
                        "filename": filename,
                        "test_filename": test_filename,
                        "error": str(e)
                    }
                )
                return {
                    "status": "failed",
                    "stdout": "",
                    "stderr": f"Validation error: {str(e)}",
                    "timed_out": False,
                    "returncode": -1,
                    "duration_seconds": 0,
                    "notes": "PHP validation encountered an unexpected error"
                }

    def _check_php_syntax(self, source_file: Path) -> dict[str, Any]:
        """Check PHP syntax using php -l."""
        try:
            # Check for PHP interpreter
            php = self._find_php_interpreter()
            if not php:
                return {
                    "status": "failed",
                    "tool": "php",
                    "command": "",
                    "stdout": "",
                    "stderr": "",
                    "timed_out": False,
                    "returncode": -1,
                    "duration_seconds": 0,
                    "notes": "PHP interpreter not found in environment"
                }

            # Syntax check command
            syntax_cmd = [php, "-l", str(source_file)]

            result = self.executor.run(
                command=syntax_cmd,
                cwd=source_file.parent
            )

            status = "passed" if result.returncode == 0 and not result.timed_out else "failed"

            return {
                "status": status,
                "tool": "php",
                "command": " ".join(syntax_cmd),
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timed_out": result.timed_out,
                "returncode": result.returncode,
                "duration_seconds": result.duration_seconds,
                "notes": "PHP syntax check passed" if status == "passed" else "PHP syntax check failed"
            }

        except Exception as e:
            return {
                "status": "failed",
                "tool": "php",
                "command": "",
                "stdout": "",
                "stderr": str(e),
                "timed_out": False,
                "returncode": -1,
                "duration_seconds": 0,
                "notes": "PHP syntax check error"
            }

    def _run_php_script(self, script_file: Path, workspace: Path) -> dict[str, Any]:
        """Run PHP script."""
        try:
            # Check for PHP interpreter
            php = self._find_php_interpreter()
            if not php:
                return {
                    "status": "failed",
                    "tool": "php",
                    "command": "",
                    "stdout": "",
                    "stderr": "",
                    "timed_out": False,
                    "returncode": -1,
                    "duration_seconds": 0,
                    "notes": "PHP interpreter not found in environment"
                }

            # Run script command
            run_cmd = [php, str(script_file)]

            result = self.executor.run(
                command=run_cmd,
                cwd=workspace
            )

            status = "passed" if result.returncode == 0 and not result.timed_out else "failed"

            return {
                "status": status,
                "tool": "php",
                "command": " ".join(run_cmd),
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timed_out": result.timed_out,
                "returncode": result.returncode,
                "duration_seconds": result.duration_seconds,
                "notes": f"PHP script {status}"
            }

        except Exception as e:
            return {
                "status": "failed",
                "tool": "php",
                "command": "",
                "stdout": "",
                "stderr": str(e),
                "timed_out": False,
                "returncode": -1,
                "duration_seconds": 0,
                "notes": "PHP script execution error"
            }

    def _run_php_tests(self, test_file: Path, workspace: Path) -> dict[str, Any]:
        """Run PHP tests."""
        try:
            # Check for PHP interpreter
            php = self._find_php_interpreter()
            if not php:
                return {
                    "status": "failed",
                    "tool": "php",
                    "command": "",
                    "stdout": "",
                    "stderr": "",
                    "timed_out": False,
                    "returncode": -1,
                    "duration_seconds": 0,
                    "notes": "PHP interpreter not found in environment"
                }

            # Try different test runners
            test_runners = [
                # Try with PHPUnit
                [php, "vendor/bin/phpunit", str(test_file)],
                # Try with Pest
                [php, "vendor/bin/pest", str(test_file)],
                # Try with built-in PHP testing
                [php, str(test_file)],
                # Try with composer test
                ["composer", "test"]
            ]

            for test_cmd in test_runners:
                try:
                    # Validate command security before execution
                    if not self._validate_command_security(test_cmd):
                        continue

                    result = self.executor.run(
                        command=test_cmd,
                        cwd=workspace
                    )

                    # If command not found, try next runner
                    if result.returncode == 127:  # Command not found
                        continue

                    status = "passed" if result.returncode == 0 and not result.timed_out else "failed"

                    return {
                        "status": status,
                        "tool": test_cmd[0],
                        "command": " ".join(test_cmd),
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "timed_out": result.timed_out,
                        "returncode": result.returncode,
                        "duration_seconds": result.duration_seconds,
                        "notes": f"PHP tests {status} with {test_cmd[0]}"
                    }

                except Exception:
                    continue

            # If all runners failed, try basic execution
            return self._run_php_script(test_file, workspace)

        except Exception as e:
            return {
                "status": "failed",
                "tool": "php",
                "command": "",
                "stdout": "",
                "stderr": str(e),
                "timed_out": False,
                "returncode": -1,
                "duration_seconds": 0,
                "notes": "PHP test execution error"
            }

    def _find_php_interpreter(self) -> str | None:
        """Find available PHP interpreter (cached)."""
        if self._php_interpreter_cache is not None:
            return self._php_interpreter_cache

        php_variants = ["php", "php8", "php8.1", "php8.0", "php7.4"]

        for php in php_variants:
            if shutil.which(php):
                self._php_interpreter_cache = php
                return php

        self._php_interpreter_cache = None
        return None

    def _validate_command_security(self, command: list[str]) -> bool:
        """Validate command for security before execution."""
        # List of allowed commands and paths
        allowed_commands = {
            "php", "php8", "php8.1", "php8.0", "php7.4",
            "composer", "vendor/bin/phpunit", "vendor/bin/pest"
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

    def _check_php_version(self) -> dict[str, Any]:
        """Check PHP version and capabilities."""
        try:
            php = self._find_php_interpreter()
            if not php:
                return {
                    "status": "failed",
                    "version": None,
                    "notes": "PHP interpreter not found"
                }

            result = self.executor.run(command=[php, "--version"])

            if result.returncode == 0:
                version_output = result.stdout.strip() or result.stderr.strip()
                return {
                    "status": "passed",
                    "version": version_output,
                    "notes": "PHP version detected"
                }
            else:
                return {
                    "status": "failed",
                    "version": None,
                    "notes": "Could not determine PHP version"
                }

        except Exception as e:
            return {
                "status": "failed",
                "version": None,
                "notes": f"Error checking PHP version: {str(e)}"
            }

    def _check_composer(self) -> dict[str, Any]:
        """Check if Composer is available for dependency management."""
        try:
            if shutil.which("composer"):
                result = self.executor.run(command=["composer", "--version"])
                if result.returncode == 0:
                    return {
                        "status": "passed",
                        "version": result.stdout.strip(),
                        "notes": "Composer available"
                    }

            return {
                "status": "failed",
                "version": None,
                "notes": "Composer not found"
            }

        except Exception as e:
            return {
                "status": "failed",
                "version": None,
                "notes": f"Error checking Composer: {str(e)}"
            }


def validate_php(
    code: str,
    tests: str,
    filename: str = "solution.php",
    test_filename: str = "test_solution.php",
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    """
    Convenience function for PHP validation.

    Args:
        code: PHP solution code
        tests: PHP test code
        filename: Solution filename
        test_filename: Test filename
        timeout_seconds: Validation timeout

    Returns:
        Validation result
    """
    validator = PhpValidator(timeout_seconds=timeout_seconds)
    return validator.validate(code, tests, filename, test_filename)
