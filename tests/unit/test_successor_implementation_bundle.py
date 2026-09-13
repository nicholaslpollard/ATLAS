from __future__ import annotations

from packages.features.successor_practitioner import successor_practitioner_feature_fingerprint
from packages.strategies.successor_implementation_bundle import (
    SUCCESSOR_IMPLEMENTATION_BUNDLE_FINGERPRINT,
    frozen_successor_implementation_bundle,
)
from packages.strategies.successor_intraday_rules import successor_intraday_rule_fingerprint
from packages.strategies.successor_practitioner_rules import (
    SUCCESSOR_POLICY_IMPLEMENTATION_FINGERPRINT,
)


def test_successor_implementation_bundle_binds_all_preoutcome_layers() -> None:
    bundle = frozen_successor_implementation_bundle()

    assert bundle["family_count"] == 21
    assert bundle["retained_family_count"] == 10
    assert bundle["new_family_count"] == 11
    assert bundle["b35_challenger_count"] == 4
    assert bundle["policy_implementation_fingerprint"] == SUCCESSOR_POLICY_IMPLEMENTATION_FINGERPRINT
    assert bundle["daily_feature_fingerprint"] == successor_practitioner_feature_fingerprint()
    assert bundle["intraday_rule_fingerprint"] == successor_intraday_rule_fingerprint()
    assert bundle["fingerprint"] == SUCCESSOR_IMPLEMENTATION_BUNDLE_FINGERPRINT
    assert len(SUCCESSOR_IMPLEMENTATION_BUNDLE_FINGERPRINT) == 64
    int(SUCCESSOR_IMPLEMENTATION_BUNDLE_FINGERPRINT, 16)


def test_successor_implementation_bundle_grants_no_outcome_or_trading_authority() -> None:
    authority = frozen_successor_implementation_bundle()["authority"]

    assert authority == {
        "strategy_authority": "RESEARCH",
        "outcome_access_authorized_by_this_bundle": False,
        "consumed_master_access": False,
        "future_blind_access": False,
        "provider_calls": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "paper_authority": False,
        "live_authority": False,
        "promotion_authority": False,
    }
