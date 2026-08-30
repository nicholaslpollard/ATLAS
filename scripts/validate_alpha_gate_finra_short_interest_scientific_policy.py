from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_CONTRACT = "alpha-gate-finra-short-interest-scientific-v1-four-position-change-crowding-buckets"
EXPECTED_FINGERPRINT = "0b32d59677e86544777807525cd4aba13dd36fd0fcfd7744458556205561d13f"
EXPECTED_PIT_FINGERPRINT = "ffdb7389ceae73f31a3781a79a8d825338102b9084cb30dd03bf21f6bf003846"
EXPECTED_PIT_HEAD = "db1af342ba4481360bf429ad696b5c7870b20f73"
EXPECTED_PIT_REPORT_SHA = "4fb3abc3e561fd4187efbf60967127230f14d37204d21b5ccb910c40a4469845"


def read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    module_path = "packages/backtesting/alpha_gate_finra_short_interest_scientific_policy.py"
    module = read(module_path)
    ast.parse(module, filename=module_path)

    from packages.backtesting.alpha_gate_finra_short_interest_scientific_policy import (
        FINRA_SHORT_INTEREST_ENTRY_PIT_AUDIT_FINGERPRINT,
        FINRA_SHORT_INTEREST_ENTRY_PIT_AUDIT_REPORT_SHA256,
        FINRA_SHORT_INTEREST_ENTRY_PIT_AUDIT_STATUS,
        FINRA_SHORT_INTEREST_ENTRY_PIT_AUDIT_TARGET_HEAD,
        FINRA_SHORT_INTEREST_ENTRY_PIT_EVIDENCE,
        FINRA_SHORT_INTEREST_HYPOTHESES,
        FINRA_SHORT_INTEREST_MULTIPLE_TESTING_METHOD,
        FINRA_SHORT_INTEREST_PRIMARY_COST_BPS,
        FINRA_SHORT_INTEREST_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED,
        FINRA_SHORT_INTEREST_RUNNER_UP_SUBSTITUTION_ALLOWED,
        FINRA_SHORT_INTEREST_SCIENTIFIC_CONTRACT,
        FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT,
        FINRA_SHORT_INTEREST_STRESS_COST_BPS,
        finra_short_interest_scientific_fingerprint,
    )

    if FINRA_SHORT_INTEREST_SCIENTIFIC_CONTRACT != EXPECTED_CONTRACT:
        raise AssertionError("FINRA scientific contract drifted")
    if FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT != EXPECTED_FINGERPRINT:
        raise AssertionError("FINRA scientific fingerprint drifted")
    if finra_short_interest_scientific_fingerprint() != EXPECTED_FINGERPRINT:
        raise AssertionError("computed FINRA scientific fingerprint drifted")
    if FINRA_SHORT_INTEREST_ENTRY_PIT_AUDIT_FINGERPRINT != EXPECTED_PIT_FINGERPRINT:
        raise AssertionError("accepted PIT fingerprint drifted")
    if FINRA_SHORT_INTEREST_ENTRY_PIT_AUDIT_TARGET_HEAD != EXPECTED_PIT_HEAD:
        raise AssertionError("accepted PIT target head drifted")
    if FINRA_SHORT_INTEREST_ENTRY_PIT_AUDIT_REPORT_SHA256 != EXPECTED_PIT_REPORT_SHA:
        raise AssertionError("accepted PIT report hash drifted")
    if FINRA_SHORT_INTEREST_ENTRY_PIT_AUDIT_STATUS != "PIT_AUDIT_PASS":
        raise AssertionError("scientific policy is not bound to a passing PIT audit")
    if FINRA_SHORT_INTEREST_ENTRY_PIT_EVIDENCE != {
        "immutable_exchange_listed_rows": 136731,
        "pit_eligible_rows": 63761,
        "unique_pit_instruments": 8054,
        "files_with_2500_pit_rows": 12,
        "target_outcome_rows_read": 0,
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
    }:
        raise AssertionError("accepted PIT evidence drifted")

    ids = [spec.candidate_id for spec in FINRA_SHORT_INTEREST_HYPOTHESES]
    directions = [spec.direction for spec in FINRA_SHORT_INTEREST_HYPOTHESES]
    if ids != [
        "rapid_short_build_crowded_short",
        "rapid_short_build_non_crowded_short",
        "rapid_short_cover_crowded_long",
        "rapid_short_cover_non_crowded_long",
    ]:
        raise AssertionError("finite hypothesis family drifted")
    if directions != ["SHORT", "SHORT", "LONG", "LONG"]:
        raise AssertionError("hypothesis directions drifted")
    if FINRA_SHORT_INTEREST_MULTIPLE_TESTING_METHOD != "HOLM_BONFERRONI_GLOBAL_4":
        raise AssertionError("global multiplicity control drifted")
    if FINRA_SHORT_INTEREST_PRIMARY_COST_BPS != {"LONG": 10.0, "SHORT": 35.0}:
        raise AssertionError("primary cost policy drifted")
    if FINRA_SHORT_INTEREST_STRESS_COST_BPS != {"LONG": 25.0, "SHORT": 100.0}:
        raise AssertionError("stress cost policy drifted")
    if FINRA_SHORT_INTEREST_RUNNER_UP_SUBSTITUTION_ALLOWED is not False:
        raise AssertionError("runner-up substitution must remain forbidden")
    if FINRA_SHORT_INTEREST_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED is not False:
        raise AssertionError("protected returns must remain finalist-only")

    for required in (
        "LN((CURRENT_SHORT+1)/(PREVIOUS_SHORT+1))",
        "AVG_RANK_MINUS_1",
        "CLOSE_63_XNYS_SESSIONS_AFTER_DECISION",
        "HOLM_BONFERRONI_GLOBAL_4",
        "protected_holdout_consumed_after_any_nonempty_return_read",
        "phase33_signal_to_trade_authority",
    ):
        if required not in module:
            raise AssertionError(f"missing frozen policy boundary: {required}")
    for forbidden in (
        "MassiveRESTClient",
        "FINRAShortInterestClient(",
        "read_parquet(",
        "canonical_file(",
        "packages.execution",
        "packages.brokers",
        "submit_order(",
        "place_order(",
    ):
        if forbidden in module:
            raise AssertionError(f"scientific policy contains forbidden outcome/trading dependency: {forbidden}")

    print("ATLAS FINRA short-interest frozen scientific policy: PASS")
    print(f"- accepted PIT target head: {EXPECTED_PIT_HEAD}")
    print(f"- accepted PIT report SHA-256: {EXPECTED_PIT_REPORT_SHA}")
    print(f"- scientific fingerprint: {EXPECTED_FINGERPRINT}")
    print("- exactly four change/crowding hypotheses are frozen before outcome access")
    print("- global Holm-Bonferroni, direction-specific costs, purge/bootstrap, and finalist-only protected policy are frozen")
    print("- market/protected outcomes and all trading authority remain sealed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
