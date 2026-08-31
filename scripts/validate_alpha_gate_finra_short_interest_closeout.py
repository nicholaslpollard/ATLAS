from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_CONTRACT = (
    "alpha-gate-finra-short-interest-closeout-v1-"
    "protected-source-insufficient-no-market-outcomes"
)
EXPECTED_SOURCE_TARGET_HEAD = "d312ec95752ab49a6fcbec18973faacb96d4aa89"
EXPECTED_PROBE_HEAD = "5ceac74ad67c8f3539b03192cf1946d51d476434"
EXPECTED_SCIENTIFIC = "0b32d59677e86544777807525cd4aba13dd36fd0fcfd7744458556205561d13f"
EXPECTED_REPORT_SHA = "56479707945a59752aeb2056f3cfbcfd2df1e4a87ada31c9e8e6d3ed93f314cd"
EXPECTED_ROWS_SHA = "21c7dd2e44013ba0f1d290019db70f7b0f23b0603c5e965cbd8b441128190e48"
EXPECTED_PROBE_EVIDENCE = "c624da82b45fb8d530c2400262598f266ec6309e614a0dcd135b38d9ba5518ce"
EXPECTED_CLOSEOUT_EVIDENCE = "bdd494a01ed23d891c460e353831cba6f9cf010c5bf38cf1c9c527b4abe8b565"


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing {label}: {needle}")


def _forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"forbidden {label}: {needle}")


def main() -> int:
    module_path = "packages/backtesting/alpha_gate_finra_short_interest_closeout.py"
    runner_path = "scripts/run_alpha_gate_finra_short_interest_closeout.py"
    closeout_doc_path = "docs/alpha_gate_finra_short_interest_source_only_closeout.md"
    module = _read(module_path)
    runner = _read(runner_path)
    closeout_doc = _read(closeout_doc_path)
    ast.parse(module, filename=module_path)
    ast.parse(runner, filename=runner_path)

    from packages.backtesting.alpha_gate_finra_short_interest_closeout import (
        FINRA_SHORT_INTEREST_ACCEPTED_CLOSEOUT_EVIDENCE_FINGERPRINT,
        FINRA_SHORT_INTEREST_ACCEPTED_PREDICTOR_REPORT_SHA256,
        FINRA_SHORT_INTEREST_ACCEPTED_PREDICTOR_ROWS_SHA256,
        FINRA_SHORT_INTEREST_ACCEPTED_PROBE_EVIDENCE_FINGERPRINT,
        FINRA_SHORT_INTEREST_ACCEPTED_PROBE_HEAD,
        FINRA_SHORT_INTEREST_ACCEPTED_SOURCE_TARGET_HEAD,
        FINRA_SHORT_INTEREST_CLOSEOUT_CONTRACT,
    )
    from packages.backtesting.alpha_gate_finra_short_interest_scientific_policy import (
        FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT,
    )

    exact = {
        "contract": (FINRA_SHORT_INTEREST_CLOSEOUT_CONTRACT, EXPECTED_CONTRACT),
        "source target head": (
            FINRA_SHORT_INTEREST_ACCEPTED_SOURCE_TARGET_HEAD,
            EXPECTED_SOURCE_TARGET_HEAD,
        ),
        "probe head": (FINRA_SHORT_INTEREST_ACCEPTED_PROBE_HEAD, EXPECTED_PROBE_HEAD),
        "scientific fingerprint": (
            FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT,
            EXPECTED_SCIENTIFIC,
        ),
        "predictor report SHA": (
            FINRA_SHORT_INTEREST_ACCEPTED_PREDICTOR_REPORT_SHA256,
            EXPECTED_REPORT_SHA,
        ),
        "predictor rows SHA": (
            FINRA_SHORT_INTEREST_ACCEPTED_PREDICTOR_ROWS_SHA256,
            EXPECTED_ROWS_SHA,
        ),
        "probe evidence fingerprint": (
            FINRA_SHORT_INTEREST_ACCEPTED_PROBE_EVIDENCE_FINGERPRINT,
            EXPECTED_PROBE_EVIDENCE,
        ),
        "closeout evidence fingerprint": (
            FINRA_SHORT_INTEREST_ACCEPTED_CLOSEOUT_EVIDENCE_FINGERPRINT,
            EXPECTED_CLOSEOUT_EVIDENCE,
        ),
    }
    for label, (actual, expected) in exact.items():
        if actual != expected:
            raise AssertionError(f"FINRA accepted {label} drifted")

    for token in (
        "FINRA_SHORT_INTEREST_ACCEPTED_PREDICTOR_ROWS = 19_343",
        "FINRA_SHORT_INTEREST_ACCEPTED_DEVELOPMENT_ROWS = 14_841",
        "FINRA_SHORT_INTEREST_ACCEPTED_PROTECTED_ROWS = 4_502",
        "FINRA_SHORT_INTEREST_ACCEPTED_UNDERPOWERED_PROTECTED_EVENT_ROWS = 257",
        "FINRA_SHORT_INTEREST_ACCEPTED_UNDERPOWERED_PROTECTED_SIGNAL_SESSIONS = 26",
        "FINRA_SHORT_INTEREST_ACCEPTED_UNDERPOWERED_PROTECTED_UNIQUE_INSTRUMENTS = 211",
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
        "MassiveReferenceProvider",
        "FINRAShortInterestClient",
        "packages.execution",
        "packages.brokers",
        ".submit_order(",
        ".place_order(",
    ):
        _forbid(module, forbidden, "provider/performance/trading dependency in closeout")
        _forbid(runner, forbidden, "provider/performance/trading dependency in closeout runner")

    for token in (
        EXPECTED_CLOSEOUT_EVIDENCE,
        "ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT",
        "257",
        "300",
        "26",
        "211",
        "market outcomes were never opened",
        "Phase33",
    ):
        _require(closeout_doc, token, "closeout documentation")

    _require(runner, "Provider calls: DISABLED / ZERO", "runner provider boundary")
    _require(runner, "Development market outcomes: FORBIDDEN / UNREAD", "runner development boundary")
    _require(runner, "Protected returns: FORBIDDEN / UNREAD", "runner protected boundary")
    _require(runner, "materially different economic/information alpha mechanism", "runner next mechanism")

    print("FINRA short-interest accepted-negative closeout validation: PASS")
    print(f"Closeout contract: {EXPECTED_CONTRACT}")
    print(f"Accepted closeout evidence fingerprint: {EXPECTED_CLOSEOUT_EVIDENCE}")
    print("Exact four-hypothesis v1 is closed; no post-result pruning or threshold retuning allowed.")
    print("Development and protected market returns remain unread; Phase33 remains blocked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
