# Advanced Examples

Advanced patterns and techniques for power users of Simanalysis.

## Prerequisites

This guide assumes familiarity with:
- Basic Simanalysis usage
- Python programming
- The Sims 4 mod structure

## Custom Conflict Detection

### Example 1: Custom Detector Implementation

Create a custom detector for specific conflict patterns:

```python
from typing import List
from simanalysis.detectors.base import ConflictDetector
from simanalysis.models import Mod, ModConflict

class DuplicateNameDetector(ConflictDetector):
    """Detect mods with suspiciously similar names."""

    def detect(self, mods: List[Mod]) -> List[ModConflict]:
        conflicts = []

        for i, mod1 in enumerate(mods):
            for mod2 in mods[i + 1 :]:
                # Check if names are similar (simple heuristic)
                if self._names_similar(mod1.name, mod2.name):
                    conflicts.append(
                        ModConflict(
                            type="duplicate_name",
                            severity="LOW",
                            description=f"Similar mod names: {mod1.name} and {mod2.name}",
                            affected_mods=[mod1.path, mod2.path],
                            recommendation="Verify these are not duplicate installations",
                        )
                    )

        return conflicts

    def _names_similar(self, name1: str, name2: str) -> bool:
        """Check if two names are similar."""
        # Remove extensions and compare
        base1 = name1.lower().rsplit(".", 1)[0]
        base2 = name2.lower().rsplit(".", 1)[0]

        # Check for substring match
        if base1 in base2 or base2 in base1:
            return True

        # Check for high character overlap
        set1 = set(base1)
        set2 = set(base2)
        overlap = len(set1 & set2) / max(len(set1), len(set2))

        return overlap > 0.8


# Usage
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

analyzer = ModAnalyzer()
result = analyzer.analyze_directory(Path("./mods"))

# Run custom detector
detector = DuplicateNameDetector()
custom_conflicts = detector.detect(result.mods)

print(f"Found {len(custom_conflicts)} duplicate name conflicts")
for conflict in custom_conflicts:
    print(f"  - {conflict.description}")
```

### Example 2: Version Conflict Detector

Detect multiple versions of the same mod:

```python
import re
from typing import List
from simanalysis.detectors.base import ConflictDetector
from simanalysis.models import Mod, ModConflict

class VersionConflictDetector(ConflictDetector):
    """Detect multiple versions of the same mod."""

    VERSION_PATTERN = re.compile(r"[_\-\s]v?(\d+\.?\d*\.?\d*)", re.IGNORECASE)

    def detect(self, mods: List[Mod]) -> List[ModConflict]:
        # Group mods by base name (without version)
        mod_groups = {}

        for mod in mods:
            base_name = self._remove_version(mod.name)
            if base_name not in mod_groups:
                mod_groups[base_name] = []
            mod_groups[base_name].append(mod)

        # Find groups with multiple versions
        conflicts = []
        for base_name, group in mod_groups.items():
            if len(group) > 1:
                versions = [self._extract_version(m.name) for m in group]
                conflicts.append(
                    ModConflict(
                        type="version_conflict",
                        severity="HIGH",
                        description=f"Multiple versions of {base_name}: {', '.join(versions)}",
                        affected_mods=[m.path for m in group],
                        recommendation=f"Keep only the latest version ({max(versions)})",
                    )
                )

        return conflicts

    def _remove_version(self, name: str) -> str:
        """Remove version from mod name."""
        return self.VERSION_PATTERN.sub("", name).strip()

    def _extract_version(self, name: str) -> str:
        """Extract version from mod name."""
        match = self.VERSION_PATTERN.search(name)
        return match.group(1) if match else "unknown"


# Usage
detector = VersionConflictDetector()
version_conflicts = detector.detect(result.mods)

if version_conflicts:
    print("⚠️  Multiple versions detected:")
    for conflict in version_conflicts:
        print(f"  {conflict.description}")
        print(f"  Recommendation: {conflict.recommendation}")
```

