from __future__ import annotations

import argparse
from datetime import date

from packages.core.settings import load_settings
from packages.features.historical_backfill_replay_build import (
    HistoricalBackfillDailyFeatureReplay,
)


def _progress(trading_date: date, index: int, total: int, rows: int) -> None:
    if index == 1 or index % 25 == 0 or index == total:
        print(
            f"    {trading_date.year}: {index:>3}/{total:<3} sessions "
            f"through {trading_date} / {rows:,} rows"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Materialize Gate 9-B isolated 1d feature replay from canonical history."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="rebuild every candidate year instead of reusing valid year checkpoints",
    )
    args = parser.parse_args()

    print("ATLAS Historical Backfill Gate 9-B Isolated Daily Feature Replay")
    print("  safety: candidate namespace only; production feature lake is read-only")
    report = HistoricalBackfillDailyFeatureReplay(load_settings()).run(
        force=args.force,
        progress=_progress,
    )
    lifecycle = report["lifecycle"]
    baseline = report["production_feature_baseline_after"]

    print(f"  contract:                         {report['contract_version']}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print(f"  Gate 9-A fingerprint:             {report['preflight_source_fingerprint']}")
    print(f"  feature contract:                 {report['feature_contract_version']}")
    print(f"  feature registry:                 {report['feature_registry_fingerprint']}")
    print(f"  storage schema:                   {report['feature_storage_schema_version']}")
    print(f"  timeframe / features:             {report['timeframe']} / {int(report['feature_count']):,}")
    print("  candidate replay:")
    print(f"    rows:                           {int(report['candidate_rows']):,}")
    print(f"    sessions:                       {int(report['candidate_sessions']):,}")
    print(f"    expected symbols:               {int(report['candidate_symbols_expected']):,}")
    print(f"    first session:                  {report['first_session']}")
    print(f"    last session:                   {report['last_session']}")
    print(f"    rebuilt years:                  {report['rebuilt_years']}")
    print(f"    reused years:                   {report['reused_years']}")
    print("  lifecycle applied:")
    print(f"    total events:                   {int(lifecycle.get('events', 0)):,}")
    print(f"    identity transfers:             {int(lifecycle.get('identity_transfers', 0)):,}")
    print(f"    seam drop events:               {int(lifecycle.get('seam_drop_events', 0)):,}")
    print(f"    seam drop hits:                 {int(lifecycle.get('seam_drop_hits', 0)):,}")
    print(f"    seam drop misses:               {int(lifecycle.get('seam_drop_misses', 0)):,}")
    print("  protected production 1d feature baseline after replay:")
    print(f"    sessions:                       {int(baseline['sessions']):,}")
    print(f"    rows:                           {int(baseline['rows']):,}")
    print(f"    feature hash failures:          {int(baseline['feature_hash_failures']):,}")
    print(f"    source hash failures:           {int(baseline['source_hash_failures']):,}")
    print(f"    manifest failures:              {int(baseline['manifest_failures']):,}")
    print("  checks:")
    for key, value in report["checks"].items():
        print(f"    {key}: {value}")
    print(f"  candidate current state:          {report['current_state_path']}")
    print(f"  report:                           {report['report_path']}")
    print(f"  production feature writes:        {int(report['production_feature_writes']):,}")

    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 9-B isolated daily feature replay: FAIL")
    print("  Historical Backfill Gate 9-B candidate materialization: PASS")
    print("  Historical Backfill Gate 9-B independent validation: CURRENT")


if __name__ == "__main__":
    main()
