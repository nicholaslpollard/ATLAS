from __future__ import annotations

from packages.core.settings import load_settings
from packages.regimes.historical_backfill_regime_replay_build import (
    HistoricalBackfillRegimeReplayBuilder,
)


def main() -> None:
    report = HistoricalBackfillRegimeReplayBuilder(load_settings()).run()
    print("ATLAS Historical Backfill Gate 10-B Isolated Split-Origin Regime Replay")
    print("  safety: production regime artifacts are hash-frozen and must remain unchanged")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print(f"  split-origin policy:              {report['split_origin_policy_version']}")
    print(f"  Gate 10-A fingerprint:            {report['gate10a_source_fingerprint']}")
    print(f"  Gate 9-C fingerprint:             {report['gate9c_handoff_source_fingerprint']}")
    print(f"  as-of date:                       {report['as_of_date']}")
    print("  replay origins:")
    print(f"    market/sector:                   {report['market_sector_origin']}")
    print(f"    ticker:                          {report['ticker_origin']}")
    print(f"    intraday policy:                 {report['intraday_policy']}")
    contracts = report["market_sector_contracts"]
    print("  versioned market/sector contracts:")
    print(f"    state policy:                    {contracts['state_policy']}")
    print(f"    snapshot:                        {contracts['snapshot']}")
    print(f"    manifest:                        {contracts['manifest']}")
    print(f"    source manifests:                {int(contracts['source_manifest_count']):,}")
    history = report["market_sector_history"]
    print("  isolated market/sector history:")
    print(f"    market raw/effective:            {int(history['market_raw_rows']):,} / {int(history['market_effective_rows']):,}")
    print(f"    market range:                    {history['market_first_evaluation']} -> {history['market_last_evaluation']}")
    print(f"    sector raw/effective:            {int(history['sector_raw_rows']):,} / {int(history['sector_effective_rows']):,}")
    print(f"    sector range:                    {history['sector_first_evaluation']} -> {history['sector_last_evaluation']}")
    print("    sector first dates:")
    for symbol, value in history["sector_first_dates"].items():
        print(f"      {symbol}: {value}")
    ticker = report["ticker_candidate"]
    print("  isolated ticker replay (Phase 9 semantics retained):")
    print(f"    records:                         {int(ticker['record_count']):,}")
    print(f"    raw state available:             {int(ticker['raw_state_available_count']):,}")
    print(f"    confirmed persistence:           {int(ticker['confirmed_persistence_count']):,}")
    print(f"    history status counts:           {ticker['history_status_counts']}")
    print(f"    persistence status counts:       {ticker['persistence_status_counts']}")
    print(f"    risk mode counts:                {ticker['risk_mode_counts']}")
    print(f"    effective state counts:          {ticker['effective_state_counts']}")
    print(f"    skipped exact existing candidate:{ticker['skipped_exact']}")
    print("  checks:")
    for key, value in report["checks"].items():
        print(f"    {key}: {value}")
    print(f"  production regime writes:         {int(report['production_regime_writes']):,}")
    print(f"  report:                            {report['report_path']}")
    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 10-B isolated regime replay: FAIL")
    print("  Historical Backfill Gate 10-B isolated regime replay: PASS")
    print("  Historical Backfill Gate 10-B independent candidate validation: CURRENT")


if __name__ == "__main__":
    main()
