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
EXPECTED_ACCEPTED_EVIDENCE_FINGERPRINT = (
    "33953ffe4543e2e9a98160821b67efd966d1974bc1685850fb2633ee138365a9"
)
EXPECTED_PIT_AUDIT_FINGERPRINT = (
    "50e68495d71f15b24e27800b66e32ab12b914162be60906058086ffc14b1519c"
)
EXPECTED_CLOSEOUT_EVIDENCE_FINGERPRINT = (
    "291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91"
)
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

    # These assertions bind the historical feasibility stage itself. Later stages
    # may freeze hypotheses and read development outcomes, but cannot rewrite what
    # the feasibility stage was authorized to do.
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
    require(
        runner,
        "Provider writes / broker / order / PAPER / LIVE / automation: DISABLED",
        "runner authority boundary",
    )
    forbid(runner, "argparse", "operator scope override")

    # Evidence-bearing living docs retain the complete historical feasibility
    # lineage. The operational phase-flow doc records final authority/cadence state
    # without being forced to duplicate every archival fingerprint.
    for text, label in (
        (spec, "XBRL mechanism spec"),
        (roadmap, "roadmap"),
        (status, "current status"),
        (readme, "README"),
    ):
        require(text, EXPECTED_PHASE32_MERGE, f"{label} Phase32 merged lineage")
        require(text, EXPECTED_CONTRACT, f"{label} retained XBRL feasibility contract")
        require(text, EXPECTED_FINGERPRINT, f"{label} retained XBRL feasibility fingerprint")
        require(text, "FEASIBILITY_PASS", f"{label} accepted feasibility state")
        require(text, "200", f"{label} accepted successful-document evidence")
        require(text, "170", f"{label} accepted accrual-readiness evidence")
        require(text, "92", f"{label} accepted profitability-readiness evidence")
        require(
            text,
            EXPECTED_ACCEPTED_EVIDENCE_FINGERPRINT,
            f"{label} accepted target feasibility evidence fingerprint",
        )
        require(
            text,
            EXPECTED_PIT_AUDIT_FINGERPRINT,
            f"{label} retained frozen PIT audit fingerprint",
        )
        require(
            text,
            EXPECTED_CLOSEOUT_EVIDENCE_FINGERPRINT,
            f"{label} final XBRL closeout evidence fingerprint",
        )
        require(text, "ACCEPTED_NEGATIVE", f"{label} final XBRL disposition")
        require(text, "Phase33", f"{label} downstream boundary")

    require(flow, "Accepted project foundation: **through Phase32**", "phase flow numbered boundary")
    require(flow, "FEASIBILITY_PASS", "phase flow retained feasibility state")
    require(flow, EXPECTED_CLOSEOUT_EVIDENCE_FINGERPRINT, "phase flow final XBRL closeout fingerprint")
    require(flow, "XBRL protected return rows read = **0**", "phase flow protected-return boundary")
    require(flow, "Phase33", "phase flow downstream boundary")

    require(spec, "Only issuer CIK discovery was reused", "CIK-only Phase32 reuse")
    require(spec, "target outcome rows read: **0**", "historical feasibility outcome blindness")
    require(spec, "protected return rows read: **0**", "protected-return boundary")
    require(roadmap, "Completed Pre-Phase33 SEC XBRL", "roadmap completed XBRL state")
    require(status, "XBRL fundamental-quality/accrual mechanism — final `ACCEPTED_NEGATIVE`", "status completed XBRL state")
    require(readme, "XBRL protected return rows read = **0**", "README protected-return boundary")

    require(workflow, "validate_alpha_gate_xbrl_feasibility.py", "dedicated feasibility validator CI")
    require(workflow, "test_alpha_gate_xbrl_feasibility.py", "focused feasibility tests CI")
    require(workflow, "validate_phase32_closeout.py", "retained Phase32 closeout boundary CI")
    require(workflow, "windows-latest", "Windows parity")
    require(workflow, "ubuntu-latest", "Ubuntu parity")

    print("ATLAS pre-Phase33 SEC XBRL source-only feasibility contracts: PASS")
    print(f"- Phase32 accepted merge lineage: {EXPECTED_PHASE32_MERGE}")
    print(f"- feasibility fingerprint: {EXPECTED_FINGERPRINT}")
    print(f"- deterministic issuer sample: {EXPECTED_SAMPLE_SIZE}")
    print(f"- accepted target feasibility evidence fingerprint: {EXPECTED_ACCEPTED_EVIDENCE_FINGERPRINT}")
    print("- accepted target source evidence: 200 successful documents / 170 accrual-ready / 92 profitability-ready")
    print("- frozen feasibility implementation remains zero-outcome and unchanged after later XBRL stages")
    print("- evidence-bearing docs retain historical lineage; operational phase flow retains final authority state")
    print("- protected returns remain unread; Phase33 remains blocked")
    print("- provider writes, broker/order/PAPER/LIVE authority and automatic failover remain disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
