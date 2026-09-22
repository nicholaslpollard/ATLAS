from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.control_plane.recurrent_cycle_health import (
    RecurrentCycleHealthService,
)
from packages.control_plane.recurrent_lifecycle_dashboard import (
    RecurrentLifecycleDashboardService,
    RecurrentLifecycleDashboardSource,
)
from packages.core.enums import SessionSegment
from packages.data.paths import MarketDataPaths
from packages.execution.current_webull_decision_stock_close import (
    build_current_webull_decision_stock_close_evidence_bundle_v1,
)
from packages.execution.current_webull_quote_bundle import (
    read_current_webull_stock_quote_bundle_v1,
)
from packages.execution.current_webull_stock_entry import (
    build_current_webull_stock_entry_evidence_bundle_v1,
    write_current_webull_stock_entry_evidence_bundle_v1,
)
from packages.execution.current_webull_stock_mark_adapter import (
    build_current_webull_stock_marks_v1,
)
from packages.execution.current_webull_time_aware_stock_close import (
    FinalStockCloseDisposition,
    build_current_webull_time_aware_stock_close_bundle_v1,
    read_current_webull_time_aware_stock_close_bundle_v1,
    write_current_webull_time_aware_stock_close_bundle_v1,
)
from packages.simulation.forecast_horizon_clock import (
    ForecastHorizonClockPolicyV1,
)
from packages.simulation.forecast_horizon_clock_book import (
    build_forecast_horizon_clock_book_v1,
    read_forecast_horizon_clock_book_v1,
    write_forecast_horizon_clock_book_v1,
)
from packages.simulation.forecast_horizon_time_disposition import (
    ForecastHorizonTimeDispositionKind,
    build_forecast_horizon_time_disposition_bundle_v1,
)
from packages.simulation.recurrent_cycle_runner import (
    RecurrentCycleRunnerV1,
    build_recurrent_cycle_run_identity_v1,
)
from packages.simulation.recurrent_decision_exit_plan import (
    StockExitPolicyInputsV1,
    build_recurrent_decision_stock_exit_plan_book_v1,
    read_recurrent_decision_stock_exit_plan_book_v1,
)
from packages.simulation.recurrent_genesis import (
    bootstrap_recurrent_genesis_v1,
)
from packages.simulation.recurrent_reserve_evidence import (
    build_recurrent_reserve_evidence_bundle_v1,
    read_recurrent_reserve_evidence_bundle_v1,
    write_recurrent_reserve_evidence_bundle_v1,
)
from packages.simulation.recurrent_time_aware_production_cycle import (
    RecurrentTimeAwareProductionCycleV1,
)
from packages.simulation.recurrent_workstation_acceptance import (
    RECURRENT_WORKSTATION_ACCEPTANCE_CONTRACT_FINGERPRINT,
    REFERENCE_THRESHOLD_FRACTION,
    RecurrentWorkstationAcceptanceError,
    build_workstation_acceptance_receipt_v1,
    build_workstation_reference_decision_v1,
    isolated_acceptance_settings,
    read_acceptance_json,
    read_workstation_acceptance_receipt_v1,
    workstation_acceptance_context_path,
    workstation_acceptance_receipt_path,
    workstation_acceptance_stage_path,
    workstation_entry_schedule_utc,
    write_acceptance_json,
    write_workstation_acceptance_receipt_v1,
)


ENTRY_SCHEDULE_ID = "workstation-acceptance-entry-v1"
CLOSE_SCHEDULE_ID = "workstation-acceptance-close-v1"
MAX_DEADLINE_WAIT_SECONDS = 180.0


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RecurrentWorkstationAcceptanceError(
            "stored acceptance timestamp must be timezone-aware"
        )
    return parsed.astimezone(UTC)


def _settings(live_root: Path):
    return isolated_acceptance_settings(
        project_root=PROJECT_ROOT,
        live_root=live_root,
    )


def _context(settings):
    return read_acceptance_json(
        workstation_acceptance_context_path(settings)
    )


def _write_stage(settings, stage: str, payload: dict[str, object]):
    payload = {
        "contract_fingerprint": (
            RECURRENT_WORKSTATION_ACCEPTANCE_CONTRACT_FINGERPRINT
        ),
        "stage": stage,
        **payload,
    }
    return write_acceptance_json(
        workstation_acceptance_stage_path(settings, stage),
        payload,
    )


