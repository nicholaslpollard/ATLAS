from __future__ import annotations

from packages.core.settings import load_settings
from packages.features.historical_backfill_feature_promotion_stage import (
    HistoricalBackfillDailyFeaturePromotionStageValidator,
)


def main() -> None:
    report = HistoricalBackfillDailyFeaturePromotionStageValidator(load_settings()).run()
    print("ATLAS Historical Backfill Gate 9-C Staged Bundle Independent Validation")
    print("  safety: read-only proof over staged production-native bundle and live rollback baseline")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  stage source fingerprint:         {report['stage_source_fingerprint']}")
    print("  independently recomputed evidence:")
    print(f"    rows:                           {int(report['rows']):,}")
    print(f"    sessions:                       {int(report['sessions']):,}")
    print(f"    feature hash failures:          {int(report['feature_hash_failures']):,}")
    print(f"    source hash failures:           {int(report['source_hash_failures']):,}")
    print(f"    production manifest failures:   {int(report['manifest_failures']):,}")
    print(f"    year-state failures:            {int(report['year_state_failures']):,}")
    print(f"    monthly-state failures:         {int(report['monthly_state_failures']):,}")
    print(f"    current-state failures:         {int(report['current_state_failures']):,}")
    print("  checks:")
    for key, value in report["checks"].items():
        print(f"    {key}: {value}")
    print(f"  stage report:                     {report['stage_report_path']}")
    print(f"  validation report:                {report['report_path']}")
    print(f"  production feature writes:        {int(report['production_feature_writes']):,}")
    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 9-C staged bundle independent validation: FAIL")
    print("  Historical Backfill Gate 9-C staged bundle independent validation: PASS")
    print("  Historical Backfill Gate 9-C production directory handoff: CURRENT")


if __name__ == "__main__":
    main()
