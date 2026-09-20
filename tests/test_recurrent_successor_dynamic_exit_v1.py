from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from packages.backtesting.recurrent_successor_daily_exit_regime_robustness_contract import (
    RECURRENT_SUCCESSOR_DAILY_EXIT_REGIME_ROBUSTNESS_CONTRACT_FINGERPRINT,
)
from packages.backtesting.recurrent_successor_daily_exit_sweep import DailyPathCase
from packages.backtesting.recurrent_successor_dynamic_exit_v1 import (
    RecurrentSuccessorDynamicExitV1Error,
    _choose_action,
    _source_static_regime_summary,
)
from packages.backtesting.recurrent_successor_dynamic_exit_v1_contract import (
    ABSTAIN_ACTION_ID,
    CONTEXT_FALLBACK_HIERARCHY,
    DYNAMIC_EXIT_ACTIONS,
    MIN_TRAINING_CASES,
    RECURRENT_SUCCESSOR_DYNAMIC_EXIT_V1_CONTRACT_FINGERPRINT,
    SOURCE_STATIC_REGIME_RUN_FINGERPRINT,
    dynamic_exit_action_id,
    recurrent_successor_dynamic_exit_v1_manifest,
)
from packages.backtesting.recurrent_successor_outcome_replay import (
    SelectedReplayOpportunity,
)


def _opportunity(
    *,
    index: int,
    fold_id: int,
    session: date,
    policy_id: str = "policy_a",
) -> SelectedReplayOpportunity:
    decision = datetime(
        session.year,
        session.month,
        session.day,
        21,
        0,
        tzinfo=UTC,
    )
    return SelectedReplayOpportunity(
        opportunity_id=f"op_{index}",
        fold_id=fold_id,
        policy_id=policy_id,
        economic_family_id="family_a",
        native_timeframe="1d",
        instrument_id=f"instrument_{index % 20}",
        ticker=f"T{index % 20}",
        signal_session=session,
        direction="LONG",
        fallback_level=1,
        selector_score=1.0,
        primary_net_return=0.01,
        gross_return=0.011,
        liquidity_bucket="GE_250M",
        decision_utc=decision,
        entry_utc=decision + timedelta(days=1),
        exit_utc=decision + timedelta(days=5),
        round_trip_cost_bps=10.0,
        training_start=session - timedelta(days=730),
        training_end=session - timedelta(days=1),
        training_sample_size=100,
        training_mean_gross_return=0.01,
        training_p10_gross_return=-0.02,
        training_p25_gross_return=-0.01,
        training_median_gross_return=0.005,
        training_p75_gross_return=0.02,
        training_p90_gross_return=0.03,
        training_probability_positive_gross=0.55,
        training_probability_positive_net=0.52,
        training_mean_mfe=0.03,
        training_mean_mae=0.02,
        training_max_abs_excursion=0.08,
        training_median_holding_minutes=None,
        source_analysis_fingerprint="a" * 64,
        market_direction_alignment="ALIGNED",
        market_volatility_state="NORMAL",
        higher_timeframe_ticker_trend="UP",
        realized_volatility_bucket="25_TO_50PCT",
        execution_liquidity_quality="HIGH",
    )


def _case(
    *,
    index: int,
    fold_id: int,
    session: date,
) -> DailyPathCase:
    return DailyPathCase(
        opportunity=_opportunity(
            index=index,
            fold_id=fold_id,
            session=session,
        ),
        bars=(),
        prior_path_evidence=None,  # not read by selector choice logic
    )


def test_dynamic_exit_contract_has_bounded_actions_and_abstain() -> None:
    manifest = recurrent_successor_dynamic_exit_v1_manifest()
    assert (
        manifest["fingerprint"]
        == RECURRENT_SUCCESSOR_DYNAMIC_EXIT_V1_CONTRACT_FINGERPRINT
    )
    assert len(DYNAMIC_EXIT_ACTIONS) == 6
    assert ABSTAIN_ACTION_ID == "ABSTAIN"
    assert all(target >= stop * 1.5 for stop, target in DYNAMIC_EXIT_ACTIONS)
    assert len(CONTEXT_FALLBACK_HIERARCHY) == 5
    assert manifest["anti_lookahead"][
        "current_case_future_path_may_influence_selection"
    ] is False
    assert manifest["authority"]["paper_authority"] is False
    assert manifest["authority"]["live_authority"] is False


