"""Result -> JSON-serialisable dict transforms.

Intended as the single source of truth for both the desktop stdio bridge
(simanalysis.bridge — already wired) and the FastAPI/WebSocket layer
(simanalysis.web.api — wiring pending; it still inlines its own transforms today).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from simanalysis.formats.types import type_name


def _hex(value: Any, width: int) -> str | None:
    if value is None:
        return None
    return f"0x{int(value):0{width}X}"


def _resource_type_counts(resources: list[Any]) -> list[dict[str, Any]]:
    counts: Counter[int] = Counter()
    for resource in resources:
        counts[int(resource.type)] += 1

    return [
        {
            "type_id": resource_type,
            "type_hex": _hex(resource_type, 8),
            "name": type_name(resource_type),
            "count": count,
        }
        for resource_type, count in sorted(counts.items())
    ]


def _parse_status_summary(items: list[Any]) -> dict[str, Any]:
    statuses = Counter(str(getattr(item, "parse_status", None) or "unknown") for item in items)
    warnings: list[dict[str, Any]] = []

    for item in items:
        status = str(getattr(item, "parse_status", None) or "unknown")
        for warning in getattr(item, "warnings", []) or []:
            warnings.append(
                {
                    "status": status,
                    "message": str(warning),
                    "resource_group": _hex(getattr(item, "resource_group", None), 8),
                    "resource_instance": _hex(getattr(item, "resource_instance", None), 16),
                }
            )

    return {
        "total": len(items),
        "statuses": dict(sorted(statuses.items())),
        "warning_count": len(warnings),
        "warnings": warnings,
    }


def _resource_summary(mod: Any) -> dict[str, Any]:
    resources = list(getattr(mod, "resources", []) or [])
    tunings = list(getattr(mod, "tunings", []) or [])
    scripts = list(getattr(mod, "scripts", []) or [])
    string_tables = list(getattr(mod, "string_tables", []) or [])
    sim_data = list(getattr(mod, "sim_data", []) or [])

    return {
        "resource_count": len(resources),
        "tuning_count": len(tunings),
        "script_count": len(scripts),
        "string_table_count": len(string_tables),
        "sim_data_count": len(sim_data),
        "resource_types": _resource_type_counts(resources),
        "parse_status": {
            "string_tables": _parse_status_summary(string_tables),
            "sim_data": _parse_status_summary(sim_data),
        },
    }


def _mod_to_dict(mod: Any, result: Any) -> dict[str, Any]:
    summary = _resource_summary(mod)
    return {
        "name": mod.name,
        "path": str(mod.path),
        "type": mod.type.value,
        "size": mod.size,
        "hash": getattr(mod, "hash", None),
        "author": mod.author or "Unknown",
        "version": mod.version or "Unknown",
        "conflicts": len([c for c in result.conflicts if mod.name in c.affected_mods]),
        "resource_count": summary["resource_count"],
        "tuning_count": summary["tuning_count"],
        "script_count": summary["script_count"],
        "string_table_count": summary["string_table_count"],
        "sim_data_count": summary["sim_data_count"],
        "resource_summary": summary,
    }


def mod_result_to_dict(analyzer: Any, result: Any) -> dict[str, Any]:
    return {
        "summary": analyzer.get_summary(result),
        "mods": [_mod_to_dict(m, result) for m in result.mods],
        "conflicts": [
            {
                "id": c.id,
                "severity": c.severity.value,
                "type": c.type.value,
                "description": c.description,
                "affected_mods": c.affected_mods,
                "resolution": c.resolution,
                "details": getattr(c, "details", {}),
            }
            for c in result.conflicts
        ],
        "performance": {
            "total_size_mb": result.performance.total_size_mb,
            "total_resources": result.performance.total_resources,
            "total_tunings": result.performance.total_tunings,
            "total_scripts": result.performance.total_scripts,
            "estimated_load_time_seconds": result.performance.estimated_load_time_seconds,
            "estimated_memory_mb": result.performance.estimated_memory_mb,
            "complexity_score": result.performance.complexity_score,
        },
        "recommendations": analyzer.get_recommendations(result),
        "warnings": getattr(result, "warnings", []),
    }


def tray_result_to_dict(analyzer: Any, result: Any) -> dict[str, Any]:
    return {
        "summary": analyzer.get_summary(result),
        "items": [item.to_dict() for item in result.items],
    }


def save_result_to_dict(analyzer: Any, result: Any) -> dict[str, Any]:
    return {
        "summary": analyzer.get_summary(result),
        "save_info": result.save_data.to_dict(),
        "used_mods": [
            {
                "name": mod.name,
                "path": str(mod.path),
                "size": mod.size,
                "resource_count": mod.resource_count,
                "matching_resources": len(mod.matching_resources),
            }
            for mod in result.used_mods
        ],
        "unused_mods": [
            {
                "name": mod.name,
                "path": str(mod.path),
                "size": mod.size,
                "resource_count": mod.resource_count,
            }
            for mod in result.unused_mods[:100]
        ],
    }


def crash_result_to_dict(result: Any) -> dict[str, Any]:
    return {
        "summary": result.summary,
        "ranked_mods": result.ranked_mods,
        "parse_errors": result.parse_errors,
        "findings": [
            {
                "source_file": f.report.source_file,
                "report_type": f.report.report_type,
                "exception_class": f.report.exception_class,
                "message": f.report.message,
                "creator_tag": f.report.creator_tag,
                "created": f.report.created,
                "game_version": f.report.game_version,
                "be_advice": f.report.be_advice,
                "suspects": [
                    {
                        "mod": s.mod_name,
                        "confidence": s.confidence,
                        "status": s.status,
                        "reason": s.reason,
                        "evidence": [fr.raw_path for fr in s.evidence],
                    }
                    for s in f.suspects
                ],
            }
            for f in result.findings
        ],
    }


def _ui_key_to_dict(key: int) -> dict[str, Any]:
    return {"decimal": key, "hex": f"0x{key:016X}"}


def ui_result_to_dict(result: Any) -> dict[str, Any]:
    return {
        "summary": result.summary,
        "parse_errors": result.parse_errors,
        "index_errors": result.index_errors,
        "findings": [
            {
                "status": finding.status,
                "reason": finding.reason,
                "keys": [_ui_key_to_dict(key) for key in finding.keys],
                "report": {
                    "source_file": finding.report.source_file,
                    "source_files": finding.report.source_files,
                    "report_type": finding.report.report_type,
                    "message": finding.report.message,
                    "category_id": finding.report.category_id,
                    "created": finding.report.created,
                    "game_version": finding.report.game_version,
                    "session_id": finding.report.session_id,
                    "desync_id": finding.report.desync_id,
                    "modded": finding.report.modded,
                    "occurrences": finding.report.occurrences,
                    "signature": finding.report.signature,
                    "stack": [
                        {
                            "raw": frame.raw,
                            "namespace": frame.namespace,
                            "function": frame.function,
                        }
                        for frame in finding.report.stack
                    ],
                },
                "hits": [
                    {
                        "key": _ui_key_to_dict(hit.key),
                        "package_name": hit.package_name,
                        "package_path": hit.package_path,
                        "resource_type": hit.resource_type,
                        "resource_type_hex": f"0x{hit.resource_type:08X}",
                        "resource_group": hit.resource_group,
                        "resource_group_hex": f"0x{hit.resource_group:08X}",
                        "status": hit.status,
                    }
                    for hit in finding.hits
                ],
            }
            for finding in result.findings
        ],
    }
