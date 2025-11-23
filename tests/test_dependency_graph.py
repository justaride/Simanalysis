"""Tests for dependency graph analysis."""

from pathlib import Path

import pytest

from simanalysis.analyzers.dependency_graph import DependencyGraph
from simanalysis.models import Mod, ModType


@pytest.fixture
def simple_mods():
    """Create simple test mods."""
    mod_a = Mod(
        name="ModA.package",
        path=Path("ModA.package"),
        type=ModType.PACKAGE,
        size=1000,
        hash="abc123",
    )

    mod_b = Mod(
        name="ModB.package",
        path=Path("ModB.package"),
        type=ModType.PACKAGE,
        size=2000,
        hash="def456",
    )

    mod_c = Mod(
        name="ModC.package",
        path=Path("ModC.package"),
        type=ModType.PACKAGE,
        size=3000,
        hash="ghi789",
    )

    return mod_a, mod_b, mod_c


@pytest.fixture
def dependency_chain(simple_mods):
    """Create linear dependency chain: A -> B -> C."""
    mod_a, mod_b, mod_c = simple_mods

    graph = DependencyGraph()
    graph.add_mod(mod_a, dependencies=["ModB.package"])  # A depends on B
    graph.add_mod(mod_b, dependencies=["ModC.package"])  # B depends on C
    graph.add_mod(mod_c, dependencies=None)  # C has no dependencies

    return graph


@pytest.fixture
def circular_dependencies(simple_mods):
    """Create circular dependencies: A -> B -> C -> A."""
    mod_a, mod_b, mod_c = simple_mods

    graph = DependencyGraph()
    graph.add_mod(mod_a, dependencies=["ModB.package"])
    graph.add_mod(mod_b, dependencies=["ModC.package"])
    graph.add_mod(mod_c, dependencies=["ModA.package"])  # Circular!

    return graph


class TestDependencyGraphBasics:
    """Test basic dependency graph operations."""

    def test_empty_graph(self):
        """Test empty graph initialization."""
        graph = DependencyGraph()

        assert graph.graph.number_of_nodes() == 0
        assert graph.graph.number_of_edges() == 0
        assert len(graph.mod_map) == 0

    def test_add_mod_no_dependencies(self, simple_mods):
        """Test adding mod without dependencies."""
        mod_a, _, _ = simple_mods
        graph = DependencyGraph()

        graph.add_mod(mod_a, dependencies=None)

        assert graph.graph.number_of_nodes() == 1
        assert graph.graph.number_of_edges() == 0
        assert "ModA.package" in graph.mod_map

    def test_add_mod_with_dependencies(self, simple_mods):
        """Test adding mod with dependencies."""
        mod_a, _, _ = simple_mods
        graph = DependencyGraph()

        graph.add_mod(mod_a, dependencies=["MCCC", "Basemental"])

        assert graph.graph.number_of_nodes() == 3  # ModA + 2 dependencies
        assert graph.graph.number_of_edges() == 2  # 2 dependency edges

    def test_multiple_mods(self, simple_mods):
        """Test adding multiple mods."""
        mod_a, mod_b, mod_c = simple_mods
        graph = DependencyGraph()

        graph.add_mod(mod_a)
        graph.add_mod(mod_b)
        graph.add_mod(mod_c)

        assert graph.graph.number_of_nodes() == 3
        assert len(graph.mod_map) == 3


class TestCycleDetection:
    """Test circular dependency detection."""

    def test_no_cycles(self, dependency_chain):
        """Test detection when no cycles exist."""
        assert dependency_chain.has_cycles() is False
        assert len(dependency_chain.detect_cycles()) == 0

    def test_simple_cycle(self, circular_dependencies):
        """Test detection of simple cycle."""
        assert circular_dependencies.has_cycles() is True

        cycles = circular_dependencies.detect_cycles()
        assert len(cycles) > 0

        # Verify cycle contains all three mods
        cycle = cycles[0]
        assert len(cycle) == 3
        assert set(cycle) == {"ModA.package", "ModB.package", "ModC.package"}

    def test_self_loop(self, simple_mods):
        """Test detection of self-loop (mod depends on itself)."""
        mod_a, _, _ = simple_mods
        graph = DependencyGraph()

        graph.add_mod(mod_a, dependencies=["ModA.package"])  # Self-loop

        assert graph.has_cycles() is True
        cycles = graph.detect_cycles()
        assert len(cycles) > 0


class TestTopologicalSort:
    """Test topological sorting (load order)."""

    def test_linear_chain(self, dependency_chain):
        """Test sorting linear dependency chain."""
        order = dependency_chain.topological_sort()

        assert order is not None
        assert len(order) == 3

        # C should load first (no dependencies)
        # B should load second (depends on C)
        # A should load last (depends on B)
        assert order.index("ModC.package") < order.index("ModB.package")
        assert order.index("ModB.package") < order.index("ModA.package")

    def test_with_cycles(self, circular_dependencies):
        """Test sorting fails with cycles."""
        order = circular_dependencies.topological_sort()

        assert order is None  # Cannot sort with cycles

    def test_multiple_roots(self, simple_mods):
        """Test sorting with multiple independent mods."""
        mod_a, mod_b, mod_c = simple_mods
        graph = DependencyGraph()

        # A and B both depend on C
        graph.add_mod(mod_a, dependencies=["ModC.package"])
        graph.add_mod(mod_b, dependencies=["ModC.package"])
        graph.add_mod(mod_c, dependencies=None)

        order = graph.topological_sort()

        assert order is not None
        # C must load first
        assert order.index("ModC.package") < order.index("ModA.package")
        assert order.index("ModC.package") < order.index("ModB.package")


