"""FastAPI web server for Simanalysis."""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from simanalysis import __version__
from simanalysis.analyzers.mod_analyzer import ModAnalyzer
from simanalysis.analyzers.tray_analyzer import TrayAnalyzer
from simanalysis.analyzers.save_analyzer import SaveAnalyzer
from simanalysis.models import AnalysisResult, ModConflict, Severity

app = FastAPI(
    title="Simanalysis API",
    version=__version__,
    description="Backend API for Simanalysis Web GUI",
)

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
    conflicts: List[dict]
    performance: dict
    recommendations: List[str]


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": __version__}


@app.websocket("/api/ws/scan")
async def websocket_scan(websocket: WebSocket):
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
        
        def progress_callback(current: int, total: int, filename: str):
            nonlocal last_update
            now = time.time()
            
            # Throttle updates to max 20 per second (every 50ms)
            # Always send the first and last update
            if current == 1 or current == total or (now - last_update) > 0.05:
                last_update = now
                # Schedule async send on the event loop
                asyncio.run_coroutine_threadsafe(
                    websocket.send_json({
                        "status": "scanning",
                        "current": current,
                        "total": total,
                        "file": filename
                    }),
                    loop
                )

        # Run analysis in thread pool to avoid blocking event loop
        result = await loop.run_in_executor(
            None,
            lambda: analyzer.analyze_directory(
                path, 
                recursive=recursive,
                progress_callback=progress_callback
            )
        )
        
        # Transform result
        response_data = {
            "summary": analyzer.get_summary(result),
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
        
        await websocket.send_json({
            "status": "complete",
            "result": response_data
        })
        
    except Exception as e:
        await websocket.send_json({"status": "error", "message": str(e)})
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@app.websocket("/api/ws/scan/tray")
async def websocket_scan_tray(websocket: WebSocket):
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
        
        def progress_callback(current: int, total: int, filename: str):
            nonlocal last_update
            now = time.time()
            
            # Throttle updates to max 20 per second (every 50ms)
            if current == 1 or current == total or (now - last_update) > 0.05:
                last_update = now
                asyncio.run_coroutine_threadsafe(
                    websocket.send_json({
                        "status": "scanning",
                        "current": current,
                        "total": total,
                        "file": filename
                    }),
                    loop
                )
        
        # Run analysis in thread pool
        result = await loop.run_in_executor(
            None,
            lambda: analyzer.analyze_directory(path, progress_callback=progress_callback)
        )
        
        # Transform result
        response_data = {
            "summary": analyzer.get_summary(result),
            "items": [item.to_dict() for item in result.items],
        }
        
        await websocket.send_json({
            "status": "complete",
            "result": response_data
        })
        
    except Exception as e:
        await websocket.send_json({"status": "error", "message": str(e)})
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@app.websocket("/api/ws/analyze/save")
async def websocket_analyze_save(websocket: WebSocket):
    """WebSocket endpoint for save file analysis."""
    await websocket.accept()
    
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
        
        def progress_callback(stage: str, current: int, total: int):
            asyncio.run_coroutine_threadsafe(
                websocket.send_json({
                    "status": "analyzing",
                    "stage": stage,
                    "current": current,
                    "total": total,
                }),
                loop
            )
        
        # Run analysis in thread pool
        result = await loop.run_in_executor(
            None,
            lambda: analyzer.analyze_save(save_path, mods_path, progress_callback=progress_callback)
        )
        
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
        
        await websocket.send_json({
            "status": "complete",
            "result": response_data
        })
        
    except Exception as e:
        await websocket.send_json({"status": "error", "message": str(e)})
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@app.post("/api/scan", response_model=ScanResponse)
async def scan_directory(request: ScanRequest):
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
        raise HTTPException(status_code=500, detail=str(e))


# Mount static files (must be last)
import sys
import os

def get_web_dist_path():
    """Get the path to the web distribution directory."""
    if getattr(sys, 'frozen', False):
        # Running in a bundle (PyInstaller)
        # We will bundle web/dist into the root of the app or a specific folder
        base_path = sys._MEIPASS
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
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/")
    async def serve_spa():
        return FileResponse(WEB_DIST / "index.html")
        
    @app.get("/{full_path:path}")
    async def catch_all(full_path: str):
        # Return index.html for any other non-api route (for client-side routing)
        if full_path.startswith("api"):
            raise HTTPException(status_code=404)
        return FileResponse(WEB_DIST / "index.html")
else:
    # Fallback for when dist is missing (e.g. dev mode without build)
    @app.get("/")
    async def root():
        return {
            "status": "ok", 
            "version": __version__,
            "message": "Frontend not built. Run 'npm run build' in web/ directory."
        }
