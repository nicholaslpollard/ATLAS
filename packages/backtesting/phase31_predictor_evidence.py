from __future__ import annotations

from typing import Any, Mapping


PHASE31_PREDICTOR_EVIDENCE_CONTRACT_VERSION = (
    "phase31-predictor-evidence-v1-first-accepted-outcome-blind-form4-construction"
)
PHASE31_PREDICTOR_EVIDENCE_POLICY_FINGERPRINT = (
    "e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67"
)
PHASE31_PREDICTOR_EVIDENCE_AUTHORITATIVE_ROWS = 2_992_608
PHASE31_PREDICTOR_EVIDENCE_QUALIFIED_ACCESSIONS = 103_773
PHASE31_PREDICTOR_EVIDENCE_RESOLVED_EVENTS = 5_870
PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_ROWS = 5_400
PHASE31_PREDICTOR_EVIDENCE_PROTECTED_ROWS = 343
PHASE31_PREDICTOR_EVIDENCE_AUTHORITATIVE_LINEAGE_SHA256 = (
    "a9a385828b436fde7bf2297d1f8b987c4899eaff7500d79fd0b6c4abf6de7918"
)
PHASE31_PREDICTOR_EVIDENCE_IDENTITY_INTERVAL_SHA256 = (
    "beabae4416f8444a5a062d3c3d49cdab46dec7919a545850ac0808ed94cfe3de"
)
PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_SHA256 = (
    "a82ff3114febc0c6f7c13d5f045549b714edbf0fd66157ef93853be9ae90c49f"
)
PHASE31_PREDICTOR_EVIDENCE_PROTECTED_SHA256 = (
    "d3bcd2696463ec1e384919007a36570475f8cb0bf1e393f109f0accd24224e27"
)
PHASE31_PREDICTOR_EVIDENCE_CANDIDATE_MEMBERSHIP = {
    "clustered_open_market_purchase_long": 1009,
    "clustered_open_market_sale_short": 1724,
    "open_market_purchase_long": 2482,
    "open_market_sale_short": 3261,
}
PHASE31_PREDICTOR_EVIDENCE_EXCLUSIONS = {
    "ACQUIRED_DISPOSED_MISMATCH": 473,
    "AFF_10B5_ONE_TRUE": 37170,
    "CONTRADICTORY_PURCHASE_SALE_TICKER_SESSION": 1014,
    "EQUITY_SWAP_TRUE": 27,
    "NOT_SUBJECT_TO_SECTION16_TRUE": 1636,
    "NO_DECISION_SESSION_IN_FROZEN_GRID": 117,
    "NO_SECTION16_ROLE": 1645,
    "NO_T20_EXIT_IN_FROZEN_GRID": 963,
    "NO_TRANSACTION_ROWS": 1568,
    "OWNER_CIK_INCONSISTENT": 9824,
    "PIT_IDENTITY_INTERVAL_DOES_NOT_COVER_EXIT": 50,
    "PIT_IDENTITY_NOT_RESOLVED": 71144,
    "PRICE_NOT_POSITIVE": 1014,
    "SECURITY_TYPE_INELIGIBLE": 2642,
    "SHARES_NOT_POSITIVE": 270,
    "TICKER_ASSOCIATION_NOT_EXACTLY_ONE": 33635,
    "TRANSACTION_CODE_NOT_PURE_P_OR_S": 707504,
}


def phase31_predictor_evidence_public_dict() -> dict[str, object]:
    return {
        "evidence_contract_version": PHASE31_PREDICTOR_EVIDENCE_CONTRACT_VERSION,
        "phase31_policy_fingerprint": PHASE31_PREDICTOR_EVIDENCE_POLICY_FINGERPRINT,
        "authoritative_rows_scanned": PHASE31_PREDICTOR_EVIDENCE_AUTHORITATIVE_ROWS,
        "qualified_accessions_before_session_identity": PHASE31_PREDICTOR_EVIDENCE_QUALIFIED_ACCESSIONS,
        "resolved_noncontradictory_events_all_signal_history": PHASE31_PREDICTOR_EVIDENCE_RESOLVED_EVENTS,
        "development_predictor_rows": PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_ROWS,
        "protected_predictor_rows": PHASE31_PREDICTOR_EVIDENCE_PROTECTED_ROWS,
        "candidate_membership_rows": dict(PHASE31_PREDICTOR_EVIDENCE_CANDIDATE_MEMBERSHIP),
        "exclusion_counts": dict(PHASE31_PREDICTOR_EVIDENCE_EXCLUSIONS),
        "authoritative_lineage_sha256": PHASE31_PREDICTOR_EVIDENCE_AUTHORITATIVE_LINEAGE_SHA256,
        "identity_interval_sha256": PHASE31_PREDICTOR_EVIDENCE_IDENTITY_INTERVAL_SHA256,
        "development_sha256": PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_SHA256,
        "protected_sha256": PHASE31_PREDICTOR_EVIDENCE_PROTECTED_SHA256,
        "target_outcome_rows_read": 0,
        "protected_return_rows_read": 0,
        "provider_writes": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "order_writes": 0,
        "paper_submits": 0,
        "live_writes": 0,
        "automation_writes": 0,
    }


def validate_phase31_predictor_report(report: Mapping[str, Any]) -> None:
    expected = phase31_predictor_evidence_public_dict()
    for field, value in expected.items():
        if field == "evidence_contract_version":
            continue
        actual = report.get(field)
        if field in {"candidate_membership_rows", "exclusion_counts"}:
            actual = dict(actual) if isinstance(actual, Mapping) else actual
        if actual != value:
            raise ValueError(
                f"Phase31 frozen predictor evidence mismatch for {field}: "
                f"{actual!r} != {value!r}"
            )
    if report.get("pass") is not True:
        raise ValueError("Phase31 frozen predictor report is not passing")
