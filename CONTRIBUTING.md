# Contributing to Code Solver AI

Thank you for your interest in contributing to Code Solver AI! This document provides guidelines and information for contributors.

## Development Environment Setup

### Prerequisites

#### System Requirements
- **Python 3.10+** (tested with Python 3.10.0)
- **Ollama** - Local AI model service
- **Git** - For version control

#### Installation Steps

1. **Install Ollama**
   ```bash
   # Windows (winget)
   winget install Ollama.Ollama
   
   # macOS (brew)
   brew install ollama
   
   # Linux (curl)
   curl -fsSL https://ollama.ai/install.sh | sh
   ```

2. **Start Ollama Service**
   ```bash
   ollama serve
   ```

3. **Clone and Setup Project**
   ```bash
   git clone https://github.com/riichspider/code-solver-ai.git
   cd code-solver-ai
   
   # Create virtual environment
   python -m venv .venv
   
   # Activate environment
   # Windows PowerShell
   .venv\Scripts\activate
   # Linux/macOS
   source .venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt
   ```

4. **Install Development Dependencies**
   ```bash
   # Install in development mode
   pip install -e .
   ```

## Running Tests

### Test Suite
```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run specific test file
python -m pytest tests/test_solver.py
```

### Test Coverage
The project maintains 100% test pass rate with 24 tests covering:
- Core functionality (solver, classifier, reasoner, coder, validator)
- Multi-language support (TypeScript, Java, Go, Rust)
- Cache and history functionality
- CLI interface
- Export cleanup mechanism

## Running Streamlit Locally

### Development Server
```bash
# Start the web interface
streamlit run app.py
```

Access the interface at `http://localhost:8501` in your browser.

### Development Workflow
1. Make changes to code
2. Run tests to verify functionality
3. Test Streamlit interface if UI changes were made
4. Run health check to verify system status
   ```bash
   python main.py --health-check
   ```

## Commit Convention

We follow conventional commits format:

### Types
- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `refactor:` Code refactoring
- `test:` Test additions/modifications
- `chore:` Maintenance tasks

### Examples
```bash
git add .
git commit -m "feat: add new language support"
git commit -m "fix: resolve validation error"
git commit -m "docs: update README with examples"
git commit -m "test: add coverage for edge cases"
git commit -m "chore: update dependencies"
```

## Pull Request Process

### Before Submitting
1. **Fork the repository** on GitHub
2. **Create a feature branch** from `main`
3. **Make your changes** following the commit convention
4. **Run tests** to ensure everything works
5. **Update documentation** if applicable
6. **Ensure all tests pass** before submitting

### Submitting PR
1. **Push your branch** to your fork
2. **Open Pull Request** against `main` branch
3. **Fill PR template** with:
   - Clear description of changes
   - Related issues (if any)
   - Testing performed
   - Screenshots if UI changes

### PR Requirements
- **All tests must pass** (24/24 tests)
- **Code must follow existing style**
- **Documentation updated** if behavior changed
- **No breaking changes** without proper version bump

## Code of Conduct

### Basic Guidelines
- Be respectful and professional
- Provide constructive feedback
- Help others learn and grow
- Focus on what is best for the project

### Communication
- Use GitHub Issues for bug reports and feature requests
- Use Discussions for questions and ideas
- Follow existing issue templates when available

## Development Guidelines

### Code Style
- Follow existing code patterns
- Use type hints consistently
- Write clear, descriptive variable names
- Add docstrings to new functions
- Keep functions focused and small

### Testing
- Write tests for new features
- Test edge cases
- Use existing test helpers from `tests/test_helpers.py`
- Maintain 100% test pass rate

### Documentation
- Update README.md for user-facing changes
- Update CONTEXT.md for internal changes
- Add entries to CHANGELOG.md for significant changes
- Keep examples up to date

## Architecture Overview

### Core Components
- **core/solver.py** - Main pipeline orchestrator
- **core/classifier.py** - Problem classification
- **core/reasoner.py** - Solution planning
- **core/coder.py** - Code generation
- **core/validator.py** - Code validation
- **core/cache.py** - Cache with TTL + history

### Supporting Components
- **models/ollama_client.py** - Ollama API client
- **utils/prompts.py** - Prompt templates
- **utils/executor.py** - Safe execution sandbox
- **app.py** - Streamlit web interface
- **main.py** - CLI interface

## Getting Help

### Resources
- **Issues**: [GitHub Issues](https://github.com/riichspider/code-solver-ai/issues)
- **Discussions**: [GitHub Discussions](https://github.com/riichspider/code-solver-ai/discussions)
- **Documentation**: [README.md](README.md)

### Questions
If you have questions about contributing:
1. Check existing issues and discussions
2. Review this CONTRIBUTING.md guide
3. Open an issue with the "question" label

Thank you for contributing to Code Solver AI! 🚀
