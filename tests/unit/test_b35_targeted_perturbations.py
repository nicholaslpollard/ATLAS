from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.backtesting.b35_development_replay import B35DevelopmentReplayError
from packages.backtesting.b35_targeted_perturbations import (
    B35_ACCEPTED_ROBUSTNESS_FINGERPRINT,
    TARGETED_PERTURBATION_FINGERPRINT,
    TARGETED_VARIANTS,
    _aggregate_group_outputs,
    _metric_template,
    _shift_setup_for_entry_delay,
    _validate_group_baseline_parity,
    ensure_targeted_authorization,
)
from packages.schemas.strategy import StrategyDirection
from packages.strategies.intraday_opening_pack import (
    B34_INTRADAY_PACK_CONTRACT,
    IntradaySetupResult,
)


def test_targeted_variant_contract_is_exact_and_finite() -> None:
    assert len(TARGETED_VARIANTS) == 27
    assert len({item.variant_id for item in TARGETED_VARIANTS}) == 27
    assert len(TARGETED_PERTURBATION_FINGERPRINT) == 64
    assert len(B35_ACCEPTED_ROBUSTNESS_FINGERPRINT) == 64

    by_family: dict[str, set[float]] = {}
    for item in TARGETED_VARIANTS:
        by_family.setdefault(item.family, set()).add(item.value)

    assert by_family == {
        "entry_delay_minutes": {0.0, 1.0, 2.0},
        "gap_threshold_multiplier": {0.9, 1.0, 1.1},
        "opening_range_minutes": {14.0, 15.0, 16.0},
        "premarket_relvol_threshold_multiplier": {0.9, 1.0, 1.1},
        "premarket_consolidation_range_multiplier": {0.9, 1.0, 1.1},
    }
    assert sum(item.baseline for item in TARGETED_VARIANTS) == 9


def test_entry_delay_shifts_signal_timestamp_without_rewriting_setup() -> None:
    signal = datetime(2024, 1, 3, 15, 0, tzinfo=UTC)
    setup = IntradaySetupResult(
        contract=B34_INTRADAY_PACK_CONTRACT,
        strategy_id="b34_opening_range_breakout_15m_v1",
        session_date="2024-01-03",
        ready=True,
        fired=True,
        direction=StrategyDirection.LONG.value,
        reason_codes=("OPENING_RANGE_BREAKOUT",),
        evidence={
            "opening_range_high": 10.0,
            "opening_range_low": 9.0,
            "breakout_bar_timestamp_utc": signal.isoformat(),
        },
    )

    unchanged = _shift_setup_for_entry_delay(setup, (), date(2024, 1, 3), 0)
    shifted = _shift_setup_for_entry_delay(setup, (), date(2024, 1, 3), 2)

    assert unchanged is setup
    assert shifted.strategy_id == setup.strategy_id
    assert shifted.direction == setup.direction
    assert shifted.evidence["opening_range_high"] == 10.0
    assert shifted.evidence["opening_range_low"] == 9.0
    assert datetime.fromisoformat(
        str(shifted.evidence["breakout_bar_timestamp_utc"])
    ) == signal + timedelta(minutes=2)
    assert shifted.evidence["intentional_entry_delay_minutes"] == 2


def test_baseline_parity_is_fail_closed() -> None:
    metrics = {item.variant_id: _metric_template(item) for item in TARGETED_VARIANTS}
    canonical = {
        strategy_id: {
            "evaluated_fired": 0,
            "comparable": 0,
            "noncomparable": 0,
        }
        for strategy_id in {
            item.strategy_id for item in TARGETED_VARIANTS
        }
    }
    _validate_group_baseline_parity(metrics, canonical)

    first_baseline = next(item for item in TARGETED_VARIANTS if item.baseline)
    metrics[first_baseline.variant_id]["fired"] = 1
    with pytest.raises(B35DevelopmentReplayError, match="baseline parity failed"):
        _validate_group_baseline_parity(metrics, canonical)


def test_group_aggregation_preserves_exact_counts_sessions_and_cost_means(
    tmp_path: Path,
) -> None:
    target_variant = TARGETED_VARIANTS[0]
    paths = []
    for index, offset in enumerate((0, 2)):
        metrics = [_metric_template(item) for item in TARGETED_VARIANTS]
        target = next(
            item for item in metrics if item["variant_id"] == target_variant.variant_id
        )
        target["fired"] = 1
        target["comparable"] = 1
        target["wins_50bps"] = 1
        target["gross_return_sum"] = 0.01 + index * 0.01
        target["risk_multiple_sum"] = 0.5 + index * 0.5
        target["mfe_sum"] = 0.02 + index * 0.01
        target["mae_sum"] = -0.01 - index * 0.01
        target["net_return_sums_by_cost_bps"] = {
            "0": 0.01 + index * 0.01,
            "10": 0.009 + index * 0.01,
            "25": 0.0075 + index * 0.01,
            "50": 0.005 + index * 0.01,
            "100": 0.0 + index * 0.01,
        }
        target["status_counts"] = {"COMPARABLE": 1}
        target["direction_counts"] = {"LONG": 1}
        target["session_bitset_hex"] = hex(1 << offset)
        target["symbols"] = [f"S{index}"]
        path = tmp_path / f"group_{index}.json"
        path.write_text(json.dumps({"metrics": metrics}), encoding="utf-8")
        paths.append(path)

    result = _aggregate_group_outputs(paths)
    row = next(item for item in result if item["variant_id"] == target_variant.variant_id)
    assert row["fired"] == 2
    assert row["comparable"] == 2
    assert row["unique_sessions"] == 2
    assert row["unique_instruments"] == 2
    assert row["win_rate_50bps"] == 1.0
    assert row["mean_gross_return"] == pytest.approx(0.015)
    assert row["mean_risk_multiple"] == pytest.approx(0.75)
    assert row["mean_net_return_by_cost_bps"]["50"] == pytest.approx(0.01)


def test_targeted_authorization_is_self_hash_bound_and_reusable(tmp_path: Path) -> None:
    plan = SimpleNamespace(
        source_fingerprint="a" * 64,
        start_session=date(2016, 1, 4),
        end_session=date(2026, 4, 30),
    )
    path = tmp_path / "authorization.json"
    first = ensure_targeted_authorization(
        path,
        plan=plan,
        split_evidence_fingerprint="b" * 64,
        development_authorization_id="c" * 64,
    )
    second = ensure_targeted_authorization(
        path,
        plan=plan,
        split_evidence_fingerprint="b" * 64,
        development_authorization_id="c" * 64,
    )
    assert first == second
    assert len(str(first["authorization_id"])) == 64
    assert first["strategy_promotion"] is False
    assert first["selector_refit"] is False
    assert first["consumed_master_rows_permitted"] == 0
    assert first["future_blind_rows_permitted"] == 0
