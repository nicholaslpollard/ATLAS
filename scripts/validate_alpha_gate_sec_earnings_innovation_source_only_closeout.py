from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_CONTRACT = (
    "alpha-gate-sec-earnings-innovation-closeout-v1-"
    "pit-source-integrity-failure-no-market-outcomes"
)
EXPECTED_FINGERPRINT = "29e72b427aa63c6ae2e0c25917fad0c9c948f2a2cd97c0d51f390ecd343baacc"
EXPECTED_DISPOSITION = "ACCEPTED_NEGATIVE_PIT_SOURCE_INTEGRITY_FAILURE"
EXPECTED_FAILED_PIT_SHA = "ca5d5494b9c4be0158bd5d89c2f5b70aae0ba3a717a4af60f437bf4eaad37cea"
EXPECTED_PARENT_SHA = "3c299447e0ed8fd48d10c8cc792cf57396d87378cb21575e219b624c6a50566a"


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing {label}: {needle}")


def _forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"forbidden {label}: {needle}")


def main() -> int:
    module_path = "packages/backtesting/alpha_gate_sec_earnings_innovation_closeout.py"
    runner_path = "scripts/close_alpha_gate_sec_earnings_innovation_source_only.py"
    doc_path = "docs/alpha_gate_sec_earnings_innovation_source_only_closeout.md"
    module = _read(module_path)
    runner = _read(runner_path)
    doc = _read(doc_path)
    ast.parse(module, filename=module_path)
    ast.parse(runner, filename=runner_path)

    from packages.backtesting.alpha_gate_sec_earnings_innovation_closeout import (
        EARNINGS_INNOVATION_ACCEPTED_FAILED_PIT_REPORT_SHA256,
        EARNINGS_INNOVATION_ACCEPTED_FEASIBILITY_PARENT_SHA256,
        EARNINGS_INNOVATION_CLOSEOUT_CONTRACT,
        EARNINGS_INNOVATION_CLOSEOUT_FINGERPRINT,
        EARNINGS_INNOVATION_SOURCE_DISPOSITION,
        earnings_innovation_closeout_fingerprint,
    )

    exact = {
        "contract": (EARNINGS_INNOVATION_CLOSEOUT_CONTRACT, EXPECTED_CONTRACT),
        "fingerprint constant": (EARNINGS_INNOVATION_CLOSEOUT_FINGERPRINT, EXPECTED_FINGERPRINT),
        "fingerprint recomputation": (earnings_innovation_closeout_fingerprint(), EXPECTED_FINGERPRINT),
        "source disposition": (EARNINGS_INNOVATION_SOURCE_DISPOSITION, EXPECTED_DISPOSITION),
        "failed PIT SHA": (EARNINGS_INNOVATION_ACCEPTED_FAILED_PIT_REPORT_SHA256, EXPECTED_FAILED_PIT_SHA),
        "feasibility parent SHA": (EARNINGS_INNOVATION_ACCEPTED_FEASIBILITY_PARENT_SHA256, EXPECTED_PARENT_SHA),
    }
    for label, (actual, expected) in exact.items():
        if actual != expected:
            raise AssertionError(f"SEC earnings-innovation accepted {label} drifted")

    for token in (
        '"period_context_ambiguities": 3',
        '"accession_metadata_contradictions": 6',
        '"audited_observations": 5896',
        '"repair_allowed_under_v1": False',
        '"target_outcome_rows_read": 0',
        '"protected_return_rows_read": 0',
        '"protected_holdout_consumed": False',
        '"historical_supported_alpha": 0',
        '"phase33_signal_to_trade_authority": False',
    ):
        _require(module, token, "accepted-negative closeout invariant")

    for forbidden in (
        "packages.providers",
        "read_parquet",
        "DuckDB",
        "packages.execution",
        "packages.brokers",
        ".submit_order(",
        ".place_order(",
    ):
        _forbid(module, forbidden, "provider/performance/trading dependency in closeout")
        _forbid(runner, forbidden, "provider/performance/trading dependency in closeout runner")

    for token in (
        EXPECTED_CONTRACT,
        EXPECTED_FINGERPRINT,
        EXPECTED_DISPOSITION,
        "three ambiguous earliest period contexts",
        "six accession/form/filing-date contradictions",
        "10-Q/A",
        "market outcomes remain unread",
        "Phase33",
        "materially different economic/information mechanism",
    ):
        _require(doc, token, "closeout documentation")

    _require(runner, "Provider calls: DISABLED / ZERO", "runner provider boundary")
    _require(runner, "Development market outcomes: FORBIDDEN / UNREAD", "runner development boundary")
    _require(runner, "Protected returns: FORBIDDEN / UNREAD", "runner protected boundary")

    print("SEC earnings-innovation source-only closeout contract validation: PASS")
    print(f"Closeout contract: {EXPECTED_CONTRACT}")
    print(f"Closeout fingerprint: {EXPECTED_FINGERPRINT}")
    print(f"Disposition: {EXPECTED_DISPOSITION}")
    print("Frozen v1 PIT source rules are not repairable after observation without changing the preregistration.")
    print("Market outcomes remain unread; protected holdout remains unconsumed; Phase33 remains blocked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
