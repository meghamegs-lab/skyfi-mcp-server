# Contributing to SkyFi MCP Server

Thank you for your interest in contributing to the SkyFi MCP Server project! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python 3.10 or later
- pip or uv
- Git

### Installation

1. **Fork the repository** on GitHub

2. **Clone your fork locally:**
   ```bash
   git clone https://github.com/your-username/skyfi-mcp-server.git
   cd skyfi-mcp-server
   ```

3. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. **Install dependencies in development mode:**
   ```bash
   pip install -e ".[dev]"
   ```

   Or with uv:
   ```bash
   uv pip install -e ".[dev]"
   ```

5. **Install pre-commit hooks (optional but recommended):**
   ```bash
   pre-commit install
   ```

## Making Changes

### Branch Naming Convention

Create a branch for your work using a clear naming pattern:

- Feature: `feature/description-of-feature`
- Bug fix: `fix/description-of-bug`
- Documentation: `docs/description-of-change`
- Refactoring: `refactor/description-of-refactor`

Example:
```bash
git checkout -b feature/add-new-api-endpoint
```

### Code Style

This project follows PEP 8 and uses:

- **Formatting:** `black` (line length: 120 characters)
- **Linting:** `ruff`
- **Type checking:** `mypy`
- **Import sorting:** `isort`

Run checks locally:
```bash
black src tests
ruff check src tests
mypy src
isort src tests
```

### Testing

All contributions must include tests. Run the test suite:

```bash
pytest tests/
pytest tests/ -v  # Verbose output
pytest tests/test_models.py  # Run specific test file
pytest tests/test_models.py::TestArchiveModel::test_archive_with_all_fields  # Run specific test
```

Aim for **>90% code coverage**:
```bash
pytest tests/ --cov=src/skyfi_mcp --cov-report=html
```

## Submitting Changes

### Commit Messages

Write clear, descriptive commit messages:

```
Add support for SAR product types in tasking orders

- Implement SAR-specific parameter validation
- Add tests for grazing angle constraints
- Update API models with new enum values

Closes #123
```

Guidelines:
- First line: concise summary (50 characters max)
- Blank line
- Detailed explanation if needed
- Reference related issues with `Closes #issue_number`

### Pull Request Process

1. **Push your branch to your fork:**
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Open a Pull Request on GitHub:**
   - Title: Clear summary of changes
   - Description: Explain what you changed and why
   - Link related issues: `Closes #123`
   - Include test coverage information

3. **Pull Request Template:**
   Use the provided `.github/pull_request_template.md`. Include:
   - Summary of changes
   - Type of change (bug fix, feature, refactoring, etc.)
   - Test plan (what you tested and how)
   - Breaking changes (if any)

4. **Ensure all checks pass:**
   - Tests must pass
   - Code coverage maintained
   - Linting checks pass
   - No merge conflicts

## Reporting Issues

### Bug Reports

Use the bug report template (`.github/ISSUE_TEMPLATE/bug_report.md`). Include:
- Clear title describing the issue
- Steps to reproduce
- Expected behavior vs actual behavior
- Environment details (Python version, OS, etc.)
- Screenshots or error logs if applicable

### Feature Requests

Use the feature request template (`.github/ISSUE_TEMPLATE/feature_request.md`). Include:
- Clear description of the desired feature
- Use cases and motivation
- Proposed API/UX changes (if applicable)
- Any implementation notes

## Project Structure

```
skyfi-mcp-server/
├── src/skyfi_mcp/
│   ├── api/           # API models and client
│   ├── auth/          # Authentication and tokens
│   ├── osm/           # OpenStreetMap utilities
│   ├── tools/         # MCP tool implementations
│   ├── webhooks/      # Webhook storage and handling
│   └── server.py      # Main MCP server
├── tests/             # Test suite
├── docs/              # Documentation
├── examples/          # Example configurations
└── pyproject.toml     # Project metadata
```

## Code Review

- All PRs require review before merging
- Please be open to feedback and suggestions
- Maintainers may request changes for consistency or quality
- Once approved, your changes will be merged to the main branch

## Licensing

By contributing to this project, you agree that your contributions will be licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Questions?

- Check existing issues and pull requests
- Open a discussion issue if you have questions
- See the main README.md for additional resources

Thank you for contributing to SkyFi MCP Server!
