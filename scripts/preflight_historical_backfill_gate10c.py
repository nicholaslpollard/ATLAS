from __future__ import annotations

from packages.core.settings import load_settings
from packages.regimes.historical_backfill_regime_promotion import (
    HistoricalBackfillRegimePromotionPreflight,
)


def _gib(value: int) -> str:
    return f"{value / (1024 ** 3):.3f} GiB"


def main() -> None:
    report = HistoricalBackfillRegimePromotionPreflight(load_settings()).run()
    print("ATLAS Historical Backfill Gate 10-C Production Regime Promotion Preflight")
    print("  safety: read-only production-boundary freeze; no production regime artifacts written")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print(f"  Gate 10-B fingerprint:            {report['builder_source_fingerprint']}")
    print(f"  as-of date:                       {report['as_of_date']}")
    print("  production policy:")
    print(f"    split-origin policy:             {report['split_origin_policy']}")
    print(f"    market/sector origin:            {report['market_sector_history_origin']}")
    print(f"    ticker/intraday origin:          {report['ticker_history_origin']}")
    print(f"    market dependency:               {report['production_market_dependency']}")
    print(f"    ticker dependency:               {report['production_ticker_dependency']}")
    print("  frozen live rollback baseline:")
    for name, entry in report["live_rollback_baseline"].items():
        print(
            f"    {name:<28} present={entry['present']} "
            f"bytes={int(entry['bytes']):,} sha256={entry['sha256']}"
        )
    print(f"    rollback footprint:              {_gib(int(report['rollback_footprint_bytes']))}")
    print("  current-state replacement plan:")
    for name, entry in report["current_replacement_plan"].items():
        print(f"    {name:<28} {entry['action']}")
    print("  versioned regime-history publication:")
    for name, entry in report["history_publication_plan"].items():
        print(f"    {name:<18} {entry['action']:<12} -> {entry['target_path']}")
    print(f"  promotion footprint:               {_gib(int(report['candidate_promotion_footprint_bytes']))}")
    print("  checks:")
    for key, value in report["checks"].items():
        print(f"    {key}: {value}")
    print(f"  report:                            {report['report_path']}")
    print(f"  production regime writes:         {int(report['production_regime_writes']):,}")
    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 10-C promotion preflight: FAIL")
    print("  Historical Backfill Gate 10-C promotion preflight: PASS")
    print("  Historical Backfill Gate 10-C production-native staging: CURRENT")


if __name__ == "__main__":
    main()
