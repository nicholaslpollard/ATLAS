from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.historical_news_v1 import (
    run_historical_news_v1_acquisition,
)
from packages.data.historical_news_v1_contract import (
    HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT,
    HISTORY_END,
    HISTORY_START,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Acquire the bounded Historical News V1 Alpaca corpus into monthly "
            "hash-verified raw and normalized partitions."
        )
    )
    parser.add_argument(
        "--authorize-source-acquisition",
        action="store_true",
        help=(
            "Required acknowledgement that this command performs source-data "
            "acquisition only and grants no strategy/PAPER/LIVE authority."
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Concurrent monthly fetch workers. Requests remain globally rate-limited.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.authorize_source_acquisition:
        raise SystemExit(
            "Refusing Historical News V1 acquisition without "
            "--authorize-source-acquisition"
        )
    settings = load_settings(PROJECT_ROOT)
    print("ATLAS Historical News V1")
    print(f"  contract fingerprint: {HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT}")
    print(f"  scope: {HISTORY_START} -> {HISTORY_END}")
    print("  source: Alpaca historical news / Benzinga")
    print("  raw: gzip JSONL provider records")
    print("  normalized: ZSTD Parquet")
    print(
        "  PIT rule: retrieved article text is available at provider updated_at, "
        "not backdated to created_at"
    )
    print(
        "  storage guard: 4 GiB news quota plus the global 50 GiB free-space floor"
    )
    print(
        "  authority: source acquisition only; no predictor/strategy/PAPER/LIVE authority"
    )

    report = run_historical_news_v1_acquisition(
        settings,
        workers=args.workers,
    )

    print("\nHISTORICAL NEWS V1: COMPLETE")
    print(f"  run fingerprint: {report['run_fingerprint']}")
    print(f"  monthly partitions: {int(report['monthly_partitions']):,}")
    print(
        "  verified partitions reused: "
        f"{int(report['reused_verified_partitions']):,}"
    )
    print(
        "  partitions acquired this run: "
        f"{int(report['acquired_partitions_this_run']):,}"
    )
    print(f"  raw provider records: {int(report['raw_provider_records']):,}")
    print(
        "  normalized unique articles: "
        f"{int(report['normalized_unique_articles']):,}"
    )
    storage = report["storage_after"]
    print(
        "  news storage: "
        f"{float(storage['news_usage_gib']):.3f} / "
        f"{float(storage['news_quota_gib']):.2f} GiB"
    )
    print(f"  disk free after: {float(storage['disk_free_gib']):.2f} GiB")
    print(
        "  summary: "
        + str(
            PROJECT_ROOT
            / "data/news/manifests/alpaca/historical_news_v1_summary.json"
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
