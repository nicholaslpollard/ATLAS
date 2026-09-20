from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.historical_news_v1_source_integrity_v2 import (
    EFFECTIVE_PIT_POLICY,
    HISTORICAL_NEWS_V1_SOURCE_INTEGRITY_V2_FINGERPRINT,
    run_historical_news_v1_source_integrity_v2,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate Historical News V1 under the frozen V2 source-integrity "
            "disposition for the four hash-bound provider chronology anomalies."
        )
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Concurrent V1 monthly integrity workers. Default: 4.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    settings = load_settings(PROJECT_ROOT)

    print("ATLAS Historical News V1 Source-Integrity V2")
    print(
        "  contract fingerprint: "
        f"{HISTORICAL_NEWS_V1_SOURCE_INTEGRITY_V2_FINGERPRINT}"
    )
    print(f"  effective PIT policy: {EFFECTIVE_PIT_POLICY}")
    print("  generic timestamp tolerance: none")
    print("  unexpected/changed chronology anomaly: fail closed")
    print("  provider calls: disabled")
    print("  source mutation: disabled")
    print("  strategy/PAPER/LIVE authority: none")

    report = run_historical_news_v1_source_integrity_v2(
        settings,
        workers=args.workers,
        progress=lambda message: print(f"  {message}", flush=True),
    )

    print(f"\nHISTORICAL NEWS V1 SOURCE-INTEGRITY V2: {report['status']}")
    print(f"  corpus fingerprint: {report['corpus_fingerprint']}")
    print(
        "  V1 failed partitions preserved: "
        + ", ".join(report["failed_partitions_under_v1"])
    )
    print(
        "  chronology anomalies accepted by exact identity/hash: "
        f"{len(report['chronology_anomalies']):,}"
    )
    print(
        "  effective PIT corrections: "
        f"{len(report['effective_pit_corrections']):,}"
    )
    for item in report["effective_pit_corrections"]:
        print(
            f"    - {item['month']} article_id={item['article_id']} "
            f"{item['stored_pit_available_at']} -> "
            f"{item['effective_pit_available_at']} "
            f"(+{float(item['forward_adjustment_seconds']):.0f}s)"
        )

    global_normalized = report["global_normalized"]
    print(f"  raw provider records: {int(report['raw_provider_records']):,}")
    print(f"  normalized articles: {int(report['normalized_articles']):,}")
    print(
        "  global distinct article ids: "
        f"{int(global_normalized['distinct_article_ids']):,}"
    )
    print(
        "  cross-month duplicate article-id rows: "
        f"{int(global_normalized['duplicate_article_id_rows']):,}"
    )
    print(f"  acceptance fingerprint: {report['acceptance_fingerprint']}")
    if report["errors"]:
        print("  errors:")
        for error in report["errors"]:
            print(f"    - {error}")
    print(
        "  report: "
        + str(
            PROJECT_ROOT
            / "data/news/manifests/alpaca/"
            "historical_news_v1_source_integrity_v2.json"
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
