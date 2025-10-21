# Contributing to Simanalysis

Thanks for your interest in improving Simanalysis! This guide explains how to set up a
development environment and run the automated checks that keep the project healthy.

## Getting Started

1. **Clone the repository**
   ```bash
   git clone https://github.com/<your-account>/Simanalysis.git
   cd Simanalysis
   ```

2. **Create a Python 3.11+ environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows use: .venv\\Scripts\\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -e .[dev]
   pre-commit install
   ```

## Running Checks

- **Formatting and linting**
  ```bash
  pre-commit run --all-files
  ```

- **Type checking**
  ```bash
  mypy
  ```

- **Tests with coverage**
  ```bash
  pytest --cov
  ```

## Submitting Changes

1. Create a feature branch from `main`.
2. Make your changes and include tests whenever possible.
3. Ensure all checks pass (`pre-commit run --all-files` and `pytest`).
4. Open a pull request describing your changes and any relevant context.

We appreciate your contributions! If you have questions, feel free to open an issue or
start a discussion thread.