def _identity(
    *,
    schedule_id: str,
    scheduled_for_utc: datetime,
):
    return build_recurrent_cycle_run_identity_v1(
        schedule_id=schedule_id,
        scheduled_for_utc=scheduled_for_utc,
    )


def _policy(decision_fp: str) -> dict[str, StockExitPolicyInputsV1]:
    return {
        decision_fp: StockExitPolicyInputsV1(
            policy_id="workstation-acceptance-wide-band-v1",
            policy_fingerprint=_sha_text(
                "workstation-acceptance-wide-band-v1|"
                f"{REFERENCE_THRESHOLD_FRACTION:.12f}"
            ),
            stop_threshold_fraction=REFERENCE_THRESHOLD_FRACTION,
            target_threshold_fraction=REFERENCE_THRESHOLD_FRACTION,
        )
    }


def _empty_time_aware_close(
    *,
    runtime,
    identity,
    evaluation_utc: datetime,
):
    account = runtime.current_account()
    plan_book = build_recurrent_decision_stock_exit_plan_book_v1(
        source_state=account.state,
        current_reserve_bundle=None,
        existing_book=None,
        exit_policy_by_decision={},
        built_at_utc=evaluation_utc,
    )
    clock_book = build_forecast_horizon_clock_book_v1(
        source_exit_plan_book=plan_book,
        existing_book=None,
        clock_policy_by_position={},
    )
    time_bundle = build_forecast_horizon_time_disposition_bundle_v1(
        source_clock_book=clock_book,
        evaluation_utc=evaluation_utc,
    )
    price_bundle = build_current_webull_decision_stock_close_evidence_bundle_v1(
        account=account,
        identity=identity,
        exit_plan_book=plan_book,
        quote_bundle=None,
        explicit_exit_fees_by_position={},
        built_at_utc=evaluation_utc,
    )
    return build_current_webull_time_aware_stock_close_bundle_v1(
        account=account,
        identity=identity,
        price_close_bundle=price_bundle,
        time_disposition_bundle=time_bundle,
        explicit_time_exit_fees_by_position={},
    )


