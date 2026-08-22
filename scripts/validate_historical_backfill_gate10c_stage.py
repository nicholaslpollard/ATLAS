from __future__ import annotations

from packages.core.settings import load_settings
from packages.regimes.historical_backfill_regime_promotion_stage import (
    HistoricalBackfillRegimePromotionStageValidator,
)


def main() -> None:
    report = HistoricalBackfillRegimePromotionStageValidator(load_settings()).run()
    print("ATLAS Historical Backfill Gate 10-C Independent Staged Regime Validation")
    print("  safety: staged bundle and live boundary are read-only during validation")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  stage fingerprint:                {report['stage_source_fingerprint']}")
    print(f"  Gate 10-C preflight fingerprint:  {report['preflight_source_fingerprint']}")
    print(f"  as-of date:                       {report['as_of_date']}")
    print(f"  history hash failures:            {int(report['history_hash_failures']):,}")
    print("  checks:")
    for key, value in report["checks"].items():
        print(f"    {key}: {value}")
    print(f"  stage report:                      {report['stage_report_path']}")
    print(f"  validation report:                 {report['report_path']}")
    print(f"  production regime writes:          {int(report['production_regime_writes']):,}")
    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 10-C staged-bundle validation: FAIL")
    print("  Historical Backfill Gate 10-C staged-bundle independent validation: PASS")
    print("  Historical Backfill Gate 10-C journaled production promotion: CURRENT")


if __name__ == "__main__":
    main()
