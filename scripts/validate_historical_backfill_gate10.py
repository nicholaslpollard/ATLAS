from __future__ import annotations

from packages.core.settings import load_settings
from packages.regimes.historical_backfill_regime_replay_validation import (
    HistoricalBackfillRegimeReplayValidator,
)


def main() -> None:
    report = HistoricalBackfillRegimeReplayValidator(load_settings()).run()
    print("ATLAS Historical Backfill Gate 10-B Independent Isolated Regime Validation")
    print("  safety: production regime artifacts are read-only; validation rebuild stays isolated")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  builder fingerprint:              {report['builder_source_fingerprint']}")
    print(f"  Gate 10-A fingerprint:            {report['gate10a_source_fingerprint']}")
    print(f"  Gate 9-C fingerprint:             {report['gate9c_handoff_source_fingerprint']}")
    print(f"  as-of date:                       {report['as_of_date']}")
    market = report["market_sector_recompute"]
    print("  market/sector independent recompute:")
    print(f"    market raw/effective rows:       {int(market['market_raw_rows']):,} / {int(market['market_effective_rows']):,}")
    print(f"    sector raw/effective rows:       {int(market['sector_raw_rows']):,} / {int(market['sector_effective_rows']):,}")
    print(f"    market raw/effective equal:      {market['market_raw_equal']} / {market['market_effective_equal']}")
    print(f"    sector raw/effective equal:      {market['sector_raw_equal']} / {market['sector_effective_equal']}")
    print(f"    history hash failures:           {int(market['history_hash_failures']):,}")
    ticker = report["ticker_proof"]
    print("  ticker proof:")
    print(f"    current population:              {int(ticker['current_population']):,}")
    print(f"    candidate rows:                  {int(ticker['candidate_rows']):,}")
    print(f"    missing in candidate:            {int(ticker['missing_in_candidate']):,}")
    print(f"    raw classified rows:             {int(ticker['raw_classified_rows']):,}")
    print(f"    raw classification mismatches:   {int(ticker['raw_classification_mismatches']):,}")
    print(f"    second isolated rebuild rows:    {int(ticker['second_rebuild_rows']):,}")
    print(f"    second isolated rebuild equal:   {ticker['second_rebuild_equal']}")
    print(f"    second rebuild skipped exact:    {ticker['second_rebuild_skipped']}")
    print("  checks:")
    for key, value in report["checks"].items():
        print(f"    {key}: {value}")
    print(f"  production regime writes:         {int(report['production_regime_writes']):,}")
    print(f"  builder report:                    {report['builder_report_path']}")
    print(f"  validation report:                 {report['validation_report_path']}")
    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 10-B independent candidate validation: FAIL")
    print("  Historical Backfill Gate 10-B independent candidate validation: PASS")
    print("  Historical Backfill Gate 10-B isolated split-origin regime replay: ACCEPTED")
    print("  Historical Backfill Gate 10-C production regime promotion: CURRENT")


if __name__ == "__main__":
    main()