def _phase_entry(live_root: Path) -> int:
    settings = _settings(live_root)
    context = _context(settings)
    ticker = str(context["ticker"])
    initial_equity = float(context["initial_equity"])
    entry_fee = float(context["entry_fee_dollars"])

    quotes = read_current_webull_stock_quote_bundle_v1(settings)
    if quotes.requested_symbols != (ticker,) or len(quotes.quotes) != 1:
        raise RecurrentWorkstationAcceptanceError(
            "ENTRY capture must contain exactly the configured ticker"
        )
    quote = quotes.quotes[0]
    if quote.session_segment != SessionSegment.REGULAR:
        raise RecurrentWorkstationAcceptanceError(
            "workstation acceptance must begin during XNYS regular session"
        )

    cutoff = quote.provider_timestamp_utc - timedelta(seconds=1)
    checkpoint = MarketDataPaths(
        settings
    ).recurrent_lifecycle_checkpoint_file()
    runtime, _genesis = bootstrap_recurrent_genesis_v1(
        checkpoint_path=checkpoint,
        initial_equity=initial_equity,
        as_of_utc=cutoff - timedelta(seconds=1),
    )
    entry_schedule_utc = workstation_entry_schedule_utc(
        provider_timestamp_utc=quote.provider_timestamp_utc,
        received_at_utc=quote.received_at_utc,
        captured_at_utc=quotes.captured_at_utc,
    )
    identity = _identity(
        schedule_id=ENTRY_SCHEDULE_ID,
        scheduled_for_utc=entry_schedule_utc,
    )
    production = RecurrentTimeAwareProductionCycleV1(
        settings=settings,
        runner=RecurrentCycleRunnerV1(
            checkpoint_path=checkpoint,
            runtime=runtime,
        ),
        identity=identity,
    )
    production.begin(now_utc=quotes.captured_at_utc)
    empty_close = _empty_time_aware_close(
        runtime=runtime,
        identity=identity,
        evaluation_utc=quotes.captured_at_utc,
    )
    production.apply_close(
        bundle=empty_close,
        now_utc=quotes.captured_at_utc,
    )

    decision = build_workstation_reference_decision_v1(
        ticker=ticker,
        reference_price=quote.ask_price,
        decision_created_utc=quote.provider_timestamp_utc,
        evidence_cutoff_utc=cutoff,
        position_notional_dollars=initial_equity * 0.10,
    )
    reserve = build_recurrent_reserve_evidence_bundle_v1(
        identity=identity,
        decisions=((decision, None),),
        built_at_utc=quote.received_at_utc,
    )
    write_recurrent_reserve_evidence_bundle_v1(settings, reserve)
    production.apply_reserve(
        bundle=reserve,
        now_utc=quote.received_at_utc,
    )

    fee_source_id = "workstation-acceptance-entry-fee-v1"
    fee_source_fp = _sha_text(
        f"{fee_source_id}|{entry_fee:.12f}"
    )
    entry = build_current_webull_stock_entry_evidence_bundle_v1(
        account=runtime.current_account(),
        reserve_bundle=reserve,
        quote_bundle=quotes,
        explicit_entry_fees_by_decision={
            decision.record_fingerprint: entry_fee
        },
        fee_source_id=fee_source_id,
        fee_source_fingerprint=fee_source_fp,
        built_at_utc=datetime.now(UTC),
    )
    write_current_webull_stock_entry_evidence_bundle_v1(
        settings,
        entry,
    )
    receipt = production.apply_entry(
        bundle=entry,
        now_utc=datetime.now(UTC),
    )
    status = runtime.status()
    _write_stage(
        settings,
        "entry",
        {
            "entry_scheduled_for_utc": (
                identity.scheduled_for_utc.isoformat()
            ),
            "entry_quote_received_at_utc": (
                quote.received_at_utc.isoformat()
            ),
            "entry_quote_bundle_captured_at_utc": (
                quotes.captured_at_utc.isoformat()
            ),
            "entry_cycle_id": identity.cycle_id,
            "entry_cycle_fingerprint": identity.cycle_fingerprint,
            "entry_quote_bundle_fingerprint": (
                quotes.bundle_fingerprint
            ),
            "decision_record_fingerprint": (
                decision.record_fingerprint
            ),
            "entry_evidence_bundle_fingerprint": (
                entry.bundle_fingerprint
            ),
            "post_entry_checkpoint_sha256": (
                status.checkpoint_sha256
            ),
            "post_entry_snapshot_fingerprint": (
                status.snapshot_fingerprint
            ),
            "post_entry_revision": status.revision,
            "recorded_stage_count": len(receipt.stages),
        },
    )
    print("phase: ENTRY")
    print("status: PASSED")
    print(f"decision_record_fingerprint: {decision.record_fingerprint}")
    return 0


