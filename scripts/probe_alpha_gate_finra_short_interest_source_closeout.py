from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_finra_short_interest_source_closeout_probe import (
    FINRA_SHORT_INTEREST_SOURCE_CLOSEOUT_PROBE_CONTRACT,
    FINRAShortInterestSourceCloseoutProbeError,
    collect_finra_source_only_closeout_evidence,
)
from packages.core.settings import load_settings


def main() -> int:
    print("ATLAS Pre-Phase33 — FINRA Short Interest Source-Only Closeout Probe")
    print(f"Probe contract: {FINRA_SHORT_INTEREST_SOURCE_CLOSEOUT_PROBE_CONTRACT}")
    print("Provider reads/writes: 0 / 0")
    print("Market outcome reads: 0")
    print("Protected return reads: 0")
    print()
    try:
        evidence = collect_finra_source_only_closeout_evidence(load_settings())
    except (FINRAShortInterestSourceCloseoutProbeError, OSError, ValueError) as exc:
        print("Source-only closeout probe: NOT ACCEPTED")
        print(f"Reason: {exc}")
        return 1

    print("Source-only closeout probe: PASS")
    print(f"Disposition: {evidence['disposition']}")
    print(f"Predictor rows: {evidence['predictor_rows']}")
    print(f"Stage counts: {evidence['stage_counts']}")
    print(f"Candidate counts: {evidence['candidate_counts']}")
    print(f"Candidate stage counts: {evidence['candidate_stage_counts']}")
    print(f"Underpowered candidate: {evidence['underpowered_candidate']}")
    print(
        "Underpowered protected source: "
        f"{evidence['underpowered_protected_source']}"
    )
    print(f"Failing frozen gate: {evidence['failing_gate']}")
    print(f"Predictor report SHA-256: {evidence['predictor_report_sha256']}")
    print(f"Predictor rows SHA-256: {evidence['predictor_rows_sha256']}")
    print(f"Evidence fingerprint: {evidence['evidence_fingerprint']}")
    print(f"Target outcome rows read: {evidence['target_outcome_rows_read']}")
    print(f"Protected return rows read: {evidence['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {evidence['protected_holdout_consumed']}")
    print(f"Phase33 authority: {evidence['phase33_signal_to_trade_authority']}")
    print("Pass: True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
