import json
from datetime import date

import pytest

from packages.backtesting.alpha_gate_finra_short_interest_pit_audit import (
    FINRA_SHORT_INTEREST_FROZEN_SETTLEMENT_DATES,
    FINRA_SHORT_INTEREST_PIT_AUDIT_CONTRACT,
    FINRA_SHORT_INTEREST_PIT_AUDIT_FINGERPRINT,
)
from packages.backtesting.alpha_gate_finra_short_interest_pit_evidence_binding_repair import (
    FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_REPORT_SHA256,
    FINRA_SHORT_INTEREST_PIT_EVIDENCE_BINDING_REPAIR_CONTRACT,
    FINRA_SHORT_INTEREST_PIT_EVIDENCE_BINDING_REPAIR_FINGERPRINT,
    pit_evidence_binding_fingerprint,
    validate_accepted_pit_evidence,
)
from packages.backtesting.alpha_gate_finra_short_interest_predictor import (
    FINRAShortInterestPredictorError,
    _average_tie_percentiles,
    _candidate,
    frozen_settlement_dates,
)


def test_frozen_finra_settlement_schedule_has_expected_boundaries_and_anchors() -> None:
    dates = frozen_settlement_dates()
    assert len(dates) == 116
    assert len(set(dates)) == 116
    assert dates[0] == date(2021, 6, 30)
    assert dates[-1] == date(2026, 4, 15)
    assert date(2026, 3, 13) in dates
    assert date(2026, 3, 31) in dates
    assert date(2026, 4, 15) in dates


def test_average_tie_percentiles_are_deterministic() -> None:
    assert _average_tie_percentiles([1.0, 2.0, 2.0, 4.0]) == (
        0.0,
        0.5,
        0.5,
        1.0,
    )
    assert _average_tie_percentiles([5.0]) == (0.5,)
    assert _average_tie_percentiles([]) == ()


def test_candidate_classification_uses_exact_frozen_boundaries() -> None:
    assert _candidate(0.90, 0.80) == (
        "rapid_short_build_crowded_short",
        "SHORT",
    )
    assert _candidate(0.90, 0.799999) == (
        "rapid_short_build_non_crowded_short",
        "SHORT",
    )
    assert _candidate(0.10, 0.80) == (
        "rapid_short_cover_crowded_long",
        "LONG",
    )
    assert _candidate(0.10, 0.799999) == (
        "rapid_short_cover_non_crowded_long",
        "LONG",
    )
    assert _candidate(0.100001, 0.95) is None
    assert _candidate(0.899999, 0.95) is None


def _accepted_pit_report() -> dict[str, object]:
    gates = {
        "accepted_feasibility_evidence_bound": True,
        "all_12_source_files_reacquired": True,
        "publication_anchors_exact": True,
        "source_symbol_exchange_unique": True,
        "immutable_exchange_listed_rows_min": True,
        "pit_eligible_rows_min": True,
        "unique_pit_instruments_min": True,
        "files_with_2500_pit_rows_min": True,
        "revised_rows_never_admitted": True,
        "split_rows_never_admitted": True,
    }
    return {
        "contract_version": FINRA_SHORT_INTEREST_PIT_AUDIT_CONTRACT,
        "pit_audit_fingerprint": FINRA_SHORT_INTEREST_PIT_AUDIT_FINGERPRINT,
        "status": "PIT_AUDIT_PASS",
        "pass": True,
        "accepted_feasibility_report": {
            "sha256": FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_REPORT_SHA256
        },
        "alpha_hypotheses_frozen": False,
        "performance_evaluated": False,
        "target_outcome_rows_read": 0,
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
        "finra_source_files_read": 12,
        "massive_reference_snapshots_read": 24,
        "provider_writes_performed": 0,
        "broker_reads_performed": 0,
        "broker_writes_performed": 0,
        "order_writes_performed": 0,
        "paper_submits_performed": 0,
        "live_writes_performed": 0,
        "automation_writes_performed": 0,
        "automatic_broker_failover": False,
        "immutable_exchange_listed_rows": 136731,
        "pit_eligible_rows": 63761,
        "unique_pit_instruments": 8054,
        "files_with_2500_pit_rows": 12,
        "status_counts": {
            "EXCLUDED_REVISION_FLAG": 542,
            "EXCLUDED_STOCK_SPLIT_FLAG": 302,
            "IDENTITY_CONTINUITY_MISMATCH": 33,
            "IMMUTABLE_EXCHANGE_LISTED": 136731,
            "NO_DECISION_ACTIVE_CS_EXACT_EXCHANGE": 256,
            "NO_SETTLEMENT_ACTIVE_CS_EXACT_EXCHANGE": 72681,
            "PIT_ELIGIBLE": 63761,
        },
        "gates": gates,
        "file_reports": [
            {
                "settlement_date": settlement,
                "source_sha256": "a" * 64,
            }
            for settlement in FINRA_SHORT_INTEREST_FROZEN_SETTLEMENT_DATES
        ],
        "failures": [],
    }


def test_pit_evidence_binding_repairs_feasibility_hash_mislabel_without_changing_science(
    tmp_path,
) -> None:
    report = _accepted_pit_report()
    assert (
        FINRA_SHORT_INTEREST_PIT_EVIDENCE_BINDING_REPAIR_CONTRACT
        == "alpha-gate-finra-short-interest-pit-evidence-binding-repair-v1-semantic-pass-evidence-no-market-outcomes"
    )
    assert (
        pit_evidence_binding_fingerprint(report)
        == FINRA_SHORT_INTEREST_PIT_EVIDENCE_BINDING_REPAIR_FINGERPRINT
        == "12491a2008d6d629e55d395ad3228ea069e538254a64b03d9046e9cc5ebe169a"
    )
    path = tmp_path / "source_audit.json"
    path.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")
    evidence = validate_accepted_pit_evidence(path)
    assert evidence["binding_fingerprint"] == FINRA_SHORT_INTEREST_PIT_EVIDENCE_BINDING_REPAIR_FINGERPRINT
    assert evidence["report_sha256"] != FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_REPORT_SHA256


def test_pit_evidence_binding_fails_closed_on_accepted_count_drift(tmp_path) -> None:
    report = _accepted_pit_report()
    report["pit_eligible_rows"] = 63760
    path = tmp_path / "source_audit.json"
    path.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(
        FINRAShortInterestPredictorError,
        match="accepted PIT semantic evidence binding drifted",
    ):
        validate_accepted_pit_evidence(path)
