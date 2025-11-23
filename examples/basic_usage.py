#!/usr/bin/env python3
"""
Basic Usage Examples for Simanalysis

This script demonstrates the core functionality of the Simanalysis Python API.
Perfect for beginners or quick integration into existing tools.

Usage:
    python basic_usage.py
"""

from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer
from simanalysis.parsers.dbpf import DBPFReader
from simanalysis.parsers.tuning import TuningParser
from simanalysis.models import Severity

print("=" * 70)
print("SIMANALYSIS - BASIC USAGE EXAMPLES")
print("=" * 70)
print()

# Example 1: Analyze a single mod file
print("Example 1: Analyzing a Single Mod File")
print("-" * 70)

# Use one of the test fixtures for demonstration
fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures" / "sample_mods"
simple_mod = fixtures_dir / "simple_mod.package"

if simple_mod.exists():
    print(f"Analyzing: {simple_mod.name}")

    # Read the DBPF package
    reader = DBPFReader(simple_mod)
    header = reader.read_header()

    print(f"  DBPF Version: {header.major_version}.{header.minor_version}")
    print(f"  Resources: {header.index_count}")
    print(f"  File Size: {simple_mod.stat().st_size} bytes")

    # Read resources
    resources = reader.read_index()
    for i, resource in enumerate(resources):
        print(f"  Resource {i+1}:")
        print(f"    Type: 0x{resource.type:08X}")
        print(f"    Instance: 0x{resource.instance:08X}")
        print(f"    Compressed: {resource.is_compressed}")

        # Extract and parse tuning
        data = reader.get_resource(resource)
        parser = TuningParser()
        try:
            tuning = parser.parse(data)
            print(f"    Tuning Name: {tuning.tuning_name}")
            print(f"    Tuning Class: {tuning.tuning_class}")
        except Exception as e:
            print(f"    (Not a tuning resource: {e})")
else:
    print("  ⚠️  Test fixtures not found. Run: cd tests/fixtures && python create_fixtures.py")

print()

# Example 2: Analyze a directory of mods
print("Example 2: Analyzing a Directory")
print("-" * 70)

if fixtures_dir.exists():
    print(f"Analyzing directory: {fixtures_dir}")

    analyzer = ModAnalyzer()
    result = analyzer.analyze_directory(fixtures_dir)

    print(f"  Total Mods: {len(result.mods)}")
    print(f"  Total Conflicts: {len(result.conflicts)}")

    # List mods
    print(f"\\n  Mods Found:")
    for mod in result.mods[:5]:  # Show first 5
        print(f"    - {mod.name}: {mod.type.value}, {mod.size} bytes")
    if len(result.mods) > 5:
        print(f"    ... and {len(result.mods) - 5} more")

    # Show conflicts
    if result.conflicts:
        print(f"\\n  Conflicts Detected:")
        for conflict in result.conflicts[:3]:  # Show first 3
            print(f"    - [{conflict.severity.value}] {conflict.description[:80]}")
            print(f"      Affected: {', '.join(conflict.affected_mods[:3])}")
    else:
        print(f"\\n  ✅ No conflicts detected!")
else:
    print("  ⚠️  Test fixtures directory not found")

print()

# Example 3: Filter conflicts by severity
print("Example 3: Filtering Conflicts by Severity")
print("-" * 70)

if fixtures_dir.exists() and result.conflicts:
    high_severity = [c for c in result.conflicts
                     if c.severity in [Severity.HIGH, Severity.CRITICAL]]

    print(f"  Total Conflicts: {len(result.conflicts)}")
    print(f"  High/Critical: {len(high_severity)}")

    if high_severity:
        print(f"\\n  High-Priority Conflicts:")
        for conflict in high_severity:
            print(f"    - {conflict.description}")
            print(f"      Mods: {', '.join(conflict.affected_mods)}")
    else:
        print(f"\\n  ✅ No high-priority conflicts")
else:
    print("  (No conflicts to filter)")

print()

# Example 4: Export results
print("Example 4: Exporting Analysis Results")
print("-" * 70)

if fixtures_dir.exists():
    output_dir = Path("/tmp")

    # Export to JSON
    json_file = output_dir / "analysis_result.json"
    analyzer.export_report(result, json_file, format="json")
    print(f"  ✅ JSON report: {json_file}")
    print(f"     Size: {json_file.stat().st_size} bytes")

    # Export to TXT
    txt_file = output_dir / "analysis_result.txt"
    analyzer.export_report(result, txt_file, format="txt")
    print(f"  ✅ TXT report: {txt_file}")
    print(f"     Size: {txt_file.stat().st_size} bytes")

    print(f"\\n  You can now:")
    print(f"    - View JSON: cat {json_file}")
    print(f"    - View TXT: cat {txt_file}")
    print(f"    - Process with jq: jq '.conflicts' {json_file}")
else:
    print("  (Skipping export - no data to export)")

print()

# Example 5: Access performance metrics
print("Example 5: Performance Metrics")
print("-" * 70)

if fixtures_dir.exists():
    perf = result.performance

    print(f"  Total Size: {perf.total_size_mb:.2f} MB")
    print(f"  Total Resources: {perf.total_resources}")
    print(f"  Estimated Load Time: {perf.estimated_load_time_seconds:.3f}s")
    print(f"  Estimated Memory: {perf.estimated_memory_mb:.2f} MB")
    print(f"  Complexity Score: {perf.complexity_score:.1f}")
else:
    print("  (Skipping metrics - no data available)")

print()
print("=" * 70)
print("EXAMPLES COMPLETE")
print("=" * 70)
print()
print("Next Steps:")
print("  - See advanced_usage.py for custom detectors and batch processing")
print("  - Check USAGE_EXAMPLES.md for more real-world scenarios")
print("  - Read API docs: https://simanalysis.readthedocs.io (coming soon)")
print()