## Advanced Analysis Patterns

### Example 3: Dependency Graph Generation

Build a dependency graph for script mods:

```python
from pathlib import Path
from collections import defaultdict
from simanalysis.parsers.script import ScriptAnalyzer

def build_dependency_graph(mods_dir: Path) -> dict:
    """Build dependency graph for script mods."""
    graph = defaultdict(set)
    script_mods = list(mods_dir.glob("*.ts4script"))

    analyzer = ScriptAnalyzer()

    for script_path in script_mods:
        try:
            script_info = analyzer.analyze(script_path)

            # Add imports as dependencies
            for import_info in script_info.imports:
                module = import_info.module
                # Track which mods import this module
                graph[module].add(script_path.name)

        except Exception as e:
            print(f"Warning: Failed to analyze {script_path.name}: {e}")

    return dict(graph)


def visualize_dependencies(graph: dict):
    """Print dependency graph."""
    print("=== DEPENDENCY GRAPH ===\n")

    for module, dependents in sorted(graph.items()):
        if len(dependents) > 1:
            print(f"{module}:")
            for dependent in sorted(dependents):
                print(f"  ← {dependent}")
            print()


# Usage
mods_dir = Path("./mods")
dep_graph = build_dependency_graph(mods_dir)
visualize_dependencies(dep_graph)

# Find most depended-on modules
most_popular = sorted(
    dep_graph.items(), key=lambda x: len(x[1]), reverse=True
)[:10]

print("Most Imported Modules:")
for module, dependents in most_popular:
    print(f"  {module}: {len(dependents)} mods")
```

### Example 4: Impact Analysis

Analyze the impact of removing a mod:

```python
from pathlib import Path
from typing import List, Set
from simanalysis.analyzers.mod_analyzer import ModAnalyzer
from simanalysis.models import Mod, ModConflict

class ImpactAnalyzer:
    """Analyze impact of mod changes."""

    def __init__(self, mods: List[Mod], conflicts: List[ModConflict]):
        self.mods = mods
        self.conflicts = conflicts

    def analyze_removal_impact(self, mod_name: str) -> dict:
        """Analyze impact of removing a specific mod."""
        # Find the mod
        target_mod = next((m for m in self.mods if m.name == mod_name), None)
        if not target_mod:
            return {"error": f"Mod {mod_name} not found"}

        # Find conflicts involving this mod
        involved_conflicts = [
            c
            for c in self.conflicts
            if target_mod.path in c.affected_mods
        ]

        # Categorize conflicts
        resolved = []  # Conflicts that would be resolved
        unresolved = []  # Conflicts that remain

        for conflict in involved_conflicts:
            affected_count = len(conflict.affected_mods)
            if affected_count == 2:
                # Two-mod conflict would be resolved
                resolved.append(conflict)
            else:
                # Multi-mod conflict would remain
                unresolved.append(conflict)

        return {
            "mod": mod_name,
            "conflicts_resolved": len(resolved),
            "conflicts_remaining": len(unresolved),
            "resolved_details": [
                {
                    "severity": c.severity,
                    "description": c.description,
                    "other_mod": next(
                        p
                        for p in c.affected_mods
                        if p != target_mod.path
                    ),
                }
                for c in resolved
            ],
            "unresolved_details": [
                {
                    "severity": c.severity,
                    "description": c.description,
                    "other_mods": [
                        p for p in c.affected_mods if p != target_mod.path
                    ],
                }
                for c in unresolved
            ],
        }


# Usage
analyzer = ModAnalyzer()
result = analyzer.analyze_directory(Path("./mods"))

impact = ImpactAnalyzer(result.mods, result.conflicts)

# Analyze impact of removing a problematic mod
mod_to_remove = "ProblematicMod.package"
analysis = impact.analyze_removal_impact(mod_to_remove)

print(f"=== IMPACT ANALYSIS: {mod_to_remove} ===\n")
print(f"Conflicts resolved: {analysis['conflicts_resolved']}")
print(f"Conflicts remaining: {analysis['conflicts_remaining']}")

if analysis['resolved_details']:
    print("\nConflicts that would be resolved:")
    for detail in analysis['resolved_details']:
        print(f"  [{detail['severity']}] {detail['description']}")
```

