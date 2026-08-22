from __future__ import annotations

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_quality import AlpacaBackfillQualityBaselineBuilder


def main() -> None:
    report = AlpacaBackfillQualityBaselineBuilder(load_settings()).run()

    print("ATLAS Historical Backfill Gate 5-A Provider Quality Baseline")
    print("  safety: retained raw SIP evidence only; no provider fetch; canonical history untouched")
    print(f"  contract:                         {report.contract_version}")
    print(f"  zero-activity class:              {report.zero_activity_placeholder_class}")
    print(f"  zero-activity candidate policy:   {report.zero_activity_candidate_policy}")
    print(f"  retained unit manifests:          {report.retained_unit_manifests:,}")
    print(f"  retained raw bar pages:           {report.retained_raw_bar_pages:,}")
    print(f"  raw payload hash failures:        {report.raw_payload_hash_failures:,}")
    print(f"  identity-safe raw bar rows:       {report.identity_safe_bar_rows:,}")
    print(f"  Gate 3 reported bar rows:         {report.gate3_reported_identity_safe_bar_rows:,}")
    print(f"  trade-backed usable rows:         {report.trade_backed_usable_rows:,}")
    print(f"  zero-activity placeholder rows:   {report.zero_activity_placeholder_rows:,}")
    print(f"  quarantined response bar rows:    {report.quarantined_response_bar_rows:,}")
    print(f"  Gate 3 reported quarantine rows:  {report.gate3_reported_quarantined_response_bar_rows:,}")
    print(f"  observed symbols:                 {report.observed_symbols:,}")
    print(f"  symbol reconciliation failures:   {report.symbol_summary_reconciliation_failures:,}")
    print("  definite bar-quality defects:")
    print(f"    definite invalid rows:           {report.definite_invalid_rows:,}")
    print(f"    missing required fields:         {report.missing_required_rows:,}")
    print(f"    invalid timestamps:              {report.invalid_timestamp_rows:,}")
    print(f"    outside acquisition unit range:  {report.out_of_unit_range_rows:,}")
    print(f"    invalid OHLC numeric:            {report.invalid_ohlc_numeric_rows:,}")
    print(f"    nonpositive OHLC:                {report.nonpositive_ohlc_rows:,}")
    print(f"    invalid OHLC geometry:           {report.invalid_ohlc_geometry_rows:,}")
    print(f"    invalid volume:                  {report.invalid_volume_rows:,}")
    print(f"    zero-volume non-placeholder:     {report.zero_volume_nonplaceholder_rows:,}")
    print(f"    invalid trade count:             {report.invalid_trade_count_rows:,}")
    print(f"    invalid VWAP:                    {report.invalid_vwap_rows:,}")
    print("  diagnostics (not automatic defects):")
    print(f"    missing trade count:             {report.missing_trade_count_rows:,}")
    print(f"    missing VWAP:                    {report.missing_vwap_rows:,}")
    print(f"    weekend-dated rows:              {report.weekend_session_rows:,}")
    print("  identity-safe raw rows by year:")
    for year, count in report.year_row_counts.items():
        print(f"    {year}: {count:,}")
    print("  zero-activity placeholders by year:")
    for year, count in report.zero_activity_year_row_counts.items():
        print(f"    {year}: {count:,}")
    print("  UTC daily-bar timestamp times:")
    for time_text, count in report.utc_time_counts.items():
        print(f"    {time_text}: {count:,}")
    print("  raw bar key patterns:")
    for pattern, count in report.bar_key_pattern_counts.items():
        print(f"    {pattern}: {count:,}")
    print("  accounting validation:")
    print(f"    Gate 3 row accounting exact:     {report.row_accounting_exact}")
    print(f"    quarantine accounting exact:     {report.quarantine_accounting_exact}")
    print(f"    symbol summary reconciliation:   {report.symbol_summary_reconciliation_exact}")
    print(f"    trade-backed row accounting:     {report.trade_backed_accounting_exact}")
    print(f"  symbol quality summary:             {report.symbol_summary_path}")
    print(f"  report:                             {report.report_path}")
    print("  canonical data modified:            False")
    print("  Historical Backfill Gate 5 provider completeness / quality: CURRENT")


if __name__ == "__main__":
    main()
