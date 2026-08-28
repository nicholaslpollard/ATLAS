from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase30_policy import (
    PHASE30_AUTHORIZED_NEWS_ALPHA_FIELDS,
    PHASE30_DECISION_BUFFER_MINUTES,
    PHASE30_NEWS_BASELINE_SESSIONS,
    phase30_policy_fingerprint,
)
from packages.backtesting.phase30_predictors import (
    Phase30NewsPredictorBuilder,
    Phase30PredictorError,
)
from packages.core.exceptions import ProviderError
from packages.core.settings import load_settings


def main() -> int:
    print("ATLAS Phase 30 — Predictor-Only Metadata News-Shock Construction")
    print(f"Frozen Phase30 policy fingerprint: {phase30_policy_fingerprint()}")
    print(f"Authorized news alpha fields: {', '.join(PHASE30_AUTHORIZED_NEWS_ALPHA_FIELDS)}")
    print(f"Decision buffer: {PHASE30_DECISION_BUFFER_MINUTES} minutes before official session close")
    print(f"Zero-filled news baseline: previous {PHASE30_NEWS_BASELINE_SESSIONS} XNYS sessions")
    print("Article text/provider sentiment/provider insights: NOT AUTHORIZED FOR PHASE30 ALPHA")
    print("Market outcome reads: ZERO")
    print("Broker/order/PAPER/LIVE activity: DISABLED")
    print()

    settings = load_settings()
    try:
        report = Phase30NewsPredictorBuilder(settings).run()
    except (Phase30PredictorError, ProviderError, OSError, ValueError) as exc:
        print("Phase 30 predictor-only news-shock construction: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("No market outcome was read and no trading authority was granted.")
        return 2

    print("Phase 30 predictor-only news-shock construction: PASS")
    print(f"Articles scanned: {report['articles_scanned']}")
    print(f"Ticker links scanned: {report['ticker_links_scanned']}")
    print(
        "Development predictor rows/tickers: "
        f"{report['development_rows']} / {report['development_tickers']}"
    )
    print(
        "Protected predictor rows/tickers: "
        f"{report['protected_rows']} / {report['protected_tickers']}"
    )
    print(
        "Source news shards / lineage SHA256: "
        f"{report['source_news_shards']} / {report['source_news_lineage_sha256']}"
    )
    print(f"Development SHA256: {report['development_sha256']}")
    print(f"Protected SHA256: {report['protected_sha256']}")
    print(f"Target outcome rows read: {report['target_outcome_rows_read']}")
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print(
        "Provider reads/writes / broker reads/writes / orders / PAPER / LIVE: "
        "0 / 0 / 0 / 0 / 0 / 0 / 0"
    )
    print(f"Predictor report: {report['report_path']}")
    print(
        "Next scientific action: join development predictors to the frozen Phase26 "
        "observation-time candidate fields and execute development-only selection. "
        "Protected returns remain forbidden."
    )
    print(f"Pass: {report['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
