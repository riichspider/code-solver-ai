"""Tests for Ruby language support."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.ruby_validator import RubyValidator, validate_ruby
from tests.test_helpers import TempDirMixin


class TestRubyValidator(TempDirMixin, unittest.TestCase):
    """Test Ruby validation functionality."""
    
    def setUp(self) -> None:
        """Set up test environment."""
        super().setUp()
        self.validator = RubyValidator(timeout_seconds=10)
    
    def test_simple_class_compilation(self) -> None:
        """Test compilation of simple Ruby class."""
        code = """class Calculator
  def initialize
    @result = 0.0
  end
  
  def add(value)
    @result += value
    @result
  end
  
  def result
    @result
  end
end
"""
        
        tests = """require 'minitest/autorun'

class TestCalculator < Minitest::Test
  def setup
    @calc = Calculator.new
  end
  
  def test_addition
    assert_equal 5, @calc.add(2)
    assert_equal 10, @calc.add(5)
  end
  
  def test_initial_result
    assert_equal 0.0, @calc.result
  end
end
"""
        
        result = self.validator.validate(code, tests)
        
        # Check if Ruby is available
        if "not found" in result.get("notes", ""):
            self.skipTest("Ruby interpreter not available")
            return
        
        # Should either pass or fail with details
        self.assertIn("status", result)
        self.assertIn("stdout", result)
        self.assertIn("stderr", result)
        self.assertIn("notes", result)
    
    def test_module_implementation(self) -> None:
        """Test Ruby module implementation."""
        code = """module MathOperations
  def self.add(a, b)
    a + b
  end
  
  def self.multiply(a, b)
    a * b
  end
  
  def self.factorial(n)
    return 1 if n <= 1
    n * factorial(n - 1)
  end
end
"""
        
        tests = """require 'minitest/autorun'

class TestMathOperations < Minitest::Test
  def test_addition
    assert_equal 5, MathOperations.add(2, 3)
  end
  
  def test_multiplication
    assert_equal 6, MathOperations.multiply(2, 3)
  end
  
  def test_factorial
    assert_equal 1, MathOperations.factorial(1)
    assert_equal 2, MathOperations.factorial(2)
    assert_equal 6, MathOperations.factorial(3)
  end
end
"""
        
        result = self.validator.validate(code, tests)
        
        if "not found" in result.get("notes", ""):
            self.skipTest("Ruby interpreter not available")
            return
        
        self.assertIn("status", result)
    
    def test_ruby_idioms(self) -> None:
        """Test Ruby idiomatic code."""
        code = """def process_numbers(numbers)
  # Ruby idiomatic processing
  squares = numbers.map { |n| n ** 2 }
  evens = numbers.select { |n| n.even? }
  sum = numbers.reduce(0, :+)
  
  {
    original: numbers,
    squares: squares,
    evens: evens,
    sum: sum
  }
end
"""
        
        tests = """require 'minitest/autorun'

class TestRubyIdioms < Minitest::Test
  def test_process_numbers
    input = [1, 2, 3, 4, 5]
    result = process_numbers(input)
    
    assert_equal [1, 4, 9, 16, 25], result[:squares]
    assert_equal [2, 4], result[:evens]
    assert_equal 15, result[:sum]
  end
