from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.alpaca_v2_acquisition import (
    V2_DEFAULT_START,
    AlpacaV2NativeAcquirer,
    V2DiskFloorError,
)
from packages.data.alpaca_v2_rebuild import (
    V2Layout,
    build_decommission_plan,
    disk_guard,
    execute_decommission_with_journal,
    write_decommission_plan,
    write_run_state,
)

NATIVE_BASE_ESTIMATE_BYTES = int(127.8 * 1024**3)
REBUILD_ACQUISITION_READY = True


def _human_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024.0 or unit == "TiB":
            return f"{size:,.2f} {unit}"
        size /= 1024.0
    return f"{value:,} B"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Resumable top-level Alpaca SIP V2 rebuild coordinator."
    )
    result.add_argument(
        "--build-v2",
        action="store_true",
        help=(
            "Delete any remaining exact V1 database-derived targets after confirmation, "
            "then acquire fresh Alpaca SIP native 1Day followed by 1Min history."
        ),
    )
    result.add_argument(
        "--execute-v1-decommission",
        action="store_true",
        help="Backward-compatible alias for --build-v2.",
    )
    result.add_argument(
        "--decommission-v1-only",
        action="store_true",
        help=(
            "Delete only the exact inventoried V1 database-derived namespaces, "
            "then stop. This does not build V2."
        ),
    )
    result.add_argument("--confirmation-token", default=None)
    result.add_argument(
        "--required-base-bytes",
        type=int,
        default=NATIVE_BASE_ESTIMATE_BYTES,
        help="Preflight capacity required for source + native 1d/1m base.",
    )
    result.add_argument(
        "--start-date",
        type=date.fromisoformat,
        default=V2_DEFAULT_START,
        help="First provider date in the frozen V2 generation (default: 2016-01-04).",
    )
    result.add_argument(
        "--timeframes",
        choices=("all", "daily", "minute"),
        default="all",
        help="Run daily then minute (all), daily only, or minute only.",
    )
    result.add_argument(
        "--max-hours",
        type=float,
        default=None,
        help="Optional graceful time limit; checkpoints after each completed page.",
    )
    result.add_argument(
        "--max-units",
        type=int,
        default=None,
        help="Optional deterministic unit limit for a smoke run.",
    )
    return result


def _decommission_paths(data_root: Path, plan_sha256: str) -> tuple[Path, Path]:
    migration = data_root / "checkpoints" / "alpaca_v2_migration"
    suffix = plan_sha256[:16]
    return (
        migration / f"v1_decommission_plan_{suffix}.json",
        migration / f"v1_decommission_receipt_{suffix}.json",
    )


def _progress_printer() -> Callable[[dict[str, object]], None]:
    started = time.monotonic()
    pages = 0

    def emit(event: dict[str, object]) -> None:
        nonlocal pages
        kind = event.get("event")
        elapsed = max(time.monotonic() - started, 0.001)
        if kind == "page":
            pages += 1
            page_number = int(event.get("page", 0))
            if bool(event.get("next_page")) and page_number % 25 != 0:
                return
            rpm = pages * 60.0 / elapsed
            print(
                f"  page checkpoint: {event.get('unit')} page={page_number:,} "
                f"rows={int(event.get('accepted_rows', 0)):,} "
                f"quarantine={int(event.get('quarantined_rows', 0)):,} "
                f"observed_rate={rpm:,.1f} pages/min",
                flush=True,
            )
        elif kind == "unit_start":
            print(
                f"  unit {int(event.get('unit_index', 0)):,}/"
                f"{int(event.get('selected_units', 0)):,}: {event.get('unit')}",
                flush=True,
            )
        elif kind == "unit":
            print(
                f"  completed: {event.get('unit')} status={event.get('status')} "
                f"pages={int(event.get('pages', 0)):,} "
                f"canonical_rows={int(event.get('canonical_rows', 0)):,} "
                f"quarantine={int(event.get('quarantined_rows', 0)):,}",
                flush=True,
            )
        elif kind == "provider_rejection":
            print(
                "  provider-rejected literal quarantined without substitution: "
                f"{event.get('symbol')}",
                flush=True,
            )
        elif kind == "skip":
            skipped_index = int(event.get("unit_index", 0))
            if skipped_index % 250 == 0:
                print(
                    f"  resume verification: {skipped_index:,}/"
                    f"{int(event.get('selected_units', 0)):,} units scanned",
                    flush=True,
                )

    return emit


