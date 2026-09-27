from __future__ import annotations

"""Build the first joined stock/news/options source casebook, ZERO provider GETs."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.integrated_2022_casebook_v1 import (
    IntegratedCasebookError, build_casebook, write_casebook,
)
from packages.data.offline_news_context_v1 import OfflineNewsContextError


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build accepted local-only 2022 stock/news/CALL source casebook"
    )
    parser.add_argument("--news-threads", type=int, default=4)
    args = parser.parse_args()
    print("ATLAS Integrated 2022 Stock + News + CALL Source Casebook V1", flush=True)
    print("  ZERO external/API requests; NO executable fills, P&L, PAPER or LIVE", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        _, external = settings.external_storage_binding_paths("research_evidence")
        print(f"  physical evidence root: {external}", flush=True)
        result = build_casebook(
            settings, news_threads=args.news_threads,
            progress=lambda row: print(
                "  " + " ".join(f"{key}={value}" for key, value in row.items()),
                flush=True,
            ),
        )
        path, action = write_casebook(settings, result)
        print(f"  status: {result['status']}", flush=True)
        for key in (
            "full_structural_denominator", "distinct_tickers",
            "news_2022_normalized_articles_scanned",
            "prior_24h_news_opportunities", "prior_7d_news_opportunities",
            "option_reference_dispositions", "provider_requests",
            "protected_outcomes_read", "casebook_fingerprint",
        ):
            print(f"  {key}: {result[key]}", flush=True)
        print(f"  derived artifact: {action} / {path}", flush=True)
        print("  This joins provenance and coverage ONLY; matched stock EOD marks, "
              "option deliverables and honest fill timing are future independent gates.",
              flush=True)
        return 0
    except (IntegratedCasebookError, OfflineNewsContextError, OSError, ValueError,
            TypeError, KeyError) as exc:
        print(f"INTEGRATED CASEBOOK STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  Preserve all originals; no automatic provider retry.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
