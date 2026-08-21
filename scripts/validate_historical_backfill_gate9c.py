from __future__ import annotations

from packages.core.settings import load_settings
from packages.features.historical_backfill_feature_handoff_runtime import (
    HistoricalBackfillDailyFeatureHandoffRuntimeValidator,
)


def main() -> None:
    report = HistoricalBackfillDailyFeatureHandoffRuntimeValidator(load_settings()).run()
    print("ATLAS Historical Backfill Gate 9-C Post-Handoff Independent Production Validation")
    print("  safety: read-only proof over live production 1d features and frozen rollback trees")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  handoff source fingerprint:       {report['handoff_source_fingerprint']}")
    print(f"  handoff id:                       {report['handoff_id']}")
    print("  production evidence:")
    print(f"    rows:                           {int(report['rows']):,}")
    print(f"    sessions:                       {int(report['sessions']):,}")
    print(f"    first session:                  {report['first_session']}")
    print(f"    last session:                   {report['last_session']}")
    print(f"    live inventory failures:        {int(report['live_inventory_failures']):,}")
    print(f"    rollback inventory failures:    {int(report['rollback_inventory_failures']):,}")
    print(f"    production manifest failures:   {int(report['manifest_failures']):,}")
    print(f"    canonical source failures:      {int(report['source_hash_failures']):,}")
    print(f"    dependency failures:            {int(report['dependency_failures']):,}")
    print(f"    state failures:                 {int(report['state_failures']):,}")
    print(f"    final manifest failures:        {int(report['final_manifest_failures']):,}")
    print(f"    current state as-of:            {report['current_state_as_of']}")
    print("  checks:")
    for key, value in report["checks"].items():
        print(f"    {key}: {value}")
    print(f"  writer report:                    {report['writer_report_path']}")
    print(f"  journal:                          {report['journal_path']}")
    print(f"  validation report:                {report['report_path']}")
    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 9-C post-handoff validation: FAIL")
    print("  Historical Backfill Gate 9-C post-handoff independent validation: PASS")
    print("  Historical Backfill Gate 9-C production daily feature promotion: ACCEPTED")
    print("  Historical Backfill Gate 10 regime replay extension: CURRENT")


if __name__ == "__main__":
    main()
