# Test Fixtures

This directory contains sample Sims 4 mod files for testing and demonstration purposes.

## Directory Structure

```
fixtures/
├── sample_mods/              # Sample mod files
│   ├── simple_mod.package           # Basic mod, no conflicts
│   ├── conflicting_mod_a.package    # Conflicts with mod B
│   ├── conflicting_mod_b.package    # Conflicts with mod A
│   ├── large_mod.package            # Multiple resources
│   └── script_mod.ts4script         # Python script mod
├── expected_results/         # Expected analysis outputs
│   └── (JSON files with expected results)
├── create_fixtures.py        # Script to regenerate fixtures
└── README.md                 # This file
```

## Sample Mods

### simple_mod.package
- **Size:** ~200 bytes
- **Resources:** 1
- **Tuning ID:** 0x11111111
- **Purpose:** Basic valid package with no conflicts
- **Use Case:** Test basic parsing and analysis

### conflicting_mod_a.package
- **Size:** ~400 bytes
- **Resources:** 2
- **Tuning ID:** 0xAAAAAAAA
- **Purpose:** First mod in conflict pair
- **Use Case:** Test conflict detection

### conflicting_mod_b.package
- **Size:** ~400 bytes
- **Resources:** 2
- **Tuning ID:** 0xAAAAAAAA (same as mod A!)
- **Purpose:** Second mod in conflict pair
- **Use Case:** Test conflict detection
- **Expected Conflict:** TUNING_OVERLAP with mod A

### large_mod.package
- **Size:** ~1 KB
- **Resources:** 10
- **Tuning ID:** 0x22222222 - 0x2222222B
- **Purpose:** Larger mod with multiple resources
- **Use Case:** Test performance metrics, multiple resource handling

### script_mod.ts4script
- **Size:** ~300 bytes
- **Type:** Python script
- **Purpose:** Example script mod with command injection
- **Use Case:** Test script parsing and analysis

## Using Fixtures

### In Tests

```python
import pytest
from pathlib import Path

@pytest.fixture
def sample_mods_dir():
    """Path to sample mods directory."""
    return Path(__file__).parent / "fixtures" / "sample_mods"

def test_analyze_fixtures(sample_mods_dir):
    """Test analysis on fixture mods."""
    from simanalysis.analyzers import ModAnalyzer

    analyzer = ModAnalyzer()
    result = analyzer.analyze_directory(sample_mods_dir)

    assert len(result.mods) == 5
    assert len(result.conflicts) >= 1  # Should detect A-B conflict
```

### For Manual Testing

```bash
# Analyze the fixtures
simanalysis analyze tests/fixtures/sample_mods --tui

# With interactive mode
simanalysis analyze tests/fixtures/sample_mods --interactive

# Export analysis
simanalysis analyze tests/fixtures/sample_mods --output fixtures_analysis.json
```

### For Documentation

The fixtures can be used to create screenshots and examples for documentation.

## Regenerating Fixtures

If fixtures need to be recreated:

```bash
cd tests/fixtures
python3 create_fixtures.py
```

## Expected Analysis Results

When analyzing the `sample_mods/` directory, you should expect:

```
Total Mods: 5
  - 4 packages (.package)
  - 1 script (.ts4script)

Total Conflicts: 1+
  - TUNING_OVERLAP between conflicting_mod_a and conflicting_mod_b
    - Instance ID: 0xAAAAAAAA
    - Severity: MEDIUM-HIGH (depends on tuning type classification)

Performance Metrics:
  - Total Size: ~2 KB
  - Resources: 15 (1 + 2 + 2 + 10)
  - Est. Load Time: <0.1s
  - Complexity: Low
```

## Binary Format Details

The `.package` files use the DBPF format:
- **Header:** 96 bytes
  - Magic: "DBPF" (bytes 0-3)
  - Version: 2.1 (bytes 4-11)
  - Index count (byte 40-43)
  - Index offset (bytes 44-47)
- **Index Entries:** 32 bytes each
  - Type ID: 0x545503B2 (XML tuning)
  - Group ID: 0x00000000
  - Instance ID: unique per resource
  - File offset, sizes
- **Resource Data:** zlib-compressed content

## Adding New Fixtures

To add new test fixtures:

1. Modify `create_fixtures.py`
2. Add new `create_package_file()` or `create_ts4script_file()` calls
3. Run the script to generate files
4. Update this README
5. Add expected results to `expected_results/`

## Notes

- These are **minimal valid** mod files
- They contain only the essential DBPF structure
- Real mods are typically larger and more complex
- These fixtures are for **testing only**
- Do NOT use these in an actual Sims 4 game!

## License

These fixture files are part of the Simanalysis test suite and are released under the same MIT license as the project.
