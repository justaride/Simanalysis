# Phase 3: Advanced Features - Implementation Plan

**Created:** 2025-11-23
**Target Duration:** 1-2 weeks
**Total Effort:** 12-16 hours
**Status:** Ready for Implementation

---

## 🎯 Goals

**Primary Objectives:**
1. Help users understand mod dependencies and load order
2. Detect circular dependencies and missing requirements
3. Speed up analysis for large collections (2-3x faster)
4. Enable incremental analysis (only analyze new/changed mods)

**User Benefits:**
- Faster workflow (seconds vs minutes for re-analysis)
- Better troubleshooting (see why mods break)
- Smarter mod management (optimal load order)
- Reduced frustration (clear dependency issues)

---

## 🔗 Feature 3.1: Dependency Graph & Load Order

### 3.1.1 Core Dependency Graph (4-5 hours)

#### Task 3.1.1.1: NetworkX Integration (1.5 hours)

**What to build:**
- Add networkx as dependency
- Create `DependencyGraph` class in `src/simanalysis/analyzers/dependency_graph.py`
- Build directed graph from mod relationships

**Implementation:**

```python
import networkx as nx
from typing import List, Set, Tuple, Optional
from pathlib import Path

class DependencyGraph:
    """Manage mod dependency relationships."""

    def __init__(self):
        self.graph = nx.DiGraph()

    def add_mod(self, mod_path: Path, dependencies: List[str]):
        """Add mod and its dependencies to graph."""
        self.graph.add_node(str(mod_path), path=mod_path)
        for dep in dependencies:
            self.graph.add_edge(str(mod_path), dep)

    def detect_cycles(self) -> List[List[str]]:
        """Find circular dependencies."""
        try:
            cycles = list(nx.simple_cycles(self.graph))
            return cycles
        except nx.NetworkXNoCycle:
            return []

    def topological_sort(self) -> List[Path]:
        """Get optimal load order (if no cycles)."""
        try:
            sorted_nodes = list(nx.topological_sort(self.graph))
            return [self.graph.nodes[n]['path'] for n in sorted_nodes]
        except nx.NetworkXError as e:
            # Has cycles, cannot sort
            return None

    def find_dependencies(self, mod_path: Path) -> Set[str]:
        """Find all dependencies (direct and transitive) of a mod."""
        node = str(mod_path)
        if node not in self.graph:
            return set()
        return set(nx.descendants(self.graph, node))

    def find_dependents(self, mod_path: Path) -> Set[str]:
        """Find all mods that depend on this mod."""
        node = str(mod_path)
        if node not in self.graph:
            return set()
        return set(nx.ancestors(self.graph, node))

    def impact_of_removal(self, mod_path: Path) -> dict:
        """Analyze impact of removing a mod."""
        dependents = self.find_dependents(mod_path)

        return {
            "mod": str(mod_path),
            "will_break": len(dependents),
            "affected_mods": list(dependents),
            "recommendation": self._generate_removal_recommendation(dependents)
        }

    def _generate_removal_recommendation(self, dependents: Set[str]) -> str:
        """Generate recommendation for mod removal."""
        if not dependents:
            return "Safe to remove (no mods depend on this)"
        elif len(dependents) == 1:
            return f"Warning: 1 mod depends on this. Consider keeping it."
        else:
            return f"⚠️  CAUTION: {len(dependents)} mods depend on this. Removing will break them!"
```

**Tests to write:**
- Test cycle detection with known circular dependencies
- Test topological sort with valid DAG
- Test impact analysis
- Test with empty graph
- Test with disconnected components

**Time:** 1.5 hours

---

#### Task 3.1.1.2: Dependency Detection (2 hours)

**What to build:**
- Enhance script analyzer to detect dependency declarations
- Add dependency extraction from package metadata
- Detect common dependency patterns

**Common dependency patterns to detect:**

```python
# Pattern 1: Package requirements (in tuning XML)
<T n="required_packs">EP01,GP02</T>

# Pattern 2: Script imports (direct dependencies)
import mccc_module  # Depends on MC Command Center
from basemental import drugs  # Depends on Basemental

# Pattern 3: Injection targets (implied dependencies)
@inject_to(mccc.main, 'execute')  # Requires MCCC

# Pattern 4: README/metadata files
# Requires: MC Command Center v2024.1+
# Optional: Wonderful Whims v1.5.0
```

