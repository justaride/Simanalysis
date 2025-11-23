#!/usr/bin/env python3
"""
Advanced Usage Examples for Simanalysis

This script demonstrates advanced features including:
- Custom conflict detectors
- Batch processing
- Custom reporters
- Integration patterns

Usage:
    python advanced_usage.py
"""

import json
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass

from simanalysis.analyzers.mod_analyzer import ModAnalyzer
from simanalysis.detectors.base import ConflictDetector
from simanalysis.models import Mod, ModConflict, Severity, ConflictType


print("=" * 70)
print("SIMANALYSIS - ADVANCED USAGE EXAMPLES")
print("=" * 70)
print()


# Example 1: Custom Conflict Detector
print("Example 1: Creating a Custom Conflict Detector")
print("-" * 70)


class DuplicateNameDetector(ConflictDetector):
    """Custom detector that finds mods with similar names."""

    def detect(self, mods: List[Mod]) -> List[ModConflict]:
        """Detect mods with very similar names (potential duplicates)."""
        conflicts = []

        # Group mods by normalized name (lowercase, no version numbers)
        name_groups: Dict[str, List[Mod]] = {}

        for mod in mods:
            # Normalize name (remove version numbers, lowercase)
            base_name = mod.name.lower()
            # Remove common version patterns
            for pattern in ['_v', '_ver', '_version', '-v', '-ver']:
                if pattern in base_name:
                    base_name = base_name.split(pattern)[0]

            if base_name not in name_groups:
                name_groups[base_name] = []
            name_groups[base_name].append(mod)

        # Find groups with multiple mods
        for base_name, mod_group in name_groups.items():
            if len(mod_group) > 1:
                conflict = ModConflict(
                    id=f"duplicate_name_{base_name}",
                    severity=Severity.LOW,
                    type=ConflictType.OTHER,
                    affected_mods=[m.name for m in mod_group],
                    description=f"Potential duplicate mods: {len(mod_group)} mods with similar names",
                    resolution=f"Keep only the latest version of '{base_name}'",
                    details={
                        "base_name": base_name,
                        "mod_count": len(mod_group),
                        "versions": [m.name for m in mod_group]
                    }
                )
                conflicts.append(conflict)

        return conflicts


print("  Custom detector: DuplicateNameDetector")
print("  Purpose: Finds mods with similar names (potential duplicates)")
print("  ✅ Detector class created")
print()

# Example 2: Batch Processing Multiple Directories
print("Example 2: Batch Processing")
print("-" * 70)


def batch_analyze_directories(directories: List[Path], output_dir: Path) -> Dict[str, Any]:
    """Analyze multiple mod directories and create consolidated report."""
    output_dir.mkdir(parents=True, exist_ok=True)

    analyzer = ModAnalyzer()
    results = {}

    for directory in directories:
        if not directory.exists():
            print(f"  ⚠️  Skipping non-existent directory: {directory}")
            continue

        print(f"  Analyzing: {directory.name}")

        # Analyze directory
        result = analyzer.analyze_directory(directory)

        # Store results
        dir_key = directory.name
        results[dir_key] = {
            "mod_count": len(result.mods),
            "conflict_count": len(result.conflicts),
            "total_size_mb": result.performance.total_size_mb,
            "high_severity_conflicts": len([
                c for c in result.conflicts
                if c.severity in [Severity.HIGH, Severity.CRITICAL]
            ])
        }

        # Export individual report
        report_file = output_dir / f"{dir_key}_report.json"
        analyzer.export_report(result, report_file, format="json")
        print(f"    ✅ Report: {report_file}")

    # Create consolidated summary
    summary_file = output_dir / "batch_summary.json"
    with open(summary_file, 'w') as f:
        json.dump({
            "total_directories": len(directories),
            "analyzed_directories": len(results),
            "results": results,
            "totals": {
                "total_mods": sum(r["mod_count"] for r in results.values()),
                "total_conflicts": sum(r["conflict_count"] for r in results.values()),
                "total_size_mb": sum(r["total_size_mb"] for r in results.values()),
            }
        }, f, indent=2)

    print(f"\\n  ✅ Batch summary: {summary_file}")
    return results


