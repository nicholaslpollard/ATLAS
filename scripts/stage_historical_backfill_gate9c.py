from __future__ import annotations

from packages.core.settings import load_settings
from packages.features.historical_backfill_feature_promotion_stage import (
    HistoricalBackfillDailyFeaturePromotionStage,
)


def _gib(value: object) -> float:
    return int(value) / (1024.0**3)


def _progress(year: int, action: str, sessions: int, rows: int) -> None:
    print(f"  year {year}: {action:<7} sessions={sessions:,} rows={rows:,}", flush=True)


def main() -> None:
    report = HistoricalBackfillDailyFeaturePromotionStage(load_settings()).run(
        progress=_progress
    )
    print("ATLAS Historical Backfill Gate 9-C Production-Native Staging")
    print("  safety: isolated staging namespace only; production 1d feature lake remains read-only")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print(f"  Gate 9-C preflight fingerprint:   {report['preflight_source_fingerprint']}")
    print("  staged bundle:")
    print(f"    rows:                           {int(report['candidate_rows']):,}")
    print(f"    sessions:                       {int(report['candidate_sessions']):,}")
    print(f"    first session:                  {report['first_session']}")
    print(f"    last session:                   {report['last_session']}")
    print(f"    rebuilt years:                  {report['rebuilt_years']}")
    print(f"    reused years:                   {report['reused_years']}")
    print(f"    staged feature files:           {int(report['staged_feature_files']):,}")
    print(f"    staged production manifests:    {int(report['staged_manifest_files']):,}")
    print(f"    monthly state checkpoints:      {int(report['monthly_checkpoints']):,}")
    print(f"    staged state files:             {int(report['staged_state_files']):,}")
    print(f"    staged footprint:               {_gib(report['staged_bytes']):.3f} GiB")
    print("  checks:")
    for key, value in report["checks"].items():
        print(f"    {key}: {value}")
    print(f"  report:                            {report['report_path']}")
    print(f"  production feature writes:        {int(report['production_feature_writes']):,}")
    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 9-C production-native staging: FAIL")
    print("  Historical Backfill Gate 9-C production-native staging: PASS")
    print("  Historical Backfill Gate 9-C staged-bundle independent validation: CURRENT")


if __name__ == "__main__":
    main()
