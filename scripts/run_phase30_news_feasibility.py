from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase30_feasibility import (
    PHASE30_PROVIDER_INSIGHTS_AUTHORITY,
    Phase30FeasibilityError,
    Phase30NewsFeasibility,
    phase30_feasibility_fingerprint,
)
from packages.core.exceptions import ProviderError
from packages.core.settings import load_settings
from packages.providers.massive.phase30 import MassivePhase30NewsClient
from packages.providers.massive.rest import MassiveRESTClient


def main() -> int:
    print("ATLAS Phase 30 — Historical News PIT/Provenance Feasibility")
    print(f"Frozen feasibility fingerprint: {phase30_feasibility_fingerprint()}")
    print("Source: accepted MassiveRESTClient -> /v2/reference/news")
    print("Scope: exact historical coverage/timestamps/ticker linkage/pagination/provenance only")
    print(f"Provider insights authority: {PHASE30_PROVIDER_INSIGHTS_AUTHORITY}")
    print("Alpha hypotheses: NOT YET FROZEN")
    print("Target/protected market outcomes: FORBIDDEN / UNREAD")
    print("Broker/order/PAPER/LIVE activity: DISABLED")
    print()

    settings = load_settings()
    client = MassivePhase30NewsClient(MassiveRESTClient(settings))
    try:
        report = Phase30NewsFeasibility(settings, client).run()
    except (Phase30FeasibilityError, ProviderError, OSError, ValueError) as exc:
        print("Phase 30 historical-news feasibility: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("No alpha hypothesis or trading authority was granted.")
        return 2

    print("Phase 30 historical-news feasibility: PASS")
    for window in report["windows"]:
        print(
            f"  {window['label']}: articles={window['articles']} "
            f"ticker_linked={window['ticker_linked_articles']} "
            f"pages={window['successful_pages']} sha256={window['evidence_sha256']}"
        )
    print(f"Total articles: {report['total_articles']}")
    print(f"Total ticker-linked articles: {report['total_ticker_linked_articles']}")
    print(f"Successful provider pages: {report['successful_provider_pages']}")
    print(f"Target outcome rows read: {report['target_outcome_rows_read']}")
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print("Provider writes / broker reads / broker writes / orders / PAPER / LIVE: 0 / 0 / 0 / 0 / 0 / 0")
    print(f"Feasibility report: {report['report_path']}")
    print("Next scientific action: freeze a finite Phase 30 alpha contract before any performance read.")
    print(f"Pass: {report['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
