from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from packages.backtesting.reference_portfolio_policy import (
    reference_portfolio_policy_fingerprint,
)
from packages.core.settings import load_settings
from packages.data.alpaca_v2_postbuild import MASTER_HOLDOUT_CONSUMPTION_CONTRACT
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.holdout_receipts import begin_holdout_consumption, write_holdout_receipt
from packages.performance.reference_replay_read_model import reference_replay_read_model
from packages.schemas.reference_portfolio import (
    REFERENCE_PORTFOLIO_REPLAY_CONTRACT_VERSION,
    ReferencePortfolioDecision,
    ReferencePortfolioDecisionStatus,
    ReferencePortfolioEquityPoint,
    ReferencePortfolioPositionOutcome,
    ReferenceSimulatedOrderEvent,
    ReferenceSimulatedOrderKind,
    ReferenceSimulatedOrderTiming,
)
from packages.schemas.strategy import StrategyDirection
from packages.schemas.strategy_lab import ResearchStrategyFamily, ReferenceExitReason


def _settings_with_derived(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(update={"derived": tmp_path})
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


def _settings_with_v2(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(update={"derived": tmp_path / "legacy"})
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"project_root": tmp_path, "data": data})


def _holdout_receipt(layout: V2Layout, *, complete: bool):
    path = layout.manifests / "master_holdout_consumption.json"
    receipt = begin_holdout_consumption(
        path, authorization_id="a" * 64, walk_forward_end=date(2026, 8, 12),
        walk_forward_manifest=layout.manifests / "walk_forward_daily.json",
    )
    if complete:
        receipt.update(status="CONSUMED_REPLAY_STARTED", protected_return_rows_read=123,
                       protected_rows_accounting_pending=False)
        receipt = write_holdout_receipt(path, receipt)
        receipt.update(status="CONSUMED_WALK_FORWARD_COMPLETE", replay_exit_code=0)
        receipt = write_holdout_receipt(path, receipt)
    return receipt


def _write_bound_jsonl(
    target: Path,
    filename: str,
    rows: tuple[BaseModel, ...],
) -> dict[str, str]:
    path = target / filename
    raw = "".join(
        json.dumps(row.model_dump(mode="json"), sort_keys=True) + "\n" for row in rows
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(raw)
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    }


def _operator_artifacts(
    target: Path,
    *,
    evaluation_stage: str = "development",
) -> dict[str, dict[str, str]]:
    if evaluation_stage == "walk-forward":
        signal_session = date(2026, 5, 12)
        entry_session = date(2026, 5, 13)
        exit_session = date(2026, 5, 14)
    else:
        signal_session = date(2025, 1, 2)
        entry_session = date(2025, 1, 3)
        exit_session = date(2025, 1, 6)
    decision = ReferencePortfolioDecision(
        decision_id="1" * 64,
        opportunity_id="2" * 64,
        strategy_id="ma_trend_cross_50_200_long_v1",
        family=ResearchStrategyFamily.MOVING_AVERAGE_TREND,
        direction=StrategyDirection.LONG,
        instrument_id="figi:TEST",
        ticker="TEST",
        signal_session=signal_session,
        requested_entry_session=entry_session,
        status=ReferencePortfolioDecisionStatus.ADMITTED,
        reason_codes=("RISK_SIZE_PASS",),
        admitted_quantity=10,
        entry_price=100.0,
        initial_stop_price=95.0,
        target_price=110.0,
        sizing_equity=100_000.0,
        risk_budget=250.0,
        effective_risk_per_share=5.1,
        admitted_notional=1_000.0,
    )
    orders = (
        ReferenceSimulatedOrderEvent(
            event_id="3" * 64,
            opportunity_id="2" * 64,
            decision_id="1" * 64,
            strategy_id="ma_trend_cross_50_200_long_v1",
            instrument_id="figi:TEST",
            ticker="TEST",
            kind=ReferenceSimulatedOrderKind.ENTRY,
            timing=ReferenceSimulatedOrderTiming.REGULAR_OPEN,
            session=entry_session,
            quantity=10,
            price=100.0,
            gross_notional=1_000.0,
            transaction_cost=0.5,
            cash_after=98_999.5,
        ),
        ReferenceSimulatedOrderEvent(
            event_id="4" * 64,
            opportunity_id="2" * 64,
            decision_id="1" * 64,
            strategy_id="ma_trend_cross_50_200_long_v1",
            instrument_id="figi:TEST",
            ticker="TEST",
            kind=ReferenceSimulatedOrderKind.EXIT,
            timing=ReferenceSimulatedOrderTiming.INTRADAY_DAILY_BAR,
            session=exit_session,
            quantity=10,
            price=110.0,
            gross_notional=1_100.0,
            transaction_cost=0.55,
            cash_after=100_099.0,
        ),
    )
    outcome = ReferencePortfolioPositionOutcome(
        opportunity_id="2" * 64,
        decision_id="1" * 64,
        strategy_id="ma_trend_cross_50_200_long_v1",
        family=ResearchStrategyFamily.MOVING_AVERAGE_TREND,
        instrument_id="figi:TEST",
        ticker="TEST",
        direction=StrategyDirection.LONG,
        entry_session=entry_session,
        exit_session=exit_session,
        quantity=10,
        entry_price=100.0,
        exit_price=110.0,
        exit_reason=ReferenceExitReason.PROFIT_TARGET,
        entry_transaction_cost=0.5,
        exit_transaction_cost=0.55,
        gross_pnl=100.0,
        net_pnl=98.95,
        net_return_on_entry_notional=0.09895,
        holding_sessions=2,
    )
    equity = ReferencePortfolioEquityPoint(
        session=exit_session,
        cash=100_099.0,
        market_value=0.0,
        equity=100_099.0,
        gross_exposure_fraction=0.0,
        open_positions=0,
        peak_equity=100_099.0,
        drawdown=0.0,
    )
    return {
        "decision_records": _write_bound_jsonl(
            target, "portfolio_decisions.jsonl", (decision,)
        ),
        "simulated_order_records": _write_bound_jsonl(
            target, "portfolio_simulated_orders.jsonl", orders
        ),
        "position_outcome_records": _write_bound_jsonl(
            target, "portfolio_position_outcomes.jsonl", (outcome,)
        ),
        "equity_curve_records": _write_bound_jsonl(
            target, "portfolio_equity_curve.jsonl", (equity,)
        ),
    }


