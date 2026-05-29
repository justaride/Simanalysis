"""Resolve Sims 4 UI exception resource keys to installed package resources."""

from __future__ import annotations

from collections.abc import Iterable
from copy import copy
from pathlib import Path

from simanalysis.analyzers.crash_analyzer import STATUS_ACTIVE, STATUS_DISABLED, _is_disabled_name
from simanalysis.exceptions import DBPFError
from simanalysis.models import UIAnalysisResult, UIExceptionReport, UIFinding, UIResourceHit
from simanalysis.parsers.dbpf import DBPFReader

STATUS_NOT_FOUND = "not_found"
STATUS_NO_KEY = "no_key"

_EXCLUDED_COPY_PREFIXES = ("_cachebackup", "_recovered")


def _is_excluded_copy_path(path: Path) -> bool:
    """True if any path segment belongs to a generated backup/recovery copy."""
    return any(
        part.lower().startswith(prefix)
        for part in Path(path).parts
        for prefix in _EXCLUDED_COPY_PREFIXES
    )


def _status_for_package(path: Path) -> str:
    """Return disabled when any path segment is a disabled/quarantine marker."""
    for part in Path(path).parts:
        if _is_disabled_name(part):
            return STATUS_DISABLED
    return STATUS_ACTIVE


def discover_disabled_roots(base: str | Path) -> list[Path]:
    """Find disabled/quarantine folders under a Sims 4/base directory."""
    base_path = Path(base)
    if not base_path.exists():
        return []
    return sorted(
        path
        for path in base_path.rglob("*")
        if path.is_dir() and _is_disabled_name(path.name) and not _is_excluded_copy_path(path)
    )


def _read_package_hits(path: Path, status: str) -> list[UIResourceHit]:
    """Read DBPF resources from one package and convert them to index hits."""
    reader = DBPFReader(path)
    resources = reader.read_index()
    return [
        UIResourceHit(
            key=resource.instance,
            package_name=path.name,
            package_path=str(path),
            resource_type=resource.type,
            resource_group=resource.group,
            status=status,
        )
        for resource in resources
    ]


class UICrashAnalyzer:
    """Analyze parsed UI exception reports against package resource indexes."""

    def __init__(self) -> None:
        self.index_errors: list[str] = []

    def build_resource_index(
        self,
        mods_dir: str | Path,
        extra_roots: Iterable[str | Path] = (),
    ) -> dict[int, list[UIResourceHit]]:
        """Build instance-key -> package-resource hits from active and disabled roots."""
        self.index_errors = []
        index: dict[int, list[UIResourceHit]] = {}
        seen_paths: set[Path] = set()

        for root in [Path(mods_dir), *(Path(root) for root in extra_roots)]:
            if not root.exists() or _is_excluded_copy_path(root):
                continue
            for package in root.rglob("*.package"):
                if _is_excluded_copy_path(package):
                    continue
                resolved = package.resolve()
                if resolved in seen_paths:
                    continue
                seen_paths.add(resolved)
                try:
                    hits = _read_package_hits(package, _status_for_package(package))
                except (DBPFError, FileNotFoundError, OSError) as exc:
                    self.index_errors.append(f"{package}: {exc}")
                    continue
                for hit in hits:
                    index.setdefault(hit.key, []).append(hit)

        return index

    def analyze(
        self,
        reports: list[UIExceptionReport],
        index: dict[int, list[UIResourceHit]],
    ) -> UIAnalysisResult:
        """Analyze reports, collapsing duplicate signatures before finding package hits."""
        collapsed = self._collapse_reports(reports)
        findings = [self._finding_for(report, index) for report in collapsed]
        return UIAnalysisResult(
            summary=self._summary(findings),
            findings=findings,
            index_errors=list(self.index_errors),
        )

    def _collapse_reports(self, reports: list[UIExceptionReport]) -> list[UIExceptionReport]:
        collapsed: dict[str, UIExceptionReport] = {}
        order: list[str] = []
        for report in reports:
            signature = report.signature or f"{report.category_id}|{report.message}|{report.keys}"
            if signature not in collapsed:
                copied = copy(report)
                copied.keys = list(report.keys)
                copied.stack = list(report.stack)
                copied.source_files = list(dict.fromkeys(report.source_files or [report.source_file]))
                copied.occurrences = report.occurrences
                collapsed[signature] = copied
                order.append(signature)
                continue

            existing = collapsed[signature]
            existing.occurrences += report.occurrences
            for source_file in report.source_files or [report.source_file]:
                if source_file not in existing.source_files:
                    existing.source_files.append(source_file)

        return [collapsed[signature] for signature in order]

    def _finding_for(
        self,
        report: UIExceptionReport,
        index: dict[int, list[UIResourceHit]],
    ) -> UIFinding:
        keys = list(dict.fromkeys(report.keys))
        if not keys:
            return UIFinding(
                report=report,
                status=STATUS_NO_KEY,
                keys=[],
                reason="no resource key found in UI exception",
            )

        hits = [hit for key in keys for hit in index.get(key, [])]
        if not hits:
            return UIFinding(
                report=report,
                status=STATUS_NOT_FOUND,
                keys=keys,
                reason="resource key not found in scanned package files",
            )

        status = (
            STATUS_ACTIVE
            if any(hit.status == STATUS_ACTIVE for hit in hits)
            else STATUS_DISABLED
        )
        return UIFinding(
            report=report,
            status=status,
            keys=keys,
            hits=hits,
            reason=f"resource key matched {status} package",
        )

    def _summary(self, findings: list[UIFinding]) -> dict[str, int]:
        summary = {
            "unique_findings": len(findings),
            "occurrences": sum(finding.report.occurrences for finding in findings),
            "active_findings": 0,
            "disabled_findings": 0,
            "not_found_findings": 0,
            "no_key_findings": 0,
        }
        for finding in findings:
            if finding.status == STATUS_ACTIVE:
                summary["active_findings"] += 1
            elif finding.status == STATUS_DISABLED:
                summary["disabled_findings"] += 1
            elif finding.status == STATUS_NOT_FOUND:
                summary["not_found_findings"] += 1
            elif finding.status == STATUS_NO_KEY:
                summary["no_key_findings"] += 1
        return summary
