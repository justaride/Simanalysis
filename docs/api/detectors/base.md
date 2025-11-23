# Base Detector

Abstract base class for implementing conflict detectors.

## Overview

The `ConflictDetector` base class provides the interface for all conflict detection implementations. Extend this class to create custom conflict detectors.

## Quick Example

```python
from typing import List
from simanalysis.detectors.base import ConflictDetector
from simanalysis.models import Mod, ModConflict

class MyCustomDetector(ConflictDetector):
    """Custom detector implementation."""

    def detect(self, mods: List[Mod]) -> List[ModConflict]:
        """Detect custom conflicts."""
        conflicts = []

        # Custom detection logic here
        for i, mod1 in enumerate(mods):
            for mod2 in mods[i + 1:]:
                if self._has_conflict(mod1, mod2):
                    conflicts.append(
                        ModConflict(
                            type="custom",
                            severity="MEDIUM",
                            description=f"Custom conflict between {mod1.name} and {mod2.name}",
                            affected_mods=[mod1.path, mod2.path],
                        )
                    )

        return conflicts

    def _has_conflict(self, mod1: Mod, mod2: Mod) -> bool:
        """Check if two mods have a conflict."""
        # Custom logic
        return False

# Usage
detector = MyCustomDetector()
conflicts = detector.detect(mods_list)
```

## API Reference

::: simanalysis.detectors.base
    options:
      show_root_heading: true
      show_source: true
      members:
        - ConflictDetector
      group_by_category: true

## Interface

### Required Methods

#### detect(mods: List[Mod]) -> List[ModConflict]

The main detection method that must be implemented.

**Parameters:**
- `mods`: List of Mod objects to analyze

**Returns:**
- List of detected ModConflict objects

**Example:**
```python
def detect(self, mods: List[Mod]) -> List[ModConflict]:
    conflicts = []
    # Detection logic
    return conflicts
```

## Creating Custom Detectors

### Example 1: Simple Name Similarity Detector

```python
from typing import List
from difflib import SequenceMatcher
from simanalysis.detectors.base import ConflictDetector
from simanalysis.models import Mod, ModConflict

class NameSimilarityDetector(ConflictDetector):
    """Detect mods with similar names (possible duplicates)."""

    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold

    def detect(self, mods: List[Mod]) -> List[ModConflict]:
        conflicts = []

        for i, mod1 in enumerate(mods):
            for mod2 in mods[i + 1:]:
                similarity = self._calculate_similarity(mod1.name, mod2.name)

                if similarity >= self.threshold:
                    conflicts.append(
                        ModConflict(
                            type="name_similarity",
                            severity="LOW",
                            description=f"Similar mod names: {mod1.name} and {mod2.name} ({similarity:.0%} similar)",
                            affected_mods=[mod1.path, mod2.path],
                            recommendation="Verify these are not duplicate installations",
                        )
                    )

        return conflicts

    def _calculate_similarity(self, name1: str, name2: str) -> float:
        """Calculate name similarity ratio."""
        return SequenceMatcher(None, name1.lower(), name2.lower()).ratio()

# Usage
detector = NameSimilarityDetector(threshold=0.85)
conflicts = detector.detect(mods_list)
```

### Example 2: File Size Anomaly Detector

```python
from typing import List
from statistics import mean, stdev
from simanalysis.detectors.base import ConflictDetector
from simanalysis.models import Mod, ModConflict

class SizeAnomalyDetector(ConflictDetector):
    """Detect unusually large mods."""

    def __init__(self, std_threshold: float = 3.0):
        self.std_threshold = std_threshold

    def detect(self, mods: List[Mod]) -> List[ModConflict]:
        if len(mods) < 3:
            return []  # Need enough data

        # Calculate statistics
        sizes = [mod.size for mod in mods]
        avg_size = mean(sizes)
        std_size = stdev(sizes)

        conflicts = []

        for mod in mods:
            # Check if size is more than N standard deviations from mean
            z_score = (mod.size - avg_size) / std_size if std_size > 0 else 0

            if abs(z_score) > self.std_threshold:
                conflicts.append(
                    ModConflict(
                        type="size_anomaly",
                        severity="LOW",
                        description=f"Unusually large mod: {mod.name} ({mod.size / 1024 / 1024:.1f} MB, {z_score:.1f}σ from mean)",
                        affected_mods=[mod.path],
                        recommendation="Verify mod is legitimate and not corrupted",
                    )
                )

        return conflicts

# Usage
detector = SizeAnomalyDetector(std_threshold=2.5)
conflicts = detector.detect(mods_list)
```

### Example 3: Outdated Mod Detector

```python
from typing import List
from datetime import datetime, timedelta
from simanalysis.detectors.base import ConflictDetector
from simanalysis.models import Mod, ModConflict

class OutdatedModDetector(ConflictDetector):
    """Detect mods that haven't been updated in a long time."""

    def __init__(self, days_threshold: int = 365):
        self.days_threshold = days_threshold

    def detect(self, mods: List[Mod]) -> List[ModConflict]:
        conflicts = []
        now = datetime.now()
        threshold_date = now - timedelta(days=self.days_threshold)

        for mod in mods:
            # Get last modification time
            mod_time = datetime.fromtimestamp(mod.path.stat().st_mtime)

            if mod_time < threshold_date:
                days_old = (now - mod_time).days

                conflicts.append(
                    ModConflict(
                        type="outdated",
                        severity="LOW",
                        description=f"Outdated mod: {mod.name} (last updated {days_old} days ago)",
                        affected_mods=[mod.path],
                        recommendation="Check for updates or verify mod still works with current game version",
                    )
                )

        return conflicts

# Usage
detector = OutdatedModDetector(days_threshold=730)  # 2 years
conflicts = detector.detect(mods_list)
```

