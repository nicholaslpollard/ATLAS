from __future__ import annotations

from packages.core.settings import load_settings
from packages.features.historical_backfill_replay import (
    HistoricalBackfillFeatureReplayPreflight,
)


def main() -> None:
    report = HistoricalBackfillFeatureReplayPreflight(load_settings()).run()
    canonical = report["canonical"]
    lifecycle = report["lifecycle"]
    baseline = report["production_feature_baseline"]

    print("ATLAS Historical Backfill Gate 9-A Daily Feature Replay Preflight")
    print("  safety: read-only with respect to production feature lake; isolated replay not started")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print(f"  Gate 8 fingerprint:               {report['gate8_source_fingerprint']}")
    print(f"  Gate 7 fingerprint:               {report['gate7_source_fingerprint']}")
    print(f"  feature contract:                 {report['feature_contract_version']}")
    print(f"  feature registry:                 {report['feature_registry_fingerprint']}")
    print(f"  timeframe / features:             {report['timeframe']} / {int(report['feature_count']):,}")
    print("  canonical daily source:")
    print(f"    rows:                           {int(canonical['rows']):,}")
    print(f"    sessions:                       {int(canonical['sessions']):,}")
    print(f"    symbols:                        {int(canonical['symbols']):,}")
    print(f"    Alpaca rows:                    {int(canonical['alpaca_rows']):,}")
    print(f"    Massive rows:                   {int(canonical['massive_rows']):,}")
    print(f"    first session:                  {canonical['first_session']}")
    print(f"    last session:                   {canonical['last_session']}")
    print(f"    schema exact:                   {canonical['schema_exact']}")
    print("  lifecycle schedule:")
    print(f"    accepted identity transfers:    {int(lifecycle['identity_transfers']):,}")
    print(f"    seam drop events:               {int(lifecycle['seam_drop_events']):,}")
    print(f"    BRIDGE_EXACT_LITERAL:            {int(lifecycle['bridge_exact_literal']):,}")
    print(f"    RESET_AT_PROVIDER_SEAM:          {int(lifecycle['reset_at_provider_seam']):,}")
    print(f"    TERMINATE_PRESEAM_CONTINUITY:    {int(lifecycle['terminate_preseam_continuity']):,}")
    print(f"    QUARANTINE_SEAM_CONTINUITY:      {int(lifecycle['quarantine_seam_continuity']):,}")
    print(f"    POSTSEAM_ONLY:                   {int(lifecycle['postseam_only']):,}")
    print("  protected production 1d feature baseline:")
    print(f"    sessions:                       {int(baseline['sessions']):,}")
    print(f"    rows:                           {int(baseline['rows']):,}")
    print(f"    first session:                  {baseline['first_session']}")
    print(f"    last session:                   {baseline['last_session']}")
    print(f"    feature hash failures:          {int(baseline['feature_hash_failures']):,}")
    print(f"    source hash failures:           {int(baseline['source_hash_failures']):,}")
    print(f"    manifest failures:              {int(baseline['manifest_failures']):,}")
    print(f"    checkpoint/state files:         {int(baseline['state_files']):,}")
    print("  checks:")
    for key, value in report["checks"].items():
        print(f"    {key}: {value}")
    print(f"  lifecycle artifact:               {report['lifecycle_path']}")
    print(f"  candidate feature root:           {report['candidate_feature_root']}")
    print(f"  production feature writes:        {int(report['production_feature_writes']):,}")
    print(f"  report:                           {report['report_path']}")

    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 9-A daily feature replay preflight: FAIL")
    print("  Historical Backfill Gate 9-A daily feature replay preflight: PASS")
    print("  Historical Backfill Gate 9-B isolated daily feature replay: CURRENT")


if __name__ == "__main__":
    main()