def _phase_mark(live_root: Path) -> int:
    settings = _settings(live_root)
    entry_stage = read_acceptance_json(
        workstation_acceptance_stage_path(settings, "entry")
    )
    identity = _identity(
        schedule_id=ENTRY_SCHEDULE_ID,
        scheduled_for_utc=_utc(
            str(entry_stage["entry_scheduled_for_utc"])
        ),
    )
    checkpoint = MarketDataPaths(
        settings
    ).recurrent_lifecycle_checkpoint_file()
    production = RecurrentTimeAwareProductionCycleV1.restore(
        settings=settings,
        checkpoint_path=checkpoint,
        identity=identity,
    )
    runtime = production.runner.runtime
    reserve = read_recurrent_reserve_evidence_bundle_v1(
        settings
    )
    decision_fp = str(
        entry_stage["decision_record_fingerprint"]
    )
    quotes = read_current_webull_stock_quote_bundle_v1(settings)
    valuation = datetime.now(UTC)
    marks = build_current_webull_stock_marks_v1(
        bundle=quotes,
        positions=runtime.current_account().state.open_positions,
        valuation_utc=valuation,
    )
    production.apply_mark(
        reserve_bundle=reserve,
        exit_policy_by_decision=_policy(decision_fp),
        mark_batch=marks,
        valuation_utc=valuation,
        now_utc=valuation,
    )
    production.complete(now_utc=datetime.now(UTC))

    plan_book = read_recurrent_decision_stock_exit_plan_book_v1(
        settings
    )
    position_ids = {
        plan.position_fingerprint for plan in plan_book.plans
    }
    if len(position_ids) != 1:
        raise RecurrentWorkstationAcceptanceError(
            "acceptance MARK expected exactly one open position plan"
        )
    position_fp = next(iter(position_ids))
    clock_book = build_forecast_horizon_clock_book_v1(
        source_exit_plan_book=plan_book,
        existing_book=None,
        clock_policy_by_position={
            position_fp: ForecastHorizonClockPolicyV1()
        },
    )
    write_forecast_horizon_clock_book_v1(
        settings,
        clock_book,
    )
    deadline = clock_book.clocks[0].deadline_utc

    pair = runtime.current_dashboard_pair()
    if pair is None:
        raise RecurrentWorkstationAcceptanceError(
            "marked recurrent runtime did not expose dashboard pair"
        )
    account, marked = pair
    dashboard = RecurrentLifecycleDashboardService(
        source_provider=lambda: RecurrentLifecycleDashboardSource(
            account=account,
            marked_state=marked,
        ),
        now_utc=lambda: valuation,
    ).snapshot()
    if dashboard.get("status") != "AVAILABLE":
        raise RecurrentWorkstationAcceptanceError(
            "recurrent dashboard was not AVAILABLE after MARK"
        )
    source = dashboard.get("source")
    if not isinstance(source, dict):
        raise RecurrentWorkstationAcceptanceError(
            "dashboard source payload is unavailable"
        )

    _write_stage(
        settings,
        "mark",
        {
            "mark_quote_bundle_fingerprint": quotes.bundle_fingerprint,
            "exit_plan_book_fingerprint": (
                plan_book.book_fingerprint
            ),
            "clock_book_fingerprint": (
                clock_book.book_fingerprint
            ),
            "deadline_utc": deadline.isoformat(),
            "dashboard_status": str(dashboard["status"]),
            "dashboard_account_state_fingerprint": str(
                source["account_state_fingerprint"]
            ),
            "marked_state_fingerprint": str(
                source["marked_state_fingerprint"]
            ),
        },
    )
    print("phase: MARK_RESTART")
    print("status: PASSED")
    print(f"deadline_utc: {deadline.isoformat()}")
    return 0


