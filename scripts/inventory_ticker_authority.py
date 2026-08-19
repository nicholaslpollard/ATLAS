from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.regimes.ticker_authority_probe import TickerAuthorityProbe


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inventory unresolved ticker identities that can be enriched by authoritative Composite-FIGI ticker events."
    )
    parser.add_argument("--as-of", required=True, type=date.fromisoformat, help="Point-in-time session (YYYY-MM-DD).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = TickerAuthorityProbe(load_settings(PROJECT_ROOT, "development")).run(args.as_of)

    print("ATLAS Phase 9 Ticker Authority Inventory")
    print(f"  contract:                         {report.contract_version}")
    print(f"  as-of session:                    {report.as_of_date}")
    print(f"  probe status:                     {report.probe_status}")
    print(f"  routed ticker-regime population: {report.route_population_count:9,d}")
    print(f"    Phase 8 discovery state         {report.discovery_count:9,d}")
    print(f"    POSITION route                  {report.position_count:9,d}")
    print(f"    WATCHLIST route                 {report.watchlist_count:9,d}")
    print(f"    CUSTOM route                    {report.custom_count:9,d}")
    print("  identity pressure:")
    print(f"    multiple observed aliases       {report.multi_alias_count:9,d}")
    print(f"    current ticker reused by IDs    {report.ticker_reuse_count:9,d}")
    print("  authority status:")
    for status, count in report.authority_status_counts.items():
        print(f"    {status:<34} {count:7,d}")
    print(f"  unresolved identities:            {report.unresolved_identity_count:9,d}")
    print(f"    with Composite FIGI             {report.unresolved_with_composite_figi_count:9,d}")
    print(f"    without Composite FIGI          {report.unresolved_without_composite_figi_count:9,d}")
    print(f"  resolved authoritative intervals: {report.resolved_authoritative_interval_count:9,d}")
    print(f"  ambiguous authoritative intervals:{report.ambiguous_authoritative_interval_count:9,d}")
    print(f"  cached ticker-event files:         {report.cached_event_file_count:9,d}")
    print(f"  new provider sync candidates:      {report.provider_sync_candidate_count:9,d}")

    if report.provider_sync_candidate_examples:
        print("  provider sync candidate examples:")
        for item in report.provider_sync_candidate_examples[:10]:
            print(
                f"    {item['ticker']:<12} aliases={item['alias_count']} reuse_ids={item['reuse_identity_count']} "
                f"figi={item['composite_figi']} cached={str(item['event_file_cached']).lower()}"
            )
    if report.unresolved_no_figi_examples:
        print("  unresolved without Composite FIGI examples:")
        for item in report.unresolved_no_figi_examples[:10]:
            print(
                f"    {item['ticker']:<12} aliases={item['alias_count']} reuse_ids={item['reuse_identity_count']}"
            )

    print("  network calls:                     NONE")
    print("  provider enrichment policy:        MEASURE BEFORE BATCH SYNC")
    print(f"  wall time:                         {report.wall_seconds:.3f}s")
    print(f"  report:                            {Path(report.report_path).resolve()}")
    print("  result:                            EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
