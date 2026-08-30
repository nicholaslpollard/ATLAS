from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_PHASE32_MERGE = "69f8aa81289934b71f2652482c747391917c15a3"
EXPECTED_CONTRACT = (
    "alpha-gate-xbrl-feasibility-v1-quarterly-fundamental-source-only-no-market-outcomes"
)
EXPECTED_FINGERPRINT = "6574a9c942d085fb897b7737961d26dd3da0c3a85b69992081a21f044960d152"
EXPECTED_MECHANISM = "PIT_SEC_XBRL_QUARTERLY_FUNDAMENTAL_PROFITABILITY_AND_ACCRUAL_QUALITY"
EXPECTED_SAMPLE_SIZE = 200
EXPECTED_GATES = (160, 100, 80, 8)
EXPECTED_GROUPS = {
    "assets": ("Assets",),
    "net_income": ("NetIncomeLoss",),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "gross_profit": ("GrossProfit",),
    "cost_of_revenue": ("CostOfRevenue", "CostOfGoodsAndServicesSold"),
}


def read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing {label}: {needle}")


def forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"forbidden {label}: {needle}")


def main() -> int:
    provider = read("packages/providers/sec_xbrl.py")
    feasibility = read("packages/backtesting/alpha_gate_xbrl_feasibility.py")
    runner = read("scripts/run_alpha_gate_xbrl_feasibility.py")
    spec = read("docs/alpha_gate_sec_xbrl_fundamental_quality.md")
    roadmap = read("docs/roadmap.md")
    status = read("docs/current_status.md")
    flow = read("docs/phase_flow.md")
    readme = read("README.md")
    workflow = read(".github/workflows/xbrl-alpha-gate-tests.yml")

    for path, text in (
        ("packages/providers/sec_xbrl.py", provider),
        ("packages/backtesting/alpha_gate_xbrl_feasibility.py", feasibility),
        ("scripts/run_alpha_gate_xbrl_feasibility.py", runner),
    ):
        ast.parse(text, filename=path)

    from packages.backtesting.alpha_gate_xbrl_feasibility import (
        XBRL_ALPHA_HYPOTHESES_FROZEN,
        XBRL_AUTOMATIC_BROKER_FAILOVER,
        XBRL_BROKER_READS,
        XBRL_BROKER_WRITES,
        XBRL_CONCEPT_GROUPS,
        XBRL_FEASIBILITY_CONTRACT,
        XBRL_LIVE_WRITES,
        XBRL_MECHANISM,
        XBRL_MIN_ACCRUAL_HISTORY_READY,
        XBRL_MIN_PERIOD_ENDS_PER_GROUP,
        XBRL_MIN_PROFITABILITY_HISTORY_READY,
        XBRL_MIN_SUCCESSFUL_DOCUMENTS,
        XBRL_ORDER_WRITES,
        XBRL_PAPER_SUBMITS,
        XBRL_PROTECTED_OUTCOME_READS_ALLOWED,
        XBRL_PROVIDER_READS_ALLOWED,
        XBRL_PROVIDER_WRITES,
        XBRL_SAMPLE_SIZE,
        XBRL_SOURCE_PHASE32_MERGE,
        XBRL_TARGET_OUTCOME_READS_ALLOWED,
        xbrl_feasibility_fingerprint,
    )
    from packages.providers.sec_xbrl import SECXBRLCompanyFactsClient, sec_companyfacts_url
    from packages.providers.sec_edgar import SECEDGARClient

    if XBRL_SOURCE_PHASE32_MERGE != EXPECTED_PHASE32_MERGE:
        raise AssertionError("XBRL gate Phase32 merge lineage drifted")
    if XBRL_FEASIBILITY_CONTRACT != EXPECTED_CONTRACT:
        raise AssertionError("XBRL feasibility contract drifted")
    if xbrl_feasibility_fingerprint() != EXPECTED_FINGERPRINT:
        raise AssertionError("XBRL feasibility fingerprint drifted")
    if XBRL_MECHANISM != EXPECTED_MECHANISM:
        raise AssertionError("XBRL economic/information mechanism drifted")
    if XBRL_SAMPLE_SIZE != EXPECTED_SAMPLE_SIZE:
        raise AssertionError("XBRL deterministic sample size drifted")
    if (
        XBRL_MIN_SUCCESSFUL_DOCUMENTS,
        XBRL_MIN_ACCRUAL_HISTORY_READY,
        XBRL_MIN_PROFITABILITY_HISTORY_READY,
        XBRL_MIN_PERIOD_ENDS_PER_GROUP,
    ) != EXPECTED_GATES:
        raise AssertionError("XBRL source-only feasibility gates drifted")
    actual_groups = {group.group_id: group.tags for group in XBRL_CONCEPT_GROUPS}
    if actual_groups != EXPECTED_GROUPS:
        raise AssertionError(f"XBRL concept groups drifted: {actual_groups}")

    if XBRL_ALPHA_HYPOTHESES_FROZEN is not False:
        raise AssertionError("XBRL alpha hypotheses must remain unfrozen during feasibility")
    if XBRL_TARGET_OUTCOME_READS_ALLOWED or XBRL_PROTECTED_OUTCOME_READS_ALLOWED:
        raise AssertionError("market/protected outcomes are forbidden during XBRL feasibility")
    if not XBRL_PROVIDER_READS_ALLOWED:
        raise AssertionError("source-only SEC provider reads must be explicitly authorized")
    if any(
        value != 0
        for value in (
            XBRL_PROVIDER_WRITES,
            XBRL_BROKER_READS,
            XBRL_BROKER_WRITES,
            XBRL_ORDER_WRITES,
            XBRL_PAPER_SUBMITS,
            XBRL_LIVE_WRITES,
        )
    ):
        raise AssertionError("XBRL feasibility acquired forbidden external/trading authority")
    if XBRL_AUTOMATIC_BROKER_FAILOVER:
        raise AssertionError("automatic broker failover must remain disabled")

    if not issubclass(SECXBRLCompanyFactsClient, SECEDGARClient):
        raise AssertionError("XBRL client must reuse accepted SEC EDGAR network seam")
    if sec_companyfacts_url(cik="4904") != (
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000004904.json"
    ):
        raise AssertionError("SEC companyfacts URL contract drifted")

    for required in (
        "class SECXBRLCompanyFactsClient(SECEDGARClient)",
        "_COMPANYFACTS_PATH_RE",
        "data.sec.gov",
        "companyfacts",
        "source_sha256",
    ):
        require(provider, required, "SEC XBRL source contract")
    for forbidden in ("urlopen", "requests.", "httpx", "www.sec.gov"):
        forbid(provider, forbidden, "parallel SEC network authority")

    for required in (
        "phase32_predictor_rows.jsonl",
        "SHA256_ZERO_PADDED_CIK_ASCENDING",
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
        "10-Q",
        "10-K",
        "us-gaap",
        "PIT accession/acceptance-time reconstruction",
    ):
        require(feasibility, required, "source-only feasibility contract")

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
        "phase32_development",
        "phase32_finalist_audit",
    ):
        forbid(feasibility, forbidden, "performance/trading/Phase32 selection dependency")

    require(runner, "Alpha hypotheses: NOT YET FROZEN", "runner blindness declaration")
    require(
        runner,
        "Market prices/returns/target outcomes/protected returns: FORBIDDEN / UNREAD",
        "runner outcome boundary",
    )
    require(runner, "Provider writes / broker / order / PAPER / LIVE / automation: DISABLED", "runner authority boundary")
    forbid(runner, "argparse", "operator scope override")

    for text, label in (
        (spec, "XBRL feasibility spec"),
        (roadmap, "roadmap"),
        (status, "current status"),
        (flow, "phase flow"),
        (readme, "README"),
    ):
        require(text, EXPECTED_PHASE32_MERGE, f"{label} Phase32 merged lineage")
        require(text, EXPECTED_CONTRACT, f"{label} current XBRL contract")
        require(text, EXPECTED_FINGERPRINT, f"{label} current XBRL fingerprint")
        require(text, "Phase33", f"{label} downstream boundary")

    require(spec, "No alpha hypothesis is frozen", "spec pre-performance boundary")
    require(spec, "Only unique zero-padded `issuer_cik` values are extracted", "CIK-only Phase32 reuse")
    require(spec, "FEASIBILITY_PASS", "feasibility acceptance semantics")
    require(roadmap, "OPEN: SOURCE-ONLY FEASIBILITY", "roadmap current gate state")
    require(status, "no alpha hypotheses frozen and no market outcomes authorized", "status current authority")
    require(flow, "Market prices/returns, target outcomes, and protected returns are **forbidden / unread**", "flow outcome boundary")
    require(readme, "source-only SEC XBRL feasibility", "README current gate")

    require(workflow, "validate_alpha_gate_xbrl_feasibility.py", "dedicated validator CI")
    require(workflow, "test_alpha_gate_xbrl_feasibility.py", "focused XBRL tests CI")
    require(workflow, "validate_phase32_closeout.py", "retained Phase32 closeout boundary CI")
    require(workflow, "windows-latest", "Windows parity")
    require(workflow, "ubuntu-latest", "Ubuntu parity")

    print("ATLAS pre-Phase33 SEC XBRL source-only feasibility contracts: PASS")
    print(f"- Phase32 accepted merge lineage: {EXPECTED_PHASE32_MERGE}")
    print(f"- feasibility fingerprint: {EXPECTED_FINGERPRINT}")
    print(f"- deterministic issuer sample: {EXPECTED_SAMPLE_SIZE}")
    print("- alpha hypotheses remain unfrozen; target/protected market outcomes remain forbidden")
    print("- SEC companyfacts reuses the accepted EDGAR network/fair-access seam")
    print("- Phase32 candidate/performance/finalist evidence is excluded from the new mechanism")
    print("- provider writes, broker/order/PAPER/LIVE authority and automatic failover remain disabled")
    print("- Phase33 remains blocked pending accepted historical SUPPORTED alpha")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
