from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "104e1c6ca44a85a0a166ea24c0318d34f3c3bbb6"
EXPECTED_CONTRACT = "alpha-gate-finra-short-interest-pit-audit-v1-publication-revision-split-active-common-stock-no-market-outcomes"
EXPECTED_FINGERPRINT = "ffdb7389ceae73f31a3781a79a8d825338102b9084cb30dd03bf21f6bf003846"
EXPECTED_FEASIBILITY = "cc80a87f020a4dece88430d20aa62e13d4dcd898656d60d53dea49b3ef975bc4"


def read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing {label}: {needle}")


def forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"forbidden {label}: {needle}")


def main() -> int:
    module = read("packages/backtesting/alpha_gate_finra_short_interest_pit_audit.py")
    runner = read("scripts/run_alpha_gate_finra_short_interest_pit_audit.py")
    spec = read("docs/alpha_gate_finra_short_interest_pit_audit.md")
    workflow = read(".github/workflows/finra-short-interest-alpha-gate-tests.yml")
    for path, text in (
        ("packages/backtesting/alpha_gate_finra_short_interest_pit_audit.py", module),
        ("scripts/run_alpha_gate_finra_short_interest_pit_audit.py", runner),
    ):
        ast.parse(text, filename=path)

    from packages.backtesting.alpha_gate_finra_short_interest_pit_audit import (
        FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_COUNTS,
        FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_FINGERPRINT,
        FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_HEAD,
        FINRA_SHORT_INTEREST_EXCHANGE_CODE_TO_MIC,
        FINRA_SHORT_INTEREST_MIN_FILES_WITH_2500_PIT_ROWS,
        FINRA_SHORT_INTEREST_MIN_IMMUTABLE_EXCHANGE_LISTED_ROWS,
        FINRA_SHORT_INTEREST_MIN_PIT_ELIGIBLE_ROWS,
        FINRA_SHORT_INTEREST_MIN_UNIQUE_PIT_INSTRUMENTS,
        FINRA_SHORT_INTEREST_PIT_AUDIT_CONTRACT,
        FINRA_SHORT_INTEREST_PIT_AUDIT_FINGERPRINT,
        FINRA_SHORT_INTEREST_PUBLICATION_ANCHORS,
        finra_short_interest_pit_audit_fingerprint,
        publication_date,
    )
    from datetime import date

    if FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_HEAD != EXPECTED_HEAD:
        raise AssertionError("accepted feasibility target head drifted")
    if FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_FINGERPRINT != EXPECTED_FEASIBILITY:
        raise AssertionError("parent feasibility fingerprint drifted")
    if FINRA_SHORT_INTEREST_PIT_AUDIT_CONTRACT != EXPECTED_CONTRACT:
        raise AssertionError("PIT audit contract drifted")
    if FINRA_SHORT_INTEREST_PIT_AUDIT_FINGERPRINT != EXPECTED_FINGERPRINT:
        raise AssertionError("pinned PIT fingerprint drifted")
    if finra_short_interest_pit_audit_fingerprint() != EXPECTED_FINGERPRINT:
        raise AssertionError("computed PIT fingerprint drifted")
    if FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_COUNTS != {
        "successful_files": 12,
        "failed_files": 0,
        "years": [2021, 2022, 2023, 2024, 2025, 2026],
        "total_rows": 244979,
        "exchange_listed_rows": 137575,
        "unique_exchange_listed_symbols": 20248,
        "revision_flagged_rows": 2328,
        "stock_split_flagged_rows": 514,
    }:
        raise AssertionError("accepted feasibility evidence counts drifted")
    if FINRA_SHORT_INTEREST_EXCHANGE_CODE_TO_MIC != {
        "A": "XNYS", "B": "XASE", "E": "ARCX", "H": "BATS", "R": "XNAS"
    }:
        raise AssertionError("FINRA exchange-to-MIC identity map drifted")
    if (
        FINRA_SHORT_INTEREST_MIN_IMMUTABLE_EXCHANGE_LISTED_ROWS,
        FINRA_SHORT_INTEREST_MIN_PIT_ELIGIBLE_ROWS,
        FINRA_SHORT_INTEREST_MIN_UNIQUE_PIT_INSTRUMENTS,
        FINRA_SHORT_INTEREST_MIN_FILES_WITH_2500_PIT_ROWS,
    ) != (100000, 60000, 5000, 10):
        raise AssertionError("PIT source-only numeric gates drifted")
    for settlement, expected in FINRA_SHORT_INTEREST_PUBLICATION_ANCHORS.items():
        if publication_date(date.fromisoformat(settlement)).isoformat() != expected:
            raise AssertionError(f"publication anchor drifted: {settlement}")

    for required in (
        "FIRST_XNYS_SESSION_OPEN_STRICTLY_AFTER_PUBLICATION_DATE",
        "EXCLUDE_ANY_NONBLANK_REVISION_FLAG_ONLY_MOST_RECENT_FINRA_DATA_AVAILABLE",
        "EXCLUDE_ANY_NONBLANK_STOCK_SPLIT_FLAG_FROM_PREDICTOR_ELIGIBILITY",
        "SAME_STRONG_OR_MEDIUM_INSTRUMENT_ID",
        '"target_outcome_rows_read": 0',
        '"protected_return_rows_read": 0',
        '"protected_holdout_consumed": False',
        '"provider_writes_performed": 0',
        '"broker_reads_performed": 0',
        '"order_writes_performed": 0',
    ):
        require(module, required, "PIT audit scientific boundary")
    for forbidden in (
        "canonical_file(", "feature_file(", "forward_return", "stock_return", "spy_return",
        "future_close", "packages.execution", "packages.brokers", "submit_order(", "paper_submit(",
    ):
        forbid(module, forbidden, "market/trading dependency")
    forbid(runner, "argparse", "operator policy override")
    require(runner, "Alpha hypotheses: NOT YET FROZEN", "runner blind state")
    require(runner, "FORBIDDEN / UNREAD", "runner outcome boundary")
    require(spec, EXPECTED_HEAD, "spec accepted parent head")
    require(spec, EXPECTED_FINGERPRINT, "spec PIT fingerprint")
    require(spec, "4:40 PM ET", "spec publication availability")
    require(spec, "only the most recent data", "spec revision limitation")
    require(workflow, "validate_alpha_gate_finra_short_interest_pit_audit.py", "focused validator")
    require(workflow, "test_alpha_gate_finra_short_interest_pit_audit.py", "focused tests")
    require(workflow, "windows-latest", "Windows parity")
    require(workflow, "ubuntu-latest", "Ubuntu parity")
    print("ATLAS FINRA short-interest PIT source audit contracts: PASS")
    print(f"- accepted feasibility head: {EXPECTED_HEAD}")
    print(f"- PIT audit fingerprint: {EXPECTED_FINGERPRINT}")
    print("- publication is delayed to the next XNYS open after FINRA's publication day")
    print("- revised/split rows fail closed; active common-stock identity must persist")
    print("- market/protected outcomes and trading authority remain sealed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