def test_reference_replay_read_model_reports_not_run_without_artifacts(tmp_path) -> None:
    payload = reference_replay_read_model(_settings_with_derived(tmp_path))
    assert payload["status"] == "NOT_RUN"
    assert payload["summary"] is None
    assert payload["recent_portfolio_decisions"] == []
    assert payload["recent_simulated_orders"] == []
    assert payload["authority"] == {
        "authority_promotion": False,
        "qualifying_historical": False,
        "operational_paper": False,
        "qualifying_paper": False,
        "live": False,
        "provider_writes": 0,
        "broker_writes": 0,
        "paper_submits": 0,
        "live_writes": 0,
    }


def test_reference_replay_read_model_returns_latest_valid_summary_and_recent_rows(tmp_path) -> None:
    target = (
        tmp_path
        / "strategy_lab"
        / "a33_b33_reference"
        / "development"
        / "2021-08-16_2026-05-11"
    )
    target.mkdir(parents=True)
    summary = {
        "contract_version": REFERENCE_PORTFOLIO_REPLAY_CONTRACT_VERSION,
        "portfolio_policy_fingerprint": reference_portfolio_policy_fingerprint(),
        "replay_fingerprint": "a" * 64,
        "final_equity": 101_000.0,
        "total_return": 0.01,
        "maximum_drawdown": -0.02,
        "completed_positions": 1,
        "admitted_positions": 1,
        "total_transaction_cost": 12.5,
        "protected_master_return_rows_read": 0,
        "provider_writes": 0,
        "broker_writes": 0,
        "paper_submits": 0,
        "live_writes": 0,
    }
    summary.update(_operator_artifacts(target))
    (target / "portfolio_run_summary.json").write_text(
        json.dumps(summary), encoding="utf-8"
    )

    payload = reference_replay_read_model(_settings_with_derived(tmp_path))
    assert payload["status"] == "AVAILABLE"
    assert payload["data_source"] == "legacy"
    assert payload["summary"] == summary
    assert payload["recent_position_outcomes"][0]["ticker"] == "TEST"
    assert payload["recent_portfolio_decisions"][0]["status"] == "ADMITTED"
    assert payload["recent_simulated_orders"][1]["kind"] == "EXIT"
    assert payload["equity_curve_tail"][0]["equity"] == 100_099.0
    assert payload["artifact_integrity"] == {
        "expected_artifacts": 4,
        "verified_artifacts": 4,
        "all_sha256_verified": True,
    }


