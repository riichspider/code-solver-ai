# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

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
