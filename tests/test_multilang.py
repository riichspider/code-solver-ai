from core.coder import CodeGenerator, LANGUAGE_DEFAULTS


class MultiLanguageClient:
    """Mock client that returns appropriate responses for different languages."""
    
    def __init__(self, language: str):
        self.language = language
        self.calls = 0
    
    def generate_json(self, **kwargs):
        self.calls += 1
        
        if self.language == "typescript":
            return {
                "filename": "solution.ts",
                "code": "function add(a: number, b: number): number {\n    return a + b;\n}",
                "test_filename": "test_solution.ts",
                "tests": "function testAdd() {\n    console.assert(add(2, 3) === 5);\n}",
                "explanation": ["TypeScript function with type annotations"],
                "notes": [],
            }
        elif self.language == "java":
            return {
                "filename": "Solution.java",
                "code": "public class Solution {\n    public int add(int a, int b) {\n        return a + b;\n    }\n}",
                "test_filename": "SolutionTest.java",
                "tests": "import org.junit.Test;\nimport static org.junit.Assert.*;\n\npublic class SolutionTest {\n    @Test\n    public void testAdd() {\n        Solution s = new Solution();\n        assertEquals(5, s.add(2, 3));\n    }\n}",
                "explanation": ["Java class with JUnit test"],
                "notes": [],
            }
        elif self.language == "go":
            return {
                "filename": "solution.go",
                "code": "package main\n\nfunc Add(a, b int) int {\n    return a + b\n}",
                "test_filename": "solution_test.go",
                "tests": "package main\n\nimport \"testing\"\n\nfunc TestAdd(t *testing.T) {\n    result := Add(2, 3)\n    if result != 5 {\n        t.Errorf(\"Expected 5, got %d\", result)\n    }\n}",
                "explanation": ["Go function with unit test"],
                "notes": [],
            }
        elif self.language == "rust":
            return {
                "filename": "solution.rs",
                "code": "pub fn add(a: i32, b: i32) -> i32 {\n    a + b\n}",
                "test_filename": "solution_test.rs",
                "tests": "#[cfg(test)]\nmod tests {\n    use super::*;\n\n    #[test]\n    fn test_add() {\n        assert_eq!(add(2, 3), 5);\n    }\n}",
                "explanation": ["Rust function with test module"],
                "notes": [],
            }
        else:
            raise ValueError(f"Unsupported language: {self.language}")


def test_typescript_code_generation():
    """Test TypeScript code generation and file naming."""
    generator = CodeGenerator(client=MultiLanguageClient("typescript"))
    
    result = generator.generate(
        problem="Create a TypeScript add function",
        classification="enhancement",
        language="typescript",
        understanding="Create a typed add function",
        plan_steps=["Write function with types"],
        constraints=["Use TypeScript"],
        risks=["Type errors"],
        success_criteria=["Code compiles"],
        context_text="",
        similar_context=[],
        model="fake-model",
        mode="fast",
        options={},
    )
    
    # Verify TypeScript-specific defaults
    assert result["filename"] == "solution.ts"
    assert result["test_filename"] == "test_solution.ts"
    
    # Verify TypeScript code structure
    assert "function add(" in result["code"]
    assert ": number" in result["code"]
    assert "return a + b" in result["code"]
    
    # Verify test structure
    assert "console.assert" in result["tests"]
    assert "add(2, 3) === 5" in result["tests"]


def test_java_code_generation():
    """Test Java code generation and file naming."""
    generator = CodeGenerator(client=MultiLanguageClient("java"))
    
    result = generator.generate(
        problem="Create a Java add method",
        classification="enhancement",
        language="java",
        understanding="Create a class with add method",
        plan_steps=["Write class with method"],
        constraints=["Use Java"],
        risks=["Compilation errors"],
        success_criteria=["Code compiles"],
        context_text="",
        similar_context=[],
        model="fake-model",
        mode="fast",
        options={},
    )
    
    # Verify Java-specific defaults
    assert result["filename"] == "Solution.java"
    assert result["test_filename"] == "SolutionTest.java"
    
    # Verify Java code structure
    assert "public class Solution" in result["code"]
    assert "public int add(" in result["code"]
    assert "return a + b" in result["code"]
    
    # Verify test structure
    assert "import org.junit.Test" in result["tests"]
    assert "assertEquals(5, s.add(2, 3))" in result["tests"]


