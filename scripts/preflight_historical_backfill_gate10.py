from __future__ import annotations

from packages.core.settings import load_settings
from packages.regimes.historical_backfill_regime_replay import (
    HistoricalBackfillRegimeReplayPreflight,
)


def main() -> None:
    report = HistoricalBackfillRegimeReplayPreflight(load_settings()).run()
    print("ATLAS Historical Backfill Gate 10-A Regime Replay Preflight")
    print("  safety: read-only regime feasibility proof; no production regime artifacts written")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print(f"  Gate 9-C handoff fingerprint:     {report['gate9c_handoff_source_fingerprint']}")
    print(f"  as-of date:                       {report['as_of_date']}")
    print("  replay origins:")
    print(f"    current Phase 9 origin:          {report['current_phase9_origin']}")
    print(f"    candidate market/sector origin:  {report['candidate_market_sector_origin']}")
    print(f"    ticker origin:                   {report['ticker_origin']}")
    print(f"    intraday policy:                 {report['intraday_policy']}")
    print("  permanent feature-manifest coverage:")
    for timeframe in ("1d", "4h", "1h"):
        row = report["feature_manifest_coverage"][timeframe]
        print(
            f"    {timeframe}: {int(row['manifest_count']):,} sessions "
            f"{row['first_session']} -> {row['last_session']} "
            f"invalid={int(row['invalid_manifests']):,}"
        )
    candidate = report["candidate_market_sector_replay"]
    print("  candidate 2016-origin market/sector replay:")
    print(f"    usable breadth sessions:         {int(candidate['usable_breadth_sessions']):,}")
    print(f"    breadth range:                   {candidate['breadth_first_session']} -> {candidate['breadth_last_session']}")
    print(f"    proxy observations:              {int(candidate['proxy_observations']):,}")
    print(f"    market raw/effective rows:       {int(candidate['market_raw_rows']):,} / {int(candidate['market_effective_rows']):,}")
    print(f"    market evaluation range:         {candidate['market_first_evaluation']} -> {candidate['market_last_evaluation']}")
    print(f"    sector raw/effective rows:       {int(candidate['sector_raw_rows']):,} / {int(candidate['sector_effective_rows']):,}")
    print(f"    sector evaluation range:         {candidate['sector_first_evaluation']} -> {candidate['sector_last_evaluation']}")
    print("    sector first evaluation dates:")
    for symbol, value in candidate["sector_first_dates"].items():
        print(f"      {symbol}: {value}")
    overlap = report["overlap_change_diagnostics"]
    print("  overlap change diagnostics vs current-origin replay on the new features:")
    for scope in ("market", "sector"):
        row = overlap[scope]
        rate = row["change_rate"]
        rate_text = "None" if rate is None else f"{float(rate):.6%}"
        print(
            f"    {scope}: overlap={int(row['overlap_rows']):,} "
            f"changed={int(row['changed_rows']):,} "
            f"unchanged={int(row['unchanged_rows']):,} rate={rate_text}"
        )
        print(f"      dimension changes: {row['dimension_change_counts']}")
    artifacts = report["existing_artifacts"]
    print("  existing production regime artifacts:")
    print(f"    market/sector snapshots/manifests: {int(artifacts['market_sector_snapshots']):,} / {int(artifacts['market_sector_manifests']):,}")
    print(f"    ticker snapshots/manifests:        {int(artifacts['ticker_snapshots']):,} / {int(artifacts['ticker_manifests']):,}")
    print(f"    latest market/sector lineage current: {artifacts['latest_market_sector_manifest']['current']}")
    print(f"    latest ticker lineage current:        {artifacts['latest_ticker_manifest']['current']}")
    print("  checks:")
    for key, value in report["checks"].items():
        print(f"    {key}: {value}")
    print(f"  report:                            {report['report_path']}")
    print(f"  production regime writes:         {int(report['production_regime_writes']):,}")
    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 10-A regime replay preflight: FAIL")
    print("  Historical Backfill Gate 10-A regime replay preflight: PASS")
    print("  Historical Backfill Gate 10-B split-origin policy version + isolated replay: CURRENT")


if __name__ == "__main__":
    main()
