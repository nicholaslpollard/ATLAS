from __future__ import annotations

from packages.core.settings import load_settings
from packages.features.historical_backfill_feature_promotion import (
    HistoricalBackfillDailyFeaturePromotionPreflight,
)


def _gib(value: object) -> float:
    return int(value) / (1024.0**3)


def main() -> None:
    report = HistoricalBackfillDailyFeaturePromotionPreflight(load_settings()).run()
    candidate = report["candidate"]
    baseline = report["production_rollback_baseline"]
    plan = report["promotion_plan"]

    print("ATLAS Historical Backfill Gate 9-C Production Daily Feature Promotion Preflight")
    print("  safety: read-only; freezes candidate replay and current production rollback baseline")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print(f"  Gate 9-B fingerprint:             {report['gate9b_replay_source_fingerprint']}")
    print(f"  Gate 9-B validation contract:     {report['gate9b_validation_contract']}")
    print("  candidate replay:")
    print(f"    rows:                           {int(candidate['rows']):,}")
    print(f"    sessions:                       {int(candidate['sessions']):,}")
    print(f"    first session:                  {candidate['first_session']}")
    print(f"    last session:                   {candidate['last_session']}")
    print(f"    feature hash failures:          {int(candidate['feature_hash_failures']):,}")
    print(f"    manifest hash failures:         {int(candidate['manifest_hash_failures']):,}")
    print(f"    year checkpoints:               {int(candidate['year_checkpoints']):,}")
    print(f"    checkpoint hash failures:       {int(candidate['year_checkpoint_hash_failures']):,}")
    print(f"    current state as-of:            {candidate['current_state_as_of']}")
    print(f"    candidate feature bytes:        {_gib(candidate['feature_bytes']):.3f} GiB")
    print("  protected production rollback baseline:")
    print(f"    rows:                           {int(baseline['rows']):,}")
    print(f"    sessions:                       {int(baseline['sessions']):,}")
    print(f"    first session:                  {baseline['first_session']}")
    print(f"    last session:                   {baseline['last_session']}")
    print(f"    state files:                    {int(baseline['state_files']):,}")
    print(f"    baseline fingerprint:           {baseline['fingerprint']}")
    print(f"    rollback footprint:             {_gib(baseline['total_bytes']):.3f} GiB")
    print("  promotion plan:")
    print(f"    candidate sessions:             {int(plan['candidate_sessions']):,}")
    print(f"    locked overlap sessions:        {int(plan['locked_overlap_sessions']):,}")
    print(f"    COPY_NEW:                       {int(plan['copy_new_sessions']):,}")
    print(f"    REUSE_EXACT:                    {int(plan['reuse_exact_sessions']):,}")
    print(
        f"    REPLACE_PROTECTED_BASELINE:     "
        f"{int(plan['replace_protected_baseline_sessions']):,}"
    )
    print(f"    FAIL_UNMANAGED_TARGET:           {int(plan['unmanaged_target_sessions']):,}")
    print(f"    candidate promotion footprint:  {_gib(plan['candidate_total_bytes']):.3f} GiB")
    if plan.get("replacement_session_examples"):
        print("    replacement examples:           " + ", ".join(plan["replacement_session_examples"][:10]))
    if plan.get("exact_reuse_session_examples"):
        print("    exact-reuse examples:           " + ", ".join(plan["exact_reuse_session_examples"][:10]))
    print("  checks:")
    for key, value in report["checks"].items():
        print(f"    {key}: {value}")
    print(f"  report:                            {report['report_path']}")
    print(f"  production feature writes:        {int(report['production_feature_writes']):,}")

    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 9-C promotion preflight: FAIL")
    print("  Historical Backfill Gate 9-C promotion preflight: PASS")
    print("  Historical Backfill Gate 9-C production feature write: NOT YET EXECUTED")


if __name__ == "__main__":
    main()
