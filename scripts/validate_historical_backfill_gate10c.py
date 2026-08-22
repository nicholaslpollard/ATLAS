from __future__ import annotations

from packages.core.settings import load_settings
from packages.regimes.historical_backfill_regime_handoff import HistoricalBackfillRegimeHandoffValidator


def main() -> None:
    report = HistoricalBackfillRegimeHandoffValidator(load_settings()).run()
    print("ATLAS Historical Backfill Gate 10-C Post-Promotion Independent Production Validation")
    print("  safety: read-only proof over live split-origin regime state, history, and frozen rollback")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  handoff source fingerprint:       {report['handoff_source_fingerprint']}")
    print(f"  handoff id:                       {report['handoff_id']}")
    print(f"  as-of date:                       {report['as_of_date']}")
    print("  independently recomputed evidence:")
    print(f"    live current hash failures:     {int(report['live_failures']):,}")
    print(f"    rollback hash failures:         {int(report['rollback_failures']):,}")
    print(f"    history hash failures:          {int(report['history_failures']):,}")
    print(f"    market dependency:              {report['market_dependency']}")
    print(f"    ticker dependency:              {report['ticker_dependency']}")
    print("  checks:")
    for key, value in report["checks"].items():
        print(f"    {key}: {value}")
    print(f"  writer report:                    {report['writer_report_path']}")
    print(f"  journal:                          {report['journal_path']}")
    print(f"  validation report:                {report['report_path']}")
    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 10-C post-promotion independent validation: FAIL")
    print("  Historical Backfill Gate 10-C post-promotion independent validation: PASS")
    print("  Historical Backfill Gate 10-C production regime promotion: ACCEPTED")
    print("  Historical Backfill Gate 11 longer-history ML evaluation: CURRENT")


if __name__ == "__main__":
    main()
