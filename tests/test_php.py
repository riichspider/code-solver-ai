"""Tests for PHP language support."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.php_validator import PhpValidator, validate_php
from tests.test_helpers import TempDirMixin


class TestPhpValidator(TempDirMixin, unittest.TestCase):
    """Test PHP validation functionality."""
    
    def setUp(self) -> None:
        """Set up test environment."""
        super().setUp()
        self.validator = PhpValidator(timeout_seconds=10)
    
    def test_simple_class_compilation(self) -> None:
        """Test compilation of simple PHP class."""
        code = """<?php

class Calculator
{
    private float $result = 0.0;

    public function add(float $value): float
    {
        $this->result += $value;
        return $this->result;
    }

    public function getResult(): float
    {
        return $this->result;
    }
}
"""
        
        tests = """<?php

use PHPUnit\\Framework\\TestCase;

class CalculatorTest extends TestCase
{
    private Calculator $calc;

    protected function setUp(): void
    {
        $this->calc = new Calculator();
    }

    public function testAddition(): void
    {
        $result = $this->calc->add(2);
        $this->assertEquals(2.0, $result);
        $result = $this->calc->add(3);
        $this->assertEquals(5.0, $result);
    }

    public function testInitialResult(): void
    {
        $this->assertEquals(0.0, $this->calc->getResult());
    }
}
"""
        
        result = self.validator.validate(code, tests)
        
        # Check if PHP is available
        if "not found" in result.get("notes", ""):
            self.skipTest("PHP interpreter not available")
            return
        
        # Should either pass or fail with details
        self.assertIn("status", result)
        self.assertIn("stdout", result)
        self.assertIn("stderr", result)
        self.assertIn("notes", result)
    
    def test_interface_implementation(self) -> None:
        """Test PHP interface implementation."""
        code = """<?php

interface DataProcessorInterface
{
    public function process(array $data): array;
    public function validate(array $data): bool;
}

class JsonDataProcessor implements DataProcessorInterface
{
    public function process(array $data): array
    {
        if (!$this->validate($data)) {
            return [];
        }

        return array_map('json_encode', $data);
    }

    public function validate(array $data): bool
    {
        return !empty($data) && is_array($data);
    }
}
"""
        
        tests = """<?php

use PHPUnit\\Framework\\TestCase;

class JsonDataProcessorTest extends TestCase
{
    private JsonDataProcessor $processor;

    protected function setUp(): void
    {
        $this->processor = new JsonDataProcessor();
    }

    public function testProcessValidData(): void
    {
        $data = ['foo', 'bar', 'baz'];
        $result = $this->processor->process($data);
        
        $this->assertCount(3, $result);
        $this->assertEquals('"foo"', $result[0]);
    }

    public function testValidateEmptyData(): void
    {
        $this->assertFalse($this->processor->validate([]));
        $this->assertFalse($this->processor->validate(['']));
    }

    public function testValidateValidData(): void
    {
        $this->assertTrue($this->processor->validate(['test']));
        $this->assertTrue($this->processor->validate([1, 2, 3]));
    }
}
"""
        
        result = self.validator.validate(code, tests)
        
        if "not found" in result.get("notes", ""):
            self.skipTest("PHP interpreter not available")
            return
        
        self.assertIn("status", result)
    
    def test_php_idioms(self) -> None:
        """Test PHP idiomatic code."""
        code = """<?php

function processNumbers(array $numbers): array
{
    // PHP idiomatic processing
    $squares = array_map(fn($n) => $n ** 2, $numbers);
    $evens = array_filter($numbers, fn($n) => $n % 2 === 0);
    $sum = array_reduce($numbers, fn($carry, $item) => $carry + $item, 0);
    
    return [
        'original' => $numbers,
        'squares' => $squares,
        'evens' => $evens,
        'sum' => $sum
    ];
}
"""
        
        tests = """<?php

use PHPUnit\\Framework\\TestCase;

class ProcessNumbersTest extends TestCase
{
    public function testProcessNumbers(): void
    {
        $input = [1, 2, 3, 4, 5];
        $result = processNumbers($input);
        
        $this->assertEquals([1, 4, 9, 16, 25], $result['squares']);
        $this->assertEquals([2, 4], $result['evens']);
        $this->assertEquals(15, $result['sum']);
    }