def _static_summary_path(project_root: Path) -> Path:
    return (
        project_root
        / "data"
        / "research"
        / "recurrent_successor_daily_exit_regime_robustness"
        / RECURRENT_SUCCESSOR_DAILY_EXIT_REGIME_ROBUSTNESS_CONTRACT_FINGERPRINT[:16]
        / SOURCE_STATIC_REGIME_RUN_FINGERPRINT[:16]
        / "regime_robustness_summary.json"
    )


def test_dynamic_exit_requires_exact_static_regime_run(tmp_path: Path) -> None:
    path = _static_summary_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "status": "COMPLETE_RETROSPECTIVE_DAILY_EXIT_REGIME_ROBUSTNESS",
        "contract_fingerprint": (
            RECURRENT_SUCCESSOR_DAILY_EXIT_REGIME_ROBUSTNESS_CONTRACT_FINGERPRINT
        ),
        "run_fingerprint": SOURCE_STATIC_REGIME_RUN_FINGERPRINT,
        "report_fingerprint": "b" * 64,
    }
    path.write_text(json.dumps(summary), encoding="utf-8")
    observed = _source_static_regime_summary(tmp_path)
    assert observed["run_fingerprint"] == SOURCE_STATIC_REGIME_RUN_FINGERPRINT

    summary["run_fingerprint"] = "c" * 64
    path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(
        RecurrentSuccessorDynamicExitV1Error,
        match="run fingerprint drifted",
    ):
        _source_static_regime_summary(tmp_path)


def test_selector_uses_prior_fold_outcomes_only_and_ignores_current_outcome() -> None:
    start = date(2024, 1, 2)
    cases = [
        _case(
            index=index,
            fold_id=1,
            session=start + timedelta(days=index // 2),
        )
        for index in range(MIN_TRAINING_CASES)
    ]
    current_index = len(cases)
    cases.append(
        _case(
            index=current_index,
            fold_id=2,
            session=start + timedelta(days=100),
        )
    )

    outcomes: dict[tuple[int, str], float] = {}
    winning_action = dynamic_exit_action_id(0.02, 0.05)
    for index in range(MIN_TRAINING_CASES):
        for stop_fraction, target_fraction in DYNAMIC_EXIT_ACTIONS:
            action_id = dynamic_exit_action_id(stop_fraction, target_fraction)
            outcomes[(index, action_id)] = (
                0.02 if action_id == winning_action else -0.01
            )

    first = _choose_action(
        cases=cases,
        current_index=current_index,
        training_indexes=tuple(range(MIN_TRAINING_CASES)),
        outcomes=outcomes,
    )
    assert first.action_id == winning_action
    assert first.training_fold_max == 1
    assert first.training_cutoff_session < cases[current_index].opportunity.signal_session

    # The current opportunity's realized path is deliberately absent from the
    # selector input. Even an extreme current outcome cannot alter the choice.
    outcomes[(current_index, winning_action)] = -0.99
    second = _choose_action(
        cases=cases,
        current_index=current_index,
        training_indexes=tuple(range(MIN_TRAINING_CASES)),
        outcomes=outcomes,
    )
    assert second == first


def test_selector_abstains_when_all_supported_actions_have_negative_lcb() -> None:
    start = date(2024, 1, 2)
    cases = [
        _case(
            index=index,
            fold_id=1,
            session=start + timedelta(days=index // 2),
        )
        for index in range(MIN_TRAINING_CASES)
    ]
    current_index = len(cases)
    cases.append(
        _case(
            index=current_index,
            fold_id=2,
            session=start + timedelta(days=100),
        )
    )
    outcomes = {
        (index, dynamic_exit_action_id(stop, target)): -0.01
        for index in range(MIN_TRAINING_CASES)
        for stop, target in DYNAMIC_EXIT_ACTIONS
    }
    choice = _choose_action(
        cases=cases,
        current_index=current_index,
        training_indexes=tuple(range(MIN_TRAINING_CASES)),
        outcomes=outcomes,
    )
    assert choice.action_id == ABSTAIN_ACTION_ID
    assert choice.reason == "NO_SUPPORTED_ACTION_HAS_POSITIVE_ROBUST_LCB"
