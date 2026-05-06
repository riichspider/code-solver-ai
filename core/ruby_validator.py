"""Ruby language validator for Code Solver AI."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from utils.executor import SandboxExecutor
from utils.logger import get_logger, log_error


class RubyValidator:
    """Ruby solution validator with execution and testing support."""
    
    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds
        self.executor = SandboxExecutor(timeout_seconds=timeout_seconds)
        self.logger = get_logger("ruby_validator")
    
    def validate(
        self,
        code: str,
        tests: str,
        filename: str = "solution.rb",
        test_filename: str = "test_solution.rb",
    ) -> dict[str, Any]:
        """
        Validate Ruby solution with execution and test running.
        
        Args:
            code: Ruby solution code
            tests: Ruby test code
            filename: Solution filename
            test_filename: Test filename
            
        Returns:
            Validation result with status, output, and details
        """
        with tempfile.TemporaryDirectory(prefix="code-solver-ruby-") as temp_dir:
            workspace = Path(temp_dir)
            
            # Write solution file
            solution_file = workspace / filename
            solution_file.write_text(code, encoding="utf-8")
            
            # Write test file
            test_file = workspace / test_filename
            test_file.write_text(tests, encoding="utf-8")
            
            try:
                # Step 1: Check Ruby syntax
                syntax_result = self._check_ruby_syntax(solution_file)
                if syntax_result["status"] != "passed":
                    return syntax_result
                
                # Step 2: Run tests if provided
                if tests.strip():
                    test_result = self._run_ruby_tests(test_file, workspace)
                    return test_result
                else:
                    # Just run the solution
                    run_result = self._run_ruby_script(solution_file, workspace)
                    return run_result
                
            except Exception as e:
                log_error(
                    self.logger,
                    RuntimeError(f"Ruby validation failed: {str(e)}"),
                    context="validate_ruby",
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
                    "notes": "Ruby validation encountered an unexpected error"
                }
    
    def _check_ruby_syntax(self, source_file: Path) -> dict[str, Any]:
        """Check Ruby syntax using ruby -c."""
        try:
            # Check for Ruby interpreter
            ruby = self._find_ruby_interpreter()
            if not ruby:
                return {
                    "status": "failed",
                    "stdout": "",
                    "stderr": "",
                    "notes": "Ruby interpreter not found in environment"
                }
            
            # Syntax check command
            syntax_cmd = [ruby, "-c", str(source_file)]
            
            result = self.executor.run(
                command=syntax_cmd,
                cwd=source_file.parent
            )
            
            if result.returncode == 0:
                return {
                    "status": "passed",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "notes": "Ruby syntax check passed"
                }
            else:
                return {
                    "status": "failed",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "notes": "Ruby syntax check failed"
                }
                
        except Exception as e:
            return {
                "status": "failed",
                "stdout": "",
                "stderr": str(e),
                "notes": "Ruby syntax check error"
            }
    
    def _run_ruby_script(self, script_file: Path, workspace: Path) -> dict[str, Any]:
        """Run Ruby script."""
        try:
            # Check for Ruby interpreter
            ruby = self._find_ruby_interpreter()
            if not ruby:
                return {
                    "status": "failed",
                    "stdout": "",
                    "stderr": "",
                    "notes": "Ruby interpreter not found in environment"
                }
            
            # Run script command
            run_cmd = [ruby, str(script_file)]
            
            result = self.executor.run(
                command=run_cmd,
                cwd=workspace
            )
            
            status = "passed" if result.returncode == 0 else "failed"
            
            return {
                "status": status,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "notes": f"Ruby script {status}"
            }
            
        except Exception as e:
            return {
                "status": "failed",
                "stdout": "",
                "stderr": str(e),
                "notes": "Ruby script execution error"
            }
    
    def _run_ruby_tests(self, test_file: Path, workspace: Path) -> dict[str, Any]:
        """Run Ruby tests."""
        try:
            # Check for Ruby interpreter
            ruby = self._find_ruby_interpreter()
            if not ruby:
                return {
                    "status": "failed",
                    "stdout": "",
                    "stderr": "",
                    "notes": "Ruby interpreter not found in environment"
                }
            
            # Try different test runners
            test_runners = [
                # Try with Minitest
                [ruby, "-I", ".", "-r", "minitest/autorun", str(test_file)],
                # Try with Test::Unit
                [ruby, "-I", ".", str(test_file)],
                # Try with RSpec if available
                [ruby, "-S", "rspec", str(test_file)],
                # Just run the file
                [ruby, str(test_file)]
            ]
            
            for test_cmd in test_runners:
                try:
                    result = self.executor.run(
                        command=test_cmd,
                        cwd=workspace
                    )
                    
                    # If command not found, try next runner
                    if result.returncode == 127:  # Command not found
                        continue
                    
                    status = "passed" if result.returncode == 0 else "failed"
                    
                    return {
                        "status": status,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "notes": f"Ruby tests {status} with {test_cmd[1] if len(test_cmd) > 1 else 'ruby'}"
                    }
                    
                except Exception:
                    continue
            
            # If all runners failed, try basic execution
            return self._run_ruby_script(test_file, workspace)
            
        except Exception as e:
            return {
                "status": "failed",
                "stdout": "",
                "stderr": str(e),
                "notes": "Ruby test execution error"
            }
    
    def _find_ruby_interpreter(self) -> str | None:
        """Find available Ruby interpreter."""
        ruby_variants = ["ruby", "ruby3", "ruby2.7", "ruby2.6"]
        
        for ruby in ruby_variants:
            if shutil.which(ruby):
                return ruby
        
        return None
    
    def _check_ruby_version(self) -> dict[str, Any]:
        """Check Ruby version and capabilities."""
        try:
            ruby = self._find_ruby_interpreter()
            if not ruby:
                return {
                    "status": "failed",
                    "version": None,
                    "notes": "Ruby interpreter not found"
                }
            
            result = self.executor.run(command=[ruby, "--version"])
            
            if result.returncode == 0:
                version_output = result.stdout.strip() or result.stderr.strip()
                return {
                    "status": "passed",
                    "version": version_output,
                    "notes": "Ruby version detected"
                }
            else:
                return {
                    "status": "failed",
                    "version": None,
                    "notes": "Could not determine Ruby version"
                }
                
        except Exception as e:
            return {
                "status": "failed",
                "version": None,
                "notes": f"Error checking Ruby version: {str(e)}"
            }


def validate_ruby(
    code: str,
    tests: str,
    filename: str = "solution.rb",
    test_filename: str = "test_solution.rb",
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    """
    Convenience function for Ruby validation.
    
    Args:
        code: Ruby solution code
        tests: Ruby test code
        filename: Solution filename
        test_filename: Test filename
        timeout_seconds: Validation timeout
        
    Returns:
        Validation result
    """
    validator = RubyValidator(timeout_seconds=timeout_seconds)
    return validator.validate(code, tests, filename, test_filename)