# Demonstrate batch processing with test fixtures
fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures" / "sample_mods"
if fixtures_dir.exists():
    output_dir = Path("/tmp/simanalysis_batch")
    batch_results = batch_analyze_directories([fixtures_dir], output_dir)

    print(f"\\n  Batch Processing Results:")
    for dir_name, stats in batch_results.items():
        print(f"    {dir_name}:")
        print(f"      Mods: {stats['mod_count']}")
        print(f"      Conflicts: {stats['conflict_count']}")
        print(f"      High-Priority: {stats['high_severity_conflicts']}")
else:
    print("  ⚠️  Test fixtures not found - batch processing demonstration skipped")

print()

# Example 3: Custom Reporter
print("Example 3: Custom Report Format")
print("-" * 70)


def generate_markdown_report(result, output_file: Path) -> None:
    """Generate a custom Markdown report."""
    with open(output_file, 'w') as f:
        # Header
        f.write("# Mod Analysis Report\\n\\n")
        f.write(f"**Generated:** {result.metadata.timestamp}\\n")
        f.write(f"**Tool Version:** {result.metadata.version}\\n\\n")

        # Summary
        f.write("## Summary\\n\\n")
        f.write(f"- **Total Mods:** {len(result.mods)}\\n")
        f.write(f"- **Total Conflicts:** {len(result.conflicts)}\\n")
        f.write(f"- **Total Size:** {result.performance.total_size_mb:.2f} MB\\n")
        f.write(f"- **Est. Load Time:** {result.performance.estimated_load_time_seconds:.2f}s\\n\\n")

        # Conflicts by severity
        f.write("## Conflicts by Severity\\n\\n")
        severity_counts = {}
        for conflict in result.conflicts:
            sev = conflict.severity.value
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
            count = severity_counts.get(severity, 0)
            if count > 0:
                emoji = "🔴" if severity == "CRITICAL" else "🟠" if severity == "HIGH" else "🟡" if severity == "MEDIUM" else "🟢"
                f.write(f"- {emoji} **{severity}**: {count}\\n")

        # Detailed conflicts
        f.write("\\n## Detailed Conflicts\\n\\n")
        for i, conflict in enumerate(result.conflicts, 1):
            f.write(f"### {i}. {conflict.description}\\n\\n")
            f.write(f"- **Severity:** {conflict.severity.value}\\n")
            f.write(f"- **Type:** {conflict.type.value}\\n")
            f.write(f"- **Affected Mods:**\\n")
            for mod_name in conflict.affected_mods:
                f.write(f"  - `{mod_name}`\\n")
            if conflict.resolution:
                f.write(f"- **Resolution:** {conflict.resolution}\\n")
            f.write("\\n")

        # Mod list
        f.write("## All Mods\\n\\n")
        f.write("| Name | Type | Size | Resources |\\n")
        f.write("|------|------|------|-----------|\\n")
        for mod in result.mods:
            size_kb = mod.size / 1024
            f.write(f"| {mod.name} | {mod.type.value} | {size_kb:.1f} KB | {len(mod.resources)} |\\n")

    print(f"  ✅ Markdown report generated: {output_file}")


# Demonstrate custom report
if fixtures_dir.exists():
    analyzer = ModAnalyzer()
    result = analyzer.analyze_directory(fixtures_dir)

    md_report = Path("/tmp/analysis_report.md")
    generate_markdown_report(result, md_report)
    print(f"  View with: cat {md_report}")
else:
    print("  ⚠️  Skipping - no test data available")

print()

# Example 4: Programmatic Conflict Resolution Suggestions
print("Example 4: Smart Conflict Resolution")
print("-" * 70)


