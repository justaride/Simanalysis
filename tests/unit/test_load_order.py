"""Resource.cfg parsing and load-order simulation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from simanalysis.load_order import (
    parse_resource_cfg_text,
    read_resource_cfg,
    simulate_package_load_order,
)

pytestmark = pytest.mark.synthetic


def test_parse_resource_cfg_keeps_priority_scoped_packed_file_rules() -> None:
    cfg = parse_resource_cfg_text(
        """
        # Default Sims 4 package rules
        Priority 500
        PackedFile *.package
        PackedFile */*.package
        DirectoryFiles unpackedmod autoupdate

        Priority 1000
        PackedFile Overrides/*.package
        NotARealDirective value
        """,
        path=Path("/Sims/Mods/Resource.cfg"),
    )

    assert cfg.path == Path("/Sims/Mods/Resource.cfg")
    assert cfg.used_default is False
    assert [(rule.priority, rule.pattern, rule.line_number) for rule in cfg.packed_files] == [
        (500, "*.package", 4),
        (500, "*/*.package", 5),
        (1000, "Overrides/*.package", 9),
    ]
    assert cfg.directory_files == (("unpackedmod", "autoupdate"),)
    assert cfg.warnings == ("Line 10: unsupported Resource.cfg directive: NotARealDirective",)


def test_read_resource_cfg_uses_honest_default_when_root_file_is_missing(tmp_path: Path) -> None:
    mods_dir = tmp_path / "Mods"
    mods_dir.mkdir()

    cfg = read_resource_cfg(mods_dir)

    assert cfg.path == mods_dir / "Resource.cfg"
    assert cfg.used_default is True
    assert cfg.packed_files
    assert cfg.warnings == ("Mods/Resource.cfg not found; using bundled default Sims 4 patterns",)


def test_simulate_package_load_order_uses_priority_then_pattern_then_path(
    tmp_path: Path,
) -> None:
    mods_dir = tmp_path / "Mods"
    mods_dir.mkdir()

    root_package = mods_dir / "Root.package"
    nested_package = mods_dir / "Creator" / "Nested.package"
    override_package = mods_dir / "Overrides" / "Patch.package"

    cfg = parse_resource_cfg_text(
        """
        Priority 500
        PackedFile *.package
        PackedFile */*.package
        Priority 1000
        PackedFile Overrides/*.package
        """,
        path=mods_dir / "Resource.cfg",
    )

    plan = simulate_package_load_order(
        mods_dir,
        [override_package, nested_package, root_package],
        resource_cfg=cfg,
    )

    assert [entry.relative_path for entry in plan.entries] == [
        "Root.package",
        "Creator/Nested.package",
        "Overrides/Patch.package",
    ]
    assert [entry.priority for entry in plan.entries] == [500, 500, 1000]

    verdict = plan.explain_winner([root_package, nested_package, override_package])
    assert verdict.winner_relative_path == "Overrides/Patch.package"
    assert verdict.confidence == "configured"
    assert verdict.reason == "winner inferred from Resource.cfg priority and path order"


def test_simulate_package_load_order_reports_partial_confidence_for_unmatched_files(
    tmp_path: Path,
) -> None:
    mods_dir = tmp_path / "Mods"
    mods_dir.mkdir()
    root_package = mods_dir / "Root.package"
    too_deep = mods_dir / "A" / "B" / "TooDeep.package"

    cfg = parse_resource_cfg_text(
        """
        Priority 500
        PackedFile *.package
        PackedFile */*.package
        """,
        path=mods_dir / "Resource.cfg",
    )

    plan = simulate_package_load_order(mods_dir, [too_deep, root_package], resource_cfg=cfg)

    assert [entry.relative_path for entry in plan.entries] == ["Root.package"]
    assert plan.unmatched_relative_paths == ("A/B/TooDeep.package",)

    verdict = plan.explain_winner([root_package, too_deep])
    assert verdict.winner_relative_path == "Root.package"
    assert verdict.confidence == "partial"
    assert verdict.unmatched_relative_paths == ("A/B/TooDeep.package",)