def _phase_close(live_root: Path) -> int:
    settings = _settings(live_root)
    context = _context(settings)
    exit_fee = float(context["exit_fee_dollars"])
    quotes = read_current_webull_stock_quote_bundle_v1(settings)
    if len(quotes.quotes) != 1:
        raise RecurrentWorkstationAcceptanceError(
            "CLOSE capture must contain exactly one quote"
        )

    checkpoint = MarketDataPaths(
        settings
    ).recurrent_lifecycle_checkpoint_file()
    clock_book = read_forecast_horizon_clock_book_v1(
        settings
    )
    plan_book = clock_book.source_exit_plan_book
    if len(plan_book.plans) != 1:
        raise RecurrentWorkstationAcceptanceError(
            "CLOSE expected exactly one persisted exit plan"
        )
    plan = plan_book.plans[0]
    bid = quotes.quotes[0].bid_price
    if not (
        plan.stop_price_per_unit
        < bid
        < plan.target_price_per_unit
    ):
        raise RecurrentWorkstationAcceptanceError(
            "acceptance quote crossed the fixed +/-20% price band; "
            "refusing to retune fixture after observation"
        )

    scheduled = quotes.captured_at_utc
    identity = _identity(
        schedule_id=CLOSE_SCHEDULE_ID,
        scheduled_for_utc=scheduled,
    )
    production = RecurrentTimeAwareProductionCycleV1.restore(
        settings=settings,
        checkpoint_path=checkpoint,
        identity=identity,
    )
    runtime = production.runner.runtime
    production.begin(now_utc=scheduled)

    built = datetime.now(UTC)
    price_close = (
        build_current_webull_decision_stock_close_evidence_bundle_v1(
            account=runtime.current_account(),
            identity=identity,
            exit_plan_book=plan_book,
            quote_bundle=quotes,
            explicit_exit_fees_by_position={},
            built_at_utc=built,
        )
    )
    if (
        price_close.triggers[0].disposition.value
        != "NO_TRIGGER"
    ):
        raise RecurrentWorkstationAcceptanceError(
            "acceptance requires price NO_TRIGGER before TIME resolution"
        )
    time_bundle = (
        build_forecast_horizon_time_disposition_bundle_v1(
            source_clock_book=clock_book,
            evaluation_utc=price_close.built_at_utc,
        )
    )
    if (
        time_bundle.dispositions[0].disposition
        != ForecastHorizonTimeDispositionKind.TIME_EXPIRED
    ):
        raise RecurrentWorkstationAcceptanceError(
            "acceptance close quote was captured before immutable horizon expiry"
        )
    position_fp = plan.position_fingerprint
    fee_source_id = "workstation-acceptance-time-exit-fee-v1"
    fee_source_fp = _sha_text(
        f"{fee_source_id}|{exit_fee:.12f}"
    )
    final = build_current_webull_time_aware_stock_close_bundle_v1(
        account=runtime.current_account(),
        identity=identity,
        price_close_bundle=price_close,
        time_disposition_bundle=time_bundle,
        explicit_time_exit_fees_by_position={
            position_fp: exit_fee
        },
        time_fee_source_id=fee_source_id,
        time_fee_source_fingerprint=fee_source_fp,
    )
    if (
        final.rows[0].final_disposition
        != FinalStockCloseDisposition.TIME
    ):
        raise RecurrentWorkstationAcceptanceError(
            "acceptance final CLOSE disposition was not TIME"
        )
    write_current_webull_time_aware_stock_close_bundle_v1(
        settings,
        final,
    )
    production.apply_close(
        bundle=final,
        now_utc=datetime.now(UTC),
    )
    account = runtime.current_account()
    if len(account.state.open_positions) != 0:
        raise RecurrentWorkstationAcceptanceError(
            "TIME CLOSE did not remove the acceptance position"
        )
    if len(account.state.closed_trades) != 1:
        raise RecurrentWorkstationAcceptanceError(
            "TIME CLOSE did not create exactly one closed trade"
        )
    status = runtime.status()
    _write_stage(
        settings,
        "close",
        {
            "close_scheduled_for_utc": scheduled.isoformat(),
            "close_cycle_id": identity.cycle_id,
            "close_cycle_fingerprint": identity.cycle_fingerprint,
            "close_quote_bundle_fingerprint": quotes.bundle_fingerprint,
            "time_disposition_bundle_fingerprint": (
                time_bundle.bundle_fingerprint
            ),
            "time_aware_close_bundle_fingerprint": (
                final.bundle_fingerprint
            ),
            "final_disposition": final.rows[0].final_disposition.value,
            "post_close_checkpoint_sha256": status.checkpoint_sha256,
            "post_close_snapshot_fingerprint": (
                status.snapshot_fingerprint
            ),
            "post_close_revision": status.revision,
            "closed_trade_count": len(account.state.closed_trades),
        },
    )
    print("phase: TIME_CLOSE")
    print("status: PASSED")
    print(f"close_bundle_fingerprint: {final.bundle_fingerprint}")
    return 0