**Implementation:**

```python
class DependencyDetector:
    """Detect mod dependencies from various sources."""

    KNOWN_MODS = {
        "mccc": "MC Command Center",
        "basemental": "Basemental Drugs",
        "wonderfulwhims": "Wonderful Whims",
        "wickedwhims": "WickedWhims",
    }

    def detect_dependencies(self, mod: Mod) -> List[str]:
        """Detect all dependencies for a mod."""
        dependencies = []

        # From pack requirements
        dependencies.extend(self._detect_pack_requirements(mod))

        # From script imports
        if mod.mod_type == "script":
            dependencies.extend(self._detect_script_dependencies(mod))

        # From injection targets
        dependencies.extend(self._detect_injection_dependencies(mod))

        return list(set(dependencies))  # Remove duplicates

    def _detect_script_dependencies(self, mod: Mod) -> List[str]:
        """Detect dependencies from Python imports."""
        dependencies = []

        for import_info in mod.script_info.imports:
            module = import_info.module.lower()

            # Check against known mods
            for key, name in self.KNOWN_MODS.items():
                if key in module:
                    dependencies.append(name)

        return dependencies
```

**Time:** 2 hours

---

#### Task 3.1.1.3: Load Order Optimization (1 hour)

**What to build:**
- Generate optimal load order for user's mods
- Provide rename suggestions for fixing order
- Detect and warn about problematic orderings

**Implementation:**

```python
class LoadOrderOptimizer:
    """Optimize mod load order based on dependencies."""

    def optimize(self, mods: List[Mod], dep_graph: DependencyGraph) -> dict:
        """Generate optimal load order."""

        # Get topological sort (optimal order)
        optimal_order = dep_graph.topological_sort()

        if optimal_order is None:
            return {
                "success": False,
                "reason": "Circular dependencies detected",
                "cycles": dep_graph.detect_cycles(),
            }

        # Current order (alphabetical by default in TS4)
        current_order = sorted(mods, key=lambda m: m.name.lower())

        # Compare and generate recommendations
        issues = self._find_ordering_issues(current_order, optimal_order)

        return {
            "success": True,
            "optimal_order": [m.name for m in optimal_order],
            "current_order": [m.name for m in current_order],
            "issues": issues,
            "recommendations": self._generate_recommendations(issues),
        }

    def _find_ordering_issues(self, current, optimal) -> List[dict]:
        """Find mods loading in wrong order."""
        issues = []

        for i, mod in enumerate(current):
            optimal_index = optimal.index(mod)

            if optimal_index < i:
                # This mod should load earlier
                issues.append({
                    "mod": mod.name,
                    "current_position": i + 1,
                    "optimal_position": optimal_index + 1,
                    "severity": "HIGH" if (i - optimal_index) > 10 else "MEDIUM",
                })

        return issues

    def _generate_recommendations(self, issues: List[dict]) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        for issue in issues:
            # Suggest prefix to force earlier load
            prefix = f"0{issue['optimal_position']:02d}_"
            recommendation = (
                f"Rename '{issue['mod']}' to '{prefix}{issue['mod']}' "
                f"to load at position {issue['optimal_position']}"
            )
            recommendations.append(recommendation)

        return recommendations
```

**Output example:**

```
=== LOAD ORDER ANALYSIS ===

Current order (alphabetical):
  1. AdvancedCAS.package ❌ Should be at position 45
  2. BaseGameTweaks.package ✅
  3. MCCC.package ❌ Should be at position 1
  ...

Optimal order:
  1. MCCC.package (no dependencies)
  2. BaseGameTweaks.package (depends on nothing)
  ...
  45. AdvancedCAS.package (depends on MCCC)

🔧 Recommendations:
  1. Rename 'MCCC.package' to '001_MCCC.package'
  2. Rename 'AdvancedCAS.package' to '045_AdvancedCAS.package'

💡 Or use a mod manager that supports custom load order!
```

**Time:** 1 hour

---

#### Task 3.1.1.4: Missing Dependency Detection (30 mins)

**What to build:**
- Detect when required mods are missing
- Provide download links when known
- Suggest alternatives

**Implementation:**

