from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_PARENT_MERGE = "208529c5562920cc0b2bcf2bae546e2b9af0a25b"
EXPECTED_CONTRACT = "alpha-gate-finra-short-interest-feasibility-v1-consolidated-position-source-only-no-market-outcomes"
EXPECTED_MECHANISM = "PIT_FINRA_CONSOLIDATED_SHORT_INTEREST_POSITIONING_AND_CROWDING"
EXPECTED_FINGERPRINT = "cc80a87f020a4dece88430d20aa62e13d4dcd898656d60d53dea49b3ef975bc4"
EXPECTED_SETTLEMENT_DATES = ('2021-06-30', '2021-12-31', '2022-06-30', '2022-12-30', '2023-06-30', '2023-12-29', '2024-06-28', '2024-12-31', '2025-06-30', '2025-12-31', '2026-03-31', '2026-07-31')
EXPECTED_GATES = (10, 5, 20_000, 10_000, 2_500)


def read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing {label}: {needle}")


def forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"forbidden {label}: {needle}")


def main() -> int:
    provider = read("packages/providers/finra_short_interest.py")
    feasibility = read(
        "packages/backtesting/alpha_gate_finra_short_interest_feasibility.py"
    )
    runner = read("scripts/run_alpha_gate_finra_short_interest_feasibility.py")
    spec = read("docs/alpha_gate_finra_short_interest_feasibility.md")
    focused_workflow = read(
        ".github/workflows/finra-short-interest-alpha-gate-tests.yml"
    )

    for path, text in (
        ("packages/providers/finra_short_interest.py", provider),
        (
            "packages/backtesting/alpha_gate_finra_short_interest_feasibility.py",
            feasibility,
        ),
        ("scripts/run_alpha_gate_finra_short_interest_feasibility.py", runner),
    ):
        ast.parse(text, filename=path)

    from packages.backtesting.alpha_gate_finra_short_interest_feasibility import (
        FINRA_SHORT_INTEREST_ALPHA_HYPOTHESES_FROZEN,
        FINRA_SHORT_INTEREST_AUTOMATIC_BROKER_FAILOVER,
        FINRA_SHORT_INTEREST_BROKER_READS,
        FINRA_SHORT_INTEREST_BROKER_WRITES,
        FINRA_SHORT_INTEREST_FEASIBILITY_CONTRACT,
        FINRA_SHORT_INTEREST_FROZEN_SETTLEMENT_DATES,
        FINRA_SHORT_INTEREST_LIVE_WRITES,
        FINRA_SHORT_INTEREST_MECHANISM,
        FINRA_SHORT_INTEREST_MIN_EXCHANGE_LISTED_ROWS,
        FINRA_SHORT_INTEREST_MIN_SUCCESSFUL_FILES,
        FINRA_SHORT_INTEREST_MIN_TOTAL_ROWS,
        FINRA_SHORT_INTEREST_MIN_UNIQUE_EXCHANGE_LISTED_SYMBOLS,
        FINRA_SHORT_INTEREST_MIN_YEARS_REPRESENTED,
        FINRA_SHORT_INTEREST_ORDER_WRITES,
        FINRA_SHORT_INTEREST_PAPER_SUBMITS,
        FINRA_SHORT_INTEREST_PROTECTED_OUTCOME_READS_ALLOWED,
        FINRA_SHORT_INTEREST_PROVIDER_READS_ALLOWED,
        FINRA_SHORT_INTEREST_PROVIDER_WRITES,
        FINRA_SHORT_INTEREST_SOURCE_PARENT_MERGE,
        FINRA_SHORT_INTEREST_TARGET_OUTCOME_READS_ALLOWED,
        finra_short_interest_feasibility_fingerprint,
    )
    from packages.providers.finra_short_interest import (
        FINRA_EXCHANGE_LISTED_CODES,
        FINRA_SHORT_INTEREST_HOST,
        FINRA_SHORT_INTEREST_MAX_RESPONSE_BYTES,
        finra_short_interest_url,
    )

    if FINRA_SHORT_INTEREST_SOURCE_PARENT_MERGE != EXPECTED_PARENT_MERGE:
        raise AssertionError("FINRA source gate parent merge lineage drifted")
    if FINRA_SHORT_INTEREST_FEASIBILITY_CONTRACT != EXPECTED_CONTRACT:
        raise AssertionError("FINRA feasibility contract drifted")
    if FINRA_SHORT_INTEREST_MECHANISM != EXPECTED_MECHANISM:
        raise AssertionError("FINRA economic/information mechanism drifted")
    if finra_short_interest_feasibility_fingerprint() != EXPECTED_FINGERPRINT:
        raise AssertionError("FINRA feasibility fingerprint drifted")
    if FINRA_SHORT_INTEREST_FROZEN_SETTLEMENT_DATES != EXPECTED_SETTLEMENT_DATES:
        raise AssertionError("FINRA frozen source settlement dates drifted")
    if (
        FINRA_SHORT_INTEREST_MIN_SUCCESSFUL_FILES,
        FINRA_SHORT_INTEREST_MIN_YEARS_REPRESENTED,
        FINRA_SHORT_INTEREST_MIN_TOTAL_ROWS,
        FINRA_SHORT_INTEREST_MIN_EXCHANGE_LISTED_ROWS,
        FINRA_SHORT_INTEREST_MIN_UNIQUE_EXCHANGE_LISTED_SYMBOLS,
    ) != EXPECTED_GATES:
        raise AssertionError("FINRA source-only numeric gates drifted")

    if FINRA_SHORT_INTEREST_ALPHA_HYPOTHESES_FROZEN is not False:
        raise AssertionError("FINRA alpha hypotheses must not be frozen during feasibility")
    if (
        FINRA_SHORT_INTEREST_TARGET_OUTCOME_READS_ALLOWED
        or FINRA_SHORT_INTEREST_PROTECTED_OUTCOME_READS_ALLOWED
    ):
        raise AssertionError("market/protected outcomes are forbidden during feasibility")
    if not FINRA_SHORT_INTEREST_PROVIDER_READS_ALLOWED:
        raise AssertionError("FINRA source reads must be explicitly authorized")
    if any(
        value != 0
        for value in (
            FINRA_SHORT_INTEREST_PROVIDER_WRITES,
            FINRA_SHORT_INTEREST_BROKER_READS,
            FINRA_SHORT_INTEREST_BROKER_WRITES,
            FINRA_SHORT_INTEREST_ORDER_WRITES,
            FINRA_SHORT_INTEREST_PAPER_SUBMITS,
            FINRA_SHORT_INTEREST_LIVE_WRITES,
        )
    ):
        raise AssertionError("FINRA feasibility acquired forbidden external authority")
    if FINRA_SHORT_INTEREST_AUTOMATIC_BROKER_FAILOVER:
        raise AssertionError("automatic broker failover must remain disabled")

    if FINRA_SHORT_INTEREST_HOST != "cdn.finra.org":
        raise AssertionError("FINRA source host drifted")
    if FINRA_SHORT_INTEREST_MAX_RESPONSE_BYTES != 16_000_000:
        raise AssertionError("FINRA bounded response ceiling drifted")
    if FINRA_EXCHANGE_LISTED_CODES != frozenset({"A", "B", "E", "H", "R"}):
        raise AssertionError("FINRA exchange-listed identity codes drifted")
    if finra_short_interest_url(settlement_date="2026-07-31") != (
        "https://cdn.finra.org/equity/otcmarket/biweekly/shrt20260731.csv"
    ):
        raise AssertionError("FINRA historical short-interest URL contract drifted")

    for required in (
        "class FINRAShortInterestClient",
        "_PATH_RE",
        "cdn.finra.org",
        "shrt(\\d{8})",
        "source_sha256",
        "FINRA_SHORT_INTEREST_MAX_RESPONSE_BYTES",
        "issueSymbolIdentifier",
        "symbolCode",
        "currentShortShareNumber",
        "currentShortPositionQuantity",
        "issuerServicesGroupExchangeCode",
        "revisionFlag",
        "stockSplitFlag",
        "row settlement mismatch",
    ):
        require(provider, required, "FINRA provider contract")
    for forbidden in (
        "requests.",
        "httpx",
        "api.finra.org",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    ):
        forbid(provider, forbidden, "parallel/mutating FINRA authority")

    for required in (
        '"target_outcome_rows_read": 0',
        '"protected_return_rows_read": 0',
        '"protected_holdout_consumed": False',
        '"provider_writes_performed": 0',
        '"broker_reads_performed": 0',
        '"broker_writes_performed": 0',
        '"order_writes_performed": 0',
        '"paper_submits_performed": 0',
        '"live_writes_performed": 0',
        '"automation_writes_performed": 0',
        "publication-time chronology",
        "point-in-time active-common-stock identity",
    ):
        require(feasibility, required, "source-only feasibility boundary")
    for forbidden in (
        "canonical_file(",
        "feature_file(",
        "forward_return",
        "stock_return",
        "spy_return",
        "future_close",
        "packages.execution",
        "packages.brokers",
        "Webull",
        "AlpacaTrading",
    ):
        forbid(feasibility, forbidden, "performance/trading dependency")

    require(runner, "Alpha hypotheses: NOT YET FROZEN", "runner blindness declaration")
    require(
        runner,
        "Market prices/returns/target outcomes/protected returns: FORBIDDEN / UNREAD",
        "runner outcome boundary",
    )
    require(
        runner,
        "Provider writes / broker / order / PAPER / LIVE / automation: DISABLED",
        "runner authority boundary",
    )
    forbid(runner, "argparse", "operator source/gate override")

    require(spec, EXPECTED_PARENT_MERGE, "spec parent merge lineage")
    require(spec, EXPECTED_CONTRACT, "spec feasibility contract")
    require(spec, EXPECTED_FINGERPRINT, "spec feasibility fingerprint")
    require(spec, EXPECTED_MECHANISM, "spec mechanism")
    require(spec, "Phase33", "spec downstream boundary")
    require(spec, "protected", "spec protected boundary")

    require(
        focused_workflow,
        "validate_alpha_gate_finra_short_interest_feasibility.py",
        "focused validator CI",
    )
    require(
        focused_workflow,
        "test_finra_short_interest_provider.py",
        "focused provider tests CI",
    )
    require(
        focused_workflow,
        "test_alpha_gate_finra_short_interest_feasibility.py",
        "focused feasibility tests CI",
    )
    require(
        focused_workflow,
        "validate_alpha_gate_beneficial_ownership_closeout.py",
        "retained previous-family closeout",
    )
    require(focused_workflow, "windows-latest", "focused Windows parity")
    require(focused_workflow, "ubuntu-latest", "focused Ubuntu parity")
    print("ATLAS pre-Phase33 FINRA consolidated short-interest source-only contracts: PASS")
    print(f"- parent accepted merge: {EXPECTED_PARENT_MERGE}")
    print(f"- feasibility fingerprint: {EXPECTED_FINGERPRINT}")
    print(f"- frozen source files: {len(EXPECTED_SETTLEMENT_DATES)}")
    print("- alpha hypotheses remain unfrozen; target/protected outcomes remain forbidden")
    print("- provider writes, broker/order/PAPER/LIVE/automation authority remain disabled")
    print("- Phase33 remains blocked pending accepted historical SUPPORTED alpha")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
