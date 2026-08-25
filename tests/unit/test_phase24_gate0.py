from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

from packages.backtesting.phase24_gate0 import (
    evaluate_counterfactual_records,
    support_evidence_from_study,
)
from packages.backtesting.phase24_policy import (
    PHASE24_BROKER_READS,
    PHASE24_BROKER_WRITES,
    PHASE24_COUNTERFACTUAL_CURRENT_RULES_ARE_AUTHORITY,
    PHASE24_EXTERNAL_PROVIDER_READS,
    PHASE24_EXTERNAL_PROVIDER_WRITES,
    PHASE24_LIVE_WRITES,
    PHASE24_ORDER_WRITES,
    PHASE24_PAPER_SUBMITS,
    PHASE24_PHASE11_SUPPORT_REPLACEMENT_AUTHORITY,
)


def test_phase24_gate0_has_no_external_execution_or_support_replacement_authority() -> None:
    assert PHASE24_EXTERNAL_PROVIDER_READS is False
    assert PHASE24_EXTERNAL_PROVIDER_WRITES is False
    assert PHASE24_BROKER_READS is False
    assert PHASE24_BROKER_WRITES is False
    assert PHASE24_ORDER_WRITES is False
    assert PHASE24_PAPER_SUBMITS is False
    assert PHASE24_LIVE_WRITES is False
    assert PHASE24_PHASE11_SUPPORT_REPLACEMENT_AUTHORITY is False
    assert PHASE24_COUNTERFACTUAL_CURRENT_RULES_ARE_AUTHORITY is False


def test_gate0_support_evidence_exposes_only_selection_evidence() -> None:
    study = {
        "studies": [
            {
                "strategy_id": "momentum_long_v1",
                "support": {
                    "strategy_id": "momentum_long_v1",
                    "status": "MIXED",
                    "eligible_for_candidate_promotion": False,
                    "primary_cost_bps": 10.0,
                    "development_mean_return": 0.001,
                    "first_half_mean_return": 0.002,
                    "second_half_mean_return": -0.001,
                    "development_rows": 100,
                    "first_half_rows": 50,
                    "second_half_rows": 50,
                    "reason_codes": ["MIXED:TEST"],
                },
                "protected_confirmation": {"aggregate_by_cost_bps": {"10": {"mean_return": 99.0}}},
            }
        ]
    }
    evidence = support_evidence_from_study(study)
    encoded = json.dumps(evidence, sort_keys=True)
    assert len(evidence) == 1
    assert evidence[0]["status"] == "MIXED"
    assert evidence[0]["development_rows"] == 100
    assert "protected" not in encoded.lower()
    assert "99.0" not in encoded


def test_counterfactual_rule_fire_is_measured_but_never_authoritative() -> None:
    record = SimpleNamespace(
        instrument_id="test-instrument",
        ticker="TEST",
        as_of_date=date(2026, 8, 21),
        ml_probability_evidence=None,
        historical_support=(
            SimpleNamespace(strategy_id="momentum_long_v1", status="MIXED"),
        ),
        route_decisions=(
            SimpleNamespace(strategy_id="momentum_long_v1", eligible=True),
            SimpleNamespace(strategy_id="momentum_short_v1", eligible=False),
        ),
    )
    features = {
        "TEST": {
            "return_1": 0.02,
            "rsi_14": 60.0,
            "macd_hist_12_26_9": 0.5,
        }
    }
    rows, summary = evaluate_counterfactual_records((record,), features)
    assert len(rows) == 1
    assert rows[0]["strategy_id"] == "momentum_long_v1"
    assert rows[0]["historical_support_status"] == "MIXED"
    assert rows[0]["fired"] is True
    assert rows[0]["authoritative"] is False
    assert summary["eligible_route_evaluations"] == 1
    assert summary["counterfactual_fires"] == 1
    assert summary["candidates_with_counterfactual_fire"] == 1