```python
MOD_SOURCES = {
    "MC Command Center": "https://deaderpool-mccc.com/",
    "Basemental Drugs": "https://basementalmod.com/",
    "Wonderful Whims": "https://wonderfulwhims.com/",
}

def detect_missing_dependencies(mods: List[Mod], dep_graph: DependencyGraph) -> List[dict]:
    """Find required mods that are missing."""
    missing = []

    installed_mods = {mod.name.lower() for mod in mods}

    for mod in mods:
        dependencies = dep_graph.find_dependencies(mod.path)

        for dep in dependencies:
            dep_lower = dep.lower()

            if dep_lower not in installed_mods:
                missing.append({
                    "required_by": mod.name,
                    "missing_mod": dep,
                    "download_url": MOD_SOURCES.get(dep),
                    "severity": "HIGH",
                })

    return missing
```

**Time:** 30 mins

---

#### Task 3.1.1.5: Visualization (ASCII Graph) (1 hour)

**What to build:**
- ASCII-art dependency graph for terminal display
- Export to DOT format for Graphviz
- Simple text report of dependencies

**Example output:**

```
Dependency Graph:

  MCCC ────┬──→ MCCC Dresser
           ├──→ MCCC Romance
           └──→ AdvancedCAS

  WonderfulWhims ───→ WW Animations

  BaseGameTweaks (no dependencies)

  SimpleMod (no dependencies)

Legend:
  A ───→ B  means "A is required by B"

Circular Dependencies: NONE ✅

Missing Dependencies:
  ⚠️  AdvancedCAS requires 'MC Command Center' (NOT FOUND)
```

**Time:** 1 hour

---

### 3.1.2 CLI Integration (30 mins)

**New commands:**

```bash
# Analyze with dependency graph
simanalysis analyze ./mods --with-dependencies

# Show dependency graph
simanalysis dependencies ./mods

# Check load order
simanalysis load-order ./mods

# Impact analysis
simanalysis impact ./mods --mod "MCCC.package"

# Find missing dependencies
simanalysis check-deps ./mods
```

**Time:** 30 mins

---

### 3.1.3 Documentation (30 mins)

- Add dependency graph section to user guide
- Document new CLI commands
- Add examples to README

**Time:** 30 mins

---

### 3.1.4 Testing (1 hour)

**Test scenarios:**
- Mods with linear dependencies (A→B→C)
- Circular dependencies (A→B→C→A)
- Missing dependencies
- Complex graphs (50+ mods, 100+ edges)
- Optimal load order generation
- Impact analysis

**Time:** 1 hour

---

**Total for Feature 3.1:** 8-9 hours

---

## ⚡ Feature 3.2: Performance Optimizations

### 3.2.1 Parallel Processing (3-4 hours)

#### Task 3.2.1.1: Multiprocessing Implementation (2 hours)

**What to build:**
- Parallel DBPF parsing using multiprocessing
- Worker pool with configurable size
- Progress reporting across workers

**Implementation:**

```python
from multiprocessing import Pool, cpu_count, Manager
from pathlib import Path
from typing import List

class ParallelAnalyzer:
    """Analyze mods in parallel for better performance."""

    def __init__(self, workers: int = None):
        self.workers = workers or max(1, cpu_count() - 1)

    def analyze_parallel(self, mod_files: List[Path]) -> List[Mod]:
        """Analyze mod files in parallel."""

        print(f"Using {self.workers} worker processes...")

        with Pool(processes=self.workers) as pool:
            # Use imap_unordered for progress reporting
            results = []

            for i, result in enumerate(pool.imap_unordered(self._analyze_single, mod_files)):
                results.append(result)

                # Progress update
                progress = (i + 1) / len(mod_files) * 100
                print(f"\rProgress: {progress:.1f}% ({i + 1}/{len(mod_files)})", end="")

            print()  # Newline after progress

        # Filter out None (failed analyses)
        return [r for r in results if r is not None]

    @staticmethod
    def _analyze_single(mod_path: Path) -> Optional[Mod]:
        """Analyze a single mod (worker function)."""
        try:
            # This runs in separate process
            from simanalysis.parsers.dbpf import DBPFReader

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
            print(f"\nError analyzing {mod_path.name}: {e}")
            return None
```

**CLI integration:**

```bash
# Auto-detect cores
simanalysis analyze ./mods --parallel

# Specify worker count
simanalysis analyze ./mods --parallel --workers 4

# Disable parallel (for debugging)
simanalysis analyze ./mods --no-parallel
```

**Time:** 2 hours

