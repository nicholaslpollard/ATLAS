from __future__ import annotations

import inspect
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import packages.backtesting.alpha_gate_sec_earnings_innovation_pit_audit as gate
from packages.backtesting.alpha_gate_sec_earnings_innovation_pit_audit import (
    EARNINGS_INNOVATION_PIT_ALPHA_HYPOTHESES_FROZEN,
    EARNINGS_INNOVATION_PIT_ANNOUNCEMENT_TIMING_CLAIM,
    EARNINGS_INNOVATION_PIT_AUDIT_CONTRACT,
    EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT,
    EARNINGS_INNOVATION_PIT_AUTOMATIC_BROKER_FAILOVER,
    EARNINGS_INNOVATION_PIT_AUTOMATION_WRITES,
    EARNINGS_INNOVATION_PIT_BROKER_READS,
    EARNINGS_INNOVATION_PIT_BROKER_WRITES,
    EARNINGS_INNOVATION_PIT_DECISION_SESSION_RULE,
    EARNINGS_INNOVATION_PIT_LIVE_WRITES,
    EARNINGS_INNOVATION_PIT_MAX_ACCEPTANCE_NOT_AFTER_PERIOD_END,
    EARNINGS_INNOVATION_PIT_MAX_ACCESSION_METADATA_CONTRADICTIONS,
    EARNINGS_INNOVATION_PIT_MAX_DECISION_SESSION_ERRORS,
    EARNINGS_INNOVATION_PIT_MAX_PERIOD_CONTEXT_AMBIGUITIES,
    EARNINGS_INNOVATION_PIT_MIN_ACCEPTANCE_PROVEN_FRACTION,
    EARNINGS_INNOVATION_PIT_MIN_AUDITED_OBSERVATIONS,
    EARNINGS_INNOVATION_PIT_MIN_CALENDAR_YEARS_OBSERVED,
    EARNINGS_INNOVATION_PIT_MIN_COMPANYFACTS_HASH_MATCHES,
    EARNINGS_INNOVATION_PIT_MIN_HISTORY_READY_ISSUERS,
    EARNINGS_INNOVATION_PIT_MIN_SUBMISSIONS_ROOT_SUCCESS,
    EARNINGS_INNOVATION_PIT_MIN_SUE_BASELINE_READY_ISSUERS,
    EARNINGS_INNOVATION_PIT_ORDER_WRITES,
    EARNINGS_INNOVATION_PIT_PAPER_SUBMITS,
    EARNINGS_INNOVATION_PIT_PHASE33_SIGNAL_TO_TRADE_AUTHORITY,
    EARNINGS_INNOVATION_PIT_PROTECTED_OUTCOME_READS_ALLOWED,
    EARNINGS_INNOVATION_PIT_PROVIDER_WRITES,
    EARNINGS_INNOVATION_PIT_TARGET_OUTCOME_READS_ALLOWED,
    earnings_innovation_pit_audit_fingerprint,
)