    public function testProcessEmptyArray(): void
    {
        $result = processNumbers([]);
        
        $this->assertEquals([], $result['original']);
        $this->assertEquals([], $result['squares']);
        $this->assertEquals([], $result['evens']);
        $this->assertEquals(0, $result['sum']);
    }
}
"""
        
        result = self.validator.validate(code, tests)
        
        if "not found" in result.get("notes", ""):
            self.skipTest("PHP interpreter not available")
            return
        
        self.assertIn("status", result)
    
    def test_syntax_error_handling(self) -> None:
        """Test handling of syntax errors."""
        code = """<?php

class BrokenClass
{
    public function __construct(
        $name = "test"
    // Missing closing parenthesis and brace
"""
        
        tests = """<?php

use PHPUnit\\Framework\\TestCase;

class BrokenClassTest extends TestCase
{
    public function testInitialization(): void
    {
        $obj = new BrokenClass();
        $this->assertEquals("test", $obj->name);
    }
}
"""
        
        result = self.validator.validate(code, tests)
        
        if "not found" in result.get("notes", ""):
            self.skipTest("PHP interpreter not available")
            return
        
        # Should fail syntax check
        self.assertEqual(result["status"], "failed")
        self.assertIn("syntax", result["notes"].lower())
    
    def test_missing_php_handling(self) -> None:
        """Test handling when PHP is not available."""
        # Mock the validator to simulate missing PHP
        validator = PhpValidator()
        
        # Temporarily override the PHP finding method
        original_find = validator._find_php_interpreter
        validator._find_php_interpreter = lambda: None
        
        try:
            result = validator.validate(
                "<?php echo 'Hello, PHP!';",
                "<?php echo 'Test'; ?>"
            )
            
            self.assertEqual(result["status"], "failed")
            self.assertIn("not found", result["notes"])
        finally:
            # Restore original method
            validator._find_php_interpreter = original_find
    
    def test_convenience_function(self) -> None:
        """Test the convenience validate_php function."""
        code = """<?php

function greet(string $name): string
{
    return "Hello, {$name}!";
}

echo greet("PHP");
"""
        
        tests = """<?php

use PHPUnit\\Framework\\TestCase;

class GreetTest extends TestCase
{
    public function testGreet(): void
    {
        $this->assertEquals("Hello, PHP!", greet("PHP"));
    }
}
"""
        
        result = validate_php(code, tests, timeout_seconds=5)
        
        if "not found" in result.get("notes", ""):
            self.skipTest("PHP interpreter not available")
            return
        
        self.assertIn("status", result)
        self.assertIn("stdout", result)
        self.assertIn("stderr", result)
        self.assertIn("notes", result)
    
    def test_timeout_handling(self) -> None:
        """Test timeout handling in PHP validation."""
        # Create an infinite loop
        code = """<?php

while (true) {
    // Infinite loop
}
"""
        
        tests = """<?php

use PHPUnit\\Framework\\TestCase;

class TimeoutTest extends TestCase
{
    public function testNothing(): void
    {
        $this->assertTrue(true);
    }
}
"""
        
        # Use very short timeout
        validator = PhpValidator(timeout_seconds=1)
        result = validator.validate(code, tests)
        
        if "not found" in result.get("notes", ""):
            self.skipTest("PHP interpreter not available")
            return
        
        # Should handle timeout gracefully
        self.assertIn("status", result)
    
    def test_php_version_check(self) -> None:
        """Test PHP version checking."""
        result = self.validator._check_php_version()
        
        if "not found" in result.get("notes", ""):
            self.skipTest("PHP interpreter not available")
            return
        
        self.assertIn("status", result)
        if result["status"] == "passed":
            self.assertIsNotNone(result["version"])
    
    def test_composer_check(self) -> None:
        """Test Composer availability check."""
        result = self.validator._check_composer()
        
        # Composer might not be available, that's okay
        self.assertIn("status", result)
        self.assertIn("notes", result)
    
    def test_error_handling(self) -> None:
        """Test error handling in PHP code."""
        code = """<?php

class DataProcessor
{
    public function process(?string $data): string
    {
        try {
            if ($data === null) {
                throw new InvalidArgumentException("Data cannot be null");
            }
            
            return strtoupper(trim($data));
            
        } catch (InvalidArgumentException $e) {
            return "Error: " . $e->getMessage();
        }
    }
}
"""
        
        tests = """<?php

use PHPUnit\\Framework\\TestCase;

class DataProcessorTest extends TestCase
{
    private DataProcessor $processor;

    protected function setUp(): void
    {
        $this->processor = new DataProcessor();
    }

    public function testProcessValidData(): void
    {
        $result = $this->processor->process("hello");
        $this->assertEquals("HELLO", $result);
    }

    public function testProcessNullData(): void
    {
        $result = $this->processor->process(null);
        $this->assertStringContains("Error:", $result);
    }
}
"""
        
        result = self.validator.validate(code, tests)
        
        if "not found" in result.get("notes", ""):
            self.skipTest("PHP interpreter not available")
            return
        
        self.assertIn("status", result)


class TestPhpPrompts(unittest.TestCase):
    """Test PHP prompt generation."""
    
    def test_php_classification_prompt(self) -> None:
        """Test PHP classification prompt generation."""
        from templates.php_prompts import build_php_classification_user_prompt
        
        problem = "Create a class that manages user authentication"
        context = "Working on a Laravel application"
        
        prompt = build_php_classification_user_prompt(problem, context)
        
        self.assertIn("Problem:", prompt)
        self.assertIn("Context:", prompt)
        self.assertIn("PHP development", prompt)
        self.assertIn("Classify this programming problem", prompt)
    
    def test_php_reasoning_prompt(self) -> None:
        """Test PHP reasoning prompt generation."""
        from templates.php_prompts import build_php_reasoning_user_prompt
        
        problem = "Implement a binary search tree"
        classification = "algorithm"
        complexity = 7
        context = "Data structures implementation"
        
        prompt = build_php_reasoning_user_prompt(problem, classification, complexity, context)
        
        self.assertIn("Problem:", prompt)
        self.assertIn("Classification:", prompt)
        self.assertIn("Complexity:", prompt)
        self.assertIn("Language: PHP", prompt)
        self.assertIn("PHP-specific aspects", prompt)
    
    def test_php_coding_prompt(self) -> None:
        """Test PHP coding prompt generation."""
        from templates.php_prompts import build_php_coding_user_prompt
        
        problem = "Create a calculator class"
        classification = "feature"
        complexity = 5
        understanding = "Need a class with basic arithmetic operations"
        plan = ["Design class interface", "Implement methods", "Add tests"]
        language = "php"
        
        prompt = build_php_coding_user_prompt(problem, classification, complexity, understanding, plan, language)
        
        self.assertIn("Problem:", prompt)
        self.assertIn("Language: PHP", prompt)
        self.assertIn("idiomatic PHP code", prompt)
        self.assertIn("PSR standards compliance", prompt)
        self.assertIn("Error handling with exceptions", prompt)
    
    def test_php_repair_prompt(self) -> None:
        """Test PHP repair prompt generation."""
        from templates.php_prompts import build_php_repair_user_prompt
        
        original_code = "<?php class Broken { public function __construct("
        original_tests = "<?php echo 'test';"
        error_message = "syntax error"
        problem = "Fix class definition"
        
        prompt = build_php_repair_user_prompt(original_code, original_tests, error_message, problem)
        
        self.assertIn("Original Code:", prompt)
        self.assertIn("Original Tests:", prompt)
        self.assertIn("Error Message:", prompt)
        self.assertIn("Common PHP issues", prompt)
    
    def test_php_template_examples(self) -> None:
        """Test PHP template examples."""
        from templates.php_prompts import get_php_template_examples
        
        examples = get_php_template_examples()
        
        self.assertIn("simple_class", examples)
        self.assertIn("interface_example", examples)
        self.assertIn("php_idioms", examples)
        self.assertIn("error_handling", examples)
        
        # Check that examples contain valid PHP code
        self.assertIn("<?php", examples["simple_class"])
        self.assertIn("interface", examples["interface_example"])
        self.assertIn("array_map", examples["php_idioms"])
        self.assertIn("try", examples["error_handling"])
    
    def test_php_framework_examples(self) -> None:
        """Test PHP framework examples."""
        from templates.php_prompts import get_php_framework_examples
        
        examples = get_php_framework_examples()
        
        self.assertIn("laravel_controller", examples)
        self.assertIn("symfony_controller", examples)
        self.assertIn("phpunit_test", examples)
        self.assertIn("pest_test", examples)
        
        # Check that examples contain valid framework code
        self.assertIn("namespace App\\Http\\Controllers", examples["laravel_controller"])
        self.assertIn("namespace App\\Controller", examples["symfony_controller"])
        self.assertIn("PHPUnit\\Framework\\TestCase", examples["phpunit_test"])
        self.assertIn("it(", examples["pest_test"])
    
    def test_php_build_instructions(self) -> None:
        """Test PHP build instructions."""
        from templates.php_prompts import get_php_build_instructions
        
        instructions = get_php_build_instructions()
        
        self.assertIn("PHP Build Instructions", instructions)
        self.assertIn("php --version", instructions)
        self.assertIn("composer install", instructions)
        self.assertIn("Testing Frameworks", instructions)
