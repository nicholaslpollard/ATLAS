from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.historical_news_v1_chronology_diagnostic import (
    DIAGNOSTIC_CONTRACT,
    run_historical_news_v1_chronology_diagnostic,
)


def _parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=(
            "Inspect Historical News V1 provider records whose updated_at precedes "
            "created_at without modifying source data or contacting providers."
        )
    )


def main() -> int:
    _parser().parse_args()
    settings = load_settings(PROJECT_ROOT)

    print("ATLAS Historical News V1 Chronology Diagnostic")
    print(f"  contract: {DIAGNOSTIC_CONTRACT}")
    print("  provider calls: disabled")
    print("  source mutation: disabled")
    print("  strategy/PAPER/LIVE authority: none")

    report = run_historical_news_v1_chronology_diagnostic(settings)

    print(f"\nCHRONOLOGY DIAGNOSTIC: {report['status']}")
    print(f"  anomalies: {int(report['anomaly_count']):,}")
    print(f"  months: {', '.join(report['months']) or 'none'}")
    print(f"  all raw records found: {report['all_raw_records_found']}")
    print(
        "  all raw/normalized hashes match: "
        f"{report['all_raw_normalized_hashes_match']}"
    )
    print(f"  all PIT == updated_at: {report['all_pit_equals_updated']}")
    print(f"  all PIT before created_at: {report['all_pit_before_created']}")

    for item in report["anomalies"]:
        print("")
        print(f"  [{item['month']}] article_id={item['article_id']}")
        print(f"    source: {item['source']}")
        print(f"    headline: {item['headline']}")
        print(f"    url: {item['url']}")
        print(f"    symbols: {item['symbols']}")
        print(f"    created_at: {item['created_at']}")
        print(f"    updated_at: {item['updated_at']}")
        print(f"    pit_available_at: {item['pit_available_at']}")
        print(
            "    updated precedes created by: "
            f"{float(item['updated_before_created_seconds']):,.3f} seconds"
        )
        print(
            "    raw/normalized hash match: "
            f"{item.get('raw_normalized_hash_match')}"
        )
        print(
            "    raw created/updated: "
            f"{item.get('raw_created_at')} / {item.get('raw_updated_at')}"
        )
        print(
            "    raw timestamp in query window (created/updated): "
            f"{item.get('raw_created_inside_query_window')} / "
            f"{item.get('raw_updated_inside_query_window')}"
        )
        print(
            "    provider record sha256: "
            f"{item['provider_record_sha256']}"
        )

    print(
        "\n  report: "
        + str(
            PROJECT_ROOT
            / "data/news/manifests/alpaca/"
            "historical_news_v1_chronology_diagnostic.json"
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
