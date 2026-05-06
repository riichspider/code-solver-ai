"""PHP language prompts for Code Solver AI."""

from __future__ import annotations

from utils.prompts import sanitize_input


def build_php_classification_user_prompt(problem: str, context_text: str) -> str:
    """Build user prompt for PHP problem classification."""
    sanitized_problem = sanitize_input(problem)
    sanitized_context = sanitize_input(context_text)

    return f"""Problem: {sanitized_problem}

Context: {sanitized_context}

Classify this programming problem for PHP development.

Consider:
- Is this a bug fix, feature implementation, algorithm, or optimization?
- What PHP concepts are involved (OOP, frameworks, APIs, databases, etc.)?
- What complexity level (1-10) for PHP implementation?
- What type of PHP solution would be most appropriate?

Respond with classification details."""


def build_php_reasoning_user_prompt(
    problem: str,
    classification: str,
    complexity: int,
    context_text: str,
) -> str:
    """Build user prompt for PHP problem reasoning."""
    sanitized_problem = sanitize_input(problem)
    sanitized_context = sanitize_input(context_text)

    return f"""Problem: {sanitized_problem}
Classification: {classification}
Complexity: {complexity}/10
Language: PHP
Context: {sanitized_context}

Analyze this PHP problem and create a structured solution plan.

Consider PHP-specific aspects:
- Object-oriented design principles
- Framework integration (Laravel, Symfony, etc.)
- Database interactions
- API development patterns
- Security considerations
- Performance optimization
- Error handling and logging
- Testing frameworks (PHPUnit, Pest)

Provide step-by-step reasoning for PHP implementation."""


def build_php_coding_user_prompt(
    problem: str,
    classification: str,
    complexity: int,
    understanding: str,
    plan: list[str],
    language: str,
) -> str:
    """Build user prompt for PHP code generation."""
    sanitized_problem = sanitize_input(problem)

    plan_text = "\n".join(f"- {step}" for step in plan)

    return f"""Problem: {sanitized_problem}
Classification: {classification}
Complexity: {complexity}/10
Language: PHP
Understanding: {understanding}

Plan:
{plan_text}

Generate complete PHP solution with:

1. **Main Solution** (.php file):
   - Clean, idiomatic PHP code
   - Proper class/interface structure
   - PSR standards compliance
   - Type hints and return types
   - Error handling with exceptions
   - Documentation with PHPDoc
   - Security best practices

2. **Test Suite** (test_*.php file):
   - Comprehensive test cases
   - Use PHPUnit or Pest
   - Unit and integration tests
   - Mocking/stubbing where needed
   - Database test cases if applicable

3. **Dependencies**:
   - composer.json if dependencies needed
   - Required packages and versions
   - Installation instructions

Focus on:
- PHP 8+ features and best practices
- PSR standards compliance
- Security (input validation, SQL injection prevention)
- Performance optimization
- Error handling and logging
- Test-driven development
- Framework compatibility

Generate production-ready PHP code."""


def build_php_repair_user_prompt(
    original_code: str,
    original_tests: str,
    error_message: str,
    problem: str,
) -> str:
    """Build user prompt for PHP code repair."""
    sanitized_problem = sanitize_input(problem)

    return f"""Problem: {sanitized_problem}

Original Code:
```php
{original_code}
```

Original Tests:
```php
{original_tests}
```

Error Message:
{error_message}

The PHP solution failed execution or testing. Analyze the issues and provide a corrected version.

Common PHP issues to check:
- Syntax errors and missing semicolons
- Variable scope and visibility issues
- Type hinting problems
- Exception handling errors
- Database connection issues
- Security vulnerabilities
- Performance bottlenecks
- Logic errors in algorithms
- Test framework issues

Provide:
1. **Analysis**: What went wrong and why
2. **Corrected Code**: Fixed PHP implementation
3. **Corrected Tests**: Updated test suite
4. **Explanation**: Changes made and reasoning

Ensure the corrected code runs cleanly and passes all tests."""