### Example 5: Conflict Resolution Planner

Generate a plan to resolve conflicts:

```python
from typing import List, Dict
from collections import defaultdict
from simanalysis.models import Mod, ModConflict

class ConflictResolutionPlanner:
    """Generate resolution plans for conflicts."""

    def __init__(self, mods: List[Mod], conflicts: List[ModConflict]):
        self.mods = mods
        self.conflicts = conflicts

    def generate_removal_plan(self) -> List[Dict]:
        """Generate plan to remove mods with most conflicts."""
        # Count conflicts per mod
        conflict_count = defaultdict(int)
        conflict_details = defaultdict(list)

        for conflict in self.conflicts:
            for mod_path in conflict.affected_mods:
                conflict_count[mod_path] += 1
                conflict_details[mod_path].append(conflict)

        # Sort mods by conflict count (descending)
        sorted_mods = sorted(
            conflict_count.items(), key=lambda x: x[1], reverse=True
        )

        # Generate plan
        plan = []
        remaining_conflicts = set(self.conflicts)

        for mod_path, count in sorted_mods:
            if not remaining_conflicts:
                break

            # Calculate how many conflicts removing this mod would resolve
            resolves = []
            for conflict in conflict_details[mod_path]:
                if conflict in remaining_conflicts:
                    # Check if removing this mod resolves the conflict
                    if len(conflict.affected_mods) == 2:
                        resolves.append(conflict)

            if resolves:
                plan.append(
                    {
                        "action": "remove",
                        "mod": Path(mod_path).name,
                        "path": mod_path,
                        "total_conflicts": count,
                        "resolves": len(resolves),
                        "resolved_conflicts": [
                            {
                                "severity": c.severity,
                                "description": c.description,
                            }
                            for c in resolves
                        ],
                    }
                )

                # Update remaining conflicts
                for conflict in resolves:
                    remaining_conflicts.discard(conflict)

        return plan

    def print_plan(self, plan: List[Dict]):
        """Print resolution plan in readable format."""
        print("=== CONFLICT RESOLUTION PLAN ===\n")
        print(f"Total steps: {len(plan)}\n")

        for i, step in enumerate(plan, 1):
            print(f"Step {i}: Remove {step['mod']}")
            print(f"  Resolves: {step['resolves']} conflicts")
            print(f"  Conflicts remaining: {step['total_conflicts'] - step['resolves']}")

            if step['resolved_conflicts']:
                print("  Resolved conflicts:")
                for conflict in step['resolved_conflicts'][:3]:
                    print(f"    [{conflict['severity']}] {conflict['description']}")
                if len(step['resolved_conflicts']) > 3:
                    print(f"    ... and {len(step['resolved_conflicts']) - 3} more")
            print()


# Usage
planner = ConflictResolutionPlanner(result.mods, result.conflicts)
plan = planner.generate_removal_plan()
planner.print_plan(plan)

# Save plan to JSON
import json
with open("resolution_plan.json", "w") as f:
    json.dump(plan, f, indent=2)
```

## Performance Optimization

### Example 6: Parallel Processing

Process large mod collections in parallel:

