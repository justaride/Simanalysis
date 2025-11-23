# Exceptions

Error handling and exception types in Simanalysis.

## Overview

Simanalysis uses a hierarchy of custom exceptions for precise error handling. All exceptions inherit from `SimanalysisError`.

## Exception Hierarchy

```
SimanalysisError (base)
├── DBPFError (DBPF parsing errors)
├── TuningError (tuning parsing errors)
├── ScriptError (script analysis errors)
└── AnalysisError (analysis errors)
```

## Core Exceptions

### SimanalysisError

Base exception for all Simanalysis errors.

```python
from simanalysis.exceptions import SimanalysisError

try:
    # Simanalysis operation
    pass
except SimanalysisError as e:
    print(f"Simanalysis error: {e}")
```

### DBPFError

Raised when DBPF package parsing fails.

```python
from pathlib import Path
from simanalysis.parsers.dbpf import DBPFReader
from simanalysis.exceptions import DBPFError

try:
    reader = DBPFReader(Path("invalid.package"))
    header = reader.read_header()
except DBPFError as e:
    print(f"Invalid DBPF file: {e}")
```

**Common causes:**
- Invalid DBPF magic bytes
- File too small for header
- Corrupted index table
- Invalid resource offsets

### TuningError

Raised when tuning XML parsing fails.

```python
from simanalysis.parsers.tuning import TuningParser
from simanalysis.exceptions import TuningError

try:
    parser = TuningParser()
    tuning = parser.parse(xml_data)
except TuningError as e:
    print(f"Tuning parsing error: {e}")
```

**Common causes:**
- Malformed XML structure
- Missing required attributes
- Invalid encoding
- Empty tuning data

### ScriptError

Raised when script analysis fails.

```python
from pathlib import Path
from simanalysis.parsers.script import ScriptAnalyzer
from simanalysis.exceptions import ScriptError

try:
    analyzer = ScriptAnalyzer()
    script_info = analyzer.analyze(Path("mod.ts4script"))
except ScriptError as e:
    print(f"Script analysis error: {e}")
```

**Common causes:**
- Invalid ZIP archive
- No Python files found
- Syntax errors in code
- Encoding issues

### AnalysisError

Raised when high-level analysis fails.

```python
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer
from simanalysis.exceptions import AnalysisError

try:
    analyzer = ModAnalyzer()
    result = analyzer.analyze_directory(Path("./mods"))
except AnalysisError as e:
    print(f"Analysis error: {e}")
```

**Common causes:**
- Invalid directory structure
- Permission denied
- Too many errors during analysis
- Memory constraints

## Error Handling Patterns

### Pattern 1: Catch Specific Exceptions

```python
from simanalysis.parsers.dbpf import DBPFReader
from simanalysis.exceptions import (
    DBPFError,
    TuningError,
    SimanalysisError,
)

try:
    reader = DBPFReader(path)
    header = reader.read_header()
    resources = reader.read_index()

except DBPFError as e:
    # Handle DBPF-specific errors
    print(f"DBPF error: {e}")
    # Maybe try to recover or skip file

except TuningError as e:
    # Handle tuning errors
    print(f"Tuning error: {e}")

except SimanalysisError as e:
    # Catch-all for Simanalysis errors
    print(f"General error: {e}")
```

### Pattern 2: Graceful Degradation

```python
from pathlib import Path
from simanalysis.parsers.dbpf import DBPFReader
from simanalysis.exceptions import DBPFError

def safe_parse(mod_path: Path) -> tuple[bool, str]:
    """Parse mod with error handling."""
    try:
        reader = DBPFReader(mod_path)
        header = reader.read_header()
        resources = reader.read_index()
        return True, f"Successfully parsed {len(resources)} resources"

    except DBPFError as e:
        return False, f"Failed to parse: {e}"

    except Exception as e:
        return False, f"Unexpected error: {e}"

# Usage
success, message = safe_parse(Path("mod.package"))
if success:
    print(f"✓ {message}")
else:
    print(f"✗ {message}")
```

### Pattern 3: Batch Processing with Errors