def get_php_template_examples() -> dict[str, str]:
    """Get PHP template examples for reference."""
    return {
        "simple_class": """<?php

class Calculator
{
    private float $result = 0.0;

    public function add(float $value): float
    {
        $this->result += $value;
        return $this->result;
    }

    public function multiply(float $value): float
    {
        $this->result *= $value;
        return $this->result;
    }

    public function getResult(): float
    {
        return $this->result;
    }
}
""",

        "interface_example": """<?php

interface DataProcessorInterface
{
    public function process(array $data): array;
    public function validate(array $data): bool;
}

abstract class AbstractDataProcessor implements DataProcessorInterface
{
    protected array $errors = [];

    public function validate(array $data): bool
    {
        return !empty($data) && is_array($data);
    }

    protected function addError(string $error): void
    {
        $this->errors[] = $error;
    }

    public function getErrors(): array
    {
        return $this->errors;
    }
}

class JsonDataProcessor extends AbstractDataProcessor
{
    public function process(array $data): array
    {
        if (!$this->validate($data)) {
            $this->addError('Invalid data format');
            return [];
        }

        return array_map('json_encode', $data);
    }
}
""",

        "php_idioms": """<?php

// PHP idiomatic examples
$numbers = [1, 2, 3, 4, 5];

// Array transformation
$squares = array_map(fn($n) => $n ** 2, $numbers);

// Filter selection
$evens = array_filter($numbers, fn($n) => $n % 2 === 0);

// Array reduction
$sum = array_reduce($numbers, fn($carry, $item) => $carry + $item, 0);

// Null coalescing operator
$username = $_GET['username'] ?? 'guest';

// Spaceship operator for sorting
$users = usort($users, fn($a, $b) => $a['name'] <=> $b['name']);

// Type declarations
function calculateTotal(array $items, float $tax = 0.0): float
{
    $subtotal = array_sum(array_column($items, 'price'));
    return $subtotal * (1 + $tax);
}

// Generator function
function fibonacci(int $limit): Generator
{
    $a = 0;
    $b = 1;
    
    while ($a <= $limit) {
        yield $a;
        [$a, $b] = [$b, $a + $b];
    }
}
""",

        "error_handling": """<?php

class DataProcessor
{
    private PDO $db;
    private Logger $logger;

    public function __construct(PDO $db, Logger $logger)
    {
        $this->db = $db;
        $this->logger = $logger;
    }

    public function processUserData(int $userId): array
    {
        try {
            $this->validateUserId($userId);
            
            $userData = $this->fetchUserData($userId);
            $processedData = $this->transformData($userData);
            
            $this->saveProcessedData($userId, $processedData);
            
            return $processedData;
            
        } catch (InvalidArgumentException $e) {
            $this->logger->error("Invalid user ID: {$userId}", ['error' => $e->getMessage()]);
            throw new DataProcessingException("Invalid user ID provided", 0, $e);
            
        } catch (PDOException $e) {
            $this->logger->error("Database error processing user {$userId}", ['error' => $e->getMessage()]);
            throw new DataProcessingException("Database error occurred", 0, $e);
            
        } catch (Exception $e) {
            $this->logger->error("Unexpected error processing user {$userId}", ['error' => $e->getMessage()]);
            throw new DataProcessingException("Unexpected error occurred", 0, $e);
        }
    }

    private function validateUserId(int $userId): void
    {
        if ($userId <= 0) {
            throw new InvalidArgumentException("User ID must be positive");
        }
    }

    private function fetchUserData(int $userId): array
    {
        $stmt = $this->db->prepare("SELECT * FROM users WHERE id = ?");
        $stmt->execute([$userId]);
        
        $data = $stmt->fetch(PDO::FETCH_ASSOC);
        if (!$data) {
            throw new NotFoundException("User not found");
        }
        
        return $data;
    }

    private function transformData(array $data): array
    {
        return [
            'id' => $data['id'],
            'name' => strtoupper($data['name']),
            'email' => strtolower($data['email']),
            'processed_at' => date('Y-m-d H:i:s')
        ];
    }

    private function saveProcessedData(int $userId, array $data): void
    {
        $stmt = $this->db->prepare(
            "INSERT INTO processed_users (user_id, data, processed_at) VALUES (?, ?, ?)"
        );
        $stmt->execute([$userId, json_encode($data), date('Y-m-d H:i:s')]);
    }
}

class DataProcessingException extends Exception {}
class NotFoundException extends Exception {}
"""
    }


