from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import load_settings
from packages.data.alpaca_v2_postbuild import (
    POSTBUILD_CONTRACT,
    AlpacaV2NotCompleteError,
    AlpacaV2PostBuildCoordinator,
    AlpacaV2SplitDailyAcquirer,
)
from packages.data.alpaca_v2_rebuild import V2Layout, write_run_state


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description=(
            "Resume-safe Alpaca SIP V2 post-build coordinator: verify every native "
            "unit, validate all native daily rows, materialize conservative identity/"
            "lifecycle evidence, acquire provider-native split-adjusted daily bars, "
            "reconcile raw versus adjusted, and create the isolated research-daily view."
        )
    )
    result.add_argument(
        "--validate-only",
        action="store_true",
        help=(
            "Stop after native/daily/identity validation. No provider request is made and "
            "no analytical research-daily view is created."
        ),
    )
    result.add_argument(
        "--max-hours",
        type=float,
        default=None,
        help="Optional graceful time limit for the split-adjusted daily acquisition stage.",
    )
    result.add_argument(
        "--max-adjusted-units",
        type=int,
        default=None,
        help="Optional deterministic split-adjusted daily unit limit for testing/resume.",
    )
    result.add_argument(
        "--through-reference-replay",
        action="store_true",
        help=(
            "After the V2 source foundation passes, run the already-frozen nine-policy "
            "DEVELOPMENT replay and A34 research account replay in a fresh process. "
            "This opens historical outcomes but grants no strategy, PAPER, or LIVE authority."
        ),
    )
    result.add_argument(
        "--reference-start",
        type=date.fromisoformat,
        default=date(2021, 8, 16),
        help="First XNYS session for the optional frozen V2 reference replay.",
    )
    result.add_argument(
        "--reference-end",
        type=date.fromisoformat,
        default=date(2026, 5, 11),
        help="Last DEVELOPMENT XNYS session for the optional frozen V2 reference replay.",
    )
    return result


