from __future__ import annotations

import inspect
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import packages.backtesting.alpha_gate_sec_earnings_innovation_feasibility as gate
from packages.backtesting.alpha_gate_sec_earnings_innovation_feasibility import (
    EARNINGS_INNOVATION_ALPHA_HYPOTHESES_FROZEN,
    EARNINGS_INNOVATION_ANNOUNCEMENT_TIMING_CLAIM,
    EARNINGS_INNOVATION_AUTOMATIC_BROKER_FAILOVER,
    EARNINGS_INNOVATION_AUTOMATION_WRITES,
    EARNINGS_INNOVATION_BROKER_READS,
    EARNINGS_INNOVATION_BROKER_WRITES,
    EARNINGS_INNOVATION_FEASIBILITY_CONTRACT,
    EARNINGS_INNOVATION_FEASIBILITY_FINGERPRINT,
    EARNINGS_INNOVATION_HISTORY_READY_MIN_DIRECT_QUARTERS,
    EARNINGS_INNOVATION_LIVE_WRITES,
    EARNINGS_INNOVATION_MAX_SAME_ACCESSION_CONTEXT_CONFLICTS,
    EARNINGS_INNOVATION_MIN_CALENDAR_YEARS_OBSERVED,
    EARNINGS_INNOVATION_MIN_DIRECT_QUARTER_OBSERVATIONS,
    EARNINGS_INNOVATION_MIN_EPS_DOCUMENTS,
    EARNINGS_INNOVATION_MIN_HISTORY_READY_ISSUERS,
    EARNINGS_INNOVATION_MIN_SUCCESSFUL_DOCUMENTS,
    EARNINGS_INNOVATION_MIN_SUE_BASELINE_READY_ISSUERS,
    EARNINGS_INNOVATION_ORDER_WRITES,
    EARNINGS_INNOVATION_PAPER_SUBMITS,
    EARNINGS_INNOVATION_PHASE33_SIGNAL_TO_TRADE_AUTHORITY,
    EARNINGS_INNOVATION_PROTECTED_OUTCOME_READS_ALLOWED,
    EARNINGS_INNOVATION_PROVIDER_WRITES,
    EARNINGS_INNOVATION_SAMPLE_SIZE,
    EARNINGS_INNOVATION_SUE_BASELINE_READY_MIN_DIRECT_QUARTERS,
    EARNINGS_INNOVATION_TARGET_OUTCOME_READS_ALLOWED,
    earnings_innovation_feasibility_fingerprint,
)


