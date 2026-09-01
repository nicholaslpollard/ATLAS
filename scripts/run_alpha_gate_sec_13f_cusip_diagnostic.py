from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_sec_13f_cusip_diagnostic import (  # noqa: E402
    SEC13FCusipDiagnostic,
    SEC_13F_CUSIP_DIAGNOSTIC_CONTRACT,
)
from packages.core.settings import load_settings  # noqa: E402


def main() -> int:
    print("ATLAS Pre-Phase33 — SEC Form 13F 2016Q1 CUSIP Source Diagnostic")
    print(f"Diagnostic contract: {SEC_13F_CUSIP_DIAGNOSTIC_CONTRACT}")
    print("Input: preserved Gate0 v2 2016Q1 SEC ZIP only")
    print("Provider reads: 0")
    print("CUSIP repair / ATLAS identity / market outcomes: FORBIDDEN")
    print()
    result = SEC13FCusipDiagnostic(load_settings()).run()
    print(f"Gate0 status preserved: {result['gate0_status_preserved']}")
    print(f"Initial 13F-HR holding rows: {result['initial_hr_rows']}")
    print(f"Nine-character CUSIP rows: {result['nine_char_rows']}")
    print(f"Malformed CUSIP rows: {result['malformed_rows']}")
    print(f"Malformed fraction: {result['malformed_fraction']:.6f}")
    print(f"Blank rows: {result['blank_rows']}")
    print(f"Short nonblank rows: {result['short_nonblank_rows']}")
    print(f"Long rows: {result['long_rows']}")
    print(f"CUSIP length histogram: {result['cusip_length_histogram']}")
    print(f"Unique malformed values: {result['unique_malformed_values']}")
    print(f"Malformed accessions: {result['malformed_accessions']}")
    print(
        "Left-zero-pad candidate already seen as valid in same archive rows: "
        f"{result['left_zero_pad_candidate_seen_as_valid_rows']}"
    )
    print(
        "Same issuer/class has exactly one valid 9-char CUSIP rows: "
        f"{result['same_issuer_class_single_valid_cusip_rows']}"
    )
    print(
        "Both diagnostic signals agree rows: "
        f"{result['both_diagnostic_signals_agree_rows']}"
    )
    print("Top malformed values:")
    for item in result["top_malformed_values"][:15]:
        print(f"  {item['value']!r}: {item['rows']}")
    print("Top malformed accessions:")
    for item in result["top_malformed_accessions"][:15]:
        print(f"  {item['value']}: {item['rows']}")
    governance = result["governance"]
    print(f"Target outcome rows read: {governance['target_outcome_rows_read']}")
    print(f"Protected return rows read: {governance['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {governance['protected_holdout_consumed']}")
    print(f"Scientific freeze allowed: {governance['scientific_freeze_allowed']}")
    print(f"Phase33 authority: {governance['phase33_signal_to_trade_authority']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