```python
import concurrent.futures
from pathlib import Path
from typing import List
from simanalysis.parsers.dbpf import DBPFReader
from simanalysis.models import Mod

def process_mod(mod_path: Path) -> Mod:
    """Process a single mod file."""
    try:
        reader = DBPFReader(mod_path)
        header = reader.read_header()
        resources = reader.read_index()

        return Mod(
            name=mod_path.name,
            path=mod_path,
            size=mod_path.stat().st_size,
            mod_type="package",
            resources=resources,
        )
    except Exception as e:
        print(f"Error processing {mod_path.name}: {e}")
        return None


def parallel_analyze(mods_dir: Path, max_workers: int = 4) -> List[Mod]:
    """Analyze mods in parallel."""
    mod_files = list(mods_dir.glob("*.package"))

    print(f"Processing {len(mod_files)} mods with {max_workers} workers...")

    mods = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = {executor.submit(process_mod, mod_path): mod_path for mod_path in mod_files}

        # Collect results as they complete
        for future in concurrent.futures.as_completed(futures):
            mod = future.result()
            if mod:
                mods.append(mod)

    return mods


# Usage
mods_dir = Path("./mods")
mods = parallel_analyze(mods_dir, max_workers=8)
print(f"Processed {len(mods)} mods successfully")
```

### Example 7: Caching Analysis Results

Cache analysis results for faster re-analysis:

```python
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta

class AnalysisCache:
    """Cache analysis results for faster re-runs."""

    def __init__(self, cache_dir: Path = Path(".cache")):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(exist_ok=True)

    def _get_file_hash(self, file_path: Path) -> str:
        """Get hash of file for cache key."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _get_cache_path(self, mod_path: Path) -> Path:
        """Get cache file path for mod."""
        file_hash = self._get_file_hash(mod_path)
        return self.cache_dir / f"{file_hash}.json"

    def get_cached(self, mod_path: Path, max_age_hours: int = 24):
        """Get cached analysis if available and fresh."""
        cache_path = self._get_cache_path(mod_path)

        if not cache_path.exists():
            return None

        # Check cache age
        cache_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
        if datetime.now() - cache_time > timedelta(hours=max_age_hours):
            return None

        # Load cache
        with open(cache_path) as f:
            return json.load(f)

    def save_cache(self, mod_path: Path, data: dict):
        """Save analysis to cache."""
        cache_path = self._get_cache_path(mod_path)
        with open(cache_path, "w") as f:
            json.dump(data, f, indent=2)

    def clear_cache(self):
        """Clear all cached data."""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()


# Usage
from simanalysis.parsers.dbpf import DBPFReader

cache = AnalysisCache()
mod_path = Path("./mods/LargeMod.package")

# Try to get from cache
cached_data = cache.get_cached(mod_path)

if cached_data:
    print(f"Using cached analysis for {mod_path.name}")
    resources = cached_data["resources"]
else:
    print(f"Analyzing {mod_path.name}...")
    reader = DBPFReader(mod_path)
    header = reader.read_header()
    resources = reader.read_index()

    # Cache results
    cache_data = {
        "version": header.major_version,
        "resources": [
            {
                "type": r.type,
                "group": r.group,
                "instance": r.instance,
                "size": r.size,
            }
            for r in resources
        ],
    }
    cache.save_cache(mod_path, cache_data)

print(f"Resources: {len(resources)}")
```

## Integration Examples

### Example 8: REST API Server

Create a REST API for Simanalysis:

```python
from flask import Flask, request, jsonify
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

app = Flask(__name__)
analyzer = ModAnalyzer()


@app.route("/analyze", methods=["POST"])
def analyze():
    """Analyze a directory of mods."""
    data = request.json
    mods_dir = Path(data.get("directory"))

    if not mods_dir.exists():
        return jsonify({"error": "Directory not found"}), 404

    # Perform analysis
    result = analyzer.analyze_directory(mods_dir)

    # Convert to JSON-serializable format
    response = {
        "total_mods": len(result.mods),
        "total_conflicts": len(result.conflicts),
        "mods": [
            {
                "name": mod.name,
                "size": mod.size,
                "type": mod.mod_type,
            }
            for mod in result.mods
        ],
        "conflicts": [
            {
                "type": conflict.type,
                "severity": conflict.severity,
                "description": conflict.description,
                "affected_mods": [str(p) for p in conflict.affected_mods],
            }
            for conflict in result.conflicts
        ],
    }

    return jsonify(response)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "version": "3.0.0"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
```

