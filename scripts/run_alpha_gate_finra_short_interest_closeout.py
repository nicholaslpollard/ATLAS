from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_finra_short_interest_closeout import (
    FINRA_SHORT_INTEREST_ACCEPTED_CLOSEOUT_EVIDENCE_FINGERPRINT,
    FINRA_SHORT_INTEREST_CLOSEOUT_CONTRACT,
    FINRAShortInterestCloseoutError,
    validate_finra_source_only_negative_closeout,
)
from packages.core.settings import load_settings


def main() -> int:
    print("ATLAS Pre-Phase33 — FINRA Short Interest Accepted-Negative Closeout")
    print(f"Closeout contract: {FINRA_SHORT_INTEREST_CLOSEOUT_CONTRACT}")
    print("Provider calls: DISABLED / ZERO")
    print("Development market outcomes: FORBIDDEN / UNREAD")
    print("Protected returns: FORBIDDEN / UNREAD")
    print()
    try:
        report = validate_finra_source_only_negative_closeout(load_settings())
    except (FINRAShortInterestCloseoutError, OSError, ValueError) as exc:
        print("FINRA source-only closeout: NOT ACCEPTED")
        print(f"Reason: {exc}")
        return 1

    print("FINRA source-only closeout: PASS")
    print(f"Disposition: {report['disposition']}")
    print(f"Source disposition: {report['source_disposition']}")
    print(
        "Accepted closeout evidence fingerprint: "
        f"{FINRA_SHORT_INTEREST_ACCEPTED_CLOSEOUT_EVIDENCE_FINGERPRINT}"
    )
    print(f"Historical supported alpha: {report['historical_supported_alpha']}")
    print(f"Target outcome rows read: {report['target_outcome_rows_read']}")
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {report['protected_holdout_consumed']}")
    print(f"Phase33 authority: {report['phase33_signal_to_trade_authority']}")
    print(f"Next scientific action: {report['next_scientific_action']}")
    print("Pass: True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