def main() -> int:
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    require(
        EARNINGS_INNOVATION_FEASIBILITY_CONTRACT
        == "alpha-gate-sec-earnings-innovation-feasibility-v1-diluted-eps-source-only-no-market-outcomes",
        "feasibility contract drifted",
    )
    require(
        earnings_innovation_feasibility_fingerprint()
        == EARNINGS_INNOVATION_FEASIBILITY_FINGERPRINT,
        "feasibility fingerprint drifted",
    )
    require(EARNINGS_INNOVATION_SAMPLE_SIZE == 300, "sample size drifted")
    require(
        EARNINGS_INNOVATION_HISTORY_READY_MIN_DIRECT_QUARTERS == 12,
        "history-depth gate drifted",
    )
    require(
        EARNINGS_INNOVATION_SUE_BASELINE_READY_MIN_DIRECT_QUARTERS == 16,
        "SUE baseline-depth gate drifted",
    )
    require(EARNINGS_INNOVATION_MIN_SUCCESSFUL_DOCUMENTS == 270, "successful-doc gate drifted")
    require(EARNINGS_INNOVATION_MIN_EPS_DOCUMENTS == 210, "EPS-doc gate drifted")
    require(EARNINGS_INNOVATION_MIN_HISTORY_READY_ISSUERS == 180, "history-ready gate drifted")
    require(
        EARNINGS_INNOVATION_MIN_SUE_BASELINE_READY_ISSUERS == 120,
        "SUE-ready gate drifted",
    )
    require(
        EARNINGS_INNOVATION_MIN_DIRECT_QUARTER_OBSERVATIONS == 2500,
        "direct-quarter observation gate drifted",
    )
    require(EARNINGS_INNOVATION_MIN_CALENDAR_YEARS_OBSERVED == 8, "calendar breadth gate drifted")
    require(
        EARNINGS_INNOVATION_MAX_SAME_ACCESSION_CONTEXT_CONFLICTS == 0,
        "same-accession conflict gate drifted",
    )
    require(
        EARNINGS_INNOVATION_ANNOUNCEMENT_TIMING_CLAIM
        == "NOT_ESTABLISHED_AT_FEASIBILITY_GATE",
        "announcement-timing boundary drifted",
    )
    require(EARNINGS_INNOVATION_ALPHA_HYPOTHESES_FROZEN is False, "hypotheses froze too early")
    require(EARNINGS_INNOVATION_TARGET_OUTCOME_READS_ALLOWED is False, "target outcomes opened")
    require(EARNINGS_INNOVATION_PROTECTED_OUTCOME_READS_ALLOWED is False, "protected outcomes opened")
    require(EARNINGS_INNOVATION_PROVIDER_WRITES == 0, "provider mutation authority opened")
    require(EARNINGS_INNOVATION_BROKER_READS == 0, "broker reads opened")
    require(EARNINGS_INNOVATION_BROKER_WRITES == 0, "broker writes opened")
    require(EARNINGS_INNOVATION_ORDER_WRITES == 0, "order writes opened")
    require(EARNINGS_INNOVATION_PAPER_SUBMITS == 0, "PAPER submits opened")
    require(EARNINGS_INNOVATION_LIVE_WRITES == 0, "LIVE writes opened")
    require(EARNINGS_INNOVATION_AUTOMATION_WRITES == 0, "automation writes opened")
    require(EARNINGS_INNOVATION_AUTOMATIC_BROKER_FAILOVER is False, "automatic failover opened")
    require(
        EARNINGS_INNOVATION_PHASE33_SIGNAL_TO_TRADE_AUTHORITY is False,
        "Phase33 authority opened",
    )

    source = inspect.getsource(gate)
    forbidden_tokens = (
        "MarketDataPaths",
        "read_parquet",
        "stock_return",
        "spy_return",
        "entry_open",
        "exit_close",
        "DuckDB",
    )
    for token in forbidden_tokens:
        require(token not in source, f"source-only feasibility module contains forbidden outcome token: {token}")

    workflow = (PROJECT_ROOT / ".github/workflows/sec-earnings-innovation-alpha-gate-tests.yml").read_text(
        encoding="utf-8"
    )
    atlas_workflow = (PROJECT_ROOT / ".github/workflows/atlas-tests.yml").read_text(encoding="utf-8")
    doc = (PROJECT_ROOT / "docs/alpha_gate_sec_earnings_innovation_feasibility.md").read_text(
        encoding="utf-8"
    )
    require(
        "validate_alpha_gate_sec_earnings_innovation_feasibility.py" in workflow,
        "focused workflow does not validate earnings-innovation feasibility",
    )
    require(
        "validate_alpha_gate_sec_earnings_innovation_feasibility.py" in atlas_workflow,
        "full retained workflow does not validate earnings-innovation feasibility",
    )
    require(
        "not an earnings-announcement PEAD gate" in doc,
        "documentation lost the earnings-announcement timing boundary",
    )
    require(
        EARNINGS_INNOVATION_FEASIBILITY_FINGERPRINT in doc,
        "documentation does not retain frozen feasibility fingerprint",
    )

    if errors:
        print("SEC earnings-innovation feasibility contract validation: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("SEC earnings-innovation feasibility contract validation: PASS")
    print(f"Contract: {EARNINGS_INNOVATION_FEASIBILITY_CONTRACT}")
    print(f"Fingerprint: {EARNINGS_INNOVATION_FEASIBILITY_FINGERPRINT}")
    print("Market outcomes/protected returns: FORBIDDEN / UNREAD")
    print("Phase33 / broker / order / PAPER / LIVE / automation authority: DISABLED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
