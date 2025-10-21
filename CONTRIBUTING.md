# Contributing to Simanalysis

Thank you for your interest in improving Simanalysis! This guide summarizes the
local development workflow and coding standards used in the repository.

## Getting started

1. Fork and clone the repository.
2. Create and activate a Python 3.9+ virtual environment.
3. Install the project in editable mode with all development dependencies:
   ```bash
   pip install -e .[dev]
   ```
4. Install and configure pre-commit hooks:
   ```bash
   pre-commit install
   ```
   Run the hooks against the entire project before submitting changes:
   ```bash
   pre-commit run --all-files
   ```

## Development workflow

- Run `ruff check`, `mypy .`, and `pytest -q` before opening a pull request.
- Code is formatted using Ruff's formatter; no separate formatting step is
  required when the pre-commit hooks are installed.
- Maintain full type annotations for new code. If a change requires relaxing the
  strict MyPy configuration, document the reasoning in the pull request.

## Submitting changes

- Create feature branches off `main`.
- Include unit tests for new behavior and ensure they rely solely on the
  dependencies declared in `pyproject.toml`.
- Update documentation (`README.md`, docstrings, examples) when modifying the
  public API or CLI.
- Open a pull request with a clear summary of the change and reference any
  relevant issues.

## Code of conduct

Please be respectful and collaborative. Report any unacceptable behavior to the
repository maintainers.