### Example 4: Composite Detector

Combine multiple detectors:

```python
from typing import List
from simanalysis.detectors.base import ConflictDetector
from simanalysis.models import Mod, ModConflict

class CompositeDetector(ConflictDetector):
    """Run multiple detectors and combine results."""

    def __init__(self, detectors: List[ConflictDetector]):
        self.detectors = detectors

    def detect(self, mods: List[Mod]) -> List[ModConflict]:
        all_conflicts = []

        for detector in self.detectors:
            conflicts = detector.detect(mods)
            all_conflicts.extend(conflicts)

        # Remove duplicates (if needed)
        return self._deduplicate(all_conflicts)

    def _deduplicate(self, conflicts: List[ModConflict]) -> List[ModConflict]:
        """Remove duplicate conflicts."""
        seen = set()
        unique = []

        for conflict in conflicts:
            # Create unique key
            key = (
                conflict.type,
                tuple(sorted(str(p) for p in conflict.affected_mods))
            )

            if key not in seen:
                seen.add(key)
                unique.append(conflict)

        return unique

# Usage
from simanalysis.detectors.tuning_conflicts import TuningConflictDetector
from simanalysis.detectors.resource_conflicts import ResourceConflictDetector

composite = CompositeDetector([
    TuningConflictDetector(),
    ResourceConflictDetector(),
    NameSimilarityDetector(),
    SizeAnomalyDetector(),
])

conflicts = composite.detect(mods_list)
```

## Best Practices

### 1. Performance Optimization

```python
class EfficientDetector(ConflictDetector):
    def detect(self, mods: List[Mod]) -> List[ModConflict]:
        # Build index first (O(n))
        index = self._build_index(mods)

        # Detect conflicts using index (faster lookups)
        conflicts = self._detect_with_index(index)

        return conflicts

    def _build_index(self, mods: List[Mod]) -> dict:
        """Build index for fast lookups."""
        index = {}
        for mod in mods:
            # Index by relevant attribute
            index[mod.name] = mod
        return index
```

### 2. Severity Classification

```python
class SmartDetector(ConflictDetector):
    def detect(self, mods: List[Mod]) -> List[ModConflict]:
        conflicts = []

        for conflict_data in self._find_conflicts(mods):
            # Determine severity based on impact
            severity = self._calculate_severity(conflict_data)

            conflicts.append(
                ModConflict(
                    type="smart_conflict",
                    severity=severity,
                    description=conflict_data["description"],
                    affected_mods=conflict_data["mods"],
                )
            )

        return conflicts

    def _calculate_severity(self, data: dict) -> str:
        """Calculate conflict severity."""
        # Complex logic to determine severity
        if data["impact"] == "game_breaking":
            return "CRITICAL"
        elif data["impact"] == "feature_broken":
            return "HIGH"
        elif data["impact"] == "minor_issue":
            return "MEDIUM"
        else:
            return "LOW"
```

### 3. Detailed Recommendations

```python
class HelpfulDetector(ConflictDetector):
    def detect(self, mods: List[Mod]) -> List[ModConflict]:
        conflicts = []

        for mod1, mod2 in self._find_conflicting_pairs(mods):
            recommendation = self._generate_recommendation(mod1, mod2)

            conflicts.append(
                ModConflict(
                    type="helpful_conflict",
                    severity="MEDIUM",
                    description=f"Conflict between {mod1.name} and {mod2.name}",
                    affected_mods=[mod1.path, mod2.path],
                    recommendation=recommendation,
                )
            )

        return conflicts

    def _generate_recommendation(self, mod1: Mod, mod2: Mod) -> str:
        """Generate helpful recommendation."""
        return (
            f"Choose one of these mods:\n"
            f"  - Keep {mod1.name} if you prefer features A, B\n"
            f"  - Keep {mod2.name} if you prefer features X, Y\n"
            f"  - Or search for compatibility patch"
        )
```

## Testing Custom Detectors

```python
import unittest
from pathlib import Path
from simanalysis.models import Mod

class TestMyDetector(unittest.TestCase):
    def setUp(self):
        self.detector = MyCustomDetector()

        # Create test mods
        self.mod1 = Mod(
            name="test1.package",
            path=Path("test1.package"),
            size=1000,
            mod_type="package",
        )

        self.mod2 = Mod(
            name="test2.package",
            path=Path("test2.package"),
            size=2000,
            mod_type="package",
        )

    def test_no_conflicts(self):
        """Test when there are no conflicts."""
        conflicts = self.detector.detect([self.mod1])
        self.assertEqual(len(conflicts), 0)

    def test_detects_conflict(self):
        """Test conflict detection."""
        conflicts = self.detector.detect([self.mod1, self.mod2])
        self.assertGreater(len(conflicts), 0)

    def test_conflict_severity(self):
        """Test conflict severity is correct."""
        conflicts = self.detector.detect([self.mod1, self.mod2])
        for conflict in conflicts:
            self.assertIn(conflict.severity, ["LOW", "MEDIUM", "HIGH", "CRITICAL"])

if __name__ == "__main__":
    unittest.main()
```

## See Also

- [Tuning Conflicts](tuning_conflicts.md) - Tuning conflict detector
- [Resource Conflicts](resource_conflicts.md) - Resource conflict detector
- [Models](../models.md) - ModConflict structure
- [Advanced Examples](../../examples/advanced.md) - Custom detector examples

---

**Version**: 3.0.0 | **Last Updated**: 2025-11-23
