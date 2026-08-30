from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_FINGERPRINT = "4bf51f02fb74a219609e2affef3319b24b7c98eb06fa9d88e405ae4f7448434c"
EXPECTED_SOURCE_REPAIR = "78bf3f18368114a5a6073e8a4d66a0c13ee29a5da78b8adeb1d71b1f10c6f78c"


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _require(text: str, token: str, label: str) -> None:
    if token not in text:
        raise AssertionError(f"missing {label}: {token}")


def _forbid(text: str, token: str, label: str) -> None:
    if token in text:
        raise AssertionError(f"forbidden {label}: {token}")


def main() -> int:
    policy_path = "packages/backtesting/alpha_gate_beneficial_ownership_scientific_policy.py"
    predictor_path = "packages/backtesting/alpha_gate_beneficial_ownership_predictor.py"
    doc_path = "docs/alpha_gate_sec_beneficial_ownership_scientific_contract.md"
    tests_path = "tests/unit/test_alpha_gate_beneficial_ownership_scientific_policy.py"

    policy = _read(policy_path)
    predictor = _read(predictor_path)
    doc = _read(doc_path)
    tests = _read(tests_path)
    for path, text in ((policy_path, policy), (predictor_path, predictor), (tests_path, tests)):
        ast.parse(text, filename=path)

    from packages.backtesting.alpha_gate_beneficial_ownership_scientific_policy import (
        BENEFICIAL_OWNERSHIP_AMENDMENTS_PERFORMANCE_ELIGIBLE,
        BENEFICIAL_OWNERSHIP_HYPOTHESES,
        BENEFICIAL_OWNERSHIP_MULTIPLE_TESTING_METHOD,
        BENEFICIAL_OWNERSHIP_PHASE33_AUTHORITY,
        BENEFICIAL_OWNERSHIP_PROTECTED_RETURNS_BEFORE_FINALIST_ALLOWED,
        BENEFICIAL_OWNERSHIP_RUNNER_UP_SUBSTITUTION_ALLOWED,
        BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT,
        beneficial_ownership_scientific_fingerprint,
    )

    if BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT != EXPECTED_FINGERPRINT:
        raise AssertionError("beneficial-ownership scientific fingerprint constant drifted")
    if beneficial_ownership_scientific_fingerprint() != EXPECTED_FINGERPRINT:
        raise AssertionError("beneficial-ownership scientific fingerprint function drifted")
    if len(BENEFICIAL_OWNERSHIP_HYPOTHESES) != 4:
        raise AssertionError("beneficial-ownership family is not exactly four hypotheses")
    if BENEFICIAL_OWNERSHIP_AMENDMENTS_PERFORMANCE_ELIGIBLE is not False:
        raise AssertionError("amendments gained performance eligibility")
    if BENEFICIAL_OWNERSHIP_MULTIPLE_TESTING_METHOD != "HOLM_BONFERRONI_GLOBAL_4":
        raise AssertionError("global multiplicity method drifted")
    if BENEFICIAL_OWNERSHIP_RUNNER_UP_SUBSTITUTION_ALLOWED is not False:
        raise AssertionError("runner-up substitution was enabled")
    if BENEFICIAL_OWNERSHIP_PROTECTED_RETURNS_BEFORE_FINALIST_ALLOWED is not False:
        raise AssertionError("protected returns were opened before finalist selection")
    if BENEFICIAL_OWNERSHIP_PHASE33_AUTHORITY is not False:
        raise AssertionError("scientific contract granted Phase33 authority")

    for token in (
        EXPECTED_FINGERPRINT,
        EXPECTED_SOURCE_REPAIR,
        "initial_13d_5_to_10_long",
        "initial_13d_10_plus_long",
        "initial_13g_5_to_10_long",
        "initial_13g_10_plus_long",
        "MAX_FINITE_COVER_PAGE_PERCENT_OF_CLASS_ACROSS_REPORTING_PERSONS_NO_SUMMATION",
        "FIRST_XNYS_SESSION_OPEN_STRICTLY_AFTER_SEC_ACCEPTANCE",
        "CLOSE_63_XNYS_SESSIONS_AFTER_DECISION",
        "HOLM_BONFERRONI_GLOBAL_4",
        "highest_primary_selection_LCB_then_candidate_id",
    ):
        _require(policy, token, "scientific-policy invariant")
        _require(doc, token, "documented scientific invariant")

    _require(predictor, "percentOfClass|classPercent", "structured percent parser")
    _require(predictor, "PERCENT\\s+OF\\s+CLASS", "legacy percent parser")
    _require(predictor, "max(percentages)", "no-summation ownership rule")
    _require(predictor, "source_repair_fingerprint", "accepted source-repair lineage")
    _require(predictor, '"target_outcome_rows_read": 0', "source-only predictor blindness")
    _require(predictor, '"protected_return_rows_read": 0', "protected blindness")

    for forbidden in (
        "read_parquet",
        "future_close",
        "forward_return",
        "packages.execution",
        "packages.brokers",
        ".place_order(",
        ".submit_order(",
    ):
        _forbid(policy, forbidden, "scientific pre-outcome dependency")
        _forbid(predictor, forbidden, "predictor pre-outcome dependency")

    _require(tests, "test_structured_13d_percent_parser_uses_max_not_sum", "13D parser regression")
    _require(tests, "test_structured_13g_class_percent_parser", "13G parser regression")
    _require(tests, "test_legacy_percent_parser_handles_13d_and_13g_cover_labels", "legacy parser regression")

    print("ATLAS SEC beneficial-ownership scientific contract: PASS")
    print(f"- scientific fingerprint: {EXPECTED_FINGERPRINT}")
    print(f"- accepted source-repair fingerprint: {EXPECTED_SOURCE_REPAIR}")
    print("- exactly four non-overlapping initial 13D/13G LONG ownership buckets are frozen")
    print("- ownership percent uses maximum reported cover-page value; affiliated values are never summed")
    print("- 63-session outcome, costs, chronology, dependence, Holm multiplicity, winner/finalist and protected rules are frozen")
    print("- predictor remains source-only; protected returns and Phase33 authority remain closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
