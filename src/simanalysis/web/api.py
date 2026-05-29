"""FastAPI web server for Simanalysis."""

import asyncio
import contextlib
import logging
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# ... existing imports ...
from fastapi import FastAPI, HTTPException, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from simanalysis import __version__
from simanalysis.analyzers.mod_analyzer import ModAnalyzer
from simanalysis.analyzers.save_analyzer import SaveAnalyzer
from simanalysis.analyzers.tray_analyzer import TrayAnalyzer
from simanalysis.services.config_service import ConfigService

# ... existing imports ...
from simanalysis.services.thumbnail_service import ThumbnailService
from simanalysis.services.update_service import UpdateService

# Initialize FastAPI app
app = FastAPI(
    title="Simanalysis",
    version=__version__,
    description="API for Simanalysis Mod Manager",
)

# Initialize services
# Initialize services
thumbnail_service = ThumbnailService()
config_service = ConfigService()
update_service = UpdateService()


@app.get("/api/mods/thumbnail")
async def get_mod_thumbnail(
    path: str = Query(..., description="Absolute path to the mod file"),
) -> Response:
    """Get thumbnail for a specific mod file."""
    try:
        mod_path = Path(path).expanduser().resolve()

        if not mod_path.exists():
            raise HTTPException(status_code=404, detail="Mod file not found")

        thumbnail_data = thumbnail_service.get_thumbnail(mod_path)

        if thumbnail_data:
            return Response(content=thumbnail_data, media_type="image/png")
        else:
            # Return 404 so frontend can show default icon
            raise HTTPException(status_code=404, detail="No thumbnail found")

    except Exception as e:
        # Log error but return 404 to avoid breaking UI
        print(f"Error serving thumbnail for {path}: {e}")
        raise HTTPException(status_code=404, detail=str(e)) from e


# ... existing endpoints ...


@app.get("/api/config")
async def get_config() -> dict[str, object]:
    """Get current configuration."""
    return {"last_scan_path": config_service.last_scan_path}


@app.post("/api/config")
async def update_config(config: dict[str, object]) -> dict[str, str]:
    """Update configuration."""
    if "last_scan_path" in config:
        config_service.last_scan_path = str(config["last_scan_path"])
    return {"status": "ok"}


@app.get("/api/updates")
async def check_updates() -> object:
    """Check for application updates."""
    return await update_service.check_for_updates()


@app.delete("/api/mods/file")
async def delete_mod_file(
    path: str = Query(..., description="Absolute path to the mod file"),
) -> dict[str, object]:
    """Delete a mod file with safety checks and audit logging."""
    try:
        file_path = Path(path).expanduser().resolve()

        # Safety checks
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")

        # Check if it's a mod file
        if file_path.suffix.lower() not in [".package", ".ts4script"]:
            raise HTTPException(status_code=400, detail="Not a valid mod file")

        # Log the deletion
        log_path = Path.home() / ".simanalysis" / "deletion_log.txt"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        with open(log_path, "a") as log_file:
            timestamp = datetime.now(timezone.utc).isoformat()
            log_file.write(f"{timestamp} | DELETED | {file_path}\n")

        # Try to move to trash instead of permanent deletion
        # macOS uses ~/.Trash
        if os.name == "posix" and os.path.exists(os.path.expanduser("~/.Trash")):
            trash_path = Path.home() / ".Trash" / file_path.name
            # Handle name conflicts
            if trash_path.exists():
                trash_path = (
                    Path.home()
                    / ".Trash"
                    / f"{file_path.stem}_{int(datetime.now(timezone.utc).timestamp())}{file_path.suffix}"
                )
            shutil.move(str(file_path), str(trash_path))
            return {
                "status": "ok",
                "message": f"File moved to trash: {trash_path}",
                "moved_to_trash": True,
            }
        else:
            # Fallback to permanent deletion if trash not available
            os.remove(file_path)
            return {"status": "ok", "message": "File deleted permanently", "moved_to_trash": False}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting file {path}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/conflicts/{conflict_id}")
async def get_conflict_details(conflict_id: str) -> dict[str, str]:
    """Get detailed information about a specific conflict."""
    # This endpoint will be used by the DuplicateModal
    # For now, return a placeholder - we'll need to store conflict data
    return {"status": "not_implemented", "message": "Detailed conflict view coming soon"}


# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, this should be restricted
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScanRequest(BaseModel):
    path: str
    recursive: bool = True
    quick: bool = False


class ScanResponse(BaseModel):
    summary: dict
    mods: list[dict]
    conflicts: list[dict]
    performance: dict
    recommendations: list[str]


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": __version__}


@app.websocket("/api/ws/scan")
async def websocket_scan(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time scanning."""
    await websocket.accept()

    try:
        # Receive configuration
        data = await websocket.receive_json()
        path_str = data.get("path")
        recursive = data.get("recursive", True)
        quick = data.get("quick", False)

        path = Path(path_str).expanduser().resolve()

        if not path.exists() or not path.is_dir():
            await websocket.send_json({"status": "error", "message": "Invalid directory path"})
            return

        analyzer = ModAnalyzer(calculate_hashes=not quick)
        loop = asyncio.get_event_loop()

        import time

        last_update = 0.0

        def progress_callback(current: int, total: int, filename: str) -> None:
            nonlocal last_update
            now = time.time()

            # Throttle updates to max 20 per second (every 50ms)
            # Always send the first and last update
            if current == 1 or current == total or (now - last_update) > 0.05:
                last_update = now
                # Schedule async send on the event loop
                asyncio.run_coroutine_threadsafe(
                    websocket.send_json(
                        {"status": "scanning", "current": current, "total": total, "file": filename}
                    ),
                    loop,
                )

        # Run analysis in thread pool to avoid blocking event loop
        result = await loop.run_in_executor(
            None,
            lambda: analyzer.analyze_directory(
                path, recursive=recursive, progress_callback=progress_callback
            ),
        )

        # Transform result
        response_data = {
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

        await websocket.send_json({"status": "complete", "result": response_data})

    except Exception as e:
        await websocket.send_json({"status": "error", "message": str(e)})
    finally:
        with contextlib.suppress(Exception):
            await websocket.close()


@app.websocket("/api/ws/scan/tray")
async def websocket_scan_tray(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time tray scanning."""
    await websocket.accept()

    try:
        # Receive configuration
        data = await websocket.receive_json()
        path_str = data.get("path")

        path = Path(path_str).expanduser().resolve()

        if not path.exists() or not path.is_dir():
            await websocket.send_json({"status": "error", "message": "Invalid directory path"})
            return

        analyzer = TrayAnalyzer()
        loop = asyncio.get_event_loop()

        import time

        last_update = 0.0

        def progress_callback(current: int, total: int, filename: str) -> None:
            nonlocal last_update
            now = time.time()

            # Throttle updates to max 20 per second (every 50ms)
            if current == 1 or current == total or (now - last_update) > 0.05:
                last_update = now
                asyncio.run_coroutine_threadsafe(
                    websocket.send_json(
                        {"status": "scanning", "current": current, "total": total, "file": filename}
                    ),
                    loop,
                )

        # Run analysis in thread pool
        result = await loop.run_in_executor(
            None, lambda: analyzer.analyze_directory(path, progress_callback=progress_callback)
        )

        # Transform result
        response_data = {
            "summary": analyzer.get_summary(result),
            "items": [item.to_dict() for item in result.items],
        }

        await websocket.send_json({"status": "complete", "result": response_data})

    except Exception as e:
        await websocket.send_json({"status": "error", "message": str(e)})
    finally:
        with contextlib.suppress(Exception):
            await websocket.close()


@app.websocket("/api/ws/analyze/save")
async def websocket_analyze_save(websocket: WebSocket) -> None:
    """WebSocket endpoint for save file analysis."""
    await websocket.accept()
    print("WebSocket accepted for save analysis")

    try:
        # Receive configuration
        data = await websocket.receive_json()
        save_path_str = data.get("save_path")
        mods_path_str = data.get("mods_path")

        save_path = Path(save_path_str).expanduser().resolve()
        mods_path = Path(mods_path_str).expanduser().resolve()

        if not save_path.exists():
            await websocket.send_json({"status": "error", "message": "Save file not found"})
            return

        if not mods_path.exists() or not mods_path.is_dir():
            await websocket.send_json({"status": "error", "message": "Invalid Mods directory path"})
            return

        analyzer = SaveAnalyzer()
        loop = asyncio.get_event_loop()

        def progress_callback(stage: str, current: int, total: int) -> None:
            asyncio.run_coroutine_threadsafe(
                websocket.send_json(
                    {
                        "status": "analyzing",
                        "stage": stage,
                        "current": current,
                        "total": total,
                    }
                ),
                loop,
            )

        # Run analysis in thread pool
        print(f"Starting analysis for save: {save_path} with mods: {mods_path}")
        result = await loop.run_in_executor(
            None,
            lambda: analyzer.analyze_save(
                save_path, mods_path, progress_callback=progress_callback
            ),
        )
        print("Analysis complete")

        # Transform result
        response_data = {
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
                for mod in result.unused_mods[:100]  # Limit to first 100 for perf
            ],
        }

        await websocket.send_json({"status": "complete", "result": response_data})

    except Exception as e:
        await websocket.send_json({"status": "error", "message": str(e)})
    finally:
        with contextlib.suppress(Exception):
            await websocket.close()


