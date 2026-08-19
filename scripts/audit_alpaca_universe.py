from __future__ import annotations

from packages.core.settings import load_settings
from packages.data.alpaca_universe_audit import AlpacaHistoricalUniverseAudit


def main() -> int:
    settings = load_settings()
    report = AlpacaHistoricalUniverseAudit(settings).run()

    print("ATLAS Alpaca Historical Universe / Inactive Asset Audit")
    print("  read-only: no provider/canonical history will be modified")
    print(f"  contract:                    {report.contract_version}")
    print(f"  trading profile:             {report.trading_profile}")
    inactive = report.inactive_assets
    print(
        "  inactive asset inventory:    "
        f"status={inactive['status']} http={inactive['http_status']} "
        f"assets={inactive['count']} unique_symbols={inactive['unique_symbols']}"
    )
    print(f"  inactive exchanges:          {inactive['exchange_counts']}")
    print("  legacy sentinels:")
    for symbol, item in report.legacy_sentinels.items():
        bars = item["bars"]
        print(
            f"    {symbol}: inactive_asset={item['present_in_inactive_assets']} "
            f"bars={bars['rows']} status={bars['status']} http={bars['http_status']} "
            f"first={bars['first']} last={bars['last']}"
        )
    reuse = report.ticker_reuse_sentinel
    print("  ticker reuse sentinel:")
    print(
        f"    S current_active={reuse['current_active_asset_present']} "
        f"name={reuse['current_active_asset_name']!r} multiple_eras={reuse['literal_ticker_has_multiple_eras']}"
    )
    for label, item in reuse["windows"].items():
        print(
            f"      {label}: rows={item['rows']} status={item['status']} "
            f"first={item['first']} last={item['last']}"
        )
    c = report.conclusions
    print(
        "  legacy coverage:              "
        f"inactive_assets={c['legacy_present_in_inactive_assets']}/{c['legacy_sentinel_count']} "
        f"historical_bars={c['legacy_with_historical_bars']}/{c['legacy_sentinel_count']}"
    )
    print(f"  ticker text proves identity:  {c['ticker_text_alone_can_prove_identity']}")
    print(f"  canonical data modified:      {report.canonical_data_modified}")
    print(f"  report:                       {report.report_path}")
    print("  result:                       EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