def test_go_code_generation():
    """Test Go code generation and file naming."""
    generator = CodeGenerator(client=MultiLanguageClient("go"))
    
    result = generator.generate(
        problem="Create a Go add function",
        classification="enhancement",
        language="go",
        understanding="Create a Go function",
        plan_steps=["Write function"],
        constraints=["Use Go"],
        risks=["Syntax errors"],
        success_criteria=["Code compiles"],
        context_text="",
        similar_context=[],
        model="fake-model",
        mode="fast",
        options={},
    )
    
    # Verify Go-specific defaults
    assert result["filename"] == "solution.go"
    assert result["test_filename"] == "solution_test.go"
    
    # Verify Go code structure
    assert "package main" in result["code"]
    assert "func Add(a, b int) int" in result["code"]
    assert "return a + b" in result["code"]
    
    # Verify test structure
    assert "package main" in result["tests"]
    assert "import \"testing\"" in result["tests"]
    assert "func TestAdd(t *testing.T)" in result["tests"]


def test_rust_code_generation():
    """Test Rust code generation and file naming."""
    generator = CodeGenerator(client=MultiLanguageClient("rust"))
    
    result = generator.generate(
        problem="Create a Rust add function",
        classification="enhancement",
        language="rust",
        understanding="Create a Rust function",
        plan_steps=["Write function"],
        constraints=["Use Rust"],
        risks=["Borrow checker issues"],
        success_criteria=["Code compiles"],
        context_text="",
        similar_context=[],
        model="fake-model",
        mode="fast",
        options={},
    )
    
    # Verify Rust-specific defaults
    assert result["filename"] == "solution.rs"
    assert result["test_filename"] == "solution_test.rs"
    
    # Verify Rust code structure
    assert "pub fn add(a: i32, b: i32) -> i32" in result["code"]
    assert "a + b" in result["code"]
    
    # Verify test structure
    assert "#[cfg(test)]" in result["tests"]
    assert "mod tests" in result["tests"]
    assert "#[test]" in result["tests"]
    assert "assert_eq!(add(2, 3), 5)" in result["tests"]


def test_language_defaults_completeness():
    """Test that all supported languages have proper defaults."""
    supported_languages = ["python", "javascript", "typescript", "java", "go", "rust"]
    
    for lang in supported_languages:
        assert lang in LANGUAGE_DEFAULTS, f"Missing defaults for {lang}"
        filename, test_filename = LANGUAGE_DEFAULTS[lang]
        
        # Verify filename patterns
        assert filename.endswith(('.py', '.js', '.ts', '.java', '.go', '.rs')), \
            f"Invalid file extension for {lang}: {filename}"
        assert test_filename.endswith(('.py', '.js', '.ts', '.java', '.go', '.rs')), \
            f"Invalid test file extension for {lang}: {test_filename}"
        
        # Verify test filename patterns
        if lang == "java":
            assert "Test" in test_filename, f"Java test file should contain 'Test': {test_filename}"
        elif lang in ["go", "rust"]:
            assert "_test" in test_filename, f"{lang} test file should contain '_test': {test_filename}"
        else:
            assert "test_" in test_filename, f"{lang} test file should start with 'test_': {test_filename}"


def test_multilang_repair_functionality():
    """Test repair functionality works for all languages."""
    languages = ["typescript", "java", "go", "rust"]
    
    for lang in languages:
        generator = CodeGenerator(client=MultiLanguageClient(lang))
        
        # Create a mock solution that needs repair
        previous_solution = {
            "filename": LANGUAGE_DEFAULTS[lang][0],
            "test_filename": LANGUAGE_DEFAULTS[lang][1],
            "code": f"// Broken {lang} code",
            "tests": f"// Broken {lang} test",
            "explanation": ["Original broken solution"],
            "notes": [],
        }
        
        validation = {
            "status": "failed",
            "errors": ["Syntax error", "Logic error"],
            "details": {"line": 1}
        }
        
        repaired = generator.repair(
            problem=f"Repair {lang} function",
            language=lang,
            previous_solution=previous_solution,
            validation=validation,
            model="fake-model",
            options={},
        )
        
        # Verify repair returns valid structure
        assert "filename" in repaired
        assert "code" in repaired
        assert "tests" in repaired
        assert repaired["filename"] == LANGUAGE_DEFAULTS[lang][0]
        assert repaired["test_filename"] == LANGUAGE_DEFAULTS[lang][1]