def get_php_framework_examples() -> dict[str, str]:
    """Get PHP framework examples."""
    return {
        "laravel_controller": """<?php

namespace App\\Http\\Controllers;
use App\\Models\\User;
use Illuminate\\Http\\Request;
use Illuminate\\Http\\JsonResponse;
use Illuminate\\Validation\\ValidationException;

class UserController extends Controller
{
    public function index(): JsonResponse
    {
        $users = User::all();
        return response()->json($users);
    }

    public function store(Request $request): JsonResponse
    {
        try {
            $validated = $request->validate([
                'name' => 'required|string|max:255',
                'email' => 'required|string|email|max:255|unique:users',
                'password' => 'required|string|min:8',
            ]);

            $user = User::create([
                'name' => $validated['name'],
                'email' => $validated['email'],
                'password' => bcrypt($validated['password']),
            ]);

            return response()->json($user, 201);
            
        } catch (ValidationException $e) {
            return response()->json([
                'message' => 'Validation failed',
                'errors' => $e->errors()
            ], 422);
        }
    }

    public function show(User $user): JsonResponse
    {
        return response()->json($user);
    }

    public function update(Request $request, User $user): JsonResponse
    {
        try {
            $validated = $request->validate([
                'name' => 'sometimes|string|max:255',
                'email' => 'sometimes|string|email|max:255|unique:users,email,' . $user->id,
            ]);

            $user->update($validated);
            return response()->json($user);
            
        } catch (ValidationException $e) {
            return response()->json([
                'message' => 'Validation failed',
                'errors' => $e->errors()
            ], 422);
        }
    }

    public function destroy(User $user): JsonResponse
    {
        $user->delete();
        return response()->json(null, 204);
    }
}
""",

        "symfony_controller": """<?php

namespace App\\Controller;

use App\\Entity\\User;
use App\\Form\\UserType;
use App\\Repository\\UserRepository;
use Doctrine\\ORM\\EntityManagerInterface;
use Symfony\\Bundle\\FrameworkBundle\\Controller\\AbstractController;
use Symfony\\Component\\HttpFoundation\\Request;
use Symfony\\Component\\HttpFoundation\\Response;
use Symfony\\Component\\Routing\\Annotation\\Route;

class UserController extends AbstractController
{
    #[Route('/users', name: 'user_index', methods: ['GET'])]
    public function index(UserRepository $userRepository): Response
    {
        $users = $userRepository->findAll();
        return $this->json($users);
    }

    #[Route('/users', name: 'user_create', methods: ['POST'])]
    public function create(Request $request, EntityManagerInterface $em): Response
    {
        $user = new User();
        $form = $this->createForm(UserType::class, $user);
        $form->handleRequest($request);

        if ($form->isSubmitted() && $form->isValid()) {
            $em->persist($user);
            $em->flush();

            return $this->json($user, Response::HTTP_CREATED);
        }

        return $this->json([
            'message' => 'Validation failed',
            'errors' => $form->getErrors(true)
        ], Response::HTTP_BAD_REQUEST);
    }

    #[Route('/users/{id}', name: 'user_show', methods: ['GET'])]
    public function show(User $user): Response
    {
        return $this->json($user);
    }
}
""",

        "phpunit_test": """<?php

namespace Tests\\Unit;

use PHPUnit\\Framework\\TestCase;
use App\\Services\\Calculator;

class CalculatorTest extends TestCase
{
    private Calculator $calculator;

    protected function setUp(): void
    {
        $this->calculator = new Calculator();
    }

    public function testAddition(): void
    {
        $result = $this->calculator->add(2, 3);
        $this->assertEquals(5, $result);
    }

    public function testMultiplication(): void
    {
        $result = $this->calculator->multiply(4, 5);
        $this->assertEquals(20, $result);
    }

    public function testDivisionByZero(): void
    {
        $this->expectException(\\InvalidArgumentException::class);
        $this->calculator->divide(10, 0);
    }

    public function testComplexCalculation(): void
    {
        $this->calculator->add(10);
        $this->calculator->multiply(2);
        $this->calculator->subtract(5);
        
        $this->assertEquals(15, $this->calculator->getResult());
    }

    /**
     * @dataProvider additionProvider
     */
    public function testAdditionWithDataProvider(int $a, int $b, int $expected): void
    {
        $result = $this->calculator->add($a, $b);
        $this->assertEquals($expected, $result);
    }

    public function additionProvider(): array
    {
        return [
            [1, 1, 2],
            [2, 3, 5],
            [10, 20, 30],
            [-5, 5, 0],
        ];
    }
}
""",

        "pest_test": """<?php

use App\\Services\\Calculator;

it('can add two numbers', function () {
    $calculator = new Calculator();
    $result = $calculator->add(2, 3);
    expect($result)->toBe(5);
});

it('can multiply two numbers', function () {
    $calculator = new Calculator();
    $result = $calculator->multiply(4, 5);
    expect($result)->toBe(20);
});

it('throws exception when dividing by zero', function () {
    $calculator = new Calculator();
    expect(fn() => $calculator->divide(10, 0))->toThrow(InvalidArgumentException::class);
});

it('performs complex calculations correctly', function () {
    $calculator = new Calculator();
    
    $calculator->add(10);
    $calculator->multiply(2);
    $calculator->subtract(5);
    
    expect($calculator->getResult())->toBe(15);
});
"""
    }