def _progress_printer():
    started = time.monotonic()
    pages = 0

    def emit(event: dict[str, object]) -> None:
        nonlocal pages
        kind = str(event.get("event") or "")
        if kind == "native_validation":
            print(
                f"  native hash validation: {int(event['completed']):,}/"
                f"{int(event['total']):,} units",
                flush=True,
            )
        elif kind == "split_unit_start":
            print(
                f"  split daily unit {int(event['completed']) + 1:,}/"
                f"{int(event['total']):,}: {event['unit']}",
                flush=True,
            )
        elif kind == "split_skip":
            print(
                f"  split daily resume verification: {int(event['completed']):,}/"
                f"{int(event['total']):,} units",
                flush=True,
            )
        elif kind == "split_page":
            pages += 1
            page = int(event["page"])
            if page % 25 == 0:
                elapsed = max(time.monotonic() - started, 0.001)
                print(
                    f"  split daily page checkpoint: {event['unit']} page={page:,} "
                    f"rows={int(event['rows']):,} "
                    f"observed_rate={pages * 60.0 / elapsed:,.1f} pages/min",
                    flush=True,
                )

    return emit


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.validate_only and args.through_reference_replay:
        raise ValueError(
            "--validate-only cannot be combined with --through-reference-replay"
        )
    if args.reference_end < args.reference_start:
        raise ValueError("--reference-end precedes --reference-start")
    settings = load_settings(PROJECT_ROOT)
    layout = V2Layout.beneath((PROJECT_ROOT / "data").resolve())
    coordinator = AlpacaV2PostBuildCoordinator(settings)
    progress = _progress_printer()

    print("ATLAS Alpaca SIP V2 post-build")
    print("  input: data/v2_build/alpaca_sip_v2 only")
    print("  V1 rows/state: forbidden")
    print("  authority: source/research preparation only; no PAPER or LIVE writes")
    write_run_state(
        layout,
        stage="V2_POSTBUILD",
        status="STARTING",
        details={
            "validate_only": bool(args.validate_only),
            "max_hours": args.max_hours,
            "max_adjusted_units": args.max_adjusted_units,
            "through_reference_replay": bool(args.through_reference_replay),
        },
    )

    try:
        print("\n1/5 Hash-verifying frozen source, plan, and every completed native unit")
        native = coordinator.validate_native(progress=progress)
        print(
            f"  PASS units={native.report['total_units']:,} "
            f"rows={native.report['canonical_rows']:,} "
            f"excluded_literals={native.report['excluded_symbol_count']:,}"
        )

        print("\n2/5 Validating the complete native daily base")
        daily = coordinator.validate_daily(native)
        print(
            f"  PASS rows={daily.report['daily_rows']:,} "
            f"symbols={daily.report['daily_symbols']:,} "
            f"internal-gap symbols={daily.report['symbols_with_internal_gaps']:,}"
        )

        print("\n3/5 Building conservative identity and lifecycle evidence")
        identity = coordinator.build_identity_lifecycle(native, daily)
        print(
            "  PASS identity-clear common stocks="
            f"{identity.report['identity_clear_common_stock_symbols']:,} "
            f"excluded={identity.report['excluded_symbols']:,}"
        )
    except AlpacaV2NotCompleteError as exc:
        write_run_state(
            layout,
            stage="V2_POSTBUILD",
            status="WAITING_FOR_NATIVE_ACQUISITION",
            details={"message": str(exc)},
        )
        print(f"\nResult: WAITING — {exc}")
        print("Rerun this command after the native acquisition reports COMPLETE.")
        return 2
    except Exception as exc:
        write_run_state(
            layout,
            stage="V2_POSTBUILD",
            status="FAILED_CLOSED",
            details={"error": f"{type(exc).__name__}: {exc}"},
        )
        raise

    if args.validate_only:
        write_run_state(
            layout,
            stage="V2_POSTBUILD",
            status="VALIDATION_ONLY_COMPLETE",
            details={
                "native_acceptance": str(coordinator.native_report_path),
                "daily_quality": str(coordinator.daily_report_path),
                "identity_lifecycle": str(coordinator.identity_report_path),
            },
        )
        print("\nResult: V2 NATIVE/DAILY/IDENTITY VALIDATION COMPLETE")
        print("No provider request, performance read, production promotion, or broker write occurred.")
        return 0

    try:
        print("\n4/5 Acquiring provider-native split-adjusted daily analytical source")
        split = AlpacaV2SplitDailyAcquirer(settings).run(
            native,
            max_units=args.max_adjusted_units,
            max_hours=args.max_hours,
            progress=progress,
        )
        print(
            f"  checkpoint: {split.report['completed_units']:,}/"
            f"{split.report['total_units']:,} units; status={split.report['status']}; "
            f"excluded symbols={split.report['excluded_symbol_count']:,}"
        )
    except Exception as exc:
        write_run_state(
            layout,
            stage="V2_POSTBUILD_SPLIT_DAILY",
            status="FAILED_CLOSED",
            details={"error": f"{type(exc).__name__}: {exc}"},
        )
        raise
    if split.report["status"] != "COMPLETE":
        write_run_state(
            layout,
            stage="V2_POSTBUILD_SPLIT_DAILY",
            status="RESUMABLE",
            details={
                "split_daily_manifest": str(
                    layout.manifests / "split_adjusted_daily.json"
                ),
                "completed_units": split.report["completed_units"],
                "total_units": split.report["total_units"],
            },
        )
        print("\nResult: RESUMABLE SPLIT-DAILY CHECKPOINT SAVED")
        print("Rerun the identical command to continue; completed units are hash-verified.")
        return 0
    try:
        if not split.report.get("clean_candidate"):
            raise RuntimeError(
                "split-adjusted daily acquisition completed with a blocked unit or an "
                "unattributed anomaly; "
                "research materialization was not started"
            )

        print("\n5/5 Reconciling raw/adjusted daily bars and materializing research view")
        research = coordinator.build_research_daily(native, daily, identity, split)
        print(
            f"  PASS rows={research.report['research_rows']:,} "
            f"symbols={research.report['eligible_symbols']:,}"
        )
    except Exception as exc:
        write_run_state(
            layout,
            stage="V2_POSTBUILD_RESEARCH_DAILY",
            status="FAILED_CLOSED",
            details={"error": f"{type(exc).__name__}: {exc}"},
        )
        raise

    summary = {
        "contract": POSTBUILD_CONTRACT,
        "status": "DAILY_RESEARCH_READY_MINUTE_PENDING_INTRADAY_ACCEPTANCE",
        "native_acceptance": str(coordinator.native_report_path),
        "daily_quality": str(coordinator.daily_report_path),
        "identity_lifecycle": str(coordinator.identity_report_path),
        "split_adjusted_daily": str(layout.manifests / "split_adjusted_daily.json"),
        "research_daily": str(layout.manifests / "research_daily.json"),
        "native_acceptance_fingerprint": native.report["acceptance_fingerprint"],
        "research_daily_fingerprint": research.report["source_fingerprint"],
        "source_cutoff_session": research.report["source_cutoff_session"],
        "development_cutoff_session": research.report["cutoff_session"],
        "protected_return_rows_materialized": 0,
        "identity_clear_common_stock_symbols": identity.report[
            "identity_clear_common_stock_symbols"
        ],
        "split_source_excluded_symbols": split.report["excluded_symbols"],
        "return_economics": research.report["return_economics"],
        "cash_dividend_credits_materialized": False,
        "minute_native_capture_verified": True,
        "minute_intraday_strategy_acceptance": False,
        "historical_performance_opened": False,
        "protected_return_rows_read": 0,
        "production_promoted": False,
        "paper_authority": False,
        "live_authority": False,
        "v1_rows_read": 0,
        "v1_ancestry": "FORBIDDEN",
    }
    summary_path = layout.manifests / "postbuild.json"
    atomic_write_text(
        summary_path,
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        fsync=True,
    )
    write_run_state(
        layout,
        stage="V2_POSTBUILD",
        status=summary["status"],
        details={"postbuild_manifest": str(summary_path)},
    )
    print(f"  post-build manifest: {summary_path}")
    if args.through_reference_replay:
        print("\n6/6 Running frozen nine-policy and A34 account DEVELOPMENT replay")
        command = [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "run_a33_b33_reference_development.py"),
            "--data-source",
            "v2",
            "--start",
            args.reference_start.isoformat(),
            "--end",
            args.reference_end.isoformat(),
        ]
        completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
        if completed.returncode != 0:
            summary["status"] = "DAILY_RESEARCH_READY_REFERENCE_REPLAY_FAILED"
            summary["reference_replay_exit_code"] = completed.returncode
            atomic_write_text(
                summary_path,
                json.dumps(summary, indent=2, sort_keys=True) + "\n",
                fsync=True,
            )
            write_run_state(
                layout,
                stage="V2_REFERENCE_REPLAY",
                status=summary["status"],
                details={
                    "postbuild_manifest": str(summary_path),
                    "exit_code": completed.returncode,
                },
            )
            print(
                "\nResult: V2 DAILY FOUNDATION READY; REFERENCE REPLAY FAILED CLOSED"
            )
            return completed.returncode
        summary.update(
            {
                "status": "DAILY_RESEARCH_AND_REFERENCE_REPLAY_COMPLETE",
                "historical_performance_opened": True,
                "reference_replay_scope": {
                    "start": args.reference_start.isoformat(),
                    "end": args.reference_end.isoformat(),
                    "data_source": "v2",
                },
                "strategy_authority_promoted": False,
                "paper_authority": False,
                "live_authority": False,
            }
        )
        atomic_write_text(
            summary_path,
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            fsync=True,
        )
        write_run_state(
            layout,
            stage="V2_REFERENCE_REPLAY",
            status=summary["status"],
            details={"postbuild_manifest": str(summary_path)},
        )
        print("\nResult: V2 DAILY FOUNDATION AND FROZEN REFERENCE REPLAY COMPLETE")
    else:
        print("\nResult: V2 DAILY RESEARCH FOUNDATION READY")
    print("Minute data remains preserved but is not yet intraday-strategy accepted.")
    if args.through_reference_replay:
        print(
            "Historical DEVELOPMENT outcomes were opened under frozen policies; "
            "protected return, PAPER order, LIVE order, and broker writes remain zero."
        )
    else:
        print(
            "No strategy performance, protected return, PAPER order, LIVE order, "
            "or broker write occurred."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
