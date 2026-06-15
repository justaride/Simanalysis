"""`simanalysis-bridge` — headless NDJSON stdio entry point for the Tauri desktop app."""

from __future__ import annotations

import argparse
import sys
import traceback

from simanalysis.bridge import commands
from simanalysis.bridge.protocol import setup


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="simanalysis-bridge")
    sub = parser.add_subparsers(dest="command", required=True)

    p_mods = sub.add_parser("scan-mods")
    p_mods.add_argument("path")
    p_mods.add_argument("--quick", action="store_true")
    p_mods.add_argument("--no-recursive", dest="recursive", action="store_false")
    p_mods.set_defaults(recursive=True)

    p_tray = sub.add_parser("scan-tray")
    p_tray.add_argument("path")

    p_save = sub.add_parser("analyze-save")
    p_save.add_argument("save_path")
    p_save.add_argument("mods_path")

    p_inventory = sub.add_parser("inventory-scan")
    p_inventory.add_argument("path")
    p_inventory.add_argument("--db", default=None)
    p_inventory.add_argument("--export", action="store_true")

    p_inventory_history = sub.add_parser("inventory-history")
    p_inventory_history.add_argument("path")
    p_inventory_history.add_argument("--db", default=None)
    p_inventory_history.add_argument("--limit", type=int, default=20)

    p_inventory_file_events = sub.add_parser("inventory-file-events")
    p_inventory_file_events.add_argument("path")
    p_inventory_file_events.add_argument("--db", default=None)
    p_inventory_file_events.add_argument("--include-unchanged", action="store_true")

    p_cleanup_plan = sub.add_parser("cleanup-plan")
    p_cleanup_plan.add_argument("path")
    p_cleanup_plan.add_argument("--db", default=None)
    p_cleanup_plan.add_argument("--export", default=None)

    p_cleanup_stage = sub.add_parser("cleanup-stage")
    p_cleanup_stage.add_argument("path")
    p_cleanup_stage.add_argument("--plan", required=True)
    p_cleanup_stage.add_argument("--action", action="append", default=[])
    p_cleanup_stage.add_argument("--all-actions", action="store_true")

    p_cleanup_apply = sub.add_parser("cleanup-apply")
    p_cleanup_apply.add_argument("manifest_path")

    p_cleanup_restore = sub.add_parser("cleanup-restore")
    p_cleanup_restore.add_argument("manifest_path")

    p_cleanup_status = sub.add_parser("cleanup-status")
    p_cleanup_status.add_argument("manifest_path")

    p_thumb = sub.add_parser("thumbnail")
    p_thumb.add_argument("path")

    p_doctor = sub.add_parser("doctor-scan")
    p_doctor.add_argument("path")
    p_doctor.add_argument("--mods", default=None)
    p_doctor.add_argument("--recursive", action="store_true")
    p_doctor.add_argument("--inventory-db", default=None)

    p_treatment_plan = sub.add_parser("treatment-plan")
    p_treatment_plan.add_argument("path")
    p_treatment_plan.add_argument("--mods", default=None)
    p_treatment_plan.add_argument("--doctor-json", default=None)
    p_treatment_plan.add_argument("--save", action="store_true")

    p_treatment_apply = sub.add_parser("treatment-apply")
    p_treatment_apply.add_argument("manifest_path")

    p_treatment_outcome = sub.add_parser("treatment-outcome")
    p_treatment_outcome.add_argument("manifest_path")
    p_treatment_outcome.add_argument(
        "--outcome",
        required=True,
        choices=("same_issue", "issue_gone", "different_issue"),
    )

    p_treatment_restore = sub.add_parser("treatment-restore")
    p_treatment_restore.add_argument("manifest_path")
    p_treatment_restore.add_argument("--step", default="latest", choices=("latest", "all"))

    p_treatment_status = sub.add_parser("treatment-status")
    p_treatment_status.add_argument("manifest_path")

    p_treatment_handoff = sub.add_parser("treatment-handoff")
    p_treatment_handoff.add_argument("manifest_path")

    p_live_monitor = sub.add_parser("live-monitor")
    p_live_monitor.add_argument("path")
    p_live_monitor.add_argument("--mods", default=None)
    p_live_monitor.add_argument("--interval", type=float, default=2.0)
    p_live_monitor.add_argument("--once", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    emit = setup()
    try:
        commands.DISPATCH[args.command](args, emit)
        return 0
    except ValueError as exc:
        emit.error(str(exc), code="INVALID_INPUT")
        return 2
    except BrokenPipeError:
        return 0
    except Exception as exc:
        traceback.print_exc()
        emit.error(f"{type(exc).__name__}: {exc}", code="INTERNAL")
        return 1


if __name__ == "__main__":
    sys.exit(main())