```python
from pathlib import Path
from typing import List, Tuple
from simanalysis.parsers.dbpf import DBPFReader
from simanalysis.exceptions import SimanalysisError

def batch_parse(mod_paths: List[Path]) -> Tuple[List, List]:
    """Parse multiple mods, collecting successes and failures."""
    successes = []
    failures = []

    for path in mod_paths:
        try:
            reader = DBPFReader(path)
            header = reader.read_header()
            resources = reader.read_index()
            successes.append((path, resources))

        except SimanalysisError as e:
            failures.append((path, str(e)))

        except Exception as e:
            failures.append((path, f"Unexpected: {e}"))

    return successes, failures

# Usage
successes, failures = batch_parse(mod_files)
print(f"Parsed: {len(successes)}/{len(mod_files)}")
if failures:
    print("\nFailed files:")
    for path, error in failures:
        print(f"  {path.name}: {error}")
```

### Pattern 4: Logging Errors

```python
import logging
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer
from simanalysis.exceptions import SimanalysisError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def analyze_with_logging(directory: Path):
    """Analyze with comprehensive logging."""
    try:
        analyzer = ModAnalyzer()
        result = analyzer.analyze_directory(directory)

        logger.info(f"Analysis complete: {len(result.mods)} mods, {len(result.conflicts)} conflicts")
        return result

    except SimanalysisError as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        raise

    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
        raise

# Usage
try:
    result = analyze_with_logging(Path("./mods"))
except Exception:
    logger.error("Failed to complete analysis")
```

### Pattern 5: Custom Error Messages

```python
from simanalysis.exceptions import DBPFError

class ModValidationError(DBPFError):
    """Custom error for mod validation."""
    pass

def validate_mod(mod_path):
    """Validate mod file."""
    if not mod_path.exists():
        raise ModValidationError(f"Mod file not found: {mod_path}")

    if mod_path.stat().st_size == 0:
        raise ModValidationError(f"Mod file is empty: {mod_path}")

    if mod_path.suffix not in [".package", ".ts4script"]:
        raise ModValidationError(f"Invalid mod file extension: {mod_path.suffix}")

# Usage
try:
    validate_mod(Path("mod.package"))
except ModValidationError as e:
    print(f"Validation failed: {e}")
```

## Error Recovery

### Retry Logic

```python
import time
from pathlib import Path
from simanalysis.parsers.dbpf import DBPFReader
from simanalysis.exceptions import DBPFError

def parse_with_retry(path: Path, max_retries: int = 3):
    """Parse with retry logic."""
    for attempt in range(max_retries):
        try:
            reader = DBPFReader(path)
            return reader.read_header()

        except DBPFError as e:
            if attempt < max_retries - 1:
                print(f"Attempt {attempt + 1} failed, retrying...")
                time.sleep(1)
            else:
                print(f"All {max_retries} attempts failed")
                raise
```

### Fallback Values

```python
from pathlib import Path
from simanalysis.parsers.dbpf import DBPFReader
from simanalysis.exceptions import DBPFError

def get_resource_count(path: Path) -> int:
    """Get resource count with fallback."""
    try:
        reader = DBPFReader(path)
        header = reader.read_header()
        return header.index_count

    except DBPFError:
        # Fallback to 0 on error
        return 0

# Usage
count = get_resource_count(Path("mod.package"))
print(f"Resources: {count}")
```

## Best Practices

### 1. Catch Specific Exceptions

```python
# Good - specific handling
try:
    ...
except DBPFError as e:
    handle_dbpf_error(e)
except TuningError as e:
    handle_tuning_error(e)

# Avoid - too broad
try:
    ...
except Exception as e:
    # Catches everything, including system exceptions
    pass
```

### 2. Preserve Tracebacks

```python
# Good - preserve traceback
try:
    ...
except DBPFError as e:
    logger.error("DBPF error", exc_info=True)
    raise

# Avoid - loses context
try:
    ...
except DBPFError as e:
    raise RuntimeError("Error occurred")
```

### 3. Provide Context

```python
# Good - detailed error
try:
    reader = DBPFReader(path)
except DBPFError as e:
    raise DBPFError(f"Failed to parse {path.name}: {e}") from e

# Avoid - generic error
try:
    reader = DBPFReader(path)
except DBPFError:
    raise DBPFError("Parse failed")
```

## See Also

- [DBPF Parser](parsers/dbpf.md) - DBPF parsing
- [Tuning Parser](parsers/tuning.md) - Tuning parsing
- [Mod Analyzer](analyzers/mod_analyzer.md) - Analysis pipeline
- [Troubleshooting](../user-guide/troubleshooting.md) - Common issues

---

**Version**: 3.0.0 | **Last Updated**: 2025-11-23
