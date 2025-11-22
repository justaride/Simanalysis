# Test Fixtures

This directory contains comprehensive sample Sims 4 mod files for testing, demonstration, and edge case validation.

## Directory Structure

```
fixtures/
├── sample_mods/              # Generated fixture files
│   ├── simple_mod.package              # Basic mod, no conflicts
│   ├── conflicting_mod_a.package       # Conflicts with mod B
│   ├── conflicting_mod_b.package       # Conflicts with mod A
│   ├── large_mod.package               # Performance testing (50 resources)
│   ├── empty.package                   # Edge case: 0 bytes
│   ├── corrupted_header.package        # Edge case: Invalid DBPF magic
│   ├── truncated.package               # Edge case: Incomplete index
│   ├── uncompressed.package            # Edge case: Uncompressed resources
│   ├── script_mod_simple.ts4script     # Basic script with command
│   ├── script_mod_injection.ts4script  # Script with injection pattern
│   └── script_mod_conflicting.ts4script # Script with command conflict
├── expected_results/         # Expected analysis outputs (TODO)
├── create_fixtures.py        # DBPFBuilder script to regenerate fixtures
└── README.md                 # This file
```

## Core Test Fixtures

### simple_mod.package
- **Size:** 310 bytes
- **Resources:** 1
- **Type:** XML Tuning (SIMDATA)
- **Tuning ID:** `0x11111111`
- **Tuning Name:** `buff_simple_happy`
- **Purpose:** Minimal valid package with no conflicts
- **Use Cases:**
  - Basic DBPF parsing tests
  - Header/index validation
  - Single resource extraction

### conflicting_mod_a.package
- **Size:** 282 bytes
- **Resources:** 1
- **Tuning ID:** `0xAAAAAAAA` ⚠️
- **Tuning Name:** `buff_confident`
- **Attributes:** `mood_weight: 2`
- **Purpose:** First mod in conflict pair
- **Use Cases:**
  - Tuning conflict detection
  - Severity classification testing
  - Multi-mod analysis

### conflicting_mod_b.package
- **Size:** 282 bytes
- **Resources:** 1
- **Tuning ID:** `0xAAAAAAAA` ⚠️ (SAME AS MOD A!)
- **Tuning Name:** `buff_confident`
- **Attributes:** `mood_weight: 5` (DIFFERENT VALUE!)
- **Purpose:** Second mod in conflict pair
- **Expected Conflicts:**
  - `TUNING_OVERLAP` with `conflicting_mod_a.package`
  - Instance ID collision on `0xAAAAAAAA`
  - Severity: MEDIUM-HIGH
- **Use Cases:**
  - Conflict detection validation
  - Conflict reporting tests
  - Resolution recommendation generation

### large_mod.package
- **Size:** 9,359 bytes (~9 KB)
- **Resources:** 50
- **Tuning IDs:** `0x22220000` - `0x22220031` (50 consecutive IDs)
- **Tuning Names:** `buff_large_mod_0` through `buff_large_mod_49`
- **Purpose:** Performance testing with multiple resources
- **Use Cases:**
  - Index parsing performance
  - Memory efficiency testing
  - Large-scale analysis benchmarks
  - Progress reporting tests

## Edge Case Fixtures

### empty.package
- **Size:** 0 bytes
- **Purpose:** Test handling of completely empty files
- **Expected Behavior:**
  - Should raise `DBPFError` (file too small)
  - Error message: "File too small: expected at least 96 bytes, got 0"
- **Use Cases:**
  - Error handling validation
  - Graceful failure testing

### corrupted_header.package
- **Size:** 96 bytes
- **Header Magic:** `XXXX` (invalid, should be `DBPF`)
- **Purpose:** Test handling of corrupted DBPF headers
- **Expected Behavior:**
  - Should raise `DBPFError` during header validation
  - Error message: "Invalid DBPF magic"
- **Use Cases:**
  - Header validation tests
  - Malformed file detection

### truncated.package
- **Size:** 96 bytes (header only)
- **Header Claims:** 10 resources at offset 96
- **Actual Content:** Header ends immediately, no index table
- **Purpose:** Test handling of truncated/incomplete files
- **Expected Behavior:**
  - Should raise `DBPFError` when reading index
  - Error message: "Could not read complete index table"
- **Use Cases:**
  - Incomplete download simulation
  - Index parsing error handling

### uncompressed.package
- **Size:** 146 bytes
- **Resources:** 1 (uncompressed)
- **Resource Type:** `0x545503B2` (XML_TUNING)
- **Instance ID:** `0x33333333`
- **Data:** `b"Uncompressed test data"`
- **Purpose:** Test handling of uncompressed resources
- **Expected Behavior:**
  - Should read successfully without decompression
  - `is_compressed` property should be `False`
- **Use Cases:**
  - Compression detection tests
  - Mixed compression handling

## Script Mod Fixtures

### script_mod_simple.ts4script
- **Type:** Python script
- **Commands:** `test_command` (Live command type)
- **Imports:** `sims4.commands`
- **Purpose:** Basic script with single command registration
- **Expected Metadata:**
  - 1 command detected
  - Module imports: `sims4.commands`