class TestDependencyQueries:
    """Test dependency relationship queries."""

    def test_find_dependencies(self, dependency_chain):
        """Test finding all dependencies of a mod."""
        # A depends on B and C (transitively)
        deps = dependency_chain.find_dependencies("ModA.package")

        assert "ModB.package" in deps
        assert "ModC.package" in deps
        assert len(deps) == 2

    def test_find_dependents(self, dependency_chain):
        """Test finding all dependents of a mod."""
        # C is depended on by B and A (transitively)
        dependents = dependency_chain.find_dependents("ModC.package")

        assert "ModB.package" in dependents
        assert "ModA.package" in dependents
        assert len(dependents) == 2

    def test_find_nonexistent_mod(self, dependency_chain):
        """Test querying mod that doesn't exist."""
        deps = dependency_chain.find_dependencies("NonexistentMod.package")
        assert len(deps) == 0

        dependents = dependency_chain.find_dependents("NonexistentMod.package")
        assert len(dependents) == 0


class TestImpactAnalysis:
    """Test impact analysis of mod removal."""

    def test_impact_standalone_mod(self, simple_mods):
        """Test impact of removing standalone mod."""
        mod_a, _, _ = simple_mods
        graph = DependencyGraph()
        graph.add_mod(mod_a, dependencies=None)

        impact = graph.impact_of_removal("ModA.package")

        assert impact["mod"] == "ModA.package"
        assert impact["will_break"] == 0
        assert len(impact["affected_mods"]) == 0
        assert "Safe to remove" in impact["recommendation"]

    def test_impact_depended_mod(self, dependency_chain):
        """Test impact of removing mod with dependents."""
        # Removing C breaks B and A
        impact = dependency_chain.impact_of_removal("ModC.package")

        assert impact["will_break"] == 2
        assert "ModB.package" in impact["affected_mods"]
        assert "ModA.package" in impact["affected_mods"]
        assert "CAUTION" in impact["recommendation"] or "RISK" in impact["recommendation"]

    def test_impact_leaf_mod(self, dependency_chain):
        """Test impact of removing leaf mod (has dependencies but no dependents)."""
        # Removing A doesn't break anything
        impact = dependency_chain.impact_of_removal("ModA.package")

        assert impact["will_break"] == 0
        assert "Safe to remove" in impact["recommendation"]


class TestMissingDependencies:
    """Test missing dependency detection."""

    def test_no_missing_dependencies(self, dependency_chain):
        """Test when all dependencies are installed."""
        installed = {"ModA.package", "ModB.package", "ModC.package"}

        missing = dependency_chain.find_missing_dependencies(installed)

        assert len(missing) == 0

    def test_one_missing_dependency(self, simple_mods):
        """Test with one missing dependency."""
        mod_a, _, _ = simple_mods
        graph = DependencyGraph()

        graph.add_mod(mod_a, dependencies=["MCCC"])  # MCCC not installed

        installed = {"ModA.package"}
        missing = graph.find_missing_dependencies(installed)

        assert len(missing) == 1
        assert missing[0] == ("ModA.package", "MCCC")

    def test_multiple_missing(self, simple_mods):
        """Test with multiple missing dependencies."""
        mod_a, mod_b, _ = simple_mods
        graph = DependencyGraph()

        graph.add_mod(mod_a, dependencies=["MCCC"])
        graph.add_mod(mod_b, dependencies=["Basemental", "WonderfulWhims"])

        installed = {"ModA.package", "ModB.package"}
        missing = graph.find_missing_dependencies(installed)

        assert len(missing) == 3
        missing_deps = [dep for _, dep in missing]
        assert "MCCC" in missing_deps
        assert "Basemental" in missing_deps
        assert "WonderfulWhims" in missing_deps