def test_reference_replay_read_model_prefers_isolated_v2_over_legacy(tmp_path) -> None:
    settings = _settings_with_v2(tmp_path)
    target = (
        V2Layout.beneath((tmp_path / "data").resolve()).derived
        / "strategy_lab"
        / "a33_b33_reference"
        / "development"
        / "2021-08-16_2026-05-11"
    )
    target.mkdir(parents=True)
    summary = {
        "contract_version": REFERENCE_PORTFOLIO_REPLAY_CONTRACT_VERSION,
        "portfolio_policy_fingerprint": reference_portfolio_policy_fingerprint(),
        "replay_fingerprint": "b" * 64,
        "data_source": "v2",
        "protected_master_return_rows_read": 0,
        "provider_writes": 0,
        "broker_writes": 0,
        "paper_submits": 0,
        "live_writes": 0,
    }
    summary.update(_operator_artifacts(target))
    (target / "portfolio_run_summary.json").write_text(
        json.dumps(summary), encoding="utf-8"
    )

    payload = reference_replay_read_model(settings)

    assert payload["status"] == "AVAILABLE"
    assert payload["data_source"] == "v2"
    assert payload["summary"]["data_source"] == "v2"


def test_reference_replay_read_model_exposes_completed_walk_forward(tmp_path) -> None:
    settings = _settings_with_v2(tmp_path)
    layout = V2Layout.beneath((tmp_path / "data").resolve())
    target = (
        layout.derived
        / "strategy_lab"
        / "a33_b33_reference"
        / "walk_forward"
        / "2021-08-16_2026-08-12"
    )
    target.mkdir(parents=True)
    authorization_id = "a" * 64
    protected_rows = 123
    summary = {
        "contract_version": REFERENCE_PORTFOLIO_REPLAY_CONTRACT_VERSION,
        "portfolio_policy_fingerprint": reference_portfolio_policy_fingerprint(),
        "replay_fingerprint": "c" * 64,
        "data_source": "v2",
        "evaluation_stage": "walk-forward",
        "evaluation_start_session": "2026-05-12",
        "evaluation_end_session": "2026-08-12",
        "replay_scope": "FROZEN_ONE_TIME_WALK_FORWARD_ACCOUNT_REPLAY",
        "master_holdout_authorization_id": authorization_id,
        "protected_master_return_rows_read": protected_rows,
        "provider_writes": 0,
        "broker_writes": 0,
        "paper_submits": 0,
        "live_writes": 0,
    }
    summary.update(_operator_artifacts(target, evaluation_stage="walk-forward"))
    (target / "portfolio_run_summary.json").write_text(
        json.dumps(summary), encoding="utf-8"
    )
    layout.manifests.mkdir(parents=True, exist_ok=True)
    _holdout_receipt(layout, complete=True)

    payload = reference_replay_read_model(settings)

    assert payload["status"] == "AVAILABLE"
    assert payload["evaluation_stage"] == "walk-forward"
    assert payload["replay_scope"] == "FROZEN_ONE_TIME_WALK_FORWARD_ACCOUNT_REPLAY"
    assert payload["summary"]["protected_master_return_rows_read"] == protected_rows
    assert "historical walk-forward" in payload["message"]


def test_reference_replay_read_model_does_not_hide_incomplete_consumption(
    tmp_path,
) -> None:
    settings = _settings_with_v2(tmp_path)
    layout = V2Layout.beneath((tmp_path / "data").resolve())
    layout.manifests.mkdir(parents=True, exist_ok=True)
    _holdout_receipt(layout, complete=False)

    payload = reference_replay_read_model(settings)

    assert payload["status"] == "INCOMPLETE"
    assert payload["evaluation_stage"] == "walk-forward"
    assert payload["summary"] is None


def test_reference_replay_read_model_rejects_malformed_consumption_receipt(
    tmp_path,
) -> None:
    settings = _settings_with_v2(tmp_path)
    layout = V2Layout.beneath((tmp_path / "data").resolve())
    layout.manifests.mkdir(parents=True, exist_ok=True)
    (layout.manifests / "master_holdout_consumption.json").write_text(
        json.dumps({"status": "CONSUMED_MATERIALIZATION_STARTED"}),
        encoding="utf-8",
    )

    payload = reference_replay_read_model(settings)

    assert payload["status"] == "INVALID"
    assert payload["evaluation_stage"] == "walk-forward"
    assert payload["summary"] is None