def generate_resolution_plan(result) -> List[Dict[str, Any]]:
    """Generate actionable resolution suggestions."""
    plan = []

    # Group conflicts by affected mods
    mod_conflict_count = {}
    for conflict in result.conflicts:
        for mod_name in conflict.affected_mods:
            mod_conflict_count[mod_name] = mod_conflict_count.get(mod_name, 0) + 1

    # Identify "problem mods" (involved in many conflicts)
    problem_threshold = 3
    problem_mods = {mod: count for mod, count in mod_conflict_count.items()
                    if count >= problem_threshold}

    if problem_mods:
        for mod, count in sorted(problem_mods.items(), key=lambda x: x[1], reverse=True):
            plan.append({
                "action": "REVIEW",
                "mod": mod,
                "reason": f"Involved in {count} conflicts",
                "priority": "HIGH" if count > 5 else "MEDIUM",
                "suggestion": f"Consider removing or updating '{mod}' - it conflicts with many other mods"
            })

    # Identify critical conflicts
    critical = [c for c in result.conflicts if c.severity == Severity.CRITICAL]
    for conflict in critical:
        plan.append({
            "action": "IMMEDIATE",
            "conflict_id": conflict.id,
            "reason": "Critical severity",
            "priority": "CRITICAL",
            "suggestion": conflict.resolution or "Manual resolution required"
        })

    return plan


if fixtures_dir.exists() and result.conflicts:
    resolution_plan = generate_resolution_plan(result)

    if resolution_plan:
        print(f"  Generated {len(resolution_plan)} resolution suggestions:\\n")
        for i, action in enumerate(resolution_plan, 1):
            print(f"  {i}. [{action['priority']}] {action['action']}")
            print(f"     {action['suggestion']}")
            print()
    else:
        print("  ✅ No critical issues requiring immediate action")
else:
    print("  (No conflicts to analyze)")

print()

# Example 5: Integration with External Tools
print("Example 5: JSON API for External Tools")
print("-" * 70)


def export_for_external_tool(result, output_file: Path) -> None:
    """Export minimal JSON for integration with other tools."""
    external_format = {
        "version": "1.0",
        "timestamp": result.metadata.timestamp.isoformat(),
        "summary": {
            "total_mods": len(result.mods),
            "total_conflicts": len(result.conflicts),
            "critical_count": len([c for c in result.conflicts if c.severity == Severity.CRITICAL]),
            "high_count": len([c for c in result.conflicts if c.severity == Severity.HIGH]),
        },
        "mods": [
            {
                "name": mod.name,
                "path": str(mod.path),
                "size_bytes": mod.size,
                "hash": mod.hash,
            }
            for mod in result.mods
        ],
        "conflicts": [
            {
                "id": conflict.id,
                "severity": conflict.severity.value,
                "description": conflict.description,
                "affected_mod_names": conflict.affected_mods,
            }
            for conflict in result.conflicts
        ]
    }

    with open(output_file, 'w') as f:
        json.dump(external_format, f, indent=2)

    print(f"  ✅ External tool format: {output_file}")
    print(f"  Usage: import this JSON in your mod manager or CI/CD pipeline")


if fixtures_dir.exists():
    external_json = Path("/tmp/simanalysis_external.json")
    export_for_external_tool(result, external_json)
    print()

print("=" * 70)
print("ADVANCED EXAMPLES COMPLETE")
print("=" * 70)
print()
print("You've learned:")
print("  ✅ Custom conflict detectors")
print("  ✅ Batch processing workflows")
print("  ✅ Custom report formats (Markdown)")
print("  ✅ Smart conflict resolution planning")
print("  ✅ External tool integration")
print()
print("Next Steps:")
print("  - Adapt these patterns to your specific needs")
print("  - Create your own custom detectors for game-specific conflicts")
print("  - Integrate with your mod management workflow")
print("  - Contribute improvements back to the project!")
print()