---

#### Task 3.2.1.2: Benchmarking (1 hour)

**What to measure:**
- Speedup factor (1 core vs N cores)
- Sweet spot for worker count
- Memory usage
- Overhead for small collections

**Create benchmark script:**

```python
import time
from pathlib import Path

def benchmark_parallel():
    """Benchmark parallel vs sequential analysis."""

    mod_files = list(Path("./test_mods").glob("*.package"))
    print(f"Testing with {len(mod_files)} mods")

    # Sequential
    start = time.time()
    analyzer = ModAnalyzer()
    result_seq = analyzer.analyze_files(mod_files, parallel=False)
    time_seq = time.time() - start

    # Parallel (various worker counts)
    for workers in [2, 4, 8]:
        start = time.time()
        result_par = analyzer.analyze_files(mod_files, parallel=True, workers=workers)
        time_par = time.time() - start

        speedup = time_seq / time_par
        print(f"{workers} workers: {time_par:.2f}s (speedup: {speedup:.2f}x)")
```

**Time:** 1 hour

---

#### Task 3.2.1.3: Error Handling (30 mins)

**What to handle:**
- Worker crashes
- Out of memory
- File access errors
- Timeout handling

**Time:** 30 mins

---

#### Task 3.2.1.4: Testing (30 mins)

- Test with 10, 100, 500 mods
- Test with 1, 2, 4, 8 workers
- Test error handling
- Verify results match sequential

**Time:** 30 mins

---

**Total for Parallel Processing:** 4 hours

---

### 3.2.2 Caching System (3-4 hours)

#### Task 3.2.2.1: Cache Infrastructure (2 hours)

**What to build:**
- Cache directory: `~/.simanalysis/cache/`
- Cache key: file path + modification time + size
- Cache format: pickle or JSON
- Cache validation

**Implementation:**

```python
import hashlib
import pickle
from pathlib import Path
from datetime import datetime

class AnalysisCache:
    """Cache analysis results for faster re-runs."""

    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or Path.home() / ".simanalysis" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cache_key(self, mod_path: Path) -> str:
        """Generate cache key from file path and metadata."""
        stat = mod_path.stat()

        # Key = hash of (path + mtime + size)
        key_data = f"{mod_path}:{stat.st_mtime}:{stat.st_size}"
        return hashlib.sha256(key_data.encode()).hexdigest()

    def get_cached(self, mod_path: Path) -> Optional[Mod]:
        """Get cached analysis result if valid."""
        cache_key = self.get_cache_key(mod_path)
        cache_file = self.cache_dir / f"{cache_key}.pkl"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "rb") as f:
                cached_mod = pickle.load(f)

            # Verify cache is still valid
            if self._is_cache_valid(mod_path, cached_mod):
                return cached_mod
            else:
                # Stale cache, remove it
                cache_file.unlink()
                return None

        except Exception as e:
            # Corrupted cache, remove it
            cache_file.unlink()
            return None

    def save_cache(self, mod: Mod):
        """Save analysis result to cache."""
        cache_key = self.get_cache_key(mod.path)
        cache_file = self.cache_dir / f"{cache_key}.pkl"

        try:
            with open(cache_file, "wb") as f:
                pickle.dump(mod, f)
        except Exception as e:
            print(f"Warning: Failed to save cache: {e}")

    def _is_cache_valid(self, mod_path: Path, cached_mod: Mod) -> bool:
        """Check if cached result is still valid."""
        current_stat = mod_path.stat()

        # Invalid if file changed
        if cached_mod.size != current_stat.st_size:
            return False

        # Could add more checks here
        return True

    def clear_cache(self, older_than_days: int = None):
        """Clear cache files."""
        if older_than_days:
            cutoff = datetime.now().timestamp() - (older_than_days * 86400)

            for cache_file in self.cache_dir.glob("*.pkl"):
                if cache_file.stat().st_mtime < cutoff:
                    cache_file.unlink()
        else:
            # Clear all
            for cache_file in self.cache_dir.glob("*.pkl"):
                cache_file.unlink()

    def get_cache_info(self) -> dict:
        """Get cache statistics."""
        cache_files = list(self.cache_dir.glob("*.pkl"))

        total_size = sum(f.stat().st_size for f in cache_files)

        return {
            "cached_mods": len(cache_files),
            "cache_size_bytes": total_size,
            "cache_size_mb": total_size / 1024 / 1024,
            "cache_directory": str(self.cache_dir),
        }
```

