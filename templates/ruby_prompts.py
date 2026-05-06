"""Ruby language prompts for Code Solver AI."""

from __future__ import annotations

from utils.prompts import sanitize_input


def build_ruby_classification_user_prompt(problem: str, context_text: str) -> str:
    """Build user prompt for Ruby problem classification."""
    sanitized_problem = sanitize_input(problem)
    sanitized_context = sanitize_input(context_text)
    
    return f"""Problem: {sanitized_problem}

Context: {sanitized_context}

Classify this programming problem for Ruby development.

Consider:
- Is this a bug fix, feature implementation, algorithm, or optimization?
- What Ruby concepts are involved (OOP, metaprogramming, gems, Rails, etc.)?
- What complexity level (1-10) for Ruby implementation?
- What type of Ruby solution would be most appropriate?

Respond with classification details."""


def build_ruby_reasoning_user_prompt(
    problem: str,
    classification: str,
    complexity: int,
    context_text: str,
) -> str:
    """Build user prompt for Ruby problem reasoning."""
    sanitized_problem = sanitize_input(problem)
    sanitized_context = sanitize_input(context_text)
    
    return f"""Problem: {sanitized_problem}
Classification: {classification}
Complexity: {complexity}/10
Language: Ruby
Context: {sanitized_context}

Analyze this Ruby problem and create a structured solution plan.

Consider Ruby-specific aspects:
- Object-oriented design principles
- Dynamic typing and duck typing
- Metaprogramming capabilities
- Ruby idioms and conventions
- Gem dependencies and management
- Performance considerations
- Testing frameworks (Minitest, RSpec)

Provide step-by-step reasoning for Ruby implementation."""


def build_ruby_coding_user_prompt(
    problem: str,
    classification: str,
    complexity: int,
    understanding: str,
    plan: list[str],
    language: str,
) -> str:
    """Build user prompt for Ruby code generation."""
    sanitized_problem = sanitize_input(problem)
    
    plan_text = "\n".join(f"- {step}" for step in plan)
    
    return f"""Problem: {sanitized_problem}
Classification: {classification}
Complexity: {complexity}/10
Language: Ruby
Understanding: {understanding}

Plan:
{plan_text}

Generate complete Ruby solution with:

1. **Main Solution** (.rb file):
   - Clean, idiomatic Ruby code
   - Proper class/module structure
   - Ruby naming conventions
   - Error handling with exceptions
   - Documentation with comments
   - Type hints where appropriate (RBS/TypeProf if needed)

2. **Test Suite** (test_*.rb file):
   - Comprehensive test cases
   - Use Minitest or RSpec
   - Edge cases and error conditions
   - Test coverage for all methods
   - Mocking/stubbing where needed

3. **Dependencies**:
   - Gemfile if dependencies needed
   - Required gems and versions
   - Installation instructions

Focus on:
- Ruby idioms and best practices
- Clean Code principles
- Performance optimization
- Memory management
- Error handling and logging
- Test-driven development

Generate production-ready Ruby code."""


def build_ruby_repair_user_prompt(
    original_code: str,
    original_tests: str,
    error_message: str,
    problem: str,
) -> str:
    """Build user prompt for Ruby code repair."""
    sanitized_problem = sanitize_input(problem)
    
    return f"""Problem: {sanitized_problem}

Original Code:
```ruby
{original_code}
```

Original Tests:
```ruby
{original_tests}
```

Error Message:
{error_message}

The Ruby solution failed execution or testing. Analyze the issues and provide a corrected version.

Common Ruby issues to check:
- Syntax errors and indentation
- Method naming and scope issues
- Variable scope and visibility
- Exception handling problems
- Gem dependency conflicts
- Performance bottlenecks
- Logic errors in algorithms
- Test framework issues

Provide:
1. **Analysis**: What went wrong and why
2. **Corrected Code**: Fixed Ruby implementation
3. **Corrected Tests**: Updated test suite
4. **Explanation**: Changes made and reasoning

Ensure the corrected code runs cleanly and passes all tests."""


