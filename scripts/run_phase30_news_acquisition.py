from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase30_acquisition import (
    Phase30NewsAcquisition,
    Phase30NewsAcquisitionError,
    phase30_news_shard_windows,
)
from packages.backtesting.phase30_policy import (
    PHASE30_AUTHORIZED_NEWS_ALPHA_FIELDS,
    PHASE30_PROVIDER_CONTENT_ALPHA_AUTHORITY,
    PHASE30_PROVIDER_INSIGHTS_ALPHA_AUTHORITY,
    phase30_policy_fingerprint,
)
from packages.core.exceptions import ProviderError
from packages.core.settings import load_settings
from packages.providers.massive.phase30 import MassivePhase30NewsClient
from packages.providers.massive.rest import MassiveRESTClient


def main() -> int:
    print("ATLAS Phase 30 — Frozen Scientific Contract + Full Historical News Acquisition")
    print(f"Frozen Phase30 policy fingerprint: {phase30_policy_fingerprint()}")
    print("Scientific hypotheses: FROZEN (4 total; global Holm family = 4)")
    print(f"Authorized news alpha fields: {', '.join(PHASE30_AUTHORIZED_NEWS_ALPHA_FIELDS)}")
    print(f"Provider text/content alpha authority: {PHASE30_PROVIDER_CONTENT_ALPHA_AUTHORITY}")
    print(f"Provider insights alpha authority: {PHASE30_PROVIDER_INSIGHTS_ALPHA_AUTHORITY}")
    print(f"Monthly immutable/resumable shards: {len(phase30_news_shard_windows())}")
    print("Target/protected market outcomes: FORBIDDEN / UNREAD")
    print("Broker/order/PAPER/LIVE activity: DISABLED")
    print()

    settings = load_settings()
    client = MassivePhase30NewsClient(MassiveRESTClient(settings))
    try:
        report = Phase30NewsAcquisition(settings, client).run()
    except (Phase30NewsAcquisitionError, ProviderError, OSError, ValueError) as exc:
        print("Phase 30 full historical news acquisition: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("No market outcome was read and no trading authority was granted.")
        return 2

    print("Phase 30 full historical news acquisition: PASS")
    print(f"Total articles: {report['total_articles']}")
    print(f"Total ticker-linked articles: {report['total_ticker_linked_articles']}")
    print(f"Historical shards: {len(report['shards'])}")
    print(f"Resumed immutable shards: {report['resumed_shards']}")
    print(f"Recorded successful provider pages: {report['recorded_successful_provider_pages']}")
    print(f"Target outcome rows read: {report['target_outcome_rows_read']}")
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print("Provider writes / broker reads / broker writes / orders / PAPER / LIVE: 0 / 0 / 0 / 0 / 0 / 0")
    print(f"Acquisition report: {report['report_path']}")
    print("Next scientific action: build predictor-only news-shock frames from the frozen policy.")
    print(f"Pass: {report['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