def _phase_retry(live_root: Path) -> int:
    settings = _settings(live_root)
    context = _context(settings)
    entry_stage = read_acceptance_json(
        workstation_acceptance_stage_path(settings, "entry")
    )
    mark_stage = read_acceptance_json(
        workstation_acceptance_stage_path(settings, "mark")
    )
    close_stage = read_acceptance_json(
        workstation_acceptance_stage_path(settings, "close")
    )
    identity = _identity(
        schedule_id=CLOSE_SCHEDULE_ID,
        scheduled_for_utc=_utc(
            str(close_stage["close_scheduled_for_utc"])
        ),
    )
    checkpoint = MarketDataPaths(
        settings
    ).recurrent_lifecycle_checkpoint_file()
    production = RecurrentTimeAwareProductionCycleV1.restore(
        settings=settings,
        checkpoint_path=checkpoint,
        identity=identity,
    )
    runtime = production.runner.runtime
    before = len(
        runtime.current_account().state.closed_trades
    )
    final = read_current_webull_time_aware_stock_close_bundle_v1(
        settings
    )
    production.apply_close(
        bundle=final,
        now_utc=datetime.now(UTC),
    )
    after = len(
        runtime.current_account().state.closed_trades
    )
    if before != 1 or after != 1:
        raise RecurrentWorkstationAcceptanceError(
            "exact CLOSE retry changed closed-trade count"
        )

    status = runtime.status()
    health = RecurrentCycleHealthService(
        settings,
        now_utc=lambda: datetime.now(UTC),
    ).snapshot()
    if health.get("status") != "OPEN_CYCLE":
        raise RecurrentWorkstationAcceptanceError(
            "cycle health did not report valid OPEN_CYCLE after CLOSE retry"
        )
    if (
        int(health.get("invalid_cycle_receipt_count", -1)) != 0
        or int(health.get("invalid_stage_admission_count", -1)) != 0
    ):
        raise RecurrentWorkstationAcceptanceError(
            "cycle health found invalid durable lineage"
        )

    receipt = build_workstation_acceptance_receipt_v1(
        run_id=str(context["run_id"]),
        ticker=str(context["ticker"]),
        isolated_live_root=str(
            settings.resolved_path(settings.data.paths.live)
        ),
        initial_equity=float(context["initial_equity"]),
        entry_fee_dollars=float(context["entry_fee_dollars"]),
        exit_fee_dollars=float(context["exit_fee_dollars"]),
        entry_cycle_id=str(entry_stage["entry_cycle_id"]),
        close_cycle_id=str(close_stage["close_cycle_id"]),
        entry_quote_bundle_fingerprint=str(
            entry_stage["entry_quote_bundle_fingerprint"]
        ),
        mark_quote_bundle_fingerprint=str(
            mark_stage["mark_quote_bundle_fingerprint"]
        ),
        close_quote_bundle_fingerprint=str(
            close_stage["close_quote_bundle_fingerprint"]
        ),
        decision_record_fingerprint=str(
            entry_stage["decision_record_fingerprint"]
        ),
        exit_plan_book_fingerprint=str(
            mark_stage["exit_plan_book_fingerprint"]
        ),
        clock_book_fingerprint=str(
            mark_stage["clock_book_fingerprint"]
        ),
        time_disposition_bundle_fingerprint=str(
            close_stage["time_disposition_bundle_fingerprint"]
        ),
        time_aware_close_bundle_fingerprint=str(
            close_stage["time_aware_close_bundle_fingerprint"]
        ),
        final_disposition=str(close_stage["final_disposition"]),
        final_checkpoint_sha256=status.checkpoint_sha256,
        final_snapshot_fingerprint=status.snapshot_fingerprint,
        final_revision=status.revision,
        closed_trade_count=after,
        dashboard_status_after_mark=str(
            mark_stage["dashboard_status"]
        ),
        dashboard_account_state_fingerprint=str(
            mark_stage["dashboard_account_state_fingerprint"]
        ),
        cycle_health_status_after_retry=str(health["status"]),
        accepted_at_utc=datetime.now(UTC).isoformat(),
        provider_read_calls=3,
    )
    path = write_workstation_acceptance_receipt_v1(
        settings,
        receipt,
    )
    _write_stage(
        settings,
        "retry",
        {
            "receipt_fingerprint": receipt.receipt_fingerprint,
            "receipt_path": str(path),
            "closed_trade_count_before_retry": before,
            "closed_trade_count_after_retry": after,
            "cycle_health_status": str(health["status"]),
        },
    )
    print("phase: RESTART_EXACT_CLOSE_RETRY")
    print("status: PASSED")
    print(f"receipt_fingerprint: {receipt.receipt_fingerprint}")
    return 0


def _capture(live_root: Path, ticker: str) -> None:
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "capture_current_webull_quotes.py"),
        "--tickers",
        ticker,
        "--live-root",
        str(live_root),
    ]
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        raise RecurrentWorkstationAcceptanceError(
            "Webull sandbox quote capture failed"
        )


def _child(live_root: Path, phase: str) -> None:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--phase",
        phase,
        "--live-root",
        str(live_root),
    ]
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        raise RecurrentWorkstationAcceptanceError(
            f"acceptance child phase failed: {phase}"
        )


