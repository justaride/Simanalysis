"""Read-only cleanup planning for Sims 4 Mods folders."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

PLAN_VERSION = 1
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z"}
SUPPORT_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".txt",
    ".md",
    ".pdf",
    ".rtf",
    ".doc",
    ".docx",
    ".url",
    ".webloc",
    ".lnk",
}
SUPPORT_NAMES = {".ds_store", "thumbs.db"}
TRAY_EXTENSIONS = {".trayitem", ".blueprint", ".bpi", ".hhi", ".householdbinary", ".sgi"}


@dataclass(frozen=True)
class CleanupFile:
    relative_path: str
    extension: str
    size: int
    sha256: str


class CleanupPlanner:
    """Build read-only cleanup plans from inventory snapshots."""

    def __init__(
        self,
        db_path: Path | str,
        *,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self.db_path = Path(db_path).expanduser()
        self._clock = clock or _utc_now

    def plan(self, root_path: Path | str) -> dict[str, object]:
        root = Path(root_path).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError(f"Cleanup root is not a directory: {root_path}")
        if not self.db_path.exists():
            raise ValueError("No inventory database exists; run inventory-scan first")

        created_at = self._clock()
        plan_id = _plan_id(created_at)
        snapshot = _load_latest_inventory_files(self.db_path, root)
        mods_files = [item for item in snapshot.files if _is_mods_path(item.relative_path)]
        findings: list[dict[str, object]] = []
        findings.extend(_duplicate_findings(mods_files, plan_id))
        findings.extend(_single_file_findings(mods_files, plan_id))
        summary = _summary(mods_files, findings)
        warnings = list(snapshot.warnings)
        if not mods_files:
            warnings.append("Latest inventory snapshot contains no Mods files")

        return {
            "version": PLAN_VERSION,
            "plan_id": plan_id,
            "created_at": created_at,
            "root_path": str(root),
            "mods_path": str(root / "Mods"),
            "db_path": str(self.db_path),
            "scan_id": snapshot.scan_id,
            "summary": summary,
            "findings": findings,
            "warnings": warnings,
        }

    def export_plan(self, root_path: Path | str, export_path: Path | str) -> dict[str, object]:
        root = Path(root_path).expanduser().resolve()
        destination = Path(export_path).expanduser().resolve()
        if destination == root or root in destination.parents:
            raise ValueError("Cleanup plan export path must be outside the selected Sims 4 folder")

        plan = self.plan(root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return plan


@dataclass(frozen=True)
class _InventorySnapshot:
    scan_id: int
    files: list[CleanupFile]
    warnings: list[str]


def _load_latest_inventory_files(db_path: Path, root: Path) -> _InventorySnapshot:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        snapshot = conn.execute(
            """
            SELECT
                s.id AS snapshot_id,
                s.scan_id,
                sc.warnings_json
            FROM snapshots s
            JOIN scans sc ON sc.id = s.scan_id
            WHERE s.root_path = ?
            ORDER BY s.id DESC
            LIMIT 1
            """,
            (str(root),),
        ).fetchone()
        if snapshot is None:
            raise ValueError(f"No inventory scan exists for {root}; run inventory-scan first")

        rows = conn.execute(
            """
            SELECT
                sf.relative_path,
                f.extension,
                sf.size,
                sf.sha256
            FROM snapshot_files sf
            JOIN files f ON f.id = sf.file_id
            WHERE sf.snapshot_id = ?
            ORDER BY sf.relative_path
            """,
            (int(snapshot["snapshot_id"]),),
        ).fetchall()

    return _InventorySnapshot(
        scan_id=int(snapshot["scan_id"]),
        files=[
            CleanupFile(
                relative_path=str(row["relative_path"]),
                extension=str(row["extension"]).lower(),
                size=int(row["size"]),
                sha256=str(row["sha256"]),
            )
            for row in rows
        ],
        warnings=json.loads(str(snapshot["warnings_json"])),
    )


def _is_mods_path(relative_path: str) -> bool:
    return relative_path == "Mods" or relative_path.startswith("Mods/")


def _duplicate_findings(files: list[CleanupFile], plan_id: str) -> list[dict[str, object]]:
    by_identity: dict[tuple[str, int], list[CleanupFile]] = {}
    for item in files:
        if item.size <= 0:
            continue
        by_identity.setdefault((item.sha256, item.size), []).append(item)

    findings: list[dict[str, object]] = []
    duplicate_index = 1
    for (sha256, size), group in sorted(by_identity.items(), key=lambda item: item[0]):
        if len(group) < 2:
            continue
        ordered_paths = sorted(item.relative_path for item in group)
        keep = min(ordered_paths, key=lambda path: (path.count("/"), len(path), path))
        actions = []
        for source in [path for path in ordered_paths if path != keep]:
            actions.append(
                {
                    "action_id": f"duplicate:{duplicate_index}",
                    "kind": "review_duplicate",
                    "source_relative_path": source,
                    "proposed_destination": _destination(plan_id, "duplicates", source),
                    "reason": f"Exact duplicate of {keep}",
                }
            )
            duplicate_index += 1
        findings.append(
            {
                "finding_id": f"duplicate:sha256:{sha256}",
                "category": "exact_duplicate",
                "severity": "review",
                "title": "Exact duplicate files",
                "explanation": "These files have identical SHA-256 and size in Mods.",
                "evidence": {
                    "sha256": sha256,
                    "size": size,
                    "paths": ordered_paths,
                    "keep_candidate": keep,
                },
                "actions": actions,
            }
        )
    return findings


def _single_file_findings(files: list[CleanupFile], plan_id: str) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for item in sorted(files, key=lambda file: file.relative_path):
        finding = _single_file_finding(item, plan_id)
        if finding is not None:
            findings.append(finding)
    return findings


def _single_file_finding(item: CleanupFile, plan_id: str) -> dict[str, object] | None:
    name = Path(item.relative_path).name
    lowered_name = name.casefold()
    if item.extension in ARCHIVE_EXTENSIONS:
        return _review_finding(
            item,
            plan_id,
            category="inactive_archive",
            kind="review_archive",
            title="Archive file inside Mods",
            explanation="The Sims 4 does not load this archive directly from Mods.",
            bucket="archives",
        )
    if lowered_name == "resource.cfg" and item.relative_path.casefold() != "mods/resource.cfg":
        return _review_finding(
            item,
            plan_id,
            category="duplicate_resource_cfg",
            kind="review_resource_cfg",
            title="Nested Resource.cfg",
            explanation="Only the root Mods/Resource.cfg is expected for normal setup.",
            bucket="resource_cfg",
        )
    if item.extension in SUPPORT_EXTENSIONS or lowered_name in SUPPORT_NAMES:
        return _review_finding(
            item,
            plan_id,
            category="support_file",
            kind="review_support_file",
            title="Support file inside Mods",
            explanation="This file is not an active package or script payload.",
            bucket="support_files",
        )
    if item.extension in TRAY_EXTENSIONS:
        return _review_finding(
            item,
            plan_id,
            category="misplaced_tray",
            kind="review_misplaced_tray",
            title="Likely Tray file inside Mods",
            explanation="Tray files normally belong in the Sims 4 Tray folder, not Mods.",
            bucket="misplaced_tray",
        )
    return None


def _review_finding(
    item: CleanupFile,
    plan_id: str,
    *,
    category: str,
    kind: str,
    title: str,
    explanation: str,
    bucket: str,
) -> dict[str, object]:
    return {
        "finding_id": f"{category}:{item.relative_path}",
        "category": category,
        "severity": "review",
        "title": title,
        "explanation": explanation,
        "evidence": {
            "path": item.relative_path,
            "extension": item.extension,
            "size": item.size,
            "sha256": item.sha256,
        },
        "actions": [
            {
                "action_id": f"{category}:1:{item.relative_path}",
                "kind": kind,
                "source_relative_path": item.relative_path,
                "proposed_destination": _destination(plan_id, bucket, item.relative_path),
                "reason": explanation,
            }
        ],
    }


def _destination(plan_id: str, bucket: str, relative_path: str) -> str:
    return f"_Simanalysis_Cleanup/{plan_id}/{bucket}/{relative_path}"


def _action_count(finding: dict[str, object]) -> int:
    actions = finding.get("actions")
    return len(actions) if isinstance(actions, list) else 0


def _summary(files: list[CleanupFile], findings: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {
        "files_considered": len(files),
        "finding_count": len(findings),
        "action_count": sum(_action_count(finding) for finding in findings),
        "duplicate_groups": 0,
        "archives": 0,
        "duplicate_resource_cfg": 0,
        "support_files": 0,
        "misplaced_tray": 0,
    }
    for finding in findings:
        category = str(finding["category"])
        if category == "exact_duplicate":
            counts["duplicate_groups"] += 1
        elif category == "inactive_archive":
            counts["archives"] += 1
        elif category == "duplicate_resource_cfg":
            counts["duplicate_resource_cfg"] += 1
        elif category == "support_file":
            counts["support_files"] += 1
        elif category == "misplaced_tray":
            counts["misplaced_tray"] += 1
    return counts


def _plan_id(created_at: str) -> str:
    digits = "".join(character for character in created_at if character.isdigit())
    return f"cleanup-{digits[:8]}-{digits[8:14]}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
