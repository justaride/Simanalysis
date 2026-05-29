"""Dispatch desktop-bridge commands onto the existing analysis core."""
from __future__ import annotations

import argparse
from pathlib import Path

from simanalysis import serialization
from simanalysis.analyzers.mod_analyzer import ModAnalyzer
from simanalysis.analyzers.save_analyzer import SaveAnalyzer
from simanalysis.analyzers.tray_analyzer import TrayAnalyzer
from simanalysis.bridge.protocol import Emitter


def _require_dir(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    if not p.exists() or not p.is_dir():
        raise ValueError(f"Invalid directory path: {path}")
    return p


def scan_mods(args: argparse.Namespace, emit: Emitter) -> None:
    path = _require_dir(args.path)
    emit.start("scan-mods")
    analyzer = ModAnalyzer(calculate_hashes=not args.quick)
    result = analyzer.analyze_directory(
        path,
        recursive=args.recursive,
        progress_callback=lambda c, t, f: emit.progress(c, t, file=f),
    )
    emit.result(serialization.mod_result_to_dict(analyzer, result))
    emit.done()


def scan_tray(args: argparse.Namespace, emit: Emitter) -> None:
    path = _require_dir(args.path)
    emit.start("scan-tray")
    analyzer = TrayAnalyzer()
    result = analyzer.analyze_directory(
        path,
        progress_callback=lambda c, t, f: emit.progress(c, t, file=f),
    )
    emit.result(serialization.tray_result_to_dict(analyzer, result))
    emit.done()


def analyze_save(args: argparse.Namespace, emit: Emitter) -> None:
    save_path = Path(args.save_path).expanduser().resolve()
    if not save_path.exists() or not save_path.is_file():
        raise ValueError("Save file not found")
    mods_path = _require_dir(args.mods_path)
    emit.start("analyze-save")
    analyzer = SaveAnalyzer()
    result = analyzer.analyze_save(
        save_path,
        mods_path,
        progress_callback=lambda stage, c, t: emit.progress(c, t, stage=stage),
    )
    emit.result(serialization.save_result_to_dict(analyzer, result))
    emit.done()


DISPATCH = {
    "scan-mods": scan_mods,
    "scan-tray": scan_tray,
    "analyze-save": analyze_save,
}
