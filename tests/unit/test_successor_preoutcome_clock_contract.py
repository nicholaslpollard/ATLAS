from __future__ import annotations

import inspect

from packages.features.successor_practitioner import (
    SUCCESSOR_PRACTITIONER_FEATURE_CONTRACT_VERSION,
    successor_practitioner_feature_fingerprint,
)
from packages.strategies.successor_implementation_bundle import (
    frozen_successor_implementation_bundle,
)
from packages.strategies.successor_intraday_rules import (
    SUCCESSOR_INTRADAY_RULE_CONTRACT,
    evaluate_gap_quality_condition_long,
    evaluate_orb_stocks_in_play_5m,
    evaluate_premarket_relvol_quality,
    successor_intraday_rule_fingerprint,
)


def test_quality_evaluator_apis_make_earlier_information_clocks_explicit() -> None:
    gap_parameters = inspect.signature(evaluate_gap_quality_condition_long).parameters
    orb_parameters = inspect.signature(evaluate_orb_stocks_in_play_5m).parameters
    premarket_parameters = inspect.signature(evaluate_premarket_relvol_quality).parameters

    # Gap and ORB prices are derived from the exact closed opening bars. A later
    # caller therefore cannot inject a later current_price into an earlier gate.
    assert "bars" in gap_parameters
    assert "current_regular_open" not in gap_parameters
    assert "current_price" not in gap_parameters
    assert "current_price" not in orb_parameters

    # Breakout participation is keyed to the exact breakout timestamp rather
    # than supplied as one free scalar that could be back-applied to older bars.
    assert "breakout_same_time_relvol" not in premarket_parameters
    assert "breakout_same_time_relvol_by_timestamp" in premarket_parameters


def test_semantic_clock_repairs_change_bound_scientific_identity() -> None:
    assert "exact-pivot-cross" in SUCCESSOR_PRACTITIONER_FEATURE_CONTRACT_VERSION
    assert "frozen-quality-clocks" in SUCCESSOR_INTRADAY_RULE_CONTRACT

    bundle = frozen_successor_implementation_bundle()
    assert bundle["daily_feature_fingerprint"] == successor_practitioner_feature_fingerprint()
    assert bundle["intraday_rule_fingerprint"] == successor_intraday_rule_fingerprint()
    assert bundle["authority"]["outcome_access_authorized_by_this_bundle"] is False
    assert bundle["authority"]["paper_authority"] is False
    assert bundle["authority"]["live_authority"] is False
