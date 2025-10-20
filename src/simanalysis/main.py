"""Command-line interface for running the Simanalysis diagnostics."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import sys
from collections import defaultdict
from pathlib import Path
from textwrap import shorten
from typing import Iterable, Sequence

from .analyzer import AnalysisResult, ModAnalyzer
from .dbpf_parser import DBPFPackage


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan a Sims 4 Mods directory and generate a diagnostics report.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to the Sims 4 Mods directory (defaults to current working directory).",
    )
    parser.add_argument(
        "--exceptions",
        action="store_true",
        help="Include summaries from lastException.txt if available.",
    )
    parser.add_argument(
        "--exceptions-path",
        type=str,
        default=None,
        help="Explicit path to a lastException log to include in the report.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Write an HTML report to the specified file.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    mods_path = Path(args.path).expanduser().resolve()

    analyzer = ModAnalyzer()

    try:
        result = analyzer.analyze_directory(str(mods_path))
    except FileNotFoundError as exc:  # pragma: no cover - CLI level validation
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    scan_time = dt.datetime.now()

    exception_entries = []
    if args.exceptions:
        exception_entries = collect_exception_summaries(mods_path, args.exceptions_path)

    render_console_report(
        result,
        mods_path,
        scan_time,
        exception_entries,
        exceptions_requested=args.exceptions,
    )

    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.write_text(
            render_html_report(result, mods_path, scan_time, exception_entries),
            encoding="utf-8",
        )
        print(f"\n📄 Report generated: {output_path}")

    return 0


def render_console_report(
    result: AnalysisResult,
    mods_path: Path,
    scan_time: dt.datetime,
    exceptions: Sequence[dict[str, str]],
    *,
    exceptions_requested: bool,
) -> None:
    divider = "=" * 80
    print(divider)
    print("🎮 SIMS 4 MOD ANALYZER")
    print(divider)
    print()
    print(f"📁 Scanning: {mods_path}")
    print()

    print("📦 Scanning package files...")
    for package in result.packages:
        print(f"Parsed: {package.path.name} ({len(package.resources)} resources)")
    for path, message in result.package_errors:
        print(f"⚠️ Failed: {path.name} — {message}")
    print(f"✓ Found {len(result.packages)} package files")
    print()

    print("📜 Scanning script files...")
    for metadata in result.scripts:
        print(f"Analyzed: {metadata.path.name} ({metadata.file_count} files)")
    for path, message in result.script_errors:
        print(f"⚠️ Failed: {path.name} — {message}")
    print(f"✓ Found {len(result.scripts)} script files")
    print()

    print("🔍 Detecting conflicts...")
    print(f"✓ Found {len(result.conflicts)} potential conflicts")
    print()

    print("⚡ Analyzing performance...")
    print(f"✓ Performance score: {result.performance_score:.0f}/100")
    print()

    print(divider)
    print("🎮 SIMS 4 MOD ANALYSIS REPORT")
    print(divider)
    print()

    print("📊 SUMMARY")
    print(f"   Scan Time: {scan_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Mods Path: {mods_path}")
    print(
        f"   Total Mods: {result.total_mods}"
        f" ({len(result.packages)} packages + {len(result.scripts)} scripts)"
    )

    severity_map = defaultdict(list)
    for conflict in result.conflicts:
        severity_map[conflict.severity.upper()].append(conflict)

    severity_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
    ordered_keys = sorted(
        severity_map.keys(),
        key=lambda item: severity_order.index(item)
        if item in severity_order
        else len(severity_order),
    )

    if result.conflicts:
        print(f"   Conflicts: {len(result.conflicts)}", end="")
        if severity_map:
            totals = [
                f"{len(entries)} {severity}"
                for severity in ordered_keys
                for entries in [severity_map[severity]]
            ]
            print(f" ({', '.join(totals)})")
        else:
            print()
    else:
        print("   Conflicts: 0")

    print()

    print("⚠️  DETECTED CONFLICTS")
    if not result.conflicts:
        print("   • None detected")
    else:
        for severity in ordered_keys:
            entries = severity_map[severity]
            print(f"\n[{severity}] {len(entries)} issue(s)")
            for conflict in entries:
                affected = ", ".join(conflict.affected_mods)
                print(f"  • {conflict.type.replace('_', ' ').title()}")
                print(f"    {conflict.description}")
                if affected:
                    print(f"    Affected: {affected}")
                if conflict.resolution:
                    print(f"    Fix: {conflict.resolution}")

    print()
    print("⚡ PERFORMANCE")
    print(f"   Score: {result.performance_score:.0f}/100")
    print(f"   Load Time: ~{max(result.total_mods * 0.03, 0):.1f} seconds")
    total_size_mb = estimate_total_package_size(result.packages)
    print(f"   Total Size: {total_size_mb:.1f} MB")

    if result.dependencies:
        print()
        print("📦 DEPENDENCIES")
        for mod_name, deps in sorted(result.dependencies.items()):
            print(f"   • {mod_name}: {', '.join(deps)}")

    if result.recommendations:
        print()
        print("💡 RECOMMENDATIONS")
        for item in result.recommendations:
            print(f"   • {item}")

    if exceptions:
        print()
        print("🧾 LAST EXCEPTION SUMMARY")
        for entry in exceptions:
            print(f"   • {entry['summary']}")
    elif exceptions_requested:
        print()
        print("🧾 LAST EXCEPTION SUMMARY")
        print("   • No exception logs located")


def estimate_total_package_size(packages: Iterable[DBPFPackage]) -> float:
    total_size = 0
    for package in packages:
        try:
            total_size += package.path.stat().st_size
        except OSError:
            continue
    return total_size / (1024 * 1024) if total_size else 0.0


def collect_exception_summaries(mods_path: Path, explicit_path: str | None) -> list[dict[str, str]]:
    candidate_paths = []
    if explicit_path:
        explicit = Path(explicit_path).expanduser()
        if explicit.exists():
            candidate_paths.append(explicit)
    else:
        for candidate in {
            mods_path / "lastException.txt",
            mods_path.parent / "lastException.txt",
            mods_path / "LastException.txt",
            mods_path.parent / "LastException.txt",
            Path.home() / "Documents/Electronic Arts/The Sims 4/lastException.txt",
        }:
            if candidate.exists():
                candidate_paths.append(candidate)

    entries = []
    for path in candidate_paths:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
        for block in blocks[-3:]:
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if not lines:
                continue
            summary = shorten(lines[0], width=120, placeholder="…")
            snippet = "\n".join(lines[:6])
            entries.append(
                {
                    "summary": summary,
                    "snippet": snippet,
                    "path": str(path),
                }
            )
    return entries


def render_html_report(
    result: AnalysisResult,
    mods_path: Path,
    scan_time: dt.datetime,
    exceptions: Sequence[dict[str, str]],
) -> str:
    def esc(value: str) -> str:
        return html.escape(value, quote=True)

    total_mods_summary = (
        f"{result.total_mods} ({len(result.packages)} packages + {len(result.scripts)} scripts)"
    )

    conflicts_rows = "".join(
        f"<tr><td>{esc(conflict.severity)}</td>"
        f"<td>{esc(conflict.type)}</td>"
        f"<td>{esc(', '.join(conflict.affected_mods))}</td>"
        f"<td>{esc(conflict.description)}</td>"
        f"<td>{esc(conflict.resolution or '')}</td></tr>"
        for conflict in result.conflicts
    )

    if not conflicts_rows:
        conflicts_rows = "<tr><td colspan='5'>No conflicts detected.</td></tr>"

    dependency_list = (
        "".join(
            f"<li><strong>{esc(mod)}</strong>: {esc(', '.join(deps))}</li>"
            for mod, deps in sorted(result.dependencies.items())
        )
        or "<li>No dependencies detected.</li>"
    )

    recommendations_list = (
        "".join(f"<li>{esc(item)}</li>" for item in result.recommendations)
        or "<li>No immediate actions recommended.</li>"
    )

    exception_section = (
        "".join(
            f"<article><h3>{esc(entry['summary'])}</h3>"
            f"<p><em>{esc(entry['path'])}</em></p>"
            f"<pre>{esc(entry['snippet'])}</pre></article>"
            for entry in exceptions
        )
        or "<p>No exception logs were found for this scan.</p>"
    )

    package_rows = (
        "".join(
            f"<tr><td>{esc(pkg.path.name)}</td><td>{len(pkg.resources)}</td></tr>"
            for pkg in result.packages
        )
        or "<tr><td colspan='2'>No packages detected.</td></tr>"
    )

    script_rows = (
        "".join(
            f"<tr><td>{esc(meta.path.name)}</td><td>{meta.file_count}</td></tr>"
            for meta in result.scripts
        )
        or "<tr><td colspan='2'>No script archives detected.</td></tr>"
    )

    html_report = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Sims 4 Mod Analysis Report</title>
  <style>
    body {{ font-family: 'Segoe UI', sans-serif; margin: 2rem; color: #1f2933; }}
    h1, h2 {{ color: #0b7285; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 1.5rem; }}
    th, td {{ border: 1px solid #d0d7de; padding: 0.5rem; text-align: left; }}
    th {{ background: #e3f2fd; }}
    pre {{ background: #f5f7fa; padding: 1rem; border-radius: 4px; overflow: auto; }}
    article {{ margin-bottom: 1.5rem; }}
  </style>
</head>
<body>
  <h1>Sims 4 Mod Analysis Report</h1>
  <p><strong>Scan Time:</strong> {esc(scan_time.strftime("%Y-%m-%d %H:%M:%S"))}</p>
  <p><strong>Mods Path:</strong> {esc(str(mods_path))}</p>
  <p><strong>Total Mods:</strong> {esc(total_mods_summary)}</p>
  <p><strong>Performance Score:</strong> {result.performance_score:.0f}/100</p>

  <h2>Package Files</h2>
  <table>
    <thead><tr><th>Package</th><th>Resource Count</th></tr></thead>
    <tbody>{package_rows}</tbody>
  </table>

  <h2>Script Archives</h2>
  <table>
    <thead><tr><th>Archive</th><th>Contained Files</th></tr></thead>
    <tbody>{script_rows}</tbody>
  </table>

  <h2>Conflicts</h2>
  <table>
    <thead>
      <tr>
        <th>Severity</th>
        <th>Type</th>
        <th>Affected Mods</th>
        <th>Description</th>
        <th>Resolution</th>
      </tr>
    </thead>
    <tbody>{conflicts_rows}</tbody>
  </table>

  <h2>Dependencies</h2>
  <ul>{dependency_list}</ul>

  <h2>Recommendations</h2>
  <ul>{recommendations_list}</ul>

  <h2>Exception Logs</h2>
  {exception_section}
</body>
</html>
"""

    return html_report


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