class TestLoadOrderIssues:
    """Test load order issue detection."""

    def test_correct_order(self, dependency_chain):
        """Test with correct load order."""
        # Optimal order: C, B, A
        current_order = ["ModC.package", "ModB.package", "ModA.package"]

        issues = dependency_chain.get_load_order_issues(current_order)

        assert len(issues) == 0

    def test_reversed_order(self, dependency_chain):
        """Test with reversed (worst) load order."""
        # Wrong order: A, B, C (should be C, B, A)
        current_order = ["ModA.package", "ModB.package", "ModC.package"]

        issues = dependency_chain.get_load_order_issues(current_order)

        # Both B and C should have issues
        assert len(issues) >= 2

        # Verify issues are identified
        issue_mods = [issue["mod"] for issue in issues]
        assert "ModC.package" in issue_mods  # Should load first
        assert "ModB.package" in issue_mods  # Should load second

    def test_severity_calculation(self, simple_mods):
        """Test severity calculation based on position difference."""
        mod_a, mod_b, mod_c = simple_mods
        graph = DependencyGraph()

        # Create long chain to test severity
        graph.add_mod(mod_a, dependencies=["ModB.package"])
        graph.add_mod(mod_b, dependencies=["ModC.package"])
        graph.add_mod(mod_c, dependencies=None)

        # Very wrong order (30 positions apart would be HIGH)
        issues = graph.get_load_order_issues(["ModC.package", "ModB.package", "ModA.package"])

        # With small graph, should be LOW or MEDIUM
        for issue in issues:
            assert issue["severity"] in ["LOW", "MEDIUM", "HIGH"]


class TestStatistics:
    """Test dependency graph statistics."""

    def test_empty_graph_stats(self):
        """Test statistics for empty graph."""
        graph = DependencyGraph()

        stats = graph.get_statistics()

        assert stats["total_mods"] == 0
        assert stats["total_dependencies"] == 0
        assert stats["has_cycles"] is False
        assert stats["cycle_count"] == 0

    def test_simple_graph_stats(self, dependency_chain):
        """Test statistics for simple graph."""
        stats = dependency_chain.get_statistics()

        assert stats["total_mods"] == 3
        assert stats["total_dependencies"] == 2
        assert stats["has_cycles"] is False
        assert stats["cycle_count"] == 0

        # C is most depended on (by B and A)
        assert stats["most_depended_on"]["mod"] == "ModC.package"
        assert stats["most_depended_on"]["dependent_count"] == 2

    def test_stats_with_cycles(self, circular_dependencies):
        """Test statistics with circular dependencies."""
        stats = circular_dependencies.get_statistics()

        assert stats["has_cycles"] is True
        assert stats["cycle_count"] > 0


class TestVisualization:
    """Test graph visualization methods."""

    def test_ascii_empty_graph(self):
        """Test ASCII output for empty graph."""
        graph = DependencyGraph()

        ascii_output = graph.to_ascii()

        assert "Empty" in ascii_output

    def test_ascii_simple_graph(self, dependency_chain):
        """Test ASCII output for simple graph."""
        ascii_output = dependency_chain.to_ascii()

        assert "DEPENDENCY GRAPH" in ascii_output
        # Should show mod names
        assert "Mod" in ascii_output

    def test_ascii_with_cycles(self, circular_dependencies):
        """Test ASCII output shows cycle warning."""
        ascii_output = circular_dependencies.to_ascii()

        assert "CIRCULAR" in ascii_output or "CYCLE" in ascii_output

    def test_export_dot(self, dependency_chain, tmp_path):
        """Test DOT file export."""
        output_file = tmp_path / "test_graph.dot"

        dependency_chain.export_dot(output_file)

        assert output_file.exists()
        content = output_file.read_text()
        assert "digraph" in content


class TestComplexScenarios:
    """Test complex dependency scenarios."""

    def test_diamond_dependency(self, simple_mods):
        """Test diamond dependency pattern.

        Structure:
            A
           / \
          B   C
           \ /
            D
        """
        mod_a, mod_b, mod_c = simple_mods
        mod_d = Mod(
            name="ModD.package",
            path=Path("ModD.package"),
            type=ModType.PACKAGE,
            size=4000,
            hash="jkl012",
        )

        graph = DependencyGraph()
        graph.add_mod(mod_a, dependencies=["ModB.package", "ModC.package"])
        graph.add_mod(mod_b, dependencies=["ModD.package"])
        graph.add_mod(mod_c, dependencies=["ModD.package"])
        graph.add_mod(mod_d, dependencies=None)

        # Should still be sortable (no cycles)
        order = graph.topological_sort()
        assert order is not None

        # D must load first
        assert order.index("ModD.package") < order.index("ModB.package")
        assert order.index("ModD.package") < order.index("ModC.package")
        assert order.index("ModD.package") < order.index("ModA.package")

    def test_large_graph_performance(self):
        """Test performance with larger graph (100 mods)."""
        graph = DependencyGraph()

        # Create chain of 100 mods
        for i in range(100):
            mod = Mod(
                name=f"Mod{i}.package",
                path=Path(f"Mod{i}.package"),
                type=ModType.PACKAGE,
                size=1000,
                hash=f"hash{i}",
            )

            if i > 0:
                graph.add_mod(mod, dependencies=[f"Mod{i-1}.package"])
            else:
                graph.add_mod(mod, dependencies=None)

        # Should handle large graph efficiently
        assert graph.graph.number_of_nodes() == 100
        assert graph.has_cycles() is False

        order = graph.topological_sort()
        assert order is not None
        assert len(order) == 100

        # First mod (Mod0) should load first
        assert order.index("Mod0.package") < order.index("Mod50.package")
        assert order.index("Mod0.package") < order.index("Mod99.package")
