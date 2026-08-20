from __future__ import annotations

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_session_quality import AlpacaBackfillSessionQualityBuilder


def main() -> None:
    report = AlpacaBackfillSessionQualityBuilder(load_settings()).run()

    print("ATLAS Historical Backfill Gate 5-B Session Coverage Audit")
    print("  safety: retained raw SIP evidence only; no provider fetch; canonical history untouched")
    print(f"  contract:                              {report.contract_version}")
    print(f"  parent quality contract:               {report.parent_quality_contract_version}")
    print(f"  exchange calendar:                     {report.calendar_name}")
    print(f"  retained unit manifests:               {report.retained_unit_manifests:,}")
    print(f"  retained raw bar pages:                {report.retained_raw_bar_pages:,}")
    print(f"  raw payload hash failures:             {report.raw_payload_hash_failures:,}")
    print("  parent classification reconciliation:")
    print(f"    identity-safe raw rows:               {report.identity_safe_raw_rows:,}")
    print(f"    parent identity-safe raw rows:        {report.parent_identity_safe_raw_rows:,}")
    print(f"    trade-backed raw rows:                {report.trade_backed_raw_rows:,}")
    print(f"    parent trade-backed raw rows:         {report.parent_trade_backed_raw_rows:,}")
    print(f"    zero-activity placeholder raw rows:   {report.zero_activity_placeholder_raw_rows:,}")
    print(f"    parent zero-activity raw rows:        {report.parent_zero_activity_placeholder_raw_rows:,}")
    print(f"    quarantined response rows:            {report.quarantined_response_bar_rows:,}")
    print(f"    parent quarantined response rows:     {report.parent_quarantined_response_bar_rows:,}")
    print(f"  observed symbols:                       {report.observed_symbols:,}")
    print("  exact symbol/session-key integrity:")
    print(f"    unique session keys:                  {report.unique_session_keys:,}")
    print(f"    duplicate session rows:               {report.duplicate_session_rows:,}")
    print(f"    duplicate session keys:               {report.duplicate_session_keys:,}")
    print(f"      exact duplicate keys:               {report.exact_duplicate_session_keys:,}")
    print(f"      conflicting duplicate keys:         {report.conflicting_duplicate_session_keys:,}")
    print(f"      status-conflicting duplicate keys:  {report.status_conflicting_duplicate_session_keys:,}")
    print("  exchange-session integrity:")
    print(f"    non-XNYS raw rows:                    {report.non_exchange_session_rows:,}")
    print(f"    non-XNYS unique session keys:         {report.non_exchange_session_keys:,}")
    print("  trade-backed lifespan coverage:")
    print(f"    evaluable symbols:                    {report.evaluable_trade_lifespan_symbols:,}")
    print(f"    placeholder-only symbols:             {report.placeholder_only_symbols:,}")
    print(f"    trade-backed non-XNYS-only symbols:   {report.trade_backed_nonexchange_only_symbols:,}")
    print(f"    expected XNYS sessions:               {report.expected_exchange_sessions_within_trade_lifespans:,}")
    print(f"    trade-backed sessions:                {report.trade_backed_sessions_within_lifespans:,}")
    print(f"    zero-activity placeholder sessions:   {report.placeholder_sessions_within_lifespans:,}")
    print(f"    absent sessions:                      {report.missing_sessions_within_lifespans:,}")
    print(f"    placeholders outside trade lifespan:  {report.placeholder_sessions_outside_trade_lifespans:,}")
    print(f"    symbols with internal placeholders:   {report.symbols_with_internal_placeholder_sessions:,}")
    print(f"    symbols with internal absent sessions:{report.symbols_with_internal_missing_sessions:>12,}")
    print("  longest internal runs:")
    print(f"    zero-activity placeholder:             {report.max_consecutive_placeholder_sessions:,}")
    print(f"    absent:                                {report.max_consecutive_missing_sessions:,}")
    print(f"    no trade-backed session:               {report.max_consecutive_no_trade_backed_sessions:,}")
    print("  market-wide completeness diagnostics:")
    print(f"    XNYS sessions with zero raw coverage:  {report.market_sessions_with_zero_raw_coverage:,}")
    print("    lowest raw-coverage sessions (active lifespan >=100):")
    for row in report.lowest_market_coverage_sessions:
        print(
            f"      {row['session_date']}: active={int(row['active_lifespan_symbols']):,} "
            f"trade={int(row['trade_backed_symbols']):,} "
            f"placeholder={int(row['zero_activity_placeholder_symbols']):,} "
            f"absent={int(row['absent_symbols']):,} "
            f"raw={float(row['raw_coverage_ratio']):.6f} "
            f"trade_ratio={float(row['trade_backed_ratio']):.6f}"
        )
    print("  sentinel coverage:")
    for symbol, row in report.sentinel_coverage.items():
        raw = row.get("raw_session_coverage_ratio")
        trade = row.get("trade_backed_coverage_ratio")
        raw_text = "n/a" if raw is None else f"{float(raw):.6f}"
        trade_text = "n/a" if trade is None else f"{float(trade):.6f}"
        print(
            f"    {symbol:6s}: expected={int(row['expected_xnys_sessions']):,} "
            f"trade={int(row['trade_backed_sessions']):,} "
            f"placeholder={int(row['placeholder_sessions']):,} "
            f"absent={int(row['missing_sessions']):,} "
            f"raw={raw_text} trade_ratio={trade_text}"
        )
    print("  accounting validation:")
    print(f"    raw row accounting exact:              {report.raw_row_accounting_exact}")
    print(f"    parent classification exact:           {report.parent_classification_accounting_exact}")
    print(f"    unique-session accounting exact:       {report.unique_session_accounting_exact}")
    print(f"  symbol session coverage:                 {report.symbol_coverage_path}")
    print(f"  market session coverage:                 {report.market_session_coverage_path}")
    print(f"  duplicate session evidence:              {report.duplicate_session_path}")
    print(f"  non-exchange session evidence:           {report.non_exchange_session_path}")
    print(f"  report:                                  {report.report_path}")
    print("  canonical data modified:                 False")
    print("  Historical Backfill Gate 5 provider completeness / quality: CURRENT")


if __name__ == "__main__":
    main()