def get_php_build_instructions() -> str:
    """Get PHP build instructions."""
    return """## PHP Build Instructions

### Prerequisites
- PHP 8.0+ (recommended 8.1+)
- Composer for dependency management
- Web server (Apache, Nginx, or PHP built-in server)

### Installation Commands

#### Check PHP Version:
```bash
php --version
composer --version
```

#### Install Dependencies:
```bash
# With Composer
composer install

# Development dependencies
composer install --dev
```

### Running Code

#### Execute PHP Script:
```bash
php solution.php
```

#### Start Development Server:
```bash
php -S localhost:8000
```

#### Run Tests:
```bash
# With PHPUnit
./vendor/bin/phpunit

# With Pest
./vendor/bin/pest

# With Composer
composer test
```

### Common PHP Flags
- `-f filename`: Parse and execute file
- `-l filename`: Check syntax only
- `-m`: Show compiled modules
- `-i`: PHP information
- `-v`: Version information
- `-d key=value`: Set INI configuration

### Composer Configuration

#### composer.json Example:
```json
{
    "name": "vendor/project",
    "description": "PHP project description",
    "require": {
        "php": "^8.0"
    },
    "require-dev": {
        "phpunit/phpunit": "^9.0",
        "pestphp/pest": "^1.0"
    },
    "autoload": {
        "psr-4": {
            "App\\": "src/"
        }
    },
    "autoload-dev": {
        "psr-4": {
            "Tests\\": "tests/"
        }
    },
    "scripts": {
        "test": "phpunit",
        "test-pest": "pest"
    }
}
```

### Testing Frameworks
- **PHPUnit**: Traditional xUnit testing framework
- **Pest**: Modern, elegant testing framework
- **SimpleTest**: Lightweight testing solution
- **Codeception**: Full-stack testing framework

### Development Tools
- **PHP-CS-Fixer**: Code style fixer
- **PHPStan**: Static analysis
- **Psalm**: Static analysis with type checking
- **Xdebug**: Debugging and profiling

### PSR Standards
- **PSR-1**: Basic coding standard
- **PSR-2**: Coding style guide
- **PSR-4**: Autoloading standard
- **PSR-7**: HTTP message interface
- **PSR-12**: Extended coding style guide
"""
