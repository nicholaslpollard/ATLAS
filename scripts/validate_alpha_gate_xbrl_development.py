from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_xbrl_development import (
    XBRL_DEVELOPMENT_CONTRACT,
    XBRL_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT,
    XBRL_FINALIST_CONTRACT,
    XBRL_OUTCOME_CONTRACT,
    development_implementation_fingerprint,
)
from packages.backtesting.alpha_gate_xbrl_predictor import XBRL_PREDICTOR_CONTRACT
from packages.backtesting.alpha_gate_xbrl_scientific_policy import (
    XBRL_SCIENTIFIC_FINGERPRINT,
)


def _read(relative: str) -> str:
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def _require(text: str, token: str, label: str) -> None:
    if token not in text:
        raise SystemExit(f"XBRL development validation failed: missing {label}: {token}")


def _forbid(text: str, token: str, label: str) -> None:
    if token in text:
        raise SystemExit(f"XBRL development validation failed: forbidden {label}: {token}")


def main() -> int:
    actual = development_implementation_fingerprint()
    if actual != XBRL_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT:
        raise SystemExit(
            "XBRL development validation failed: implementation fingerprint drifted: "
            f"actual={actual} expected={XBRL_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT}"
        )

    predictor = _read("packages/backtesting/alpha_gate_xbrl_predictor.py")
    development = _read("packages/backtesting/alpha_gate_xbrl_development.py")
    provider = _read("packages/providers/sec_xbrl_pit.py")
    runner = _read("scripts/run_alpha_gate_xbrl_development.py")
    predictor_tests = _read("tests/unit/test_alpha_gate_xbrl_predictor.py")
    development_tests = _read("tests/unit/test_alpha_gate_xbrl_development.py")
    doc = _read("docs/alpha_gate_sec_xbrl_development.md")
    workflow = _read(".github/workflows/xbrl-alpha-gate-tests.yml")

    for path, text in (
        ("packages/backtesting/alpha_gate_xbrl_predictor.py", predictor),
        ("packages/backtesting/alpha_gate_xbrl_development.py", development),
        ("packages/providers/sec_xbrl_pit.py", provider),
        ("scripts/run_alpha_gate_xbrl_development.py", runner),
        ("tests/unit/test_alpha_gate_xbrl_predictor.py", predictor_tests),
        ("tests/unit/test_alpha_gate_xbrl_development.py", development_tests),
    ):
        ast.parse(text, filename=path)

    # Imported lineage constants should be bound by symbol in implementation code;
    # only the normative document duplicates immutable literal fingerprints/contracts.
    for token in (
        "XBRL_SCIENTIFIC_FINGERPRINT",
        "XBRL_PREDICTOR_CONTRACT",
        "XBRL_DEVELOPMENT_CONTRACT",
        "XBRL_OUTCOME_CONTRACT",
        "XBRL_FINALIST_CONTRACT",
        "XBRL_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT",
    ):
        _require(development, token, "implementation lineage binding")

    for token, label in (
        (XBRL_SCIENTIFIC_FINGERPRINT, "normative scientific fingerprint"),
        (XBRL_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT, "normative implementation fingerprint"),
        (XBRL_PREDICTOR_CONTRACT, "normative predictor contract"),
        (XBRL_DEVELOPMENT_CONTRACT, "normative development contract"),
        (XBRL_OUTCOME_CONTRACT, "normative outcome contract"),
        (XBRL_FINALIST_CONTRACT, "normative finalist contract"),
    ):
        _require(doc, token, label)

    for token in (
        "filing_metadata_many",
        "later_same_fiscal_period_accessions_excluded",
        "feature_history.setdefault",
        '"DEVELOPMENT"',
        '"PROTECTED"',
        "tradable_common_stock_snapshot",
    ):
        _require(predictor, token, "PIT predictor invariant")

    for token in (
        "XBRL_PRIMARY_HORIZON_SESSIONS",
        "XBRL_SELECTION_FOLDS",
        "XBRL_INTERNAL_VALIDATION_FOLDS",
        "XBRL_INTERNAL_PURGE_SESSIONS",
        "holm_bonferroni",
        "selection_checks",
        "internal_checks",
        "protected_source_precheck",
        '"protected_return_rows_read": 0',
        '"protected_holdout_consumed": False',
        '"phase33_signal_to_trade_authority": False',
    ):
        _require(development, token, "development invariant")

    _require(
        provider,
        "Resolve many exact accessions with one root submissions read per issuer",
        "batched SEC submissions authority",
    )
    _require(
        development,
        'XBRL_SELECTION_WINNER_RULE != "highest_primary_selection_LCB_then_candidate_id"',
        "selection-only winner rule enforcement",
    )
    _require(
        development,
        "for candidate_id in winners:",
        "internal validation only for selected winners",
    )

    outcome_start = development.index("    def _development_outcomes(")
    outcome_end = development.index("    def run(self)", outcome_start)
    outcome_body = development[outcome_start:outcome_end]
    _forbid(outcome_body, "protected", "protected market outcome reference")
    _require(outcome_body, "xbrl_predictors", "development-only price driver")
    _require(outcome_body, "SPY", "frozen benchmark")
    _require(outcome_body, "split_crossing", "split censor")

    winners_position = development.index("        winners: list[str] = []")
    internal_position = development.index("        internal_metrics:", winners_position)
    if internal_position <= winners_position:
        raise SystemExit("XBRL development validation failed: internal metrics precede winner freeze")

    protected_precheck_position = development.index("        protected_prechecks =", internal_position)
    if protected_precheck_position <= internal_position:
        raise SystemExit("XBRL development validation failed: protected precheck precedes internal validation")

    for forbidden in (
        "packages.execution",
        "packages.brokers",
        ".place_order(",
        ".submit_order(",
    ):
        _forbid(predictor, forbidden, "predictor trading dependency")
        _forbid(development, forbidden, "development trading dependency")
        _forbid(runner, forbidden, "runner trading dependency")

    _require(runner, "Protected returns: SEALED / UNREAD", "runner protected boundary")
    _require(runner, "XBRLDevelopmentStudy", "development runner")
    _require(predictor_tests, "test_q4_annual_is_incrementalized", "quarter reconstruction regression")
    _require(development_tests, "test_protected_source_precheck_can_pass_without_return_columns", "protected blindness regression")

    for token in (
        "packages/backtesting/alpha_gate_xbrl_predictor.py",
        "packages/backtesting/alpha_gate_xbrl_development.py",
        "scripts/validate_alpha_gate_xbrl_development.py",
        "tests/unit/test_alpha_gate_xbrl_predictor.py",
        "tests/unit/test_alpha_gate_xbrl_development.py",
    ):
        _require(workflow, token, "XBRL workflow coverage")

    print("ATLAS XBRL development implementation: PASS")
    print(f"- development fingerprint: {actual}")
    print("- PIT quarter reconstruction preserves first-public fiscal-period state")
    print("- selection/Holm/winner freeze precedes internal validation")
    print("- protected predictors are source-count only; protected market returns have no join path")
    print("- Phase33 and all trading/mutation authority remain disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
