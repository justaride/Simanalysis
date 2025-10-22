# Contributing to Simanalysis

Thank you for your interest in contributing to Simanalysis! This document provides guidelines and instructions for contributing.

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Testing](#testing)
- [Code Style](#code-style)
- [Pull Request Process](#pull-request-process)

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you are expected to uphold this code.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Create a branch** for your changes
4. **Make your changes**
5. **Test your changes**
6. **Submit a pull request**

## Development Setup

### Prerequisites
- Python 3.9 or higher
- Git
- (Optional) The Sims 4 installed with mods for testing

### Installation

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/Simanalysis.git
cd Simanalysis

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with all dependencies
pip install -e ".[all]"

# Install pre-commit hooks
pre-commit install
```

### Verify Installation

```bash
# Run tests
pytest

# Run linter
ruff check .

# Run type checker
mypy src/simanalysis

# Run all pre-commit hooks
pre-commit run --all-files
```

## How to Contribute

### Reporting Bugs

When reporting bugs, please include:
- **Clear description** of the bug
- **Steps to reproduce** the issue
- **Expected behavior** vs actual behavior
- **System information** (OS, Python version)
- **Sample mod files** (if applicable and safe to share)
- **Error messages/stack traces**

### Suggesting Features

Feature requests are welcome! Please include:
- **Use case** - Why is this feature needed?
- **Proposed solution** - How should it work?
- **Alternatives considered** - What other approaches did you think about?
- **Impact** - Who benefits from this feature?

### Contributing Code

We welcome contributions in these areas:

1. **Parsers** - Improve DBPF/tuning/script parsing
2. **Detectors** - Add new conflict detection algorithms
3. **Analyzers** - Enhance analysis capabilities
4. **Reports** - Improve report generation
5. **Tests** - Expand test coverage
6. **Documentation** - Improve docs and examples
7. **Performance** - Optimize slow operations

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_dbpf_parser.py

# Run tests matching pattern
pytest -k "test_conflict"

# Run with coverage
pytest --cov=simanalysis --cov-report=html

# Run only fast tests
pytest -m "not slow"
```

### Writing Tests

- Place unit tests in `tests/unit/`
- Place integration tests in `tests/integration/`
- Use descriptive test names: `test_dbpf_parser_handles_invalid_header`
- Include docstrings explaining what is being tested
- Use fixtures for common test data
- Mark slow tests with `@pytest.mark.slow`

Example test:

```python
import pytest
from simanalysis.parsers.dbpf import DBPFReader

def test_dbpf_reader_parses_valid_header():
    """Test that DBPFReader correctly parses a valid DBPF header."""
    reader = DBPFReader("tests/fixtures/valid_package.package")
    header = reader.read_header()

    assert header.magic == b"DBPF"
    assert header.major_version == 2
    assert header.minor_version == 0
```

### Test Coverage

We aim for:
- **90%+ overall coverage**
- **100% coverage for critical parsers**
- **All public APIs tested**

Check coverage:
```bash
pytest --cov=simanalysis --cov-report=term-missing
```

## Code Style

### Python Style Guide

We follow PEP 8 with these specifics:
- **Line length:** 100 characters
- **Indentation:** 4 spaces
- **Quotes:** Double quotes for strings
- **Docstrings:** Google style
- **Type hints:** Required for all public functions

### Formatting

Code is automatically formatted with **Ruff**:

```bash
# Check formatting
ruff format --check .

# Apply formatting
ruff format .
```

### Linting

Code is linted with **Ruff**:

```bash
# Run linter
ruff check .

# Fix auto-fixable issues
ruff check --fix .
```

### Type Checking

Type hints are checked with **MyPy**:

```bash
mypy src/simanalysis
```

### Docstring Example

```python
def parse_tuning_file(xml_data: bytes) -> TuningData:
    """Parse XML tuning file data.

    Args:
        xml_data: Raw XML data as bytes

    Returns:
        TuningData object containing parsed information

    Raises:
        ValueError: If XML is invalid or missing required fields

    Example:
        >>> with open("tuning.xml", "rb") as f:
        ...     data = parse_tuning_file(f.read())
        >>> print(data.instance_id)
        12345678
    """
    # Implementation
```

## Pull Request Process

### Before Submitting

- [ ] All tests pass locally
- [ ] New code has tests
- [ ] Code is formatted with Ruff
- [ ] Type hints are added and pass MyPy
- [ ] Documentation is updated
- [ ] CHANGELOG.md is updated (if applicable)
- [ ] Commit messages are clear and descriptive

### Commit Messages

Use conventional commit format:

```
type(scope): description

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Formatting changes
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Adding/updating tests
- `chore`: Build/tooling changes

**Examples:**
```
feat(parser): add support for compressed DBPF resources

fix(detector): correct tuning conflict severity calculation

docs(readme): add installation instructions for Windows
```

### PR Description Template

```markdown
## Summary
Brief description of changes

## Changes
- List of specific changes
- Another change

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Manually tested with real mods

## Related Issues
Fixes #123
Relates to #456

## Checklist
- [ ] Tests pass
- [ ] Code is formatted
- [ ] Documentation updated
- [ ] CHANGELOG updated
```

### Review Process

1. **Automated checks** must pass (tests, linting, type checking)
2. **Code review** by maintainers
3. **Discussion** of implementation details if needed
4. **Approval** from at least one maintainer
5. **Merge** by maintainer

### After Merge

- Your contribution will be included in the next release
- You'll be added to CONTRIBUTORS.md (if not already there)
- Thank you for improving Simanalysis! 🎉

## Development Tips

### Working with Real Mods

If you have The Sims 4 installed:

```bash
# Analyze your own mods
simanalysis analyze --mods-dir ~/Documents/Electronic\ Arts/The\ Sims\ 4/Mods

# Use for testing (be careful not to commit personal mods)
export SIMS4_MODS_DIR=~/Documents/Electronic\ Arts/The\ Sims\ 4/Mods
pytest tests/integration/ --requires-mods
```

### Debugging

```bash
# Run pytest with debugger on failure
pytest --pdb

# Use ipdb for interactive debugging
import ipdb; ipdb.set_trace()

# Verbose output
pytest -vv
```

### Performance Profiling

```bash
# Profile with py-spy
py-spy record -o profile.svg -- python -m simanalysis analyze --mods-dir /path/to/mods

# Memory profiling
python -m memory_profiler scripts/profile_memory.py
```

## Questions?

- **Documentation:** Check the [docs/](docs/) directory
- **Discussions:** Use [GitHub Discussions](https://github.com/justaride/Simanalysis/discussions)
- **Issues:** Search [existing issues](https://github.com/justaride/Simanalysis/issues)
- **Discord:** Join the Sims 4 Modding Community Discord (link in README)

## Recognition

Contributors are recognized in:
- CONTRIBUTORS.md
- GitHub contributors page
- Release notes

Thank you for contributing to Simanalysis!

---

*"In complexity, we find clarity. In chaos, we find patterns."* - Derrick
