from __future__ import annotations

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_inventory import AlpacaBackfillInventoryBuilder


def main() -> None:
    settings = load_settings()
    builder = AlpacaBackfillInventoryBuilder(settings)

    print("ATLAS Alpaca Historical Backfill Inventory / Pilot")
    print("  provider/canonical safety: canonical history will not be modified")
    print("  building active + inactive + Massive-observed + corporate-action candidate union...")
    report = builder.run()

    print(f"  contract:                    {report.contract_version}")
    print(f"  parent contract:             {report.parent_contract_version}")
    print(f"  credential profile:          {report.credential_profile}")
    print(f"  range:                       {report.backfill_start}->{report.backfill_end}")
    print(f"  source semantics:            feed={report.feed} adjustment={report.adjustment} asof={report.asof} timeframe={report.timeframe}")
    print("  discovery source counts:")
    for key, value in report.source_counts.items():
        print(f"    {key}: {value:,}")
    print(f"  inventory rows:              {report.inventory_rows:,}")
    print(f"  SIP acquisition candidates: {report.sip_candidate_symbols:,}")
    print(f"  known OTC-only excluded:     {report.known_otc_only_excluded:,}")
    print(f"  inactive reference-only:     {report.inactive_reference_only_identifier_excluded:,} excluded from SIP")
    print(f"  corporate-action pages:      {report.corporate_action_pages:,}")
    print(f"  raw discovery payloads:      {report.raw_discovery_payloads:,}")
    print("  provenance combinations:")
    for key, value in report.provenance_combination_counts.items():
        print(f"    {key}: {value:,}")
    print("  deterministic January-2016 pilot:")
    print(f"    symbols={report.pilot_symbols:,} observed={report.pilot_observed_symbols:,} bars={report.pilot_bar_rows:,} pages={report.pilot_pages:,}")
    print(f"  canonical data modified:     {report.canonical_data_modified}")
    print(f"  inventory:                   {report.inventory_path}")
    print(f"  report:                      {report.report_path}")
    print("  result:                      EVIDENCE CAPTURED")


if __name__ == "__main__":
    main()