def _parent(args: argparse.Namespace) -> int:
    if not math.isfinite(args.initial_equity) or args.initial_equity <= 0.0:
        raise RecurrentWorkstationAcceptanceError(
            "initial equity must be finite and positive"
        )
    for label, value in (
        ("entry fee", args.entry_fee),
        ("exit fee", args.exit_fee),
    ):
        if not math.isfinite(value) or value < 0.0:
            raise RecurrentWorkstationAcceptanceError(
                f"{label} must be finite and nonnegative"
            )
    if args.entry_fee >= args.initial_equity * 0.50:
        raise RecurrentWorkstationAcceptanceError(
            "entry fee is too large for the isolated acceptance account"
        )

    run_id = (
        args.run_id
        or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    )
    live_root = (
        args.live_root.expanduser().resolve()
        if args.live_root is not None
        else (
            PROJECT_ROOT
            / "data"
            / "acceptance"
            / "recurrent_workstation"
            / run_id
            / "live"
        ).resolve()
    )
    if live_root.exists() and any(live_root.iterdir()):
        raise RecurrentWorkstationAcceptanceError(
            "acceptance live root already contains artifacts; choose a new run id"
        )
    settings = _settings(live_root)
    context = {
        "contract_fingerprint": (
            RECURRENT_WORKSTATION_ACCEPTANCE_CONTRACT_FINGERPRINT
        ),
        "run_id": run_id,
        "ticker": args.ticker.strip(),
        "initial_equity": float(args.initial_equity),
        "entry_fee_dollars": float(args.entry_fee),
        "exit_fee_dollars": float(args.exit_fee),
        "isolated_live_root": str(live_root),
        "created_at_utc": datetime.now(UTC).isoformat(),
        "reference_fixture_not_strategy_evidence": True,
        "paper_authority": False,
        "live_authority": False,
    }
    write_acceptance_json(
        workstation_acceptance_context_path(settings),
        context,
    )

    print("ATLAS recurrent workstation acceptance")
    print(f"run_id: {run_id}")
    print(f"ticker: {context['ticker']}")
    print(f"isolated_live_root: {live_root}")
    print("environment: WEBULL_SANDBOX_READ_ONLY_L1")
    print("paper_authority: False")
    print("live_authority: False")
    print("reference_fixture_not_strategy_evidence: True")

    _capture(live_root, str(context["ticker"]))
    _child(live_root, "entry")

    _capture(live_root, str(context["ticker"]))
    _child(live_root, "mark")

    mark_stage = read_acceptance_json(
        workstation_acceptance_stage_path(settings, "mark")
    )
    deadline = _utc(str(mark_stage["deadline_utc"]))
    remaining = (deadline - datetime.now(UTC)).total_seconds()
    if remaining > MAX_DEADLINE_WAIT_SECONDS:
        raise RecurrentWorkstationAcceptanceError(
            "immutable horizon deadline is too far away for one-command "
            "acceptance; rerun with more regular-session time remaining"
        )
    if remaining > 0.0:
        print(
            "waiting_for_immutable_deadline_seconds: "
            f"{remaining:.1f}"
        )
        time.sleep(remaining + 1.0)

    _capture(live_root, str(context["ticker"]))
    _child(live_root, "close")
    _child(live_root, "retry")

    receipt = read_workstation_acceptance_receipt_v1(
        settings
    )
    print("status: ACCEPTED")
    print(f"receipt_fingerprint: {receipt.receipt_fingerprint}")
    print(
        "acceptance_receipt: "
        + str(workstation_acceptance_receipt_path(settings))
    )
    print(f"final_disposition: {receipt.final_disposition}")
    print(f"closed_trade_count: {receipt.closed_trade_count}")
    print(
        "cycle_health_status_after_retry: "
        f"{receipt.cycle_health_status_after_retry}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the isolated ATLAS recurrent workstation acceptance proof "
            "using read-only Webull sandbox L1 evidence."
        )
    )
    parser.add_argument("--ticker", default="SPY")
    parser.add_argument("--initial-equity", type=float)
    parser.add_argument("--entry-fee", type=float)
    parser.add_argument("--exit-fee", type=float)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--live-root", type=Path, default=None)
    parser.add_argument(
        "--phase",
        choices=("entry", "mark", "close", "retry"),
        default=None,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    try:
        if args.phase is not None:
            if args.live_root is None:
                raise RecurrentWorkstationAcceptanceError(
                    "child phase requires --live-root"
                )
            phases = {
                "entry": _phase_entry,
                "mark": _phase_mark,
                "close": _phase_close,
                "retry": _phase_retry,
            }
            return phases[args.phase](args.live_root)

        missing = [
            name
            for name, value in (
                ("--initial-equity", args.initial_equity),
                ("--entry-fee", args.entry_fee),
                ("--exit-fee", args.exit_fee),
            )
            if value is None
        ]
        if missing:
            parser.error(
                "parent acceptance run requires "
                + ", ".join(missing)
            )
        return _parent(args)
    except RecurrentWorkstationAcceptanceError as exc:
        print("status: BLOCKED")
        print(f"reason: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