**Start server:**
```bash
pip install flask
python api_server.py
```

**Test API:**
```bash
curl -X POST http://localhost:5000/analyze \
  -H "Content-Type: application/json" \
  -d '{"directory": "/path/to/mods"}'
```

### Example 9: Discord Bot Integration

Create a Discord bot for mod analysis:

```python
import discord
from discord.ext import commands
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

bot = commands.Bot(command_prefix="!")
analyzer = ModAnalyzer()


@bot.command()
async def analyze_mods(ctx, directory: str):
    """Analyze mods in a directory."""
    await ctx.send(f"Analyzing mods in {directory}...")

    try:
        mods_dir = Path(directory)
        result = analyzer.analyze_directory(mods_dir)

        # Create embed
        embed = discord.Embed(
            title="Mod Analysis Report",
            color=discord.Color.blue(),
        )

        embed.add_field(name="Total Mods", value=len(result.mods), inline=True)
        embed.add_field(
            name="Total Conflicts", value=len(result.conflicts), inline=True
        )

        # Count by severity
        severity_counts = {}
        for conflict in result.conflicts:
            severity_counts[conflict.severity] = (
                severity_counts.get(conflict.severity, 0) + 1
            )

        if severity_counts:
            severity_text = "\n".join(
                f"{severity}: {count}"
                for severity, count in severity_counts.items()
            )
            embed.add_field(
                name="Conflicts by Severity", value=severity_text, inline=False
            )

        # Show high-severity conflicts
        high_conflicts = [
            c for c in result.conflicts if c.severity in ["HIGH", "CRITICAL"]
        ]

        if high_conflicts:
            conflicts_text = "\n".join(
                f"[{c.severity}] {c.description[:100]}"
                for c in high_conflicts[:5]
            )
            embed.add_field(
                name="High Priority Conflicts",
                value=conflicts_text,
                inline=False,
            )

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"Error: {str(e)}")


bot.run("YOUR_BOT_TOKEN")
```

## Testing and Validation

### Example 10: Automated Testing

Create automated tests for mod compatibility:

```python
import unittest
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

class ModCompatibilityTests(unittest.TestCase):
    """Test mod compatibility."""

    def setUp(self):
        self.analyzer = ModAnalyzer()
        self.mods_dir = Path("./test_mods")

    def test_no_critical_conflicts(self):
        """Ensure no critical conflicts in production mods."""
        result = self.analyzer.analyze_directory(self.mods_dir)

        critical = [c for c in result.conflicts if c.severity == "CRITICAL"]

        self.assertEqual(
            len(critical),
            0,
            f"Found {len(critical)} critical conflicts: {[c.description for c in critical]}",
        )

    def test_high_conflicts_below_threshold(self):
        """Ensure high-severity conflicts are manageable."""
        result = self.analyzer.analyze_directory(self.mods_dir)

        high = [c for c in result.conflicts if c.severity == "HIGH"]

        self.assertLessEqual(
            len(high), 5, f"Too many high-severity conflicts: {len(high)}"
        )

    def test_all_mods_parseable(self):
        """Ensure all mods can be parsed without errors."""
        result = self.analyzer.analyze_directory(self.mods_dir)

        # Count expected mods
        expected_count = len(
            list(self.mods_dir.glob("*.package"))
            + list(self.mods_dir.glob("*.ts4script"))
        )

        self.assertEqual(
            len(result.mods),
            expected_count,
            "Some mods failed to parse",
        )


if __name__ == "__main__":
    unittest.main()
```

**Run tests:**
```bash
python -m unittest mod_tests.py
```

## Next Steps

- Review [Basic Examples](basic.md) for fundamentals
- Check [CI/CD Integration](cicd.md) for automation
- Read [API Reference](../api/overview.md) for complete API docs
- Visit [GitHub](https://github.com/justaride/Simanalysis) for more examples

---

**Version**: 3.0.0 | **Last Updated**: 2025-11-23
