from __future__ import annotations

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_seam import (
    ALPACA_BACKFILL_SEAM_PROBE_CONTRACT_VERSION,
    AlpacaBackfillSeamProbe,
)


def _fmt(value: object, digits: int = 8) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def main() -> None:
    settings = load_settings()
    report = AlpacaBackfillSeamProbe(settings).run()

    print("ATLAS Historical Backfill Gate 7-A Same-Session Provider Bridge")
    print("  safety: one-session Alpaca validation probe only; candidate/production canonical untouched")
    print(f"  contract:                         {ALPACA_BACKFILL_SEAM_PROBE_CONTRACT_VERSION}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print(f"  Gate 6 candidate fingerprint:     {report['candidate_source_fingerprint']}")
    print(f"  candidate boundary session:       {report['candidate_boundary_session']}")
    print(f"  Massive boundary session:         {report['massive_boundary_session']}")
    print(f"  request semantics:                feed={report['feed']} timeframe={report['timeframe']} adjustment={report['adjustment']} asof={report['asof']}")
    print(f"  candidate boundary SHA256:        {report['candidate_boundary_sha256']}")
    print(f"  Massive boundary SHA256:          {report['massive_boundary_sha256']}")
    print(f"  candidate schema exact:           {report['candidate_boundary_schema_exact']}")
    print(f"  Massive schema exact:             {report['massive_boundary_schema_exact']}")
    print("  probe inventory:")
    print(f"    candidate Friday symbols:       {report['candidate_boundary_symbols']:,}")
    print(f"    Massive Monday symbols:         {report['massive_boundary_symbols']:,}")
    print(f"    exact union symbols:            {report['union_symbols']:,}")
    print(f"    planned/completed units:        {report['planned_units']:,} / {report['completed_units']:,}")
    print(f"    executed this run:              {report['executed_units_this_run']:,}")
    print(f"    cached/skipped this run:        {report['skipped_units_this_run']:,}")
    print(f"    provider-rejected symbols:      {report['provider_rejected_symbols']:,}")
    print("  response-symbol safety:")
    print(f"    safe Alpaca target rows:        {report['safe_rows']:,}")
    print(f"    anomaly records:                {report['anomaly_records']:,}")
    print(f"    quarantined target rows:        {report['anomaly_target_rows']:,}")
    print(f"    raw hash failures:              {report['raw_hash_failures']:,}")
    print("  same-session Alpaca vs Massive, 2021-08-16:")
    print(f"    safe Alpaca symbols:            {report['alpaca_safe_target_symbols']:,}")
    print(f"    Massive symbols:                {report['massive_target_symbols']:,}")
    print(f"    matched exact symbols:          {report['matched_exact_symbols']:,}")
    print(f"    Alpaca-safe only symbols:       {report['alpaca_safe_only_symbols']:,}")
    print(f"    Massive-only vs safe Alpaca:    {report['massive_only_vs_safe_alpaca_symbols']:,}")
    print(f"    exact OHLC symbols:             {report['exact_ohlc_symbols']:,}")
    print(f"    exact close symbols:            {report['exact_close_symbols']:,}")
    print(f"    close within 1 bp fraction:     {_fmt(report['close_within_1bp_fraction'])}")
    print(f"    OHLC relative diff median:      {_fmt(report['ohlc_relative_diff_median'])}")
    print(f"    OHLC relative diff p95:         {_fmt(report['ohlc_relative_diff_p95'])}")
    print(f"    OHLC relative diff max:         {_fmt(report['ohlc_relative_diff_max'])}")
    print(f"    close relative diff p95:        {_fmt(report['close_relative_diff_p95'])}")
    print(f"    volume relative diff median:    {_fmt(report['volume_relative_diff_median'])}")
    print(f"    volume relative diff p95:       {_fmt(report['volume_relative_diff_p95'])}")
    print("  adjacent candidate/Massive boundary:")
    print(f"    exact Friday->Monday symbols:   {report['candidate_friday_massive_monday_exact_symbols']:,}")
    print(f"    Friday-only symbols:            {report['candidate_friday_only_symbols']:,}")
    print(f"    Monday-only symbols:            {report['massive_monday_only_symbols']:,}")
    print(f"    Friday close->Monday open p95:  {_fmt(report['boundary_open_move_p95'])}")
    print(f"    Friday close->Monday open max:  {_fmt(report['boundary_open_move_max'])}")
    print(f"    Friday close->Monday close p95: {_fmt(report['boundary_close_move_p95'])}")
    print(f"    Friday close->Monday close max: {_fmt(report['boundary_close_move_max'])}")
    print("  structural checks:")
    for key, value in report["structural_checks"].items():
        print(f"    {key}: {value}")
    print(f"  safe Alpaca bars:                 {report['safe_bars_path']}")
    print(f"  response anomalies:               {report['response_symbol_anomalies_path']}")
    print(f"  provider comparison:              {report['provider_comparison_path']}")
    print(f"  boundary status:                  {report['boundary_status_path']}")
    print(f"  report:                           {report['report_path']}")
    print(f"  canonical data modified:          {report['canonical_data_modified']}")

    if report.get("structural_pass") is not True:
        raise SystemExit("Historical Backfill Gate 7-A same-session provider bridge: FAIL")
    print("  Historical Backfill Gate 7-A same-session provider bridge: PASS")
    print("  Historical Backfill Gate 7 Massive seam reconciliation: CURRENT")


if __name__ == "__main__":
    main()
