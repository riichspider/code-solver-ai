"""C++ language prompts for Code Solver AI."""

from __future__ import annotations

from utils.prompts import sanitize_input


def build_cpp_classification_user_prompt(problem: str, context_text: str) -> str:
    """Build user prompt for C++ problem classification."""
    sanitized_problem = sanitize_input(problem)
    sanitized_context = sanitize_input(context_text)
    
    return f"""Problem: {sanitized_problem}

Context: {sanitized_context}

Classify this programming problem for C++ development.

Consider:
- Is this a bug fix, feature implementation, algorithm, or optimization?
- What C++ concepts are involved (OOP, templates, STL, etc.)?
- What complexity level (1-10) for C++ implementation?
- What type of C++ solution would be most appropriate?

Respond with classification details."""


def build_cpp_reasoning_user_prompt(
    problem: str,
    classification: str,
    complexity: int,
    context_text: str,
) -> str:
    """Build user prompt for C++ problem reasoning."""
    sanitized_problem = sanitize_input(problem)
    sanitized_context = sanitize_input(context_text)
    
    return f"""Problem: {sanitized_problem}
Classification: {classification}
Complexity: {complexity}/10
Language: C++
Context: {sanitized_context}

Analyze this C++ problem and create a structured solution plan.

Consider C++-specific aspects:
- Memory management (RAII, smart pointers)
- Standard Library usage (STL containers, algorithms)
- Template considerations
- Performance implications
- Compilation requirements

Provide step-by-step reasoning for C++ implementation."""


def build_cpp_coding_user_prompt(
    problem: str,
    classification: str,
    complexity: int,
    understanding: str,
    plan: list[str],
    language: str,
) -> str:
    """Build user prompt for C++ code generation."""
    sanitized_problem = sanitize_input(problem)
    
    plan_text = "\n".join(f"- {step}" for step in plan)
    
    return f"""Problem: {sanitized_problem}
Classification: {classification}
Complexity: {complexity}/10
Language: C++
Understanding: {understanding}

Plan:
{plan_text}

Generate complete C++ solution with:

1. **Main Solution** (.cpp file):
   - Modern C++ (C++17 or later)
   - Proper includes and namespaces
   - RAII principles
   - Smart pointers where appropriate
   - STL containers and algorithms
   - Error handling with exceptions
   - Comments for complex logic

2. **Test Suite** (test_*.cpp file):
   - Comprehensive test cases
   - Edge cases and error conditions
   - Performance considerations
   - Memory leak detection
   - Output validation

3. **Build Instructions**:
   - Compilation command
   - Required libraries
   - Dependencies

Focus on:
- Code clarity and maintainability
- Performance optimization
- Memory safety
- Standard best practices
- Cross-platform compatibility (if applicable)

Generate production-ready C++ code."""


def build_cpp_repair_user_prompt(
    original_code: str,
    original_tests: str,
    error_message: str,
    problem: str,
) -> str:
    """Build user prompt for C++ code repair."""
    sanitized_problem = sanitize_input(problem)
    
    return f"""Problem: {sanitized_problem}

Original Code:
```cpp
{original_code}
```

Original Tests:
```cpp
{original_tests}
```

Error Message:
{error_message}

The C++ solution failed compilation or testing. Analyze the issues and provide a corrected version.

Common C++ issues to check:
- Memory management problems
- Include statement issues
- Template syntax errors
- STL usage mistakes
- Compilation flags needed
- Linking errors
- Runtime exceptions
- Logic errors

Provide:
1. **Analysis**: What went wrong and why
2. **Corrected Code**: Fixed C++ implementation
3. **Corrected Tests**: Updated test suite
4. **Explanation**: Changes made and reasoning

Ensure the corrected code compiles cleanly and passes all tests."""


def get_cpp_template_examples() -> dict[str, str]:
    """Get C++ template examples for reference."""
    return {
        "simple_function": """#include <iostream>
#include <vector>
#include <algorithm>

std::vector<int> sortNumbers(std::vector<int> numbers) {
    std::sort(numbers.begin(), numbers.end());
    return numbers;
}
""",
        
        "class_implementation": """#include <iostream>
#include <string>
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
""",
        
        "stl_usage": """#include <iostream>
#include <vector>
#include <map>
#include <algorithm>

void processItems() {
    std::vector<int> numbers = {1, 2, 3, 4, 5};
    std::map<std::string, int> scores;
    
    // Process with STL algorithms
    std::for_each(numbers.begin(), numbers.end(), [](int& n) {
        n *= 2;
    });
}
""",
        
        "smart_pointers": """#include <iostream>
#include <memory>
#include <vector>

class Data {
private:
    std::vector<int> values;
    
public:
    Data(std::vector<int> vals) : values(vals) {}
    
    void display() const {
        for (int val : values) {
            std::cout << val << " ";
        }
        std::cout << std::endl;
    }
};

void processData() {
    auto data = std::make_unique<Data>(std::vector<int>{1, 2, 3});
    data->display();
}
"""
    }


def get_cpp_build_instructions() -> str:
    """Get C++ build instructions."""
    return """## C++ Build Instructions

### Prerequisites
- C++ compiler (g++ 7+ or clang++ 5+)
- Make (optional, for build automation)

### Compilation Commands

#### Basic Compilation:
```bash
g++ -std=c++17 -Wall -Wextra -O2 solution.cpp -o solution
```

#### With Debug Info:
```bash
g++ -std=c++17 -g -Wall -Wextra solution.cpp -o solution
```

#### With Specific Libraries:
```bash
g++ -std=c++17 -Wall -Wextra solution.cpp -o solution -lpthread -lm
```

### Testing
```bash
# Compile and run
g++ -std=c++17 -Wall -Wextra test_solution.cpp -o test_solution
./test_solution
```

### Common Flags
- `-std=c++17`: Use C++17 standard
- `-Wall`: Enable all warnings
- `-Wextra`: Enable extra warnings
- `-O2`: Optimize for performance
- `-g`: Include debug information
- `-pthread`: Link pthread library (if needed)
"""
