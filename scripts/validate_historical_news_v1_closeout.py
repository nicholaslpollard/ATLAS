from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.historical_news_v1_closeout import (
    EXPECTED_ACQUISITION_RUN_FINGERPRINT,
    HISTORICAL_NEWS_V1_CLOSEOUT_CONTRACT_FINGERPRINT,
    run_historical_news_v1_closeout,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Independently validate the completed Historical News V1 corpus before "
            "any news predictor or strategy research is allowed."
        )
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Concurrent monthly integrity workers. Default: 4.",
    )
    parser.add_argument(
        "--expected-run-fingerprint",
        default=EXPECTED_ACQUISITION_RUN_FINGERPRINT,
        help=(
            "Expected completed acquisition run fingerprint. Defaults to the "
            "2026-09-20 target-workstation completion."
        ),
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    settings = load_settings(PROJECT_ROOT)

    print("ATLAS Historical News V1 Source-Integrity Closeout")
    print(
        "  closeout contract fingerprint: "
        f"{HISTORICAL_NEWS_V1_CLOSEOUT_CONTRACT_FINGERPRINT}"
    )
    print(f"  expected acquisition run: {args.expected_run_fingerprint}")
    print(
        "  authority: source-integrity validation only; "
        "no predictor/strategy/PAPER/LIVE authority"
    )

    report = run_historical_news_v1_closeout(
        settings,
        workers=args.workers,
        expected_run_fingerprint=args.expected_run_fingerprint,
        progress=lambda message: print(f"  {message}", flush=True),
    )

    print(f"\nHISTORICAL NEWS V1 SOURCE-INTEGRITY CLOSEOUT: {report['status']}")
    print(f"  corpus fingerprint: {report['corpus_fingerprint']}")
    print(f"  closeout fingerprint: {report['closeout_fingerprint']}")
    print(f"  monthly partitions: {int(report['monthly_partitions']):,}")
    print(f"  failed partitions: {len(report['failed_partitions']):,}")
    print(f"  raw provider records: {int(report['raw_provider_records']):,}")
    print(f"  normalized articles: {int(report['normalized_articles']):,}")
    global_normalized = report["global_normalized"]
    print(
        "  global distinct article ids: "
        f"{int(global_normalized['distinct_article_ids']):,}"
    )
    print(
        "  cross-month duplicate article-id rows: "
        f"{int(global_normalized['duplicate_article_id_rows']):,}"
    )
    if report["errors"]:
        print("  errors:")
        for error in report["errors"]:
            print(f"    - {error}")
    print(
        "  report: "
        + str(
            PROJECT_ROOT
            / "data/news/manifests/alpaca/historical_news_v1_closeout.json"
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