- **Use Cases:**
  - Script parsing tests
  - Command detection
  - AST analysis validation

### script_mod_injection.ts4script
- **Type:** Python script with injection
- **Commands:** `custom_cmd`
- **Injections:** `inject_to(social_mixer.SocialMixer, 'apply_posture_state')`
- **Imports:** `sims4.commands`, `interactions.social_mixer`
- **Purpose:** Script with code injection pattern
- **Expected Metadata:**
  - 1 command detected
  - 1 injection pattern detected
  - High-risk injection: `social_mixer.SocialMixer`
- **Use Cases:**
  - Injection pattern detection
  - Conflict severity escalation
  - Security analysis tests

### script_mod_conflicting.ts4script
- **Type:** Python script
- **Commands:** `test_command` ⚠️ (CONFLICTS WITH simple!)
- **Purpose:** Script with duplicate command name
- **Expected Conflicts:**
  - `SCRIPT_CONFLICT` with `script_mod_simple.ts4script`
  - Command name collision: `test_command`
  - Severity: HIGH (command conflicts are serious)
- **Use Cases:**
  - Script conflict detection
  - Command collision handling
  - Multi-script analysis

## Using Fixtures

### In Unit Tests

```python
import pytest
from pathlib import Path

@pytest.fixture
def sample_mods_dir():
    """Path to sample mods directory."""
    return Path(__file__).parent / "fixtures" / "sample_mods"

@pytest.fixture
def simple_mod(sample_mods_dir):
    """Path to simple_mod.package."""
    return sample_mods_dir / "simple_mod.package"

def test_parse_simple_mod(simple_mod):
    """Test parsing a basic valid mod."""
    from simanalysis.parsers.dbpf import DBPFReader

    reader = DBPFReader(simple_mod)
    header = reader.read_header()

    assert header.major_version == 2
    assert header.index_count == 1

def test_detect_conflicts(sample_mods_dir):
    """Test conflict detection on conflicting mods."""
    from simanalysis.analyzers import ModAnalyzer

    analyzer = ModAnalyzer()
    result = analyzer.analyze_directory(sample_mods_dir)

    # Should detect tuning conflict between A and B
    tuning_conflicts = [c for c in result.conflicts
                       if c.conflict_type == "TUNING_OVERLAP"]
    assert len(tuning_conflicts) >= 1

    # Should detect script command conflict
    script_conflicts = [c for c in result.conflicts
                       if c.conflict_type == "SCRIPT_CONFLICT"]
    assert len(script_conflicts) >= 1
```

### In Integration Tests

```python
def test_full_analysis_pipeline(sample_mods_dir):
    """Test complete analysis pipeline on all fixtures."""
    from simanalysis.analyzers import ModAnalyzer

    analyzer = ModAnalyzer()
    result = analyzer.analyze_directory(sample_mods_dir)

    # Core mods (excluding edge cases which should fail)
    assert len(result.mods) == 7  # 4 packages + 3 scripts
    assert len(result.conflicts) >= 2  # Tuning + script conflicts

    # Performance metrics should be calculated
    assert result.performance.total_size_mb > 0
    assert result.performance.estimated_load_time_seconds >= 0
```

### For Manual Testing

```bash
# Analyze all fixtures (will skip edge cases that fail)
simanalysis analyze tests/fixtures/sample_mods

# With rich TUI
simanalysis analyze tests/fixtures/sample_mods --tui

# With interactive mode
simanalysis analyze tests/fixtures/sample_mods --interactive

# Export analysis
simanalysis analyze tests/fixtures/sample_mods --output fixtures_analysis.json

# Test individual fixture
simanalysis analyze tests/fixtures/sample_mods/simple_mod.package

# Enable debug logging to see parsing details
simanalysis analyze tests/fixtures/sample_mods --verbose
```

### For Documentation & Screenshots

The fixtures provide realistic examples for:
- README examples
- CLI usage demonstrations
- TUI screenshots
- Tutorial content
- Blog posts and presentations

## Regenerating Fixtures

The fixtures are programmatically generated using `DBPFBuilder` for reproducibility.

```bash
cd tests/fixtures
python3 create_fixtures.py
```

This will:
1. Create all 4 core packages (simple, conflicting A/B, large)
2. Create all 4 edge case files (empty, corrupted, truncated, uncompressed)
3. Create all 3 script mods (simple, injection, conflicting)
4. Output creation summary with file sizes

**Output:**
```
✅ Created: simple_mod.package (1 resources, 310 bytes)
✅ Created: conflicting_mod_a.package (1 resources, 282 bytes)
✅ Created: conflicting_mod_b.package (1 resources, 282 bytes)
✅ Created: large_mod.package (50 resources, 9359 bytes)
✅ Created: empty.package (0 bytes)
✅ Created: corrupted_header.package (corrupted header)
✅ Created: truncated.package (truncated)
✅ Created: uncompressed.package (1 resources, 146 bytes)
✅ Created: script_mod_simple.ts4script
✅ Created: script_mod_injection.ts4script
✅ Created: script_mod_conflicting.ts4script
```

