# Simanalysis

Simanalysis helps Sims 4 players audit their mod folders. The current toolkit
collects useful statistics such as total mods and an estimated performance score
while laying the foundation for deeper conflict analysis.

## Features

- Count Sims 4 `.package` and `.ts4script` files inside a directory.
- Estimate a basic performance score based on the number of detected mods.
- Provide placeholder hooks for future conflict and dependency analysis.
- Ship a Typer-based command line interface and typed Python API.

## Installation

Create and activate a virtual environment, then install the project in editable
mode together with its development dependencies:

```bash
pip install -e .[dev]
```

The optional `dev` extra installs the tools used in continuous integration such
as Ruff, MyPy, and pytest.

## Usage

### Command line

After installation a `simanalysis` executable becomes available:

```bash
simanalysis --help
simanalysis analyze /path/to/Mods
```

The CLI prints the total number of mods discovered, the estimated performance
score, and any generated recommendations.

### Python API

```python
from pathlib import Path

from simanalysis import ModAnalyzer

mods_dir = Path("/path/to/Mods")
analyzer = ModAnalyzer()
result = analyzer.analyze_directory(mods_dir)
print(result.total_mods)
print(result.performance_score)
```

## Development

The repository uses Ruff, MyPy, and pytest. Run them locally before opening a
pull request:

```bash
ruff check
mypy .
pytest -q
```

## Contributing

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on local setup and
code style expectations.

## License

Simanalysis is distributed under the terms of the [MIT License](LICENSE).
