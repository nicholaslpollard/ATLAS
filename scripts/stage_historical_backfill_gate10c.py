from __future__ import annotations

from packages.core.settings import load_settings
from packages.regimes.historical_backfill_regime_promotion_stage import (
    HistoricalBackfillRegimePromotionStage,
)


def _gib(value: object) -> float:
    return int(value) / (1024.0**3)


def main() -> None:
    report = HistoricalBackfillRegimePromotionStage(load_settings()).run()
    print("ATLAS Historical Backfill Gate 10-C Production-Native Regime Staging")
    print("  safety: isolated staging namespace only; production regime artifacts remain read-only")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print(f"  Gate 10-C preflight fingerprint:  {report['preflight_source_fingerprint']}")
    print(f"  as-of date:                       {report['as_of_date']}")
    print("  staged bundle:")
    print(f"    artifacts:                       {int(report['staged_artifact_count']):,}")
    print(f"    copied files:                    {int(report['copied_files']):,}")
    print(f"    reused exact files:              {int(report['reused_files']):,}")
    print(f"    staged footprint:                {_gib(report['staged_bytes']):.3f} GiB")
    print("    current state:")
    for key in ("market_sector_snapshot", "market_sector_manifest", "ticker_snapshot", "ticker_manifest"):
        entry = report["artifacts"][key]
        print(f"      {key:<26} sha256={entry['sha256']}")
    print("    history:")
    for name, entry in report["artifacts"]["history"].items():
        print(f"      {name:<18} sha256={entry['sha256']}")
    print("  checks:")
    for key, value in report["checks"].items():
        print(f"    {key}: {value}")
    print(f"  report:                            {report['report_path']}")
    print(f"  production regime writes:         {int(report['production_regime_writes']):,}")
    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 10-C production-native regime staging: FAIL")
    print("  Historical Backfill Gate 10-C production-native regime staging: PASS")
    print("  Historical Backfill Gate 10-C staged-bundle independent validation: CURRENT")


if __name__ == "__main__":
    main()
