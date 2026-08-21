from __future__ import annotations

from packages.core.settings import load_settings
from packages.features.historical_backfill_replay_validation import (
    HistoricalBackfillDailyFeatureReplayValidator,
)


def main() -> None:
    report = HistoricalBackfillDailyFeatureReplayValidator(load_settings()).run()
    candidate = report["candidate"]
    transfer = report["identity_transfer_proof"]
    sentinel = report["liquid_sentinel_proof"]
    seam = report["seam_proof"]

    print("ATLAS Historical Backfill Gate 9-B Independent Daily Feature Replay Validation")
    print("  safety: read-only proof over candidate replay and protected production features")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  validation contract:              {report['validation_contract_version']}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print(f"  Gate 9-A fingerprint:             {report['preflight_source_fingerprint']}")
    print("  candidate feature lake:")
    print(f"    rows:                           {int(candidate['rows']):,}")
    print(f"    sessions:                       {int(candidate['sessions']):,}")
    print(f"    symbols:                        {int(candidate['symbols']):,}")
    print(f"    first session:                  {candidate['first_session']}")
    print(f"    last session:                   {candidate['last_session']}")
    print(f"    schema exact:                   {candidate['schema_exact']}")
    print(f"    feature hash failures:          {int(report['feature_hash_failures']):,}")
    print(f"    source hash failures:           {int(report['source_hash_failures']):,}")
    print(f"    key-mismatched sessions:        {int(report['key_mismatched_sessions']):,}")
    print(f"    duplicate candidate keys:       {int(report['duplicate_candidate_keys']):,}")
    print("  identity-transfer proof:")
    print(f"    transfers:                      {int(transfer['transfers']):,}")
    print(f"    missing inputs:                 {int(transfer['missing']):,}")
    print(f"    return mismatches:              {int(transfer['mismatches']):,}")
    print(f"    max abs return error:           {transfer['max_abs_error']}")
    print("  liquid sentinel equivalence:")
    print(f"    sentinels:                      {int(sentinel['sentinels']):,}")
    print(f"    rows:                           {int(sentinel['rows']):,}")
    print(f"    keys exact:                     {sentinel['keys_exact']}")
    print(f"    feature mismatches:             {int(sentinel['feature_mismatches']):,}")
    print(f"    max abs feature error:          {sentinel['max_abs_error']}")
    print("  provider-seam state proof:")
    print(f"    bridge rows:                    {int(seam['bridge_rows']):,}")
    print(f"    bridge null returns:            {int(seam['bridge_null_returns']):,}")
    print(f"    fresh target symbols:           {int(seam['fresh_target_symbols']):,}")
    print(f"    fresh observed symbols:         {int(seam['fresh_observed_symbols']):,}")
    print(f"    fresh genesis mismatches:       {int(seam['fresh_genesis_mismatches']):,}")
    print("  checks:")
    for key, value in report["checks"].items():
        print(f"    {key}: {value}")
    print(f"  validation report:                {report['report_path']}")
    print(f"  stored replay report:             {report['stored_replay_report_path']}")
    print(f"  production feature writes:        {int(report['production_feature_writes']):,}")

    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 9-B independent validation: FAIL")
    print("  Historical Backfill Gate 9-B isolated daily feature replay: PASS")
    print("  Historical Backfill Gate 9-C production daily feature promotion: CURRENT")


if __name__ == "__main__":
    main()
