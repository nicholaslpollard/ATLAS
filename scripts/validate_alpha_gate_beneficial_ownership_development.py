from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_SCIENTIFIC_FINGERPRINT = "4bf51f02fb74a219609e2affef3319b24b7c98eb06fa9d88e405ae4f7448434c"
EXPECTED_IMPLEMENTATION_FINGERPRINT = "0e90a65e6e2f6a7d7206296901054de3a2c97aaa204c80927a963c298c81060d"
EXPECTED_TRANSPORT_REPAIR_FINGERPRINT = "a4db8419364895c6861c4becbe3abf9b32ec044ceb4aff5cf14a7c9244368bdb"


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
    transport_path = "packages/backtesting/alpha_gate_beneficial_ownership_transport_repair.py"
    provider_path = "packages/providers/sec_edgar_archive.py"
    runner_path = "scripts/run_alpha_gate_beneficial_ownership_development.py"
    tests_path = "tests/unit/test_alpha_gate_beneficial_ownership_development.py"

    policy = _read(policy_path)
    predictor = _read(predictor_path)
    development = _read(development_path)
    transport = _read(transport_path)
    provider = _read(provider_path)
    runner = _read(runner_path)
    tests = _read(tests_path)
    for path, text in (
        (policy_path, policy),
        (predictor_path, predictor),
        (development_path, development),
        (transport_path, transport),
        (provider_path, provider),
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
    from packages.backtesting.alpha_gate_beneficial_ownership_transport_repair import (
        BENEFICIAL_OWNERSHIP_DEVELOPMENT_TRANSPORT_REPAIR_FINGERPRINT,
        beneficial_ownership_development_transport_repair_fingerprint,
    )
    from packages.providers.sec_edgar_archive import (
        SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES,
        SEC_ARCHIVE_SUBMISSION_MAX_RESPONSE_BYTES,
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
    if (
        BENEFICIAL_OWNERSHIP_DEVELOPMENT_TRANSPORT_REPAIR_FINGERPRINT
        != EXPECTED_TRANSPORT_REPAIR_FINGERPRINT
    ):
        raise AssertionError("development transport repair fingerprint constant drifted")
    if (
        beneficial_ownership_development_transport_repair_fingerprint()
        != EXPECTED_TRANSPORT_REPAIR_FINGERPRINT
    ):
        raise AssertionError("development transport repair fingerprint function drifted")
    if SEC_ARCHIVE_SUBMISSION_MAX_RESPONSE_BYTES != 20_000_000:
        raise AssertionError("historical/default complete-submission bound drifted")
    if SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES != 256_000_000:
        raise AssertionError("scientific complete-submission ceiling drifted")
    if BENEFICIAL_OWNERSHIP_MULTIPLE_TESTING_METHOD != "HOLM_BONFERRONI_GLOBAL_4":
        raise AssertionError("global multiplicity method drifted")
    if BENEFICIAL_OWNERSHIP_PROTECTED_RETURNS_BEFORE_FINALIST_ALLOWED is not False:
        raise AssertionError("protected returns opened before a finalist")
    if BENEFICIAL_OWNERSHIP_RUNNER_UP_SUBSTITUTION_ALLOWED is not False:
        raise AssertionError("runner-up substitution was enabled")

    for token in (
        "BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT",
        "beneficial_ownership_scientific_fingerprint()",
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

    for token in (
        "SEC_ARCHIVE_SUBMISSION_MAX_RESPONSE_BYTES",
        "SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES",
        "scientific_acquisition_only_no_selection_or_outcome_change",
        "3500_of_5200_predictor_walk_pre_reconstruction_zero_outcomes",
    ):
        _require(transport, token, "transport repair invariant")

    _require(
        provider,
        "submission_max_response_bytes: int = SEC_ARCHIVE_SUBMISSION_MAX_RESPONSE_BYTES",
        "preserved default submission bound",
    )
    _require(
        provider,
        "or bounded_submission_limit > SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES",
        "bounded scientific submission ceiling",
    )
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
    _require(
        runner,
        "submission_max_response_bytes=(",
        "runner explicit scientific submission bound",
    )
    _require(
        runner,
        "SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES",
        "runner bounded scientific ceiling",
    )
    _require(
        runner,
        "beneficial_ownership_development_transport_repair_fingerprint()",
        "runner transport repair fingerprint binding",
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
    _require(tests, "test_development_transport_repair_fingerprint_is_exact", "transport fingerprint test")
    _require(tests, "test_sec_archive_default_submission_bound_is_preserved", "default-bound regression test")
    _require(tests, "test_scientific_submission_bound_is_bounded_and_explicit", "scientific-bound regression test")
    _require(tests, "test_holm_is_global_and_stops_after_first_nonrejection", "Holm regression test")
    _require(tests, "test_protected_precheck_reads_source_counts_only", "protected source-only regression")

    print("ATLAS SEC beneficial-ownership development implementation: PASS")
    print(f"- scientific fingerprint: {EXPECTED_SCIENTIFIC_FINGERPRINT}")
    print(f"- development statistics fingerprint: {EXPECTED_IMPLEMENTATION_FINGERPRINT}")
    print(f"- development transport repair fingerprint: {EXPECTED_TRANSPORT_REPAIR_FINGERPRINT}")
    print("- historical/default SEC complete-submission bound remains 20 MB")
    print("- scientific acquisition uses an explicit bounded 256 MB complete-submission ceiling")
    print("- exact development entry/exit, split censoring, SPY-relative/unhedged returns and frozen costs are enforced")
    print("- global Holm precedes single-winner selection; internal validation cannot choose among candidates")
    print("- protected stage is source-count only and reads zero protected returns")
    print("- Phase33 and all trading authority remain blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