## Expected Analysis Results

When analyzing the `sample_mods/` directory with valid fixtures, expect:

```
Total Mods: 7
  - 4 valid packages (.package files)
  - 3 script mods (.ts4script files)
  - 4 edge case files (will fail parsing, logged as errors)

Total Conflicts: 2+
  - TUNING_OVERLAP: conflicting_mod_a.package ↔ conflicting_mod_b.package
    - Instance ID: 0xAAAAAAAA (buff_confident)
    - Severity: MEDIUM-HIGH
    - Cause: Both modify same tuning with different values

  - SCRIPT_CONFLICT: script_mod_simple.ts4script ↔ script_mod_conflicting.ts4script
    - Command: test_command
    - Severity: HIGH
    - Cause: Duplicate command registration

Performance Metrics:
  - Total Size: ~10 KB (9,359 bytes for large_mod alone)
  - Resources: 53 total (1 + 1 + 1 + 50 from packages)
  - Est. Load Time: <0.1s
  - Complexity: Low-Medium
```

## DBPFBuilder API

The `create_fixtures.py` script uses a builder pattern for creating packages:

```python
from create_fixtures import DBPFBuilder

# Create a simple package
builder = DBPFBuilder(major_version=2, minor_version=1)
builder.add_xml_tuning(
    instance_id=0x12345678,
    tuning_name="my_custom_buff",
    tuning_class="Buff",
    module="buffs.buff_tuning",
    attributes={
        "visible": "True",
        "mood_weight": "3"
    }
)
builder.build(Path("my_custom_mod.package"))
```

**Builder Methods:**
- `add_resource(type, group, instance, data, compressed=True)` - Add any resource
- `add_xml_tuning(instance_id, tuning_name, ...)` - Add XML tuning (convenience)
- `build(output_path)` - Write package to disk

## Adding New Fixtures

To add new test fixtures:

1. **Edit `create_fixtures.py`:**
   ```python
   def create_new_fixture(output_dir: Path) -> None:
       builder = DBPFBuilder()
       builder.add_xml_tuning(
           instance_id=0xNEWID123,
           tuning_name="new_feature",
           # ... configuration
       )
       builder.build(output_dir / "new_fixture.package")
   ```

2. **Call in `main()`:**
   ```python
   def main():
       fixtures_dir = Path(__file__).parent / "sample_mods"
       create_new_fixture(fixtures_dir)  # Add this line
   ```

3. **Regenerate:**
   ```bash
   python3 create_fixtures.py
   ```

4. **Update this README** with fixture documentation

5. **Add tests** that use the new fixture

## Binary Format Details

The `.package` files use the DBPF (Database Packed File) format:

**Header (96 bytes):**
- Bytes 0-3: Magic (`DBPF`)
- Bytes 4-7: Major version (2)
- Bytes 8-11: Minor version (1)
- Bytes 40-43: Index entry count
- Bytes 44-47: Index table offset
- Bytes 48-51: Index table size

**Index Entry (32 bytes each):**
- Bytes 0-3: Resource type ID (e.g., `0x545238C9` for SIMDATA)
- Bytes 4-7: Group ID (typically `0x00000000`)
- Bytes 8-15: Instance ID (unique 64-bit identifier)
- Bytes 16-19: Resource data offset
- Bytes 20-23: Uncompressed size
- Bytes 24-27: Compressed size (0 if uncompressed)

**Resource Data:**
- ZLib-compressed XML/binary data (or uncompressed if sizes match)

See `docs/DBPF_FORMAT.md` for complete specification.

## Fixture Statistics

| Category | Count | Total Size | Purpose |
|----------|-------|------------|---------|
| Core Packages | 4 | 10,233 bytes | Basic functionality |
| Edge Cases | 4 | 338 bytes | Error handling |
| Script Mods | 3 | ~900 bytes | Script analysis |
| **TOTAL** | **11** | **~11 KB** | Comprehensive testing |

## Notes & Best Practices

- ✅ These fixtures are **production-quality** test data
- ✅ All packages are **minimal valid** DBPF files
- ✅ Edge cases test **error handling robustness**
- ✅ Script mods test **AST analysis** and **conflict detection**
- ⚠️ These are **NOT** playable Sims 4 mods - testing only!
- ⚠️ Do **NOT** install these in your actual Mods folder
- 📝 Keep this README **synchronized** with `create_fixtures.py`
- 🔄 Regenerate fixtures after **any builder changes**

## Continuous Integration

These fixtures are used in CI/CD pipelines:

```yaml
# .github/workflows/test.yml
- name: Run integration tests
  run: pytest tests/integration/test_real_fixtures.py -v
```

All fixtures are committed to version control for:
- Reproducible test environments
- Historical regression testing
- Cross-platform validation

## License

These fixture files are part of the Simanalysis test suite and are released under the MIT license.

**Copyright (c) 2025 justaride**

---

**Last Updated:** 2025-11-22 (v3.0.0)
**Fixture Count:** 11 files
**Total Coverage:** Core functionality + edge cases + script analysis