**Time:** 2 hours

---

#### Task 3.2.2.2: CLI Integration (1 hour)

**New commands:**

```bash
# Enable caching (default)
simanalysis analyze ./mods --cache

# Disable caching
simanalysis analyze ./mods --no-cache

# Cache management
simanalysis cache info
simanalysis cache clear
simanalysis cache clear --older-than 7d

# Force re-analysis (ignore cache)
simanalysis analyze ./mods --force-reanalyze
```

**Time:** 1 hour

---

#### Task 3.2.2.3: Integration with Analyzer (30 mins)

**Modify ModAnalyzer to use cache:**

```python
class ModAnalyzer:
    def __init__(self, use_cache: bool = True):
        self.use_cache = use_cache
        self.cache = AnalysisCache() if use_cache else None

    def analyze_file(self, mod_path: Path) -> Mod:
        """Analyze a single mod file (with caching)."""

        # Try cache first
        if self.cache:
            cached = self.cache.get_cached(mod_path)
            if cached:
                return cached

        # Not in cache, analyze
        mod = self._do_analysis(mod_path)

        # Save to cache
        if self.cache:
            self.cache.save_cache(mod)

        return mod
```

**Time:** 30 mins

---

#### Task 3.2.2.4: Testing & Documentation (1 hour)

**Tests:**
- Cache hit/miss scenarios
- Cache invalidation
- Cache corruption handling
- Cache clearing

**Documentation:**
- Explain caching benefits
- Document cache commands
- Add troubleshooting tips

**Time:** 1 hour

---

**Total for Caching:** 4.5 hours

---

## 📊 Implementation Summary

### Time Estimates

| Feature | Tasks | Effort | Priority |
|---------|-------|--------|----------|
| **Dependency Graph** | 3.1.1 - 3.1.4 | 8-9 hours | HIGH |
| **Parallel Processing** | 3.2.1 | 4 hours | MEDIUM |
| **Caching System** | 3.2.2 | 4.5 hours | MEDIUM |
| **Total** | | **16-18 hours** | |

### Implementation Order

**Week 1 (Dependency Graph):**
- Day 1-2: Core dependency graph (Tasks 3.1.1.1 - 3.1.1.3)
- Day 3: Missing deps + visualization (Tasks 3.1.1.4 - 3.1.1.5)
- Day 4: CLI integration + testing (Tasks 3.1.2 - 3.1.4)

**Week 2 (Performance):**
- Day 5-6: Parallel processing (Task 3.2.1)
- Day 7: Caching system (Task 3.2.2)
- Day 8: Final testing + documentation

---

## 🎯 Success Metrics

**Dependency Graph:**
- ✅ Detect circular dependencies correctly
- ✅ Generate valid topological sort
- ✅ Identify all missing dependencies
- ✅ Provide actionable load order recommendations

**Performance:**
- ✅ 2-3x speedup with parallel processing (4+ cores)
- ✅ <100ms overhead for cache lookups
- ✅ 90%+ cache hit rate on re-analysis
- ✅ <50MB cache size for 500 mods

**User Experience:**
- ✅ Clear, actionable dependency reports
- ✅ Simple cache management commands
- ✅ Noticeable speed improvement for large collections
- ✅ Comprehensive documentation

---

## 🚀 User Impact

**Before Phase 3:**
```
User has 500 mods, runs analysis: 8 minutes
User adds 1 new mod, re-analyzes: 8 minutes
User sees conflict, doesn't know why: confused
```

**After Phase 3:**
```
User has 500 mods, runs analysis: 3 minutes (parallel)
User adds 1 new mod, re-analyzes: 10 seconds (cache)
User sees "ModX requires ModY (missing)": downloads ModY
User sees optimal load order: renames 3 files, fixed!
```

**ROI:**
- 60-70% time savings on re-analysis
- Clear dependency understanding
- Fewer "why isn't my mod working" questions
- Better mod collection management

---

## Next Steps

1. Review this plan with user
2. Get approval to proceed
3. Start with Task 3.1.1.1 (NetworkX Integration)
4. Implement incrementally with testing
5. Document as we go

---

**Plan Status:** READY FOR USER REVIEW
**Created By:** Claude
**Date:** 2025-11-23