def _timeframes(value: str) -> tuple[str, ...]:
    if value == "daily":
        return ("1d",)
    if value == "minute":
        return ("1m",)
    return ("1d", "1m")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    build_requested = bool(args.build_v2 or args.execute_v1_decommission)
    selected_modes = sum(
        int(value)
        for value in (args.build_v2, args.execute_v1_decommission, args.decommission_v1_only)
    )
    if selected_modes > 1:
        raise ValueError("choose only one rebuild/decommission mode")

    data_root = (PROJECT_ROOT / "data").resolve()
    data_root.mkdir(parents=True, exist_ok=True)
    layout = V2Layout.beneath(data_root)
    plan = build_decommission_plan(data_root)
    plan_path, receipt_path = _decommission_paths(data_root, plan.plan_sha256)
    write_decommission_plan(plan, plan_path)

    projected_free = disk_guard(data_root, required_bytes=args.required_base_bytes)
    projected_free["reclaimable_v1_bytes"] = plan.total_bytes
    projected_free["projected_free_after_decommission_bytes"] = (
        projected_free["free_bytes"] + plan.total_bytes
    )
    projected_free["accepted_after_decommission"] = (
        projected_free["projected_free_after_decommission_bytes"]
        >= projected_free["required_bytes"] + projected_free["reserve_bytes"]
    )

    print("ATLAS Alpaca SIP V2 rebuild preflight")
    print(f"  decommission plan: {plan_path}")
    print(f"  remaining database-derived targets: {len(plan.entries)}")
    print(f"  remaining database-derived files: {plan.total_files:,}")
    print(f"  reclaimable bytes: {plan.total_bytes:,}")
    print(f"  confirmation token: {plan.confirmation_token}")
    print(f"  base storage accepted after decommission: {projected_free['accepted_after_decommission']}")
    print("  exact historical targets:")
    if not plan.entries:
        print("    <none>")
    for entry in plan.entries:
        print(
            f"    {entry.relative_path} "
            f"({entry.kind}; {entry.files:,} files; {_human_bytes(entry.bytes)})"
        )

    if not build_requested and not args.decommission_v1_only:
        print("Result: PREFLIGHT_ONLY — no files deleted and no provider requests made")
        return 0
    if build_requested and not projected_free["accepted_after_decommission"]:
        raise RuntimeError("native base disk preflight failed; no files were deleted")

    removed = 0
    if plan.entries:
        supplied_token = args.confirmation_token
        if supplied_token is None:
            print()
            print("This permanently deletes only the exact database-derived targets listed above.")
            print(
                "It preserves Git/source, data/live, models, accepted strategy/source evidence, "
                "and the original V1 deletion receipt."
            )
            supplied_token = input(f"Type {plan.confirmation_token} to continue: ").strip()
        removed = execute_decommission_with_journal(
            plan,
            confirmation_token=supplied_token,
            journal_path=receipt_path,
            progress=lambda target: print(f"  removed: {target}", flush=True),
        )
        print(f"  removed remaining database-derived targets: {removed}")
        print(f"  retained independent deletion receipt: {receipt_path}")

    if args.decommission_v1_only:
        print("Result: REMAINING V1 DATABASE-DERIVED TARGETS DECOMMISSIONED / V2 NOT STARTED")
        return 0
    if not REBUILD_ACQUISITION_READY:
        raise RuntimeError("V2 acquisition is code-locked")

    layout.create()
    write_run_state(
        layout,
        stage="V2_NATIVE_ACQUISITION",
        status="STARTING",
        details={
            "removed_targets_this_run": removed,
            "decommission_plan_sha256": plan.plan_sha256,
            "decommission_receipt": str(receipt_path) if removed else None,
            "disk_preflight": projected_free,
            "start_date": args.start_date.isoformat(),
            "timeframes": args.timeframes,
        },
    )
    print()
    print("Starting fresh-source V2 acquisition")
    print("  order: assets -> corporate actions -> frozen plan -> native 1Day -> native 1Min")
    print("  source: Alpaca SIP / raw adjustment / no V1 ancestry")
    print("  restart boundary: every provider page; completed units are hash-verified")
    print("  disk floor: 30 GiB reserve plus transient working space")
    print(
        "  timing: full native minute history is expected to exceed one night; rerun the same "
        "command to resume"
    )

    settings = load_settings(PROJECT_ROOT)
    acquirer = AlpacaV2NativeAcquirer(settings, start_date=args.start_date)
    try:
        report = acquirer.run(
            max_units=args.max_units,
            max_hours=args.max_hours,
            timeframes=_timeframes(args.timeframes),
            progress=_progress_printer(),
        )
    except KeyboardInterrupt:
        write_run_state(
            layout,
            stage="V2_NATIVE_ACQUISITION",
            status="INTERRUPTED_RESUMABLE",
            details={"message": "Operator interruption; rerun the same command."},
        )
        print("\nResult: INTERRUPTED SAFELY — rerun the same command to resume", flush=True)
        return 130
    except V2DiskFloorError as exc:
        write_run_state(
            layout,
            stage="V2_NATIVE_ACQUISITION",
            status="PAUSED_DISK_FLOOR",
            details={"message": str(exc)},
        )
        print(f"Result: PAUSED SAFELY — {exc}", flush=True)
        return 3
    except Exception as exc:
        write_run_state(
            layout,
            stage="V2_NATIVE_ACQUISITION",
            status="FAILED_RESUMABLE",
            details={"error": f"{type(exc).__name__}: {exc}"},
        )
        raise

    write_run_state(
        layout,
        stage="V2_NATIVE_ACQUISITION",
        status=str(report["status"]),
        details={
            "report_path": str(acquirer.report_path),
            "completed_units": report["completed_units"],
            "total_units": report["total_units"],
            "canonical_rows": report["canonical_rows"],
            "native_base_complete": report["native_base_complete"],
            "production_promoted": False,
        },
    )
    print()
    print("ATLAS Alpaca SIP V2 acquisition checkpoint")
    print(f"  report: {acquirer.report_path}")
    print(f"  status: {report['status']}")
    print(f"  units: {report['completed_units']:,}/{report['total_units']:,}")
    print(f"  daily: {report['daily_completed']:,}/{report['daily_units']:,}")
    print(f"  minute: {report['minute_completed']:,}/{report['minute_units']:,}")
    print(f"  canonical rows: {report['canonical_rows']:,}")
    print(f"  quarantined rows: {report['quarantined_rows']:,}")
    print("  authority: isolated V2 build only; not production, PAPER, or LIVE approved")
    if report["native_base_complete"]:
        print("Result: NATIVE V2 BASE ACQUISITION COMPLETE / IDENTITY AND ACCEPTANCE STILL PENDING")
    else:
        print("Result: RESUMABLE V2 CHECKPOINT SAVED — rerun the same command to continue")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