def main() -> int:
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    require(
        EARNINGS_INNOVATION_PIT_AUDIT_CONTRACT
        == "alpha-gate-sec-earnings-innovation-pit-audit-v1-original-accession-acceptance-source-only-no-market-outcomes",
        "PIT audit contract drifted",
    )
    require(
        earnings_innovation_pit_audit_fingerprint() == EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT,
        "PIT audit fingerprint drifted",
    )
    require(EARNINGS_INNOVATION_PIT_MIN_COMPANYFACTS_HASH_MATCHES == 300, "Company Facts lineage gate drifted")
    require(EARNINGS_INNOVATION_PIT_MIN_SUBMISSIONS_ROOT_SUCCESS == 295, "submissions root gate drifted")
    require(EARNINGS_INNOVATION_PIT_MIN_AUDITED_OBSERVATIONS == 4000, "audited-observation gate drifted")
    require(EARNINGS_INNOVATION_PIT_MIN_HISTORY_READY_ISSUERS == 160, "history-ready gate drifted")
    require(EARNINGS_INNOVATION_PIT_MIN_SUE_BASELINE_READY_ISSUERS == 130, "SUE-ready gate drifted")
    require(EARNINGS_INNOVATION_PIT_MIN_ACCEPTANCE_PROVEN_FRACTION == 0.95, "acceptance-coverage gate drifted")
    require(EARNINGS_INNOVATION_PIT_MIN_CALENDAR_YEARS_OBSERVED == 8, "calendar breadth gate drifted")
    require(EARNINGS_INNOVATION_PIT_MAX_PERIOD_CONTEXT_AMBIGUITIES == 0, "period ambiguity gate drifted")
    require(EARNINGS_INNOVATION_PIT_MAX_ACCESSION_METADATA_CONTRADICTIONS == 0, "metadata contradiction gate drifted")
    require(EARNINGS_INNOVATION_PIT_MAX_ACCEPTANCE_NOT_AFTER_PERIOD_END == 0, "acceptance chronology gate drifted")
    require(EARNINGS_INNOVATION_PIT_MAX_DECISION_SESSION_ERRORS == 0, "decision-session gate drifted")
    require(
        EARNINGS_INNOVATION_PIT_DECISION_SESSION_RULE
        == "FIRST_XNYS_REGULAR_SESSION_OPEN_STRICTLY_AFTER_SEC_ACCEPTANCE",
        "decision-session rule drifted",
    )
    require(
        EARNINGS_INNOVATION_PIT_ANNOUNCEMENT_TIMING_CLAIM == "NOT_ESTABLISHED_PIT_PERIODIC_FILING_ONLY",
        "announcement timing boundary drifted",
    )
    require(EARNINGS_INNOVATION_PIT_ALPHA_HYPOTHESES_FROZEN is False, "hypotheses froze too early")
    require(EARNINGS_INNOVATION_PIT_TARGET_OUTCOME_READS_ALLOWED is False, "target outcomes opened")
    require(EARNINGS_INNOVATION_PIT_PROTECTED_OUTCOME_READS_ALLOWED is False, "protected outcomes opened")
    require(EARNINGS_INNOVATION_PIT_PROVIDER_WRITES == 0, "provider writes opened")
    require(EARNINGS_INNOVATION_PIT_BROKER_READS == 0, "broker reads opened")
    require(EARNINGS_INNOVATION_PIT_BROKER_WRITES == 0, "broker writes opened")
    require(EARNINGS_INNOVATION_PIT_ORDER_WRITES == 0, "order writes opened")
    require(EARNINGS_INNOVATION_PIT_PAPER_SUBMITS == 0, "PAPER submits opened")
    require(EARNINGS_INNOVATION_PIT_LIVE_WRITES == 0, "LIVE writes opened")
    require(EARNINGS_INNOVATION_PIT_AUTOMATION_WRITES == 0, "automation writes opened")
    require(EARNINGS_INNOVATION_PIT_AUTOMATIC_BROKER_FAILOVER is False, "automatic broker failover opened")
    require(EARNINGS_INNOVATION_PIT_PHASE33_SIGNAL_TO_TRADE_AUTHORITY is False, "Phase33 authority opened")

    source = inspect.getsource(gate)
    for token in ("MarketDataPaths", "read_parquet", "DuckDB", "stock_return", "spy_return"):
        require(token not in source, f"source-only PIT audit contains forbidden market-outcome token: {token}")

    focused = (PROJECT_ROOT / ".github/workflows/sec-earnings-innovation-alpha-gate-tests.yml").read_text(encoding="utf-8")
    retained = (PROJECT_ROOT / ".github/workflows/atlas-tests.yml").read_text(encoding="utf-8")
    doc = (PROJECT_ROOT / "docs/alpha_gate_sec_earnings_innovation_pit_audit.md").read_text(encoding="utf-8")
    require("validate_alpha_gate_sec_earnings_innovation_pit_audit.py" in focused, "focused workflow missing PIT validator")
    require("validate_alpha_gate_sec_earnings_innovation_pit_audit.py" in retained, "retained workflow missing PIT validator")
    require(EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT in doc, "PIT documentation missing fingerprint")
    require("does not establish an earnings-announcement timestamp" in doc, "PIT documentation lost announcement boundary")

    if errors:
        print("SEC earnings-innovation PIT audit contract validation: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("SEC earnings-innovation PIT audit contract validation: PASS")
    print(f"Contract: {EARNINGS_INNOVATION_PIT_AUDIT_CONTRACT}")
    print(f"Fingerprint: {EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT}")
    print("Market outcomes/protected returns: FORBIDDEN / UNREAD")
    print("Phase33 / broker / order / PAPER / LIVE / automation authority: DISABLED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
