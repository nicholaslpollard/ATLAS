from __future__ import annotations

from packages.core.settings import load_settings
from packages.ml.historical_backfill_long_history_dataset_validation import (
    HistoricalBackfillLongHistoryDatasetValidator,
)


def main() -> None:
    report = HistoricalBackfillLongHistoryDatasetValidator(load_settings()).run()
    b = dict(report["B"])
    x = dict(report["C_extension"])
    a_to_b = dict(report["A_to_B"])
    c = dict(report["C_composite"])
    b_source = dict(report["B_source_audit"])
    x_source = dict(report["C_extension_source_audit"])
    accepted = dict(report["accepted_phase10"])

    print("ATLAS Historical Backfill Gate 11-C Independent Dataset Validation")
    print("  safety: read-only proof over isolated B/C datasets and protected Phase 10 artifacts")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print(f"  builder fingerprint:              {report['builder_source_fingerprint']}")
    print(f"  as-of date:                       {report['as_of_date']}")

    print("  B independent disk proof:")
    print(f"    partitions:                     {int(b['partition_count']):,}")
    print(f"    partition hash failures:        {int(b['partition_hash_failures']):,}")
    print(f"    checkpoint failures:            {int(b['checkpoint_failures']):,}")
    print(f"    schema failures:                {int(b['schema_failures']):,}")
    print(f"    partition metadata failures:    {int(b['partition_metadata_failures']):,}")
    print(f"    rows / keys:                    {int(b['rows']):,} / {int(b['keys']):,}")
    print(f"    symbols:                        {int(b['symbols']):,}")
    print(f"    range:                          {b['first_session']} -> {b['last_session']}")
    print(f"    classes:                        {b['class_rows']}")
    print(f"    observation-key mismatches:     {int(b['observation_key_mismatches']):,}")
    print(f"    predictor integrity failures:   {int(b['predictor_value_failures']):,}")
    print(f"    outcome integrity failures:     {int(b['outcome_integrity_failures']):,}")
    print(f"    context nullability failures:   {int(b['context_nullability_failures']):,}")
    print(f"    source audit:                   {b_source}")

    print("  C-extension independent disk proof:")
    print(f"    partitions:                     {int(x['partition_count']):,}")
    print(f"    partition hash failures:        {int(x['partition_hash_failures']):,}")
    print(f"    checkpoint failures:            {int(x['checkpoint_failures']):,}")
    print(f"    schema failures:                {int(x['schema_failures']):,}")
    print(f"    partition metadata failures:    {int(x['partition_metadata_failures']):,}")
    print(f"    rows / keys:                    {int(x['rows']):,} / {int(x['keys']):,}")
    print(f"    symbols:                        {int(x['symbols']):,}")
    print(f"    range:                          {x['first_session']} -> {x['last_session']}")
    print(f"    classes:                        {x['class_rows']}")
    print(f"    observation-key mismatches:     {int(x['observation_key_mismatches']):,}")
    print(f"    predictor integrity failures:   {int(x['predictor_value_failures']):,}")
    print(f"    outcome integrity failures:     {int(x['outcome_integrity_failures']):,}")
    print(f"    context nullability failures:   {int(x['context_nullability_failures']):,}")
    print(f"    source/identity audit:          {x_source}")

    print("  A -> B independent relationship:")
    print(f"    A rows:                         {int(a_to_b['A_rows']):,}")
    print(f"    overlap rows:                   {int(a_to_b['overlap_rows']):,}")
    print(f"    B-only rows:                    {int(a_to_b['B_only_rows']):,}")
    print(f"    A-only rows:                    {int(a_to_b['A_only_rows']):,}")
    print(f"    overlap label mismatches:       {int(a_to_b['overlap_label_mismatches']):,}")

    print("  C composite independent recompute:")
    print(f"    rows / keys:                    {int(c['rows']):,} / {int(c['keys']):,}")
    print(f"    symbols:                        {int(c['symbols']):,}")
    print(f"    range:                          {c['first_session']} -> {c['last_session']}")
    print(f"    classes:                        {c['class_rows']}")
    print(f"    market context rows:            {int(c['market_context_rows']):,}")

    print("  protected Phase 10:")
    print(f"    dataset id:                     {accepted['dataset_id']}")
    print(f"    model id:                       {accepted['model_id']}")
    print(f"    model hash exact:               {accepted['model_hash_exact']}")

    print("  checks:")
    for name, value in dict(report["checks"]).items():
        print(f"    {name}: {value}")
    print(f"  report:                            {report['report_path']}")
    print(f"  production ML writes:              {report['production_ml_writes']}")
    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 11-C independent dataset validation: FAIL")
    print("  Historical Backfill Gate 11-C independent dataset validation: PASS")
    print("  Historical Backfill Gate 11-C lineage-controlled datasets: ACCEPTED")
    print("  Historical Backfill Gate 11-D B-vs-C model evaluation design: CURRENT")


if __name__ == "__main__":
    main()
