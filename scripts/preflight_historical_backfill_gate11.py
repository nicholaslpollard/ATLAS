from __future__ import annotations

from packages.core.settings import load_settings
from packages.ml.historical_backfill_long_history_preflight_runtime import (
    HistoricalBackfillLongHistoryMLPreflightRuntime,
)


def _pct(value: float) -> str:
    return f"{100.0 * value:.6f}%"


def main() -> None:
    report = HistoricalBackfillLongHistoryMLPreflightRuntime(load_settings()).run()
    accepted = report["accepted_phase10_A"]
    rebase = report["B_rebase_evidence"]
    pre = report["C_preseam_feasibility_before_structural_reconciliation"]
    lineage = report["feature_lineage"]

    print("ATLAS Historical Backfill Gate 11-A Longer-History ML Preflight")
    print("  safety: read-only feasibility/comparison proof; accepted Phase 10 model remains protected")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print(f"  fingerprint scope:                {report['fingerprint_scope']}")
    print(f"  as-of date:                       {report['as_of_date']}")
    print("  locked comparison:")
    print("    A: frozen accepted Phase 10 dataset/model")
    print("    B: 2021-origin rebase on promoted long-warmup feature lineage")
    print("    C: B plus safe 2016-2021 history after Gate 11-B structural reconciliation")
    print("    attribution: A->B = lineage/warmup rebase; B->C = marginal older-history effect")
    print("    final Phase 10 holdout used for Gate 11 selection: False")
    print("    accepted production model replacement allowed here: False")
    print("  frozen Phase 10 A:")
    print(f"    dataset id:                     {accepted['dataset_id']}")
    print(f"    rows:                           {int(accepted['dataset_rows']):,}")
    print(f"    range:                          {accepted['dataset_first_session']} -> {accepted['dataset_last_session']}")
    print(f"    partition hash failures:        {accepted['dataset_partition_hash_failures']}")
    print(f"    accepted model:                 {accepted['model_id']}")
    print(f"    model hash exact:               {accepted['model_hash_exact']}")
    print("  promoted feature lineage:")
    print(
        "    B 2021-origin:                 "
        f"{lineage['B_rebase']['manifest_count']:,} manifests / "
        f"fingerprint={lineage['B_rebase']['fingerprint']}"
    )
    print(
        "    C 2016-origin:                 "
        f"{lineage['C_full']['manifest_count']:,} manifests / "
        f"fingerprint={lineage['C_full']['fingerprint']}"
    )
    print("  B rebase evidence (same Phase 10 identity/label policy, new feature lineage):")
    print(f"    rows / keys:                    {int(rebase['rows']):,} / {int(rebase['distinct_keys']):,}")
    print(f"    symbols:                        {int(rebase['symbols']):,}")
    print(f"    range:                          {rebase['first_session']} -> {rebase['last_session']}")
    print(f"    class rows:                     {rebase['class_rows']}")
    print(f"    overlap with A:                 {int(rebase['overlap_with_A_rows']):,}")
    print(f"    B-only rows:                    {int(rebase['B_only_rows']):,}")
    print(f"    A-only rows:                    {int(rebase['A_only_rows']):,}")
    print(f"    overlap label mismatches:       {int(rebase['overlap_label_mismatches']):,}")
    print("  C pre-seam feasibility before structural reference reconciliation:")
    print(f"    canonical rows:                 {int(pre['source_rows']):,}")
    print(f"    symbols:                        {int(pre['symbols']):,}")
    print(f"    range:                          {pre['first_session']} -> {pre['last_session']}")
    print(f"    identity-unmatched rows:        {int(pre['identity_unmatched_rows']):,}")
    print(f"    identity-ambiguous rows:        {int(pre['identity_ambiguous_rows']):,}")
    print(f"    feature key audit rows:         {int(pre['feature_key_audit_canonical_rows']):,}")
    print(f"    missing feature rows:           {int(pre['missing_feature_rows']):,}")
    print(f"    duplicate feature keys:         {int(pre['duplicate_feature_keys']):,}")
    print(f"    matched feature rows:           {int(pre['matched_feature_rows']):,}")
    print(f"    complete feature rows:          {int(pre['complete_feature_rows']):,}")
    print(f"    complete+liquid rows:           {int(pre['complete_liquid_rows']):,}")
    print(f"    identity/feature candidates:    {int(pre['identity_feature_label_candidates']):,}")
    print(f"    split events / symbols:         {int(pre['split_events']):,} / {int(pre['split_symbols']):,}")
    print(f"    provider-seam censored:         {int(pre['provider_seam_censored']):,}")
    print(f"    same-symbol future missing:     {int(pre['same_symbol_future_missing']):,}")
    print(f"    split-censored:                 {int(pre['split_censored']):,}")
    print(f"    usable pre-structural rows:     {int(pre['usable_before_structural_reconciliation']):,}")
    print(f"    usable range:                   {pre['first_usable_session']} -> {pre['last_usable_session']}")
    print(f"    provisional class rows:         {pre['class_rows_before_structural_reconciliation']}")
    print(
        "    market context coverage:        "
        f"{int(pre['market_context_rows']):,} / {int(pre['usable_before_structural_reconciliation']):,} "
        f"({_pct(float(pre['market_context_fraction']))})"
    )
    print(
        "    unique-ref metadata lower bound:"
        f" {int(pre['unique_reference_metadata_rows_lower_bound']):,} rows "
        f"({_pct(float(pre['unique_reference_metadata_row_fraction_lower_bound']))})"
    )
    print(f"    structural status:              {pre['structural_reconciliation_status']}")
    print("  checks:")
    for key, value in report["checks"].items():
        print(f"    {key}: {value}")
    print(f"  report:                            {report['report_path']}")
    print(f"  production ML writes:              {report['production_ml_writes']}")
    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 11-A longer-history ML preflight: FAIL")
    print("  Historical Backfill Gate 11-A longer-history ML preflight: PASS")
    print("  Historical Backfill Gate 11-B pre-2021 structural identity/eligibility reconciliation: CURRENT")


if __name__ == "__main__":
    main()
