"""Dependency graph analysis for mod collections."""

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx

from simanalysis.models import Mod


class DependencyGraph:
    """Manage and analyze mod dependency relationships.

    This class builds a directed graph of mod dependencies and provides
    analysis capabilities including cycle detection, topological sorting,
    and impact analysis.

    Attributes:
        graph: NetworkX directed graph of dependencies
        mod_map: Mapping of mod names to Mod objects
    """

    def __init__(self) -> None:
        """Initialize an empty dependency graph."""
        self.graph: nx.DiGraph = nx.DiGraph()
        self.mod_map: Dict[str, Mod] = {}

    def add_mod(self, mod: Mod, dependencies: Optional[List[str]] = None) -> None:
        """Add a mod and its dependencies to the graph.

        Args:
            mod: The mod to add
            dependencies: List of dependency mod names (e.g., ["MC Command Center"])
        """
        mod_name = mod.name

        # Add node with mod data
        self.graph.add_node(mod_name, mod=mod, path=mod.path)
        self.mod_map[mod_name] = mod

        # Add dependency edges
        if dependencies:
            for dep_name in dependencies:
                # Add dependency node if not exists
                if not self.graph.has_node(dep_name):
                    self.graph.add_node(dep_name, mod=None, path=None)

                # Add edge: mod depends on dep_name
                # Edge direction: dependent -> dependency
                self.graph.add_edge(mod_name, dep_name)

    def detect_cycles(self) -> List[List[str]]:
        """Find circular dependencies in the graph.

        Returns:
            List of cycles, where each cycle is a list of mod names

        Example:
            >>> cycles = graph.detect_cycles()
            >>> print(cycles)
            [['ModA', 'ModB', 'ModC', 'ModA']]
        """
        try:
            cycles = list(nx.simple_cycles(self.graph))
            return cycles
        except nx.NetworkXNoCycle:
            return []

    def topological_sort(self) -> Optional[List[str]]:
        """Get optimal load order (if no cycles exist).

        Returns:
            List of mod names in optimal load order, or None if cycles exist

        Example:
            >>> order = graph.topological_sort()
            >>> print(order)
            ['BaseModA', 'ModB', 'ModC']  # BaseModA loads first
        """
        if self.has_cycles():
            return None

        try:
            # Reverse topological sort: dependencies load first
            sorted_nodes = list(nx.topological_sort(self.graph))
            # Reverse so that mods with no dependencies come first
            return list(reversed(sorted_nodes))
        except nx.NetworkXError:
            return None

    def has_cycles(self) -> bool:
        """Check if graph contains any cycles.

        Returns:
            True if circular dependencies exist
        """
        return not nx.is_directed_acyclic_graph(self.graph)

    def find_dependencies(self, mod_name: str) -> Set[str]:
        """Find all dependencies (direct and transitive) of a mod.

        Args:
            mod_name: Name of the mod to analyze

        Returns:
            Set of all dependency mod names

        Example:
            >>> deps = graph.find_dependencies("AdvancedMod")
            >>> print(deps)
            {'MCCC', 'BaseGameTweaks'}
        """
        if mod_name not in self.graph:
            return set()

        # Get all descendants (things this mod depends on)
        return set(nx.descendants(self.graph, mod_name))

    def find_dependents(self, mod_name: str) -> Set[str]:
        """Find all mods that depend on this mod.

        Args:
            mod_name: Name of the mod to analyze

        Returns:
            Set of all dependent mod names

        Example:
            >>> dependents = graph.find_dependents("MCCC")
            >>> print(dependents)
            {'AdvancedMod', 'CustomInteractions', 'MCCCDresser'}
        """
        if mod_name not in self.graph:
            return set()

        # Get all ancestors (things that depend on this mod)
        return set(nx.ancestors(self.graph, mod_name))

    def impact_of_removal(self, mod_name: str) -> Dict[str, any]:
        """Analyze impact of removing a mod.

        Args:
            mod_name: Name of the mod to analyze

        Returns:
            Dictionary with impact analysis:
            - mod: Mod name
            - will_break: Number of mods that will break
            - affected_mods: List of affected mod names
            - recommendation: Human-readable recommendation

        Example:
            >>> impact = graph.impact_of_removal("MCCC")
            >>> print(impact['will_break'])
            12
        """
        dependents = self.find_dependents(mod_name)

        return {
            "mod": mod_name,
            "will_break": len(dependents),
            "affected_mods": sorted(list(dependents)),
            "recommendation": self._generate_removal_recommendation(dependents),
        }

    def _generate_removal_recommendation(self, dependents: Set[str]) -> str:
        """Generate recommendation for mod removal.

        Args:
            dependents: Set of mods that depend on the target mod

        Returns:
            Human-readable recommendation string
        """
        count = len(dependents)

        if count == 0:
            return "✅ Safe to remove (no mods depend on this)"
        elif count == 1:
            return f"⚠️  Warning: 1 mod depends on this. Consider keeping it."
        elif count <= 5:
            return f"⚠️  CAUTION: {count} mods depend on this. Removing will break them."
        else:
            return f"🛑 HIGH RISK: {count} mods depend on this. Strongly recommend keeping!"

    def find_missing_dependencies(self, installed_mods: Set[str]) -> List[Tuple[str, str]]:
        """Find dependencies that are referenced but not installed.

        Args:
            installed_mods: Set of installed mod names

        Returns:
            List of (mod_name, missing_dependency) tuples

        Example:
            >>> missing = graph.find_missing_dependencies({'ModA', 'ModB'})
            >>> print(missing)
            [('ModA', 'MCCC'), ('ModB', 'Basemental')]
        """
        missing = []

        for node in self.graph.nodes():
            # Get dependencies of this node
            dependencies = set(self.graph.successors(node))

            # Check which are not installed
            for dep in dependencies:
                if dep not in installed_mods:
                    missing.append((node, dep))

        return missing

    def get_load_order_issues(
        self, current_order: List[str]
    ) -> List[Dict[str, any]]:
        """Identify mods loading in suboptimal order.

        Args:
            current_order: Current load order (e.g., alphabetical)

        Returns:
            List of issues, each containing:
            - mod: Mod name
            - current_position: Current position (1-indexed)
            - should_be_at: Optimal position
            - reason: Why it should move
            - severity: Issue severity (HIGH, MEDIUM, LOW)

        Example:
            >>> issues = graph.get_load_order_issues(['AdvancedMod', 'MCCC'])
            >>> print(issues[0])
            {'mod': 'MCCC', 'current_position': 2, 'should_be_at': 1, ...}
        """
        optimal_order = self.topological_sort()

        if optimal_order is None:
            # Has cycles, can't determine optimal order
            return []

        issues = []

        # Create position lookup for current order
        current_positions = {mod: i for i, mod in enumerate(current_order)}

        for i, mod_name in enumerate(current_order):
            if mod_name not in optimal_order:
                continue

            current_pos = i + 1
            optimal_pos = optimal_order.index(mod_name) + 1

            # Check for dependency violations: does this mod load before any of its dependencies?
            has_violation = False
            if mod_name in self.graph:
                # Get direct dependencies (nodes this mod points to)
                dependencies = list(self.graph.successors(mod_name))
                for dep in dependencies:
                    if dep in current_positions:
                        dep_current_pos = current_positions[dep]
                        if i > dep_current_pos:
                            # Mod loads after its dependency - OK
                            pass
                        else:
                            # Mod loads before or at same time as dependency - VIOLATION
                            has_violation = True
                            break

            # Check if mod loads in wrong position or has dependency violations
            if optimal_pos != current_pos or has_violation:
                position_diff = abs(current_pos - optimal_pos)

                # Determine reason
                if has_violation:
                    reason = "Loads before its dependencies"
                elif optimal_pos < current_pos:
                    reason = "Loads after its dependents"
                else:
                    reason = "Loads before its dependencies"

                issues.append({
                    "mod": mod_name,
                    "current_position": current_pos,
                    "should_be_at": optimal_pos,
                    "reason": reason,
                    "severity": self._calculate_issue_severity(position_diff),
                })

        return issues

    def _calculate_issue_severity(self, position_diff: int) -> str:
        """Calculate severity based on position difference.

        Args:
            position_diff: How many positions mod is from optimal

        Returns:
            Severity level: HIGH, MEDIUM, or LOW
        """
        if position_diff > 20:
            return "HIGH"
        elif position_diff > 5:
            return "MEDIUM"
        else:
            return "LOW"

    def get_statistics(self) -> Dict[str, any]:
        """Get dependency graph statistics.

        Returns:
            Dictionary with statistics:
            - total_mods: Number of mods
            - total_dependencies: Number of dependency relationships
            - has_cycles: Whether circular dependencies exist
            - cycle_count: Number of cycles
            - isolated_mods: Mods with no dependencies or dependents
            - most_depended_on: Mods with most dependents

        Example:
            >>> stats = graph.get_statistics()
            >>> print(stats['total_mods'])
            47
        """
        stats = {
            "total_mods": self.graph.number_of_nodes(),
            "total_dependencies": self.graph.number_of_edges(),
            "has_cycles": self.has_cycles(),
            "cycle_count": len(self.detect_cycles()),
        }

        # Find isolated mods (no incoming or outgoing edges)
        isolated = [
            node for node in self.graph.nodes()
            if self.graph.in_degree(node) == 0 and self.graph.out_degree(node) == 0
        ]
        stats["isolated_mods"] = len(isolated)

        # Find most depended-on mods
        if self.graph.number_of_nodes() > 0:
            most_depended = max(
                self.graph.nodes(),
                key=lambda n: len(self.find_dependents(n))
            )
            stats["most_depended_on"] = {
                "mod": most_depended,
                "dependent_count": len(self.find_dependents(most_depended)),
            }
        else:
            stats["most_depended_on"] = None

        return stats

    def export_dot(self, output_path: Path) -> None:
        """Export graph to DOT format for visualization with Graphviz.

        Args:
            output_path: Path to save DOT file

        Example:
            >>> graph.export_dot(Path("dependencies.dot"))
            >>> # Then: dot -Tpng dependencies.dot -o dependencies.png
        """
        nx.drawing.nx_pydot.write_dot(self.graph, str(output_path))

    def to_ascii(self, max_depth: int = 3) -> str:
        """Generate ASCII-art representation of dependency graph.

        Args:
            max_depth: Maximum depth to display

        Returns:
            Multi-line ASCII string

        Example:
            >>> print(graph.to_ascii())
            MCCC ────┬──→ MCCC Dresser
                     ├──→ AdvancedMod
                     └──→ CustomInteractions
        """
        if self.graph.number_of_nodes() == 0:
            return "Empty dependency graph"

        lines = []
        lines.append("=== DEPENDENCY GRAPH ===\n")

        # Get root nodes (no dependencies)
        roots = [n for n in self.graph.nodes() if self.graph.out_degree(n) == 0]

        for root in roots[:10]:  # Limit to first 10 roots
            dependents = list(self.find_dependents(root))

            if not dependents:
                lines.append(f"{root} (standalone mod)")
            else:
                lines.append(f"{root} ────┬──→ {dependents[0]}")

                for i, dep in enumerate(dependents[1:], 1):
                    if i < len(dependents) - 1:
                        lines.append(f"{'':>{len(root)}} ├──→ {dep}")
                    else:
                        lines.append(f"{'':>{len(root)}} └──→ {dep}")

            lines.append("")  # Blank line between trees

        # Add cycle warning
        if self.has_cycles():
            lines.append("⚠️  CIRCULAR DEPENDENCIES DETECTED!")
            for cycle in self.detect_cycles()[:3]:  # Show first 3 cycles
                cycle_str = " → ".join(cycle + [cycle[0]])
                lines.append(f"  Cycle: {cycle_str}")

        return "\n".join(lines)
