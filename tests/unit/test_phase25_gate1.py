from __future__ import annotations

from datetime import date
from pathlib import Path

import packages.backtesting.phase25_gate1 as phase25_gate1_module
from packages.backtesting.phase25_gate0 import PHASE25_GATE0_REPORT_CONTRACT_VERSION
from packages.backtesting.phase25_gate1 import (
    Phase25Gate1ScopeInventory,
    classify_symbol_evidence,
)
from packages.backtesting.phase25_policy import (
    PHASE25_EXACT_PIT_REFERENCE_REQUIRED_FOR_AUTHORITATIVE_PHASE7_REPLAY,
    PHASE25_FUTURE_REFERENCE_METADATA_AUTHORITY_ALLOWED,
    PHASE25_PROVIDER_READS,
    PHASE25_PROXY_UNIVERSE_SUPPORT_AUTHORITY_ALLOWED,
    phase25_gate0_policy_fingerprint,
    phase25_gate1_policy_fingerprint,
)


def test_gate1_exact_first_seen_reference_classification() -> None:
    category, interval, bracketed = classify_symbol_evidence(
        reference_observation_count=2,
        reference_instrument_count=1,
        exact_first_seen_reference_count=1,
        exact_first_seen_classifiable_count=1,
        prior_or_same_reference_count=1,
        future_reference_count=1,
        metadata_variant_count=1,
        authoritative_interval_instrument_count=1,
    )
    assert category == "EXACT_FIRST_SEEN_REFERENCE"
    assert interval is True
    assert bracketed is True


def test_gate1_future_only_reference_never_becomes_authoritative() -> None:
    category, interval, bracketed = classify_symbol_evidence(
        reference_observation_count=3,
        reference_instrument_count=1,
        exact_first_seen_reference_count=0,
        exact_first_seen_classifiable_count=0,
        prior_or_same_reference_count=0,
        future_reference_count=3,
        metadata_variant_count=1,
        authoritative_interval_instrument_count=1,
    )
    assert category == "FUTURE_ONLY_REFERENCE"
    assert interval is True
    assert bracketed is False
    assert PHASE25_FUTURE_REFERENCE_METADATA_AUTHORITY_ALLOWED is False


def test_gate1_ambiguous_identity_fails_closed() -> None:
    category, interval, bracketed = classify_symbol_evidence(
        reference_observation_count=4,
        reference_instrument_count=2,
        exact_first_seen_reference_count=1,
        exact_first_seen_classifiable_count=1,
        prior_or_same_reference_count=2,
        future_reference_count=2,
        metadata_variant_count=1,
        authoritative_interval_instrument_count=2,
    )
    assert category == "AMBIGUOUS_LOCAL_IDENTITY"
    assert interval is False
    assert bracketed is False


def test_gate1_prior_reference_can_only_be_proxy_candidate_when_bracketed() -> None:
    category, interval, bracketed = classify_symbol_evidence(
        reference_observation_count=2,
        reference_instrument_count=1,
        exact_first_seen_reference_count=0,
        exact_first_seen_classifiable_count=0,
        prior_or_same_reference_count=1,
        future_reference_count=1,
        metadata_variant_count=1,
        authoritative_interval_instrument_count=1,
    )
    assert category == "PRIOR_REFERENCE_ONLY"
    assert interval is True
    assert bracketed is True
    assert PHASE25_PROXY_UNIVERSE_SUPPORT_AUTHORITY_ALLOWED is False


def test_gate1_binds_to_gate0_report_policy_fingerprint_field(monkeypatch) -> None:
    through_date = date(2026, 8, 21)
    gate0_path = Path("gate0-feasibility-inventory.json")
    report = {
        "contract_version": PHASE25_GATE0_REPORT_CONTRACT_VERSION,
        "through_date": through_date.isoformat(),
        "policy_fingerprint": phase25_gate0_policy_fingerprint(),
        "pass": True,
        "provider_reads": 0,
        "provider_writes": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "order_writes": 0,
        "paper_submits": 0,
        "live_writes": 0,
        "phase11_support_writes": 0,
        "protected_strategy_evidence_reads": 0,
    }

    class FakeGate0Inventory:
        def __init__(self, settings) -> None:
            self.settings = settings

        def report_path(self, requested_date: date) -> Path:
            assert requested_date == through_date
            return gate0_path

    monkeypatch.setattr(phase25_gate1_module, "Phase25Gate0Inventory", FakeGate0Inventory)
    monkeypatch.setattr(phase25_gate1_module, "_read_json", lambda path: report)

    inventory = object.__new__(Phase25Gate1ScopeInventory)
    inventory.settings = object()
    resolved_path, resolved_report = inventory._gate0_evidence(through_date)

    assert resolved_path == gate0_path
    assert resolved_report is report


def test_gate1_policy_keeps_authority_zero_and_exact_pit_required() -> None:
    assert PHASE25_PROVIDER_READS == 0
    assert PHASE25_FUTURE_REFERENCE_METADATA_AUTHORITY_ALLOWED is False
    assert PHASE25_PROXY_UNIVERSE_SUPPORT_AUTHORITY_ALLOWED is False
    assert PHASE25_EXACT_PIT_REFERENCE_REQUIRED_FOR_AUTHORITATIVE_PHASE7_REPLAY is True
    assert len(phase25_gate1_policy_fingerprint()) == 64
