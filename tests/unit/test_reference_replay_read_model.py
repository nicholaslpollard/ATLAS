from __future__ import annotations

import json

from packages.backtesting.reference_portfolio_policy import (
    reference_portfolio_policy_fingerprint,
)
from packages.core.settings import load_settings
from packages.performance.reference_replay_read_model import reference_replay_read_model
from packages.schemas.reference_portfolio import REFERENCE_PORTFOLIO_REPLAY_CONTRACT_VERSION


def _settings_with_derived(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(update={"derived": tmp_path})
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


def test_reference_replay_read_model_reports_not_run_without_artifacts(tmp_path) -> None:
    payload = reference_replay_read_model(_settings_with_derived(tmp_path))
    assert payload["status"] == "NOT_RUN"
    assert payload["summary"] is None
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
        "completed_positions": 2,
        "admitted_positions": 2,
        "total_transaction_cost": 12.5,
        "protected_master_return_rows_read": 0,
        "provider_writes": 0,
        "broker_writes": 0,
        "paper_submits": 0,
        "live_writes": 0,
    }
    (target / "portfolio_run_summary.json").write_text(
        json.dumps(summary), encoding="utf-8"
    )
    (target / "portfolio_position_outcomes.jsonl").write_text(
        json.dumps({"ticker": "TEST", "net_pnl": 10.0}) + "\n",
        encoding="utf-8",
    )
    (target / "portfolio_equity_curve.jsonl").write_text(
        json.dumps({"session": "2025-01-02", "equity": 101_000.0}) + "\n",
        encoding="utf-8",
    )

    payload = reference_replay_read_model(_settings_with_derived(tmp_path))
    assert payload["status"] == "AVAILABLE"
    assert payload["summary"] == summary
    assert payload["recent_position_outcomes"][0]["ticker"] == "TEST"
    assert payload["equity_curve_tail"][0]["equity"] == 101_000.0


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
