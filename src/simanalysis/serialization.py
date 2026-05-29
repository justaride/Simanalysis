"""Result -> JSON-serialisable dict transforms.

Intended as the single source of truth for both the desktop stdio bridge
(simanalysis.bridge — already wired) and the FastAPI/WebSocket layer
(simanalysis.web.api — wiring pending; it still inlines its own transforms today).
"""

from __future__ import annotations

from typing import Any


def mod_result_to_dict(analyzer: Any, result: Any) -> dict[str, Any]:
    return {
        "summary": analyzer.get_summary(result),
        "mods": [
            {
                "name": m.name,
                "path": str(m.path),
                "type": m.type.value,
                "size": m.size,
                "author": m.author or "Unknown",
                "version": m.version or "Unknown",
                "conflicts": len([c for c in result.conflicts if m.name in c.affected_mods]),
            }
            for m in result.mods
        ],
        "conflicts": [
            {
                "id": c.id,
                "severity": c.severity.value,
                "type": c.type.value,
                "description": c.description,
                "affected_mods": c.affected_mods,
                "resolution": c.resolution,
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