def get_ruby_template_examples() -> dict[str, str]:
    """Get Ruby template examples for reference."""
    return {
        "simple_class": """class Calculator
  def initialize
    @result = 0.0
  end
  
  def add(value)
    @result += value
    @result
  end
  
  def multiply(value)
    @result *= value
    @result
  end
  
  def result
    @result
  end
end
""",
        
        "module_example": """module MathOperations
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
""",
        
        "ruby_idioms": """# Ruby idiomatic examples
numbers = [1, 2, 3, 4, 5]

# Map transformation
squares = numbers.map { |n| n ** 2 }

# Filter selection
evens = numbers.select { |n| n.even? }

# Reduce aggregation
sum = numbers.reduce(0, :+)

# Symbol to proc
upcased = numbers.map(&:to_s).map(&:upcase)

# Safe navigation
user&.profile&.name

# Array#each with index
numbers.each_with_index do |number, index|
  puts "#{index}: #{number}"
end
""",
        
        "error_handling": """class DataProcessor
  def process_data(data)
    validate_data!(data)
    
    begin
      result = transform_data(data)
      save_result(result)
      result
    rescue StandardError => e
      log_error(e)
      raise ProcessingError, "Failed to process data: #{e.message}"
    end
  end
  
  private
  
  def validate_data!(data)
    raise ArgumentError, "Data cannot be nil" if data.nil?
    raise ArgumentError, "Data must be a hash" unless data.is_a?(Hash)
  end
  
  def transform_data(data)
    # Transformation logic
    data.transform_values(&:to_s)
  end
  
  def save_result(result)
    # Save logic
  end
  
  def log_error(error)
    puts "Error: #{error.class} - #{error.message}"
  end
end

class ProcessingError < StandardError; end
"""
    }


def get_ruby_framework_examples() -> dict[str, str]:
    """Get Ruby framework examples."""
    return {
        "minitest": """require 'minitest/autorun'

class TestCalculator < Minitest::Test
  def setup
    @calc = Calculator.new
  end
  
  def test_addition
    assert_equal 5, @calc.add(2)
    assert_equal 10, @calc.add(5)
  end
  
  def test_multiplication
    @calc.add(2)
    assert_equal 6, @calc.multiply(3)
  end
  
  def test_initial_result
    assert_equal 0.0, @calc.result
  end
end
""",
        
        "rspec": """RSpec.describe Calculator do
  let(:calculator) { Calculator.new }
  
  describe '#add' do
    it 'adds numbers correctly' do
      expect(calculator.add(2)).to eq(2)
      expect(calculator.add(3)).to eq(5)
    end
  end
  
  describe '#multiply' do
    it 'multiplies correctly' do
      calculator.add(2)
      expect(calculator.multiply(3)).to eq(6)
    end
  end
  
  describe '#result' do
    it 'returns current result' do
      expect(calculator.result).to eq(0.0)
    end
  end
end
""",
        
        "rails_controller": """class UsersController < ApplicationController
  before_action :set_user, only: [:show, :update, :destroy]
  
  def index
    @users = User.all
    render json: @users
  end
  
  def show
    render json: @user
  end
  
  def create
    @user = User.new(user_params)
    
    if @user.save
      render json: @user, status: :created
    else
      render json: @user.errors, status: :unprocessable_entity
    end
  end
  
  private
  
  def set_user
    @user = User.find(params[:id])
  end
  
  def user_params
    params.require(:user).permit(:name, :email)
  end
end
"""
    }


def get_ruby_build_instructions() -> str:
    """Get Ruby build instructions."""
    return """## Ruby Build Instructions

### Prerequisites
- Ruby 2.7+ or Ruby 3.0+
- RubyGems package manager
- Bundler for dependency management

### Installation Commands

#### Check Ruby Version:
```bash
ruby --version
gem --version
bundler --version
```

#### Install Dependencies:
```bash
# With Gemfile
bundle install

# Individual gems
gem install rspec
gem install minitest
```

### Running Code

#### Execute Ruby Script:
```bash
ruby solution.rb
```

#### Run Tests:
```bash
# With Minitest
ruby -I lib test_solution.rb

# With RSpec
rspec test_solution.rb

# With Bundler
bundle exec rspec
```

### Common Ruby Flags
- `-I path`: Add to load path
- `-r library`: Require library
- `-w`: Enable warnings
- `-e code`: Execute one-line code
- `-v`: Verbose mode

### Gemfile Example:
```ruby
source 'https://rubygems.org'

gem 'rspec', '~> 3.0'
gem 'minitest', '~> 5.0'
gem 'rubocop', '~> 1.0'
```

### Testing Frameworks
- **Minitest**: Built-in, lightweight
- **RSpec**: Feature-rich, BDD-style
- **Test::Unit**: Traditional xUnit style

### Development Tools
- **RuboCop**: Code style linter
- **SimpleCov**: Coverage analysis
- **Pry**: Debugging REPL
- **Bundler**: Dependency management
"""
