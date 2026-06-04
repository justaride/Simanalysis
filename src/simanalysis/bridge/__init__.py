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

    p_thumb = sub.add_parser("thumbnail")
    p_thumb.add_argument("path")

    p_world_scan = sub.add_parser("world-scan")
    p_world_scan.add_argument("path")

    p_world_status = sub.add_parser("world-status")
    p_world_status.add_argument("path")

    p_fix_plan = sub.add_parser("fix-plan")
    p_fix_plan.add_argument("path")

    p_fix_status = sub.add_parser("fix-status")
    p_fix_status.add_argument("path")

    p_fix_apply = sub.add_parser("fix-apply")
    p_fix_apply.add_argument("path")
    p_fix_apply.add_argument("--kind", required=True, choices=("cache_cleanup",))

    p_fix_restore = sub.add_parser("fix-restore")
    p_fix_restore.add_argument("manifest_path")

    p_fix_session_status = sub.add_parser("fix-session-status")
    p_fix_session_status.add_argument("manifest_path")

    p_master_plan = sub.add_parser("master-plan")
    p_master_plan.add_argument("path")

    p_master_status = sub.add_parser("master-status")
    p_master_status.add_argument("path")

    p_master_baseline_save = sub.add_parser("master-baseline-save")
    p_master_baseline_save.add_argument("path")
    p_master_baseline_save.add_argument("--label", default=None)

    p_master_baseline_diff = sub.add_parser("master-baseline-diff")
    p_master_baseline_diff.add_argument("path")
    p_master_baseline_diff.add_argument("--baseline", default=None)

    p_master_baseline_status = sub.add_parser("master-baseline-status")
    p_master_baseline_status.add_argument("path")

    p_doctor = sub.add_parser("doctor-scan")
    p_doctor.add_argument("path")
    p_doctor.add_argument("--mods", default=None)
    p_doctor.add_argument("--recursive", action="store_true")

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
