from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_sec_earnings_innovation_closeout import (
    EARNINGS_INNOVATION_CLOSEOUT_CONTRACT,
    EARNINGS_INNOVATION_CLOSEOUT_FINGERPRINT,
    EarningsInnovationCloseoutError,
    close_sec_earnings_innovation_source_only,
)
from packages.core.settings import load_settings


def main() -> int:
    print("ATLAS Pre-Phase33 — SEC Earnings-Innovation Source-Only Closeout")
    print(f"Closeout contract: {EARNINGS_INNOVATION_CLOSEOUT_CONTRACT}")
    print(f"Closeout fingerprint: {EARNINGS_INNOVATION_CLOSEOUT_FINGERPRINT}")
    print("Frozen PIT audit: PRESERVED / NOT REWRITTEN")
    print("V2 diagnostic: PERSISTED EVIDENCE ONLY / NO PROVIDER REPLAY")
    print("Provider calls: DISABLED / ZERO")
    print("Development market outcomes: FORBIDDEN / UNREAD")
    print("Protected returns: FORBIDDEN / UNREAD")
    print("Broker / order / PAPER / LIVE / automation: DISABLED")
    print()

    try:
        report = close_sec_earnings_innovation_source_only(load_settings())
    except (EarningsInnovationCloseoutError, OSError, ValueError) as exc:
        print("SEC earnings-innovation source-only closeout: FAIL-CLOSED")
        print(f"Reason: {exc}")
        print("No source rule, market outcome, protected evidence, or trading authority was changed.")
        return 2

    print("SEC earnings-innovation source-only closeout: PASS")
    print(f"Disposition: {report['source_disposition']}")
    print(f"Preserved failed PIT report SHA-256: {report['failed_pit_report_sha256']}")
    print(f"Diagnostic report SHA-256: {report['diagnostic_report_sha256']}")
    print(f"Period-context ambiguities: {report['period_context_ambiguities']}")
    print(f"Accession-metadata contradictions: {report['accession_metadata_contradictions']}")
    print(f"Audited observations retained before failed gates: {report['audited_observations']}")
    print(f"Target outcome rows read: {report['target_outcome_rows_read']}")
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {report['protected_holdout_consumed']}")
    print(f"Historical supported alpha: {report['historical_supported_alpha']}")
    print(f"Phase33 Signal-to-Trade authority: {report['phase33_signal_to_trade_authority']}")
    print(f"Closeout report: {report['report_path']}")
    print("This exact v1 family is closed. Any future study must use a materially different economic/information alpha mechanism.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