def test_reference_replay_read_model_preserves_retry_accounting_over_stale_summary(tmp_path):
    settings = _settings_with_v2(tmp_path)
    layout = V2Layout.beneath((tmp_path / "data").resolve())
    receipt = _holdout_receipt(layout, complete=False)
    path = layout.manifests / "master_holdout_consumption.json"
    receipt.update(status="CONSUMED_REPLAY_STARTED", protected_return_rows_read=123,
                   protected_rows_accounting_pending=False)
    receipt = write_holdout_receipt(path, receipt)
    receipt["status"] = "CONSUMED_REPLAY_FAILED"
    write_holdout_receipt(path, receipt)
    failed = reference_replay_read_model(settings)
    assert failed["status"] == "INVALID"
    assert failed["holdout_consumption"]["protected_return_rows_read"] == 123
    _holdout_receipt(layout, complete=False)
    target = layout.derived / "strategy_lab/a33_b33_reference/walk_forward/stale"
    target.mkdir(parents=True)
    (target / "portfolio_run_summary.json").write_text("invalid stale partial summary")
    payload = reference_replay_read_model(settings)
    assert payload["status"] == "INCOMPLETE"
    assert payload["summary"] is None
    assert payload["holdout_consumption"]["attempt_number"] == 2
    assert payload["holdout_consumption"]["protected_return_rows_read"] == 123
    assert payload["holdout_consumption"]["preserved_prior_states"] == 3


def test_reference_replay_read_model_rejects_missing_current_receipt_with_history(tmp_path):
    settings = _settings_with_v2(tmp_path)
    layout = V2Layout.beneath((tmp_path / "data").resolve())
    _holdout_receipt(layout, complete=True)
    (layout.manifests / "master_holdout_consumption.json").unlink()
    payload = reference_replay_read_model(settings)
    assert payload["status"] == "INVALID"
    assert payload["evaluation_stage"] == "walk-forward"
    assert payload["summary"] is None


def test_reference_replay_read_model_rejects_complete_receipt_without_summary(
    tmp_path,
) -> None:
    settings = _settings_with_v2(tmp_path)
    layout = V2Layout.beneath((tmp_path / "data").resolve())
    layout.manifests.mkdir(parents=True, exist_ok=True)
    _holdout_receipt(layout, complete=True)

    payload = reference_replay_read_model(settings)

    assert payload["status"] == "INVALID"
    assert payload["evaluation_stage"] == "walk-forward"
    assert payload["summary"] is None


def test_reference_replay_read_model_fails_closed_on_bound_artifact_tamper(tmp_path) -> None:
    target = (
        tmp_path
        / "strategy_lab"
        / "a33_b33_reference"
        / "development"
        / "2021-08-16_2026-05-11"
    )
    target.mkdir(parents=True)
    summary = {
        "contract_version": REFERENCE_PORTFOLIO_REPLAY_CONTRACT_VERSION,
        "portfolio_policy_fingerprint": reference_portfolio_policy_fingerprint(),
        "protected_master_return_rows_read": 0,
        "provider_writes": 0,
        "broker_writes": 0,
        "paper_submits": 0,
        "live_writes": 0,
    }
    summary.update(_operator_artifacts(target))
    (target / "portfolio_run_summary.json").write_text(
        json.dumps(summary), encoding="utf-8"
    )
    with (target / "portfolio_decisions.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("{}\n")

    payload = reference_replay_read_model(_settings_with_derived(tmp_path))
    assert payload["status"] == "INVALID"
    assert payload["summary"] is None
    assert payload["artifact_integrity"]["all_sha256_verified"] is False


def test_reference_replay_read_model_fails_closed_on_policy_drift(tmp_path) -> None:
    target = (
        tmp_path
        / "strategy_lab"
        / "a33_b33_reference"
        / "development"
        / "2021-08-16_2026-05-11"
    )
    target.mkdir(parents=True)
    (target / "portfolio_run_summary.json").write_text(
        json.dumps(
            {
                "contract_version": REFERENCE_PORTFOLIO_REPLAY_CONTRACT_VERSION,
                "portfolio_policy_fingerprint": "0" * 64,
            }
        ),
        encoding="utf-8",
    )
    payload = reference_replay_read_model(_settings_with_derived(tmp_path))
    assert payload["status"] == "INVALID"
    assert payload["summary"] is None
