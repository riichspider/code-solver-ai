# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [1.0.0] - 2026-05-05

### 🎉 Production Release
- **Real Ollama Validation**: Pipeline tested and validated with qwen2.5-coder:latest
- **Performance Benchmarks**: Comprehensive metrics and optimization guide
- **Production Deployment**: Docker, Kubernetes, and security configurations
- **Expansion Roadmap**: Strategic plan for language support and features

### ✅ Quality Improvements
- **39 Tests**: 100% pass rate covering all components
- **SonarQube Compliance**: All code smells resolved
- **Code Refactoring**: String literals extracted to constants
- **Exception Handling**: Improved error specificity and handling
- **Type Safety**: Enhanced type hints throughout codebase

### 📚 Documentation
- **Performance Benchmarks**: Detailed metrics and analysis
- **Release Plan**: Comprehensive v1.0.0 release strategy
- **Expansion Roadmap**: Multi-phase development plan
- **Production Deployment**: Complete deployment guide
- **Demo Section**: Working screenshot in README

### 🔧 Technical Features
- **Input Sanitization**: Protection against prompt injection
- **Structured Logging**: Comprehensive logging system
- **GitHub Labels**: Automated issue categorization
- **EditorConfig**: Consistent code formatting
- **Cache Optimization**: Improved TTL and storage management

### 🌟 User Experience
- **Streamlit Interface**: Validated with real Ollama models
- **CLI Enhancements**: Improved health checks and batch processing
- **Error Messages**: Clear and actionable feedback
- **Demo Functionality**: Complete working example

## [0.1.2] - 2026-05-06

### Added
- **C++ Validator Enhancement** - Complete robustness improvements
- **C++ Security** - Command injection protection for compilation
- **C++ Performance** - Compiler caching to reduce system calls
- **C++ Tests** - 3 new comprehensive tests (fields, security, cache)

### Fixed
- **C++ Validator Structure** - Added missing fields (tool, command, timed_out, returncode, duration_seconds)
- **C++ Error Handling** - Standardized error structure across all validation methods
- **C++ Timeout Handling** - Added proper timeout checks in compilation and execution
- **C++ Command Validation** - Prevent execution of dangerous compilation commands

### Performance
- **Compiler Cache** - Cache C++ compiler lookup results
- **Reduced System Calls** - Eliminate repeated compiler searches
- **Optimized Validation** - Faster validation with cached resources

### Security
- **Command Validation** - Prevent execution of dangerous commands in C++ compilation
- **Input Sanitization** - Validate compilation commands before execution
- **Injection Protection** - Block shell metacharacters and dangerous patterns

## [0.1.1] - 2026-05-05

### Added
- **PHP Language Support** - Complete PHP validation pipeline
- **PHP Templates** - Classification, reasoning, and coding prompts
- **PHP Security** - Command injection protection for test execution
- **PHP Performance** - Interpreter caching to reduce lookup overhead
- **PHP Tests** - 7 comprehensive unit tests for validator

### Fixed
- **PHP Validator Structure** - Added missing fields (tool, command, timed_out, returncode, duration_seconds)
- **PHP Error Handling** - Standardized error structure across all validation methods
- **PHP Import Safety** - Added try/catch for php_validator module import
- **Unicode Escapes** - Fixed \U sequences in PHP namespace declarations
- **Duplicate Commands** - Removed redundant test command in PHP runners
- **Timeout Handling** - Added proper timeout checks in all PHP validation methods

### Security
- **Command Validation** - Prevent execution of dangerous commands in PHP tests
- **Input Sanitization** - Validate test commands before execution
- **Safe Imports** - Graceful fallback when PHP validator unavailable

### Performance
- **Interpreter Cache** - Cache PHP interpreter lookup results
- **Reduced System Calls** - Eliminate repeated interpreter searches

## [0.1.0] - 2026-05-03

### Added
- Complete pipeline: classify → reason → code → validate
- Auto-repair functionality with intelligent fallback
- Consistent error handling with friendly messages
- Centralized solve_batch in core/solver.py
- Dedicated test helpers in tests/test_helpers.py
- Configurable cache TTL via config.yaml (default 24h)
- Optimized similarity with Jaccard pre-filtering
- Multi-language tests: TypeScript, Java, Go, Rust (6/6)
- Silent truncations documented with warnings
- Updated README with usage examples
- DeepSource integration (PRs #5 and #6 accepted)
- CI with pytest on GitHub Actions (.github/workflows/ci.yml)
- Real validation for TypeScript (tsc) and Go (go test)
- MIT license added (LICENSE)
- Health check CLI with --health-check
- Automatic exports cleanup (max 20 folders)
- Python 3.10 correctly declared in pyproject.toml
- SECURITY.md rewritten for v0.1.0
- Dependabot configured for pip
- README badges (CI, License, Python 3.10+, Languages)

### Fixed
- Fixed walrus operator syntax error in main.py health check
- Fixed git command chaining on Windows PowerShell
- Fixed Dependabot package-ecosystem configuration
- Fixed missing qwen2.5-coder:7b model in config.yaml
- Fixed GitHub Actions deprecation warnings (updated to v4)
- Fixed Python version quoting in CI matrix to prevent YAML parsing issues

### Security
- Added real TypeScript validation using tsc --noEmit
- Added real Go validation using go test ./...
- Added GitHub Actions CI workflow with pytest
- Added Dependabot for automated dependency updates
- Added SECURITY.md with proper vulnerability reporting guidelines
- Updated GitHub Actions to latest stable versions (v4)
