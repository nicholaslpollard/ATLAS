from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_xbrl_scientific_policy import (
    XBRL_ENTRY_SOURCE_REPAIR_FINGERPRINT,
    XBRL_HYPOTHESES,
    XBRL_SCIENTIFIC_CONTRACT,
    XBRL_SCIENTIFIC_FINGERPRINT,
    xbrl_scientific_fingerprint,
)


def _read(relative: str) -> str:
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def _require(text: str, token: str, label: str) -> None:
    if token not in text:
        raise SystemExit(f"XBRL scientific contract validation failed: missing {label}: {token}")


def _forbid(text: str, token: str, label: str) -> None:
    if token in text:
        raise SystemExit(f"XBRL scientific contract validation failed: forbidden {label}: {token}")


def main() -> int:
    actual_fingerprint = xbrl_scientific_fingerprint()
    if actual_fingerprint != XBRL_SCIENTIFIC_FINGERPRINT:
        raise SystemExit(
            "XBRL scientific contract validation failed: frozen fingerprint drifted: "
            f"actual={actual_fingerprint} expected={XBRL_SCIENTIFIC_FINGERPRINT}"
        )
    if len(XBRL_HYPOTHESES) != 6:
        raise SystemExit("XBRL scientific contract validation failed: hypothesis family is not exactly six")

    policy = _read("packages/backtesting/alpha_gate_xbrl_scientific_policy.py")
    runner = _read("scripts/run_alpha_gate_xbrl_scientific_contract.py")
    tests = _read("tests/unit/test_alpha_gate_xbrl_scientific_policy.py")
    doc = _read("docs/alpha_gate_sec_xbrl_scientific_contract.md")
    repair = _read("packages/backtesting/alpha_gate_xbrl_pit_identity_repair.py")

    for path, text in (
        ("packages/backtesting/alpha_gate_xbrl_scientific_policy.py", policy),
        ("scripts/run_alpha_gate_xbrl_scientific_contract.py", runner),
        ("tests/unit/test_alpha_gate_xbrl_scientific_policy.py", tests),
    ):
        ast.parse(text, filename=path)

    for text, label in ((policy, "policy"), (doc, "normative doc")):
        _require(text, XBRL_SCIENTIFIC_CONTRACT, f"{label} contract")
        _require(text, XBRL_SCIENTIFIC_FINGERPRINT, f"{label} fingerprint")
        _require(text, XBRL_ENTRY_SOURCE_REPAIR_FINGERPRINT, f"{label} source-repair lineage")

    for token in (
        'XBRL_STUDY_CIK_POPULATION = "ACCEPTED_XBRL_FEASIBILITY_SAMPLE_EXACT_200_CIKS_NO_PERFORMANCE_RESAMPLING"',
        'XBRL_PUBLIC_AVAILABILITY_RULE = "FIRST_XNYS_SESSION_OPEN_STRICTLY_AFTER_SEC_ACCEPTANCE"',
        'XBRL_INSTRUMENT_RULE = "MASSIVE_EXACT_CIK_DATE_ACTIVE_TRUE_TYPE_CS_UNIQUE_STRONG_OR_MEDIUM"',
        'XBRL_INSTANT_FACT_RULE = "ASSETS_USD_EXACT_ACCESSION_END_INSTANT"',
        'XBRL_DURATION_FACT_RULE = "USD_ONLY_ORIGINAL_10Q_10K_ACCESSION_VERSIONED"',
        'XBRL_PRIMARY_HORIZON_SESSIONS = 63',
        'XBRL_MULTIPLE_TESTING_METHOD = "HOLM_BONFERRONI_GLOBAL_6"',
        'XBRL_SELECTION_WINNER_RULE = "highest_primary_selection_LCB_then_candidate_id"',
        'XBRL_MAX_SELECTION_WINNERS_PER_DIRECTION = 1',
        'XBRL_MAX_FINALISTS_PER_DIRECTION = 1',
        'XBRL_RUNNER_UP_SUBSTITUTION_ALLOWED = False',
        'XBRL_PROTECTED_SOURCE_ONLY_PRECHECK_REQUIRED = True',
        'XBRL_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED = False',
        'XBRL_PROTECTED_HOLDOUT_CONSUMED_AFTER_ANY_NONEMPTY_RETURN_READ = True',
        'XBRL_PHASE33_SIGNAL_TO_TRADE_AUTHORITY = False',
    ):
        _require(policy, token, "frozen policy invariant")

    for candidate_id in (
        "gross_profitability_improvement_long",
        "gross_profitability_deterioration_short",
        "cash_profitability_improvement_long",
        "cash_profitability_deterioration_short",
        "accrual_quality_improvement_long",
        "accrual_quality_deterioration_short",
    ):
        _require(policy, candidate_id, "finite hypothesis")
        _require(doc, candidate_id, "documented finite hypothesis")

    for token in (
        "Q2_Q3_CURRENT_YTD_MINUS_PREVIOUS_PIT_YTD",
        "Q4_FY_MINUS_PIT_Q1_Q2_Q3",
        "SAME_ISSUER_SAME_FISCAL_QUARTER_PRIOR_FY_ORIGINAL_PIT_FEATURE_VERSION",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "CostOfGoodsAndServicesSold",
    ):
        _require(policy, token, "quarter/PIT feature semantics")

    for forbidden in (
        "packages.data.market",
        "packages.execution",
        "packages.brokers",
        "read_parquet",
        "forward_return",
        "future_close",
        "stock_return",
        "spy_return",
        ".place_order(",
        ".submit_order(",
    ):
        _forbid(policy, forbidden, "market outcome/trading dependency")
        _forbid(runner, forbidden, "preflight market outcome/trading dependency")

    _require(
        repair,
        '"identity_source": "Massive:/v3/reference/tickers?cik=...&date=...&active=true&type=CS"',
        "accepted repaired common-stock source semantics",
    )
    _require(
        repair,
        "EXACT_CIK_DATE_ACTIVE_COMMON_STOCK_ONLY_STRONG_OR_MEDIUM_EXACTLY_ONE_UNIQUE_INSTRUMENT",
        "accepted repaired common-stock identity rule",
    )
    _require(runner, "Market prices/returns and protected returns read by this preflight: 0", "preflight blindness")
    _require(runner, "Phase33 authority: False", "preflight downstream block")
    _require(tests, "test_primary_horizon_and_outer_embargo_do_not_overlap", "chronology regression")
    _require(tests, "test_selection_is_global_and_protected_cannot_be_shopped", "selection/protected regression")

    print("ATLAS XBRL fundamental alpha scientific contract: PASS")
    print(f"- contract: {XBRL_SCIENTIFIC_CONTRACT}")
    print(f"- fingerprint: {XBRL_SCIENTIFIC_FINGERPRINT}")
    print("- six hypotheses, PIT quarter semantics, 63-session outcome, costs, multiplicity and protected rules frozen")
    print("- winner selection uses only selection-tranche evidence; internal validation cannot choose the winner")
    print("- accepted v2 identity repair is bound to active=true + type=CS on exact historical CIK/date")
    print("- this validation reads zero market outcomes and grants zero Phase33/trading authority")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
