from __future__ import annotations

import argparse

from packages.core.settings import load_settings
from packages.features.historical_backfill_feature_handoff_runtime import (
    HistoricalBackfillDailyFeatureHandoffRuntime,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Promote or rollback the accepted Gate 9-C production 1d feature bundle."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--apply",
        action="store_true",
        help="Apply the journaled rollback-protected production directory handoff.",
    )
    action.add_argument(
        "--rollback",
        action="store_true",
        help="Restore the frozen pre-Gate-9-C production 1d feature baseline.",
    )
    args = parser.parse_args()

    handoff = HistoricalBackfillDailyFeatureHandoffRuntime(load_settings())
    if args.rollback:
        report = handoff.rollback()
        print("ATLAS Historical Backfill Gate 9-C Production Daily Feature Rollback")
        print(f"  contract:                         {report['contract_version']}")
        print(f"  source fingerprint:               {report['source_fingerprint']}")
        print(f"  handoff id:                       {report['handoff_id']}")
        print(f"  status:                           {report['status']}")
        print(f"  rollback restored:                {report['rollback_restored']}")
        print(f"  journal:                          {report['journal_path']}")
        if report.get("rollback_restored") is not True:
            raise SystemExit("Historical Backfill Gate 9-C rollback: FAIL")
        print("  Historical Backfill Gate 9-C rollback: PASS")
        return

    report = handoff.apply()
    print("ATLAS Historical Backfill Gate 9-C Production Daily Feature Directory Handoff")
    print("  safety: old production trees preserved intact in same-filesystem rollback roots")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print(f"  handoff id:                       {report['handoff_id']}")
    print(f"  status:                           {report['status']}")
    print("  production 1d feature lake:")
    print(f"    rows:                           {int(report['rows']):,}")
    print(f"    sessions:                       {int(report['sessions']):,}")
    print(f"    first session:                  {report['first_session']}")
    print(f"    last session:                   {report['last_session']}")
    print(f"    feature files:                  {int(report['production_feature_files']):,}")
    print(f"    production manifests:           {int(report['production_manifest_files']):,}")
    print(f"    state files:                    {int(report['production_state_files']):,}")
    print("  frozen rollback baseline:")
    print(f"    feature files:                  {int(report['rollback_feature_files']):,}")
    print(f"    production manifests:           {int(report['rollback_manifest_files']):,}")
    print(f"    state files:                    {int(report['rollback_state_files']):,}")
    print(f"    inventory fingerprint:          {report['rollback_inventory_fingerprint']}")
    print("  rollback paths:")
    for key, value in report["rollback_paths"].items():
        print(f"    {key}: {value}")
    print("  checks:")
    for key, value in report["checks"].items():
        print(f"    {key}: {value}")
    print(f"  journal:                          {report['journal_path']}")
    print(f"  report:                           {report['report_path']}")
    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 9-C production directory handoff: FAIL")
    print("  Historical Backfill Gate 9-C production directory handoff: PASS")
    print("  Historical Backfill Gate 9-C post-handoff independent validation: CURRENT")


if __name__ == "__main__":
    main()