end
"""
        
        result = self.validator.validate(code, tests)
        
        if "not found" in result.get("notes", ""):
            self.skipTest("Ruby interpreter not available")
            return
        
        self.assertIn("status", result)
    
    def test_syntax_error_handling(self) -> None:
        """Test handling of syntax errors."""
        code = """class BrokenClass
  def initialize(
    @name = "test"
  end
end
"""
        
        tests = """require 'minitest/autorun'

class TestBrokenClass < Minitest::Test
  def test_initialization
    obj = BrokenClass.new
    assert_equal "test", obj.name
  end
end
"""
        
        result = self.validator.validate(code, tests)
        
        if "not found" in result.get("notes", ""):
            self.skipTest("Ruby interpreter not available")
            return
        
        # Should fail syntax check
        self.assertEqual(result["status"], "failed")
        self.assertIn("syntax", result["notes"].lower())
    
    def test_missing_ruby_handling(self) -> None:
        """Test handling when Ruby is not available."""
        # Mock the validator to simulate missing Ruby
        validator = RubyValidator()
        
        # Temporarily override the Ruby finding method
        original_find = validator._find_ruby_interpreter
        validator._find_ruby_interpreter = lambda: None
        
        try:
            result = validator.validate(
                "puts 'Hello, Ruby!'",
                "require 'minitest/autorun'"
            )
            
            self.assertEqual(result["status"], "failed")
            self.assertIn("not found", result["notes"])
        finally:
            # Restore original method
            validator._find_ruby_interpreter = original_find
    
    def test_convenience_function(self) -> None:
        """Test the convenience validate_ruby function."""
        code = """def greet(name)
  "Hello, #{name}!"
end

puts greet("Ruby")
"""
        
        tests = """require 'minitest/autorun'

class TestGreet < Minitest::Test
  def test_greet
    assert_equal "Hello, Ruby!", greet("Ruby")
  end
end
"""
        
        result = validate_ruby(code, tests, timeout_seconds=5)
        
        if "not found" in result.get("notes", ""):
            self.skipTest("Ruby interpreter not available")
            return
        
        self.assertIn("status", result)
        self.assertIn("stdout", result)
        self.assertIn("stderr", result)
        self.assertIn("notes", result)
    
    def test_timeout_handling(self) -> None:
        """Test timeout handling in Ruby validation."""
        # Create an infinite loop
        code = """while true
  # Infinite loop
end
"""
        
        tests = """require 'minitest/autorun'

class TestTimeout < Minitest::Test
  def test_nothing
    # Empty test
  end
end
"""
        
        # Use very short timeout
        validator = RubyValidator(timeout_seconds=1)
        result = validator.validate(code, tests)
        
        if "not found" in result.get("notes", ""):
            self.skipTest("Ruby interpreter not available")
            return
        
        # Should handle timeout gracefully
        self.assertIn("status", result)
    
    def test_ruby_version_check(self) -> None:
        """Test Ruby version checking."""
        result = self.validator._check_ruby_version()
        
        if "not found" in result.get("notes", ""):
            self.skipTest("Ruby interpreter not available")
            return
        
        self.assertIn("status", result)
        if result["status"] == "passed":
            self.assertIsNotNone(result["version"])
    
    def test_error_handling(self) -> None:
        """Test error handling in Ruby code."""
        code = """class DataProcessor
  def process(data)
    raise ArgumentError, "Data cannot be nil" if data.nil?
    data.to_s.upcase
  rescue StandardError => e
    "Error: #{e.message}"
  end
end
"""
        
        tests = """require 'minitest/autorun'

class TestDataProcessor < Minitest::Test
  def test_process_valid_data
    processor = DataProcessor.new
    assert_equal "HELLO", processor.process("hello")
  end
  
  def test_process_nil_data
    processor = DataProcessor.new
    assert_match(/Error:/, processor.process(nil))
  end
end
"""
        
        result = self.validator.validate(code, tests)
        
        if "not found" in result.get("notes", ""):
            self.skipTest("Ruby interpreter not available")
            return
        
        self.assertIn("status", result)


class TestRubyPrompts(unittest.TestCase):
    """Test Ruby prompt generation."""
    
    def test_ruby_classification_prompt(self) -> None:
        """Test Ruby classification prompt generation."""
        from templates.ruby_prompts import build_ruby_classification_user_prompt
        
        problem = "Create a class that manages user authentication"
        context = "Working on a Rails application"
        
        prompt = build_ruby_classification_user_prompt(problem, context)
        
        self.assertIn("Problem:", prompt)
        self.assertIn("Context:", prompt)
        self.assertIn("Ruby development", prompt)
        self.assertIn("Classify this programming problem", prompt)
    
    def test_ruby_reasoning_prompt(self) -> None:
        """Test Ruby reasoning prompt generation."""
        from templates.ruby_prompts import build_ruby_reasoning_user_prompt
        
        problem = "Implement a binary search tree"
        classification = "algorithm"
        complexity = 7
        context = "Data structures implementation"
        
        prompt = build_ruby_reasoning_user_prompt(problem, classification, complexity, context)
        
        self.assertIn("Problem:", prompt)
        self.assertIn("Classification:", prompt)
        self.assertIn("Complexity:", prompt)
        self.assertIn("Language: Ruby", prompt)
        self.assertIn("Ruby-specific aspects", prompt)
    
    def test_ruby_coding_prompt(self) -> None:
        """Test Ruby coding prompt generation."""
        from templates.ruby_prompts import build_ruby_coding_user_prompt
        
        problem = "Create a calculator class"
        classification = "feature"
        complexity = 5
        understanding = "Need a class with basic arithmetic operations"
        plan = ["Design class interface", "Implement methods", "Add tests"]
        language = "ruby"
        
        prompt = build_ruby_coding_user_prompt(problem, classification, complexity, understanding, plan, language)
        
        self.assertIn("Problem:", prompt)
        self.assertIn("Language: Ruby", prompt)
        self.assertIn("idiomatic Ruby code", prompt)
        self.assertIn("Ruby naming conventions", prompt)
        self.assertIn("Error handling with exceptions", prompt)
    
    def test_ruby_repair_prompt(self) -> None:
        """Test Ruby repair prompt generation."""
        from templates.ruby_prompts import build_ruby_repair_user_prompt
        
        original_code = "class Broken def initialize end"
        original_tests = "require 'minitest/autorun'"
        error_message = "syntax error"
        problem = "Fix class definition"
        
        prompt = build_ruby_repair_user_prompt(original_code, original_tests, error_message, problem)
        
        self.assertIn("Original Code:", prompt)
        self.assertIn("Original Tests:", prompt)
        self.assertIn("Error Message:", prompt)
        self.assertIn("Common Ruby issues", prompt)
    
    def test_ruby_template_examples(self) -> None:
        """Test Ruby template examples."""
        from templates.ruby_prompts import get_ruby_template_examples
        
        examples = get_ruby_template_examples()
        
        self.assertIn("simple_class", examples)
        self.assertIn("module_example", examples)
        self.assertIn("ruby_idioms", examples)
        self.assertIn("error_handling", examples)
        
        # Check that examples contain valid Ruby code
        self.assertIn("class Calculator", examples["simple_class"])
        self.assertIn("module MathOperations", examples["module_example"])
        self.assertIn("numbers.map", examples["ruby_idioms"])
        self.assertIn("rescue StandardError", examples["error_handling"])
    
    def test_ruby_framework_examples(self) -> None:
        """Test Ruby framework examples."""
        from templates.ruby_prompts import get_ruby_framework_examples
        
        examples = get_ruby_framework_examples()
        
        self.assertIn("minitest", examples)
        self.assertIn("rspec", examples)
        self.assertIn("rails_controller", examples)
        
        # Check that examples contain valid framework code
        self.assertIn("Minitest::Test", examples["minitest"])
        self.assertIn("RSpec.describe", examples["rspec"])
        self.assertIn("ApplicationController", examples["rails_controller"])
    
    def test_ruby_build_instructions(self) -> None:
        """Test Ruby build instructions."""
        from templates.ruby_prompts import get_ruby_build_instructions
        
        instructions = get_ruby_build_instructions()
        
        self.assertIn("Ruby Build Instructions", instructions)
        self.assertIn("ruby --version", instructions)
        self.assertIn("bundle install", instructions)
        self.assertIn("Testing Frameworks", instructions)
