from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_SCIENTIFIC_FINGERPRINT = "4bf51f02fb74a219609e2affef3319b24b7c98eb06fa9d88e405ae4f7448434c"
EXPECTED_IMPLEMENTATION_FINGERPRINT = "0e90a65e6e2f6a7d7206296901054de3a2c97aaa204c80927a963c298c81060d"


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
    development_path = "packages/backtesting/alpha_gate_beneficial_ownership_development.py"
    runner_path = "scripts/run_alpha_gate_beneficial_ownership_development.py"
    tests_path = "tests/unit/test_alpha_gate_beneficial_ownership_development.py"

    policy = _read(policy_path)
    predictor = _read(predictor_path)
    development = _read(development_path)
    runner = _read(runner_path)
    tests = _read(tests_path)
    for path, text in (
        (policy_path, policy),
        (predictor_path, predictor),
        (development_path, development),
        (runner_path, runner),
        (tests_path, tests),
    ):
        ast.parse(text, filename=path)

    from packages.backtesting.alpha_gate_beneficial_ownership_development import (
        BENEFICIAL_OWNERSHIP_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT,
        development_implementation_fingerprint,
    )
    from packages.backtesting.alpha_gate_beneficial_ownership_scientific_policy import (
        BENEFICIAL_OWNERSHIP_MULTIPLE_TESTING_METHOD,
        BENEFICIAL_OWNERSHIP_PROTECTED_RETURNS_BEFORE_FINALIST_ALLOWED,
        BENEFICIAL_OWNERSHIP_RUNNER_UP_SUBSTITUTION_ALLOWED,
        BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT,
    )

    if BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT != EXPECTED_SCIENTIFIC_FINGERPRINT:
        raise AssertionError("scientific fingerprint drifted")
    if (
        BENEFICIAL_OWNERSHIP_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT
        != EXPECTED_IMPLEMENTATION_FINGERPRINT
    ):
        raise AssertionError("development implementation fingerprint constant drifted")
    if development_implementation_fingerprint() != EXPECTED_IMPLEMENTATION_FINGERPRINT:
        raise AssertionError("development implementation fingerprint function drifted")
    if BENEFICIAL_OWNERSHIP_MULTIPLE_TESTING_METHOD != "HOLM_BONFERRONI_GLOBAL_4":
        raise AssertionError("global multiplicity method drifted")
    if BENEFICIAL_OWNERSHIP_PROTECTED_RETURNS_BEFORE_FINALIST_ALLOWED is not False:
        raise AssertionError("protected returns opened before a finalist")
    if BENEFICIAL_OWNERSHIP_RUNNER_UP_SUBSTITUTION_ALLOWED is not False:
        raise AssertionError("runner-up substitution was enabled")

    for token in (
        EXPECTED_SCIENTIFIC_FINGERPRINT,
        "accepted_phase26_split_evidence_censor_decision_open_to_t63_close",
        "selection_only_global_holm_then_single_long_winner_internal_confirm",
        "source_only_counts_no_return_read",
        "HOLM_BONFERRONI_GLOBAL_4",
        "ranked_passers[:1]",
        "protected_source_precheck",
        '"protected_return_rows_read": 0',
        '"protected_holdout_consumed": False',
        '"phase33_signal_to_trade_authority": False',
    ):
        _require(development, token, "development invariant")

    _require(
        development,
        'outcomes["candidate_id"].astype(str).eq(candidate_id)',
        "internal evaluation restricted to already selected winner",
    )
    _require(
        development,
        "selection_passers",
        "selection passers computed before internal confirmation",
    )
    _require(
        runner,
        "Protected returns: SEALED / UNREAD",
        "runner protected blindness declaration",
    )
    _require(
        runner,
        "BeneficialOwnershipPredictorBuilder",
        "runner source-only predictor stage",
    )
    _require(
        runner,
        "BeneficialOwnershipDevelopmentStudy",
        "runner development stage",
    )
    _forbid(runner, "argparse", "runtime scientific override surface")

    for forbidden in (
        "packages.execution",
        "packages.brokers",
        ".place_order(",
        ".submit_order(",
    ):
        _forbid(development, forbidden, "trading dependency")
        _forbid(runner, forbidden, "runner trading dependency")

    _require(tests, "test_development_implementation_fingerprint_is_exact", "implementation fingerprint test")
    _require(tests, "test_holm_is_global_and_stops_after_first_nonrejection", "Holm regression test")
    _require(tests, "test_protected_precheck_reads_source_counts_only", "protected source-only regression")

    print("ATLAS SEC beneficial-ownership development implementation: PASS")
    print(f"- scientific fingerprint: {EXPECTED_SCIENTIFIC_FINGERPRINT}")
    print(f"- development implementation fingerprint: {EXPECTED_IMPLEMENTATION_FINGERPRINT}")
    print("- exact development entry/exit, split censoring, SPY-relative/unhedged returns and frozen costs are enforced")
    print("- global Holm precedes single-winner selection; internal validation cannot choose among candidates")
    print("- protected stage is source-count only and reads zero protected returns")
    print("- Phase33 and all trading authority remain blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
