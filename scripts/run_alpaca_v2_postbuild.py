from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import load_settings
from packages.data.alpaca_v2_postbuild import (
    MASTER_HOLDOUT_AUTHORIZATION_CONTRACT,
    MASTER_HOLDOUT_CONSUMPTION_CONTRACT,
    POSTBUILD_CONTRACT,
    V2_REFERENCE_DEVELOPMENT_END,
    V2_REFERENCE_MASTER_PROTECTED_END,
    V2_REFERENCE_MASTER_PROTECTED_START,
    AlpacaV2NotCompleteError,
    AlpacaV2PostBuildCoordinator,
    AlpacaV2SplitDailyAcquirer,
    master_holdout_authorization_id,
)
from packages.data.alpaca_v2_rebuild import V2Layout, write_run_state
from packages.data.holdout_receipts import (
    begin_holdout_consumption,
    read_holdout_receipt,
    write_holdout_receipt,
)
from packages.features.reference_daily import REFERENCE_DAILY_FEATURE_FINGERPRINT
from packages.backtesting.reference_portfolio_policy import (
    reference_portfolio_policy_fingerprint,
)
from packages.strategies.reference_library import (
    REFERENCE_STRATEGY_POLICY_FINGERPRINT,
)


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
        "--through-walk-forward-replay",
        action="store_true",
        help=(
            "After the DEVELOPMENT replay, materialize and run the separately "
            "authorized one-time walk-forward from 2026-05-12 through the latest "
            "validated session. This permanently consumes the master holdout."
        ),
    )
    result.add_argument(
        "--authorize-master-holdout-consumption",
        action="store_true",
        help=(
            "Required with --through-walk-forward-replay. Records explicit, immutable "
            "authorization before protected strategy outcomes are opened."
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
    result.add_argument(
        "--walk-forward-end",
        type=date.fromisoformat,
        default=None,
        help=(
            "Optional assertion for the last walk-forward session. When supplied it "
            "must equal the V2 source cutoff; otherwise the cutoff is selected exactly."
        ),
    )
    return result


def _holdout_authorization(
    layout: V2Layout,
    *,
    native_fingerprint: str,
    split_fingerprint: str,
    source_cutoff: str,
    development_start: date,
    development_end: date,
) -> dict[str, object]:
    path = layout.manifests / "master_holdout_authorization.json"
    binding = {
        "contract": MASTER_HOLDOUT_AUTHORIZATION_CONTRACT,
        "status": "AUTHORIZED_PENDING_HOLDOUT_READ",
        "purpose": "A33_B33_FROZEN_REFERENCE_WALK_FORWARD",
        "authorization_mechanism": "EXPLICIT_OPERATOR_CLI_FLAG",
        "master_protected_start": V2_REFERENCE_MASTER_PROTECTED_START.isoformat(),
        "master_protected_end": V2_REFERENCE_MASTER_PROTECTED_END.isoformat(),
        "source_cutoff_session": source_cutoff,
        "development_start": development_start.isoformat(),
        "development_end": development_end.isoformat(),
        "native_acceptance_fingerprint": native_fingerprint,
        "split_daily_fingerprint": split_fingerprint,
        "strategy_policy_fingerprint": REFERENCE_STRATEGY_POLICY_FINGERPRINT,
        "feature_fingerprint": REFERENCE_DAILY_FEATURE_FINGERPRINT,
        "portfolio_policy_fingerprint": reference_portfolio_policy_fingerprint(),
        "parameter_changes_during_forward_window_permitted": False,
        "historical_reclassification_as_paper_permitted": False,
        "strategy_authority_promoted": False,
        "paper_authority": False,
        "live_authority": False,
    }
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(existing, dict):
            raise RuntimeError("master holdout authorization must be a JSON object")
        if any(existing.get(key) != value for key, value in binding.items()):
            raise RuntimeError(
                "existing master holdout authorization binds a different source or policy"
            )
        if existing.get("authorization_id") != master_holdout_authorization_id(existing):
            raise RuntimeError("master holdout authorization self-hash mismatch")
        return existing
    authorization = {
        **binding,
        "authorized_at_utc": datetime.now(UTC).isoformat(),
    }
    authorization["authorization_id"] = master_holdout_authorization_id(authorization)
    atomic_write_text(
        path,
        json.dumps(authorization, indent=2, sort_keys=True) + "\n",
        fsync=True,
    )
    return authorization


def _begin_holdout_consumption(
    layout: V2Layout,
    *,
    authorization_id: str,
    walk_forward_end: date,
) -> tuple[Path, dict[str, object]]:
    """Persist irreversible consumption evidence before protected rows are touched."""

    path = layout.manifests / "master_holdout_consumption.json"
    receipt = begin_holdout_consumption(
        path,
        authorization_id=authorization_id,
        walk_forward_end=walk_forward_end,
        walk_forward_manifest=layout.manifests / "walk_forward_daily.json",
    )
    return path, receipt


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


def _completed_walk_forward_reusable(settings, authorization_id: str) -> bool:
    """Completed evidence may be reused only after the normal operator verifier passes."""
    layout = V2Layout.beneath((settings.project_root / "data").resolve())
    path = layout.manifests / "master_holdout_consumption.json"
    if not path.exists():
        return False
    receipt = read_holdout_receipt(path)
    if receipt["authorization_id"] != authorization_id:
        raise RuntimeError("existing holdout receipt binds a different authorization")
    if receipt["status"] != "CONSUMED_WALK_FORWARD_COMPLETE":
        return False
    from packages.performance.reference_replay_read_model import reference_replay_read_model

    view = reference_replay_read_model(settings)
    if (
        view["status"] != "AVAILABLE"
        or view.get("evaluation_stage") != "walk-forward"
        or (view.get("summary") or {}).get("master_holdout_authorization_id") != authorization_id
    ):
        raise RuntimeError("completed walk-forward evidence failed verification; preserve it for review")
    return True


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.validate_only and (
        args.through_reference_replay or args.through_walk_forward_replay
    ):
        raise ValueError(
            "--validate-only cannot be combined with a reference replay"
        )
    if args.through_walk_forward_replay and not (
        args.authorize_master_holdout_consumption
    ):
        raise ValueError(
            "--through-walk-forward-replay requires "
            "--authorize-master-holdout-consumption"
        )
    if args.authorize_master_holdout_consumption and not (
        args.through_walk_forward_replay
    ):
        raise ValueError(
            "--authorize-master-holdout-consumption is valid only with "
            "--through-walk-forward-replay"
        )
    if args.reference_end < args.reference_start:
        raise ValueError("--reference-end precedes --reference-start")
    if args.reference_end > V2_REFERENCE_DEVELOPMENT_END:
        raise ValueError("--reference-end cannot cross the DEVELOPMENT boundary")
    if (
        args.through_walk_forward_replay
        and args.reference_end != V2_REFERENCE_DEVELOPMENT_END
    ):
        raise ValueError(
            "walk-forward staging requires DEVELOPMENT through exactly 2026-05-11"
        )
    settings = load_settings(PROJECT_ROOT)
    layout = V2Layout.beneath((PROJECT_ROOT / "data").resolve())
    receipt_path = layout.manifests / "master_holdout_consumption.json"
    prior_receipt = None
    if receipt_path.exists() or any(
        receipt_path.with_name("master_holdout_consumption_history").glob("*.json")
    ):
        prior_receipt = read_holdout_receipt(receipt_path)
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
            "through_walk_forward_replay": bool(args.through_walk_forward_replay),
            "master_holdout_consumption_authorized": bool(
                args.authorize_master_holdout_consumption
            ),
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
    if prior_receipt is not None:
        # A new source-validation invocation cannot erase earlier holdout access.
        summary.update({
            "master_holdout_consumed": True,
            "master_holdout_consumption_receipt": str(receipt_path),
            "prior_holdout_status": prior_receipt["status"],
            "protected_return_rows_read": prior_receipt["protected_return_rows_read"],
            "protected_return_rows_materialized": prior_receipt["protected_return_rows_read"],
            "protected_rows_accounting_pending": prior_receipt["protected_rows_accounting_pending"],
            "historical_performance_opened": None,
            "current_invocation_performance_opened": False,
        })
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
    authorization: dict[str, object] | None = None
    walk_forward_end: date | None = None
    if args.through_walk_forward_replay:
        walk_forward_end = date.fromisoformat(
            str(research.report["source_cutoff_session"])
        )
        if walk_forward_end < V2_REFERENCE_MASTER_PROTECTED_END:
            raise ValueError(
                "accepted V2 source does not contain the complete master holdout"
            )
        if (
            args.walk_forward_end is not None
            and args.walk_forward_end != walk_forward_end
        ):
            raise ValueError(
                "--walk-forward-end does not equal the accepted V2 source cutoff "
                f"{walk_forward_end}"
            )
        authorization = _holdout_authorization(
            layout,
            native_fingerprint=str(native.report["acceptance_fingerprint"]),
            split_fingerprint=str(split.report["source_fingerprint"]),
            source_cutoff=str(research.report["source_cutoff_session"]),
            development_start=args.reference_start,
            development_end=args.reference_end,
        )
        summary["master_holdout_authorization"] = str(
            layout.manifests / "master_holdout_authorization.json"
        )
        summary["master_holdout_authorization_id"] = authorization[
            "authorization_id"
        ]
        atomic_write_text(
            summary_path,
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            fsync=True,
        )
        print(
            "  immutable pre-read holdout authorization: "
            f"{layout.manifests / 'master_holdout_authorization.json'}"
        )
        if _completed_walk_forward_reusable(settings, str(authorization["authorization_id"])):
            summary.update({
                "status": "DEVELOPMENT_AND_WALK_FORWARD_COMPLETE",
                "completed_walk_forward_reused": True,
                "historical_performance_opened": True,
                "current_invocation_performance_opened": False,
                "walk_forward_daily": str(layout.manifests / "walk_forward_daily.json"),
            })
            atomic_write_text(summary_path, json.dumps(summary, indent=2, sort_keys=True) + "\n", fsync=True)
            write_run_state(layout, stage="V2_WALK_FORWARD_REPLAY", status=summary["status"],
                            details={"postbuild_manifest": str(summary_path), "reused": True})
            print("\nResult: completed frozen walk-forward artifacts verified and reused; no replay repeated")
            return 0

    run_development = (
        args.through_reference_replay or args.through_walk_forward_replay
    )
    if run_development:
        total_steps = 7 if args.through_walk_forward_replay else 6
        print(
            f"\n6/{total_steps} Running frozen nine-policy and A34 account "
            "DEVELOPMENT replay"
        )
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
                "current_invocation_performance_opened": True,
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
        print("  DEVELOPMENT replay: COMPLETE")

    if args.through_walk_forward_replay:
        assert authorization is not None
        assert walk_forward_end is not None
        print(
            "\n7/7 Materializing and running the authorized one-time "
            "walk-forward replay"
        )
        receipt_path, receipt = _begin_holdout_consumption(
            layout,
            authorization_id=str(authorization["authorization_id"]),
            walk_forward_end=walk_forward_end,
        )
        summary.update(
            {
                "status": "MASTER_HOLDOUT_CONSUMPTION_STARTED",
                "master_holdout_consumed": True,
                "master_holdout_consumption_receipt": str(receipt_path),
                "protected_return_rows_read": receipt["protected_return_rows_read"],
                "protected_return_rows_materialized": receipt["protected_return_rows_read"],
                "protected_rows_accounting_pending": True,
            }
        )
        atomic_write_text(
            summary_path,
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            fsync=True,
        )
        try:
            walk_forward = coordinator.build_walk_forward_daily(
                native,
                daily,
                identity,
                split,
                holdout_authorization=authorization,
            )
            materialized_end = date.fromisoformat(str(walk_forward.report["cutoff_session"]))
            protected_rows = int(walk_forward.report["protected_return_rows_materialized"])
            if protected_rows < 1:
                raise ValueError("walk-forward materialization did not account for protected rows")
        except BaseException as exc:
            receipt.update(
                {
                    "status": "CONSUMED_MATERIALIZATION_FAILED",
                    "completed_at_utc": datetime.now(UTC).isoformat(),
                    "materialization_error": f"{type(exc).__name__}: {exc}",
                }
            )
            receipt = write_holdout_receipt(receipt_path, receipt)
            summary["status"] = "MASTER_HOLDOUT_CONSUMED_MATERIALIZATION_FAILED"
            summary["walk_forward_error"] = f"{type(exc).__name__}: {exc}"
            summary["master_holdout_consumed"] = True
            atomic_write_text(
                summary_path,
                json.dumps(summary, indent=2, sort_keys=True) + "\n",
                fsync=True,
            )
            write_run_state(
                layout,
                stage="V2_WALK_FORWARD_MATERIALIZATION",
                status=summary["status"],
                details={"postbuild_manifest": str(summary_path)},
            )
            raise
        if materialized_end != walk_forward_end:
            receipt.update(
                {
                    "status": "CONSUMED_MATERIALIZATION_SCOPE_MISMATCH",
                    "completed_at_utc": datetime.now(UTC).isoformat(),
                    "materialized_end": materialized_end.isoformat(),
                    "protected_return_rows_read": protected_rows,
                }
            )
            receipt = write_holdout_receipt(receipt_path, receipt)
            summary.update(
                {
                    "status": "MASTER_HOLDOUT_CONSUMED_MATERIALIZATION_SCOPE_MISMATCH",
                    "master_holdout_consumed": True,
                    "protected_return_rows_read": protected_rows,
                    "protected_return_rows_materialized": protected_rows,
                    "walk_forward_error": (
                        "walk-forward materialization end differs from the "
                        "authorized source cutoff"
                    ),
                    "authorized_walk_forward_end": walk_forward_end.isoformat(),
                    "materialized_walk_forward_end": materialized_end.isoformat(),
                }
            )
            atomic_write_text(
                summary_path,
                json.dumps(summary, indent=2, sort_keys=True) + "\n",
                fsync=True,
            )
            write_run_state(
                layout,
                stage="V2_WALK_FORWARD_MATERIALIZATION",
                status=summary["status"],
                details={"postbuild_manifest": str(summary_path)},
            )
            raise RuntimeError(
                "walk-forward materialization end differs from the authorized source cutoff"
            )
        receipt.update(
            {
                "status": "CONSUMED_REPLAY_STARTED",
                "protected_return_rows_read": protected_rows,
                "protected_rows_accounting_pending": False,
            }
        )
        receipt = write_holdout_receipt(receipt_path, receipt)
        summary.update({
            "status": "MASTER_HOLDOUT_REPLAY_STARTED",
            "protected_return_rows_read": protected_rows,
            "protected_return_rows_materialized": protected_rows,
            "protected_rows_accounting_pending": False,
        })
        atomic_write_text(summary_path, json.dumps(summary, indent=2, sort_keys=True) + "\n", fsync=True)
        command = [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "run_a33_b33_reference_development.py"),
            "--data-source",
            "v2",
            "--evaluation-stage",
            "walk-forward",
            "--authorize-master-holdout-consumption",
            "--start",
            args.reference_start.isoformat(),
            "--evaluation-start",
            V2_REFERENCE_MASTER_PROTECTED_START.isoformat(),
            "--end",
            walk_forward_end.isoformat(),
        ]
        try:
            completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
        except BaseException as exc:
            receipt.update({
                "status": "CONSUMED_REPLAY_FAILED",
                "completed_at_utc": datetime.now(UTC).isoformat(),
                "replay_error": f"{type(exc).__name__}: {exc}",
            })
            write_holdout_receipt(receipt_path, receipt)
            summary.update({
                "status": "MASTER_HOLDOUT_CONSUMED_WALK_FORWARD_FAILED",
                "walk_forward_error": f"{type(exc).__name__}: {exc}",
            })
            atomic_write_text(summary_path, json.dumps(summary, indent=2, sort_keys=True) + "\n", fsync=True)
            write_run_state(layout, stage="V2_WALK_FORWARD_REPLAY", status=summary["status"],
                            details={"postbuild_manifest": str(summary_path)})
            raise
        if completed.returncode != 0:
            receipt["status"] = "CONSUMED_REPLAY_FAILED"
            receipt["completed_at_utc"] = datetime.now(UTC).isoformat()
            receipt["replay_exit_code"] = completed.returncode
            receipt = write_holdout_receipt(receipt_path, receipt)
            summary.update(
                {
                    "status": "MASTER_HOLDOUT_CONSUMED_WALK_FORWARD_FAILED",
                    "protected_return_rows_read": protected_rows,
                    "master_holdout_consumed": True,
                    "walk_forward_exit_code": completed.returncode,
                }
            )
            atomic_write_text(
                summary_path,
                json.dumps(summary, indent=2, sort_keys=True) + "\n",
                fsync=True,
            )
            write_run_state(
                layout,
                stage="V2_WALK_FORWARD_REPLAY",
                status=summary["status"],
                details={
                    "postbuild_manifest": str(summary_path),
                    "exit_code": completed.returncode,
                },
            )
            print(
                "\nResult: MASTER HOLDOUT CONSUMED; WALK-FORWARD FAILED "
                "AND CANNOT BE RESET"
            )
            return completed.returncode
        receipt["status"] = "CONSUMED_WALK_FORWARD_COMPLETE"
        receipt["completed_at_utc"] = datetime.now(UTC).isoformat()
        receipt["replay_exit_code"] = 0
        receipt = write_holdout_receipt(receipt_path, receipt)
        summary.update(
            {
                "status": "DEVELOPMENT_AND_WALK_FORWARD_COMPLETE",
                "walk_forward_daily": str(
                    layout.manifests / "walk_forward_daily.json"
                ),
                "walk_forward_daily_fingerprint": walk_forward.report[
                    "source_fingerprint"
                ],
                "walk_forward_scope": {
                    "warmup_start": args.reference_start.isoformat(),
                    "evaluation_start": V2_REFERENCE_MASTER_PROTECTED_START.isoformat(),
                    "evaluation_end": walk_forward_end.isoformat(),
                    "data_source": "v2",
                },
                "protected_return_rows_materialized": protected_rows,
                "protected_return_rows_read": protected_rows,
                "protected_rows_accounting_pending": False,
                "master_holdout_consumed": True,
                "master_holdout_consumption_receipt": str(receipt_path),
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
            stage="V2_WALK_FORWARD_REPLAY",
            status=summary["status"],
            details={"postbuild_manifest": str(summary_path)},
        )

    if args.through_walk_forward_replay:
        print("\nResult: V2 DEVELOPMENT AND FROZEN WALK-FORWARD REPLAYS COMPLETE")
    elif args.through_reference_replay:
        print("\nResult: V2 DAILY FOUNDATION AND FROZEN REFERENCE REPLAY COMPLETE")
    else:
        print("\nResult: V2 DAILY RESEARCH FOUNDATION READY")
    print("Minute data remains preserved but is not yet intraday-strategy accepted.")
    if args.through_walk_forward_replay:
        print(
            "Master holdout was consumed once for historical walk-forward evidence; "
            "this is not prospective PAPER and grants no strategy or trading authority."
        )
    elif args.through_reference_replay:
        print(
            "Historical DEVELOPMENT outcomes were opened under frozen policies; "
            "protected return, PAPER order, LIVE order, and broker writes remain zero."
        )
    else:
        print(
            "This invocation opened no new strategy performance or protected returns "
            "and made no PAPER, LIVE, or broker write. Any prior consumption remains recorded."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