@app.post("/api/scan", response_model=ScanResponse)
async def scan_directory(request: ScanRequest) -> dict[str, object]:
    """Scan a directory for mods."""
    path = Path(request.path).expanduser().resolve()

    if not path.exists() or not path.is_dir():
        raise HTTPException(status_code=400, detail="Invalid directory path")

    try:
        analyzer = ModAnalyzer(
            calculate_hashes=not request.quick,
        )
        result = analyzer.analyze_directory(path, recursive=request.recursive)

        # Transform result for JSON response
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/system/browse")
async def browse_system(path: str = Query(None, description="Path to browse")) -> dict[str, object]:
    """Browse system files and directories."""
    try:
        current_path = Path.home() if not path else Path(path).expanduser().resolve()

        if not current_path.exists():
            raise HTTPException(status_code=404, detail="Path not found")

        # Handle parent directory
        parent_path = current_path.parent

        items: list[dict[str, object]] = []

        # Add parent directory entry if not at root
        if current_path != current_path.parent:
            items.append(
                {"name": "..", "path": str(parent_path), "type": "directory", "is_parent": True}
            )

        # List directory contents
        if current_path.is_dir():
            try:
                for item in current_path.iterdir():
                    # Skip hidden files/dirs
                    if item.name.startswith("."):
                        continue

                    try:
                        stats = item.stat()
                        items.append(
                            {
                                "name": item.name,
                                "path": str(item),
                                "type": "directory" if item.is_dir() else "file",
                                "size": stats.st_size,
                                "modified": stats.st_mtime,
                            }
                        )
                    except PermissionError:
                        continue
            except PermissionError as exc:
                raise HTTPException(status_code=403, detail="Permission denied") from exc

        # Sort: Directories first, then files, alphabetically
        items.sort(key=lambda x: (x["type"] != "directory", str(x["name"]).lower()))

        return {"current_path": str(current_path), "items": items}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# Mount static files (must be last)


def get_web_dist_path() -> Path:
    """Get the path to the web distribution directory."""
    if getattr(sys, "frozen", False):
        # Running in a bundle (PyInstaller)
        # sys._MEIPASS is set by PyInstaller but not in the stdlib type stubs.
        base_path: str = sys._MEIPASS  # type: ignore[attr-defined]  # PyInstaller runtime attr
        # Check potential locations
        possible_paths = [
            Path(base_path) / "web" / "dist",
            Path(base_path) / "dist",
        ]
        for path in possible_paths:
            if path.exists():
                return path
        return Path(base_path) / "web" / "dist"
    else:
        # Running in normal Python environment
        # src/simanalysis/web/api.py -> ../../../web/dist
        return Path(__file__).parent.parent.parent.parent / "web" / "dist"


WEB_DIST = get_web_dist_path()

if WEB_DIST.exists():
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/")
    async def serve_spa() -> "FileResponse":
        return FileResponse(WEB_DIST / "index.html")

    @app.get("/{full_path:path}")
    async def catch_all(full_path: str) -> "FileResponse":
        # Return index.html for any other non-api route (for client-side routing)
        if full_path.startswith("api"):
            raise HTTPException(status_code=404)
        return FileResponse(WEB_DIST / "index.html")
else:
    # Fallback for when dist is missing (e.g. dev mode without build)
    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "status": "ok",
            "version": __version__,
            "message": "Frontend not built. Run 'npm run build' in web/ directory.",
        }
