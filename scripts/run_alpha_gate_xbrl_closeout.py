from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_xbrl_closeout import (
    XBRL_ACCEPTED_DEVELOPMENT_TARGET_HEAD,
    XBRL_ACCEPTED_EVIDENCE_FINGERPRINT,
    XBRL_CLOSEOUT_CONTRACT,
    XBRLCloseoutError,
    validate_xbrl_negative_closeout,
)
from packages.backtesting.alpha_gate_xbrl_development import (
    XBRL_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT,
)
from packages.backtesting.alpha_gate_xbrl_scientific_policy import XBRL_SCIENTIFIC_FINGERPRINT
from packages.core.settings import load_settings


def main() -> int:
    print("ATLAS Pre-Phase33 SEC XBRL Fundamental Alpha — Negative Closeout")
    print(f"Closeout contract: {XBRL_CLOSEOUT_CONTRACT}")
    print(f"Accepted development target head: {XBRL_ACCEPTED_DEVELOPMENT_TARGET_HEAD}")
    print(f"Scientific fingerprint: {XBRL_SCIENTIFIC_FINGERPRINT}")
    print(f"Development implementation fingerprint: {XBRL_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT}")
    print(f"Accepted closeout evidence fingerprint: {XBRL_ACCEPTED_EVIDENCE_FINGERPRINT}")
    print("Protected returns: FORBIDDEN / UNREAD")
    print("Provider calls: DISABLED / ZERO")
    print("Provider writes / broker / orders / PAPER / LIVE / automation: DISABLED")
    print()

    try:
        result = validate_xbrl_negative_closeout(load_settings())
    except (XBRLCloseoutError, OSError, ValueError) as exc:
        print("XBRL negative closeout: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("No protected return, historical support, Phase33 entry, or trading authority was granted.")
        return 2

    evidence = result["evidence"]
    print("XBRL negative closeout: PASS")
    print(f"Disposition: {result['disposition']}")
    print(f"Evidence fingerprint: {result['evidence_fingerprint']}")
    print(f"Development report SHA-256: {evidence['development_report_sha256']}")
    print(f"Predictor report SHA-256: {evidence['predictor_report_sha256']}")
    print(f"Predictor rows SHA-256: {evidence['predictor_rows_sha256']}")
    print(f"Development outcomes SHA-256: {evidence['development_outcomes_sha256']}")
    print(f"Finalists SHA-256: {evidence['finalists_sha256']}")
    print(f"Development status: {evidence['development_status']}")
    print(f"Predictor rows: {evidence['predictor_rows']}")
    print(f"Development predictor rows: {evidence['development_predictor_rows']}")
    print(f"Development outcome rows: {evidence['development_outcome_rows']}")
    print(f"Protected predictor rows: {evidence['protected_predictor_rows']}")
    print(f"Selection passers: {evidence['selection_passers']}")
    print(f"Selection winners: {evidence['selection_winners']}")
    print(f"Internal finalists: {evidence['internal_finalists']}")
    print(
        "Protected-return eligible finalists: "
        f"{evidence['protected_return_eligible_finalists']}"
    )
    print(f"Protected return rows read: {result['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {result['protected_holdout_consumed']}")
    print(f"Historical supported alpha: {result['historical_supported_alpha']}")
    print(f"Phase33 authority: {result['phase33_signal_to_trade_authority']}")
    print(
        "Provider reads / provider writes / broker reads / broker writes / orders / PAPER / LIVE / automation: "
        f"{result['provider_reads_performed']} / {result['provider_writes_performed']} / "
        f"{result['broker_reads_performed']} / {result['broker_writes_performed']} / "
        f"{result['order_writes_performed']} / {result['paper_submits_performed']} / "
        f"{result['live_writes_performed']} / {result['automation_writes_performed']}"
    )
    print("Next scientific action: close this XBRL mechanism without support and select a materially different alpha mechanism; do not retune this family after results.")
    print(f"Pass: {result['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
