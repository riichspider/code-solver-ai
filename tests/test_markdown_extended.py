"""Extended test cases for utils/markdown.py to improve coverage."""

import pytest
from utils.markdown import render_solution_markdown, LANGUAGE_ALIASES


class TestLanguageAliases:
    """Test language aliases configuration."""

    def test_language_aliases_contains_expected_languages(self):
        """Test that all expected languages are in aliases."""
        expected_languages = ["python", "javascript", "typescript", "java", "go", "rust"]
        for lang in expected_languages:
            assert lang in LANGUAGE_ALIASES
            assert LANGUAGE_ALIASES[lang] == lang

    def test_language_aliases_is_complete(self):
        """Test that language aliases covers all supported languages."""
        # Should match the languages in config.yaml
        config_languages = ["python", "javascript", "typescript", "java", "go", "rust", "cpp", "ruby", "php"]
        
        # All config languages should either be in aliases or default to "text"
        for lang in config_languages:
            alias = LANGUAGE_ALIASES.get(lang, "text")
            assert alias in ["python", "javascript", "typescript", "java", "go", "rust", "text"]


class TestRenderSolutionMarkdownExtended:
    """Extended test cases for render_solution_markdown function."""

    def test_render_with_minimal_result(self):
        """Test rendering with minimal required fields."""
        minimal_result = {
            "classification": "bug",
            "complexity": 5,
            "labels": ["bug", "python"],
            "model": "qwen2.5-coder:latest",
            "mode": "fast",
            "understanding": "Test understanding",
            "plan_steps": ["Step 1", "Step 2"],
            "constraints": ["Constraint 1"],
            "risks": ["Risk 1"],
            "explanation": ["Explanation 1"],
            "code": "print('hello')",
            "tests": "assert True",
            "success_criteria": ["Criteria 1"]
        }
        
        markdown = render_solution_markdown(minimal_result)
        
        assert "# Code Solver AI Report" in markdown
        assert "## 1. Classification" in markdown
        assert "bug" in markdown
        assert "print('hello')" in markdown
        assert "assert True" in markdown

    def test_render_with_unknown_language(self):
        """Test rendering with unknown language defaults to text."""
        result = {
            "classification": "bug",
            "complexity": 5,
            "labels": ["bug"],
            "model": "test",
            "mode": "fast",
            "understanding": "Test",
            "plan_steps": [],
            "constraints": [],
            "risks": [],
            "explanation": [],
            "code": "some code",
            "tests": "some tests",
            "success_criteria": [],
            "language": "unknown_language"
        }
        
        markdown = render_solution_markdown(result)
        assert "```text" in markdown

    def test_render_with_cpp_language(self):
        """Test rendering with C++ language."""
        result = {
            "classification": "bug",
            "complexity": 5,
            "labels": ["bug"],
            "model": "test",
            "mode": "fast",
            "understanding": "Test",
            "plan_steps": [],
            "constraints": [],
            "risks": [],
            "explanation": [],
            "code": "#include <iostream>",
            "tests": "int main() { return 0; }",
            "success_criteria": [],
            "language": "cpp"
        }
        
        markdown = render_solution_markdown(result)
        assert "```text" in markdown  # CPP not in aliases, defaults to text

    def test_render_with_empty_optional_fields(self):
        """Test rendering with empty optional fields."""
        result = {
            "classification": "bug",
            "complexity": 5,
            "labels": ["bug"],
            "model": "test",
            "mode": "fast",
            "understanding": "Test",
            "plan_steps": [],
            "constraints": [],
            "risks": [],
            "explanation": [],
            "code": "test code",
            "tests": "",
            "success_criteria": [],
            "validation": {},
            "similar_context": [],
            "metadata": {}
        }
        
        markdown = render_solution_markdown(result)
        
        # Should handle empty tests gracefully
        assert "# No tests generated" in markdown
        # Should not include validation command if empty
        assert "- **Command:** n/a" in markdown

    def test_render_with_full_validation_details(self):
        """Test rendering with complete validation information."""
        result = {
            "classification": "bug",
            "complexity": 5,
            "labels": ["bug"],
            "model": "test",
            "mode": "fast",
            "understanding": "Test",
            "plan_steps": [],
            "constraints": [],
            "risks": [],
            "explanation": [],
            "code": "test code",
            "tests": "test",
            "success_criteria": [],
            "validation": {
                "status": "passed",
                "tool": "pytest",
                "command": "python -m pytest",
                "notes": "All tests passed",
                "stdout": "PASSED\n1 test passed",
                "stderr": ""
            }
        }
        
        markdown = render_solution_markdown(result)
        
        assert "- **Status:** passed" in markdown
        assert "- **Tool:** pytest" in markdown
        assert "- **Command:** `python -m pytest`" in markdown
        assert "- **Notes:** All tests passed" in markdown
        assert "### Stdout" in markdown
        assert "PASSED" in markdown
        assert "### Stderr" not in markdown  # Should not include empty stderr

    def test_render_with_stderr_only(self):
        """Test rendering with only stderr output."""
        result = {
            "classification": "bug",
            "complexity": 5,
            "labels": ["bug"],
            "model": "test",
            "mode": "fast",
            "understanding": "Test",
            "plan_steps": [],
            "constraints": [],
            "risks": [],
            "explanation": [],
            "code": "test code",
            "tests": "test",
            "success_criteria": [],
            "validation": {
                "status": "failed",
                "tool": "pytest",
                "notes": "Tests failed",
                "stdout": "",
                "stderr": "FAILED\nTest failed"
            }
        }
        
        markdown = render_solution_markdown(result)
        
        assert "### Stdout" not in markdown  # Should not include empty stdout
        assert "### Stderr" in markdown
        assert "FAILED" in markdown

    def test_render_with_similar_context(self):
        """Test rendering with similar context items."""
        result = {
            "classification": "bug",
            "complexity": 5,
            "labels": ["bug"],
            "model": "test",
            "mode": "fast",
            "understanding": "Test",
            "plan_steps": [],
            "constraints": [],
            "risks": [],
            "explanation": [],
            "code": "test code",
            "tests": "test",
            "success_criteria": [],
            "similar_context": [
                {
                    "score": 0.85,
                    "classification": "bug",
                    "language": "python",
                    "problem": "Similar null pointer issue"
                },
                {
                    "score": 0.72,
                    "classification": "enhancement",
                    "language": "javascript",
                    "problem": "Add input validation"
                }
            ]
        }
        
        markdown = render_solution_markdown(result)
        
        assert "## 11. Related History" in markdown
        assert "Score 0.85" in markdown
        assert "bug · python · Similar null pointer issue" in markdown
        assert "Score 0.72" in markdown
        assert "enhancement · javascript · Add input validation" in markdown

    def test_render_with_complete_metadata(self):
        """Test rendering with complete metadata."""
        result = {
            "classification": "bug",
            "complexity": 5,
            "labels": ["bug"],
            "model": "test",
            "mode": "fast",
            "understanding": "Test",
            "plan_steps": [],
            "constraints": [],
            "risks": [],
            "explanation": [],
            "code": "test code",
            "tests": "test",
            "success_criteria": [],
            "metadata": {
                "generated_at": "2026-05-07T14:30:00Z",
                "repair_applied": True,
                "context_files": ["src/main.py", "tests/test_main.py"]
            }
        }
        
        markdown = render_solution_markdown(result)
        
        assert "## 12. Metadata" in markdown
        assert "**Generated at:** 2026-05-07T14:30:00Z" in markdown
        assert "**Repair applied:** yes" in markdown
        assert "**Context files:** src/main.py, tests/test_main.py" in markdown

    def test_render_with_empty_metadata_fields(self):
        """Test rendering with empty metadata fields."""
        result = {
            "classification": "bug",
            "complexity": 5,
            "labels": ["bug"],
            "model": "test",
            "mode": "fast",
            "understanding": "Test",
            "plan_steps": [],
            "constraints": [],
            "risks": [],
            "explanation": [],
            "code": "test code",
            "tests": "test",
            "success_criteria": [],
            "metadata": {
                "generated_at": "",
                "repair_applied": False,
                "context_files": []
            }
        }
        
        markdown = render_solution_markdown(result)
        
        assert "**Generated at:** n/a" in markdown
        assert "**Repair applied:** no" in markdown
        assert "**Context files:** none" in markdown

    def test_render_output_format(self):
        """Test that output format is correct."""
        result = {
            "classification": "bug",
            "complexity": 5,
            "labels": ["bug"],
            "model": "test",
            "mode": "fast",
            "understanding": "Test",
            "plan_steps": ["Step 1"],
            "constraints": ["Constraint 1"],
            "risks": ["Risk 1"],
            "explanation": ["Explanation 1"],
            "code": "print('test')",
            "tests": "assert True",
            "success_criteria": ["Criteria 1"]
        }
        
        markdown = render_solution_markdown(result)
        
        # Should end with newline
        assert markdown.endswith("\n")
        
        # Should have proper section numbering
        assert "## 1. Classification" in markdown
        assert "## 2. Understanding" in markdown
        assert "## 3. Step-by-step Plan" in markdown
        assert "## 4. Constraints" in markdown
        assert "## 5. Risks" in markdown
        assert "## 6. Solution Explanation" in markdown
        assert "## 7. Generated Code" in markdown
        assert "## 8. Generated Tests" in markdown
        assert "## 9. Validation" in markdown
        assert "## 10. Success Criteria" in markdown

    def test_render_with_multiline_code_and_tests(self):
        """Test rendering with multiline code and tests."""
        result = {
            "classification": "bug",
            "complexity": 5,
            "labels": ["bug"],
            "model": "test",
            "mode": "fast",
            "understanding": "Test",
            "plan_steps": [],
            "constraints": [],
            "risks": [],
            "explanation": [],
            "code": "def function():\n    return 'hello'\n\nprint(function())",
            "tests": "def test_function():\n    assert function() == 'hello'\n    print('Test passed')",
            "success_criteria": []
        }
        
        markdown = render_solution_markdown(result)
        
        # Should preserve code formatting
        assert "def function():" in markdown
        assert "return 'hello'" in markdown
        assert "def test_function():" in markdown
        assert "assert function() == 'hello'" in markdown