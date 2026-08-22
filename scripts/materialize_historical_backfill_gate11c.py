from __future__ import annotations

from packages.core.settings import load_settings
from packages.ml.historical_backfill_long_history_datasets import (
    HistoricalBackfillLongHistoryDatasetBuilder,
)


def _pct(numerator: int, denominator: int) -> str:
    return "0.000000%" if denominator <= 0 else f"{100.0 * numerator / denominator:.6f}%"


def main() -> None:
    report = HistoricalBackfillLongHistoryDatasetBuilder(load_settings()).run()
    b = dict(report["B"])
    x = dict(report["C_extension"])
    c = dict(report["C_composite"])
    accepted = dict(report["accepted_phase10"])

    print("ATLAS Historical Backfill Gate 11-C Lineage-Controlled Long-History Datasets")
    print("  safety: isolated B + pre-seam extension; accepted Phase 10 dataset/model remain protected")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print(f"  fingerprint scope:                {report['fingerprint_scope']}")
    print(f"  Gate 11-A fingerprint:            {report['gate11a_source_fingerprint']}")
    print(f"  Gate 11-B fingerprint:            {report['gate11b_source_fingerprint']}")
    print(f"  as-of date:                       {report['as_of_date']}")

    print("  B — 2021-origin rebase on promoted feature lineage:")
    print(f"    dataset id:                     {b['dataset_id']}")
    print(f"    lineage fingerprint:            {b['dataset_lineage_fingerprint']}")
    print(f"    rows / keys:                    {int(b['row_count']):,} / {int(b['distinct_observation_keys']):,}")
    print(f"    symbols:                        {int(b['symbol_count']):,}")
    print(f"    range:                          {b['first_session_date']} -> {b['last_session_date']}")
    print(f"    classes:                        {b['class_row_counts']}")
    print(
        "    market context:                 "
        f"{int(b['market_context_rows']):,} / {int(b['row_count']):,} "
        f"({_pct(int(b['market_context_rows']), int(b['row_count']))})"
    )
    print(f"    rebuilt years:                  {b['rebuilt_years']}")
    print(f"    reused years:                   {b['reused_years']}")
    print(f"    manifest:                       {b['manifest_path']}")

    print("  C-extension — accepted pre-seam structural population only:")
    print(f"    dataset id:                     {x['dataset_id']}")
    print(f"    lineage fingerprint:            {x['dataset_lineage_fingerprint']}")
    print(f"    rows / keys:                    {int(x['row_count']):,} / {int(x['distinct_observation_keys']):,}")
    print(f"    symbols:                        {int(x['symbol_count']):,}")
    print(f"    range:                          {x['first_session_date']} -> {x['last_session_date']}")
    print(f"    classes:                        {x['class_row_counts']}")
    print(
        "    market context:                 "
        f"{int(x['market_context_rows']):,} / {int(x['row_count']):,} "
        f"({_pct(int(x['market_context_rows']), int(x['row_count']))})"
    )
    print(f"    rebuilt years:                  {x['rebuilt_years']}")
    print(f"    reused years:                   {x['reused_years']}")
    print(f"    manifest:                       {x['manifest_path']}")

    print("  C — composite B + C-extension (no duplicate physical B copy):")
    print(f"    dataset id:                     {c['dataset_id']}")
    print(f"    lineage fingerprint:            {c['dataset_lineage_fingerprint']}")
    print(f"    rows / keys:                    {int(c['row_count']):,} / {int(c['distinct_observation_keys']):,}")
    print(f"    symbols:                        {int(c['symbol_count']):,}")
    print(f"    range:                          {c['first_session_date']} -> {c['last_session_date']}")
    print(f"    classes:                        {c['class_row_counts']}")
    print(
        "    market context:                 "
        f"{int(c['market_context_rows']):,} / {int(c['row_count']):,} "
        f"({_pct(int(c['market_context_rows']), int(c['row_count']))})"
    )
    print(f"    physical B rows:                {int(c['B_rows']):,}")
    print(f"    physical extension rows:        {int(c['extension_rows']):,}")
    print(f"    duplicated B rows in C:         {int(c['duplicated_B_rows']):,}")
    print(f"    composite manifest:             {c['manifest_path']}")

    print("  protected Phase 10 production:")
    print(f"    dataset id:                     {accepted['dataset_id']}")
    print(f"    accepted model:                 {accepted['model_id']}")
    print(f"    model hash exact:               {accepted['model_hash_exact']}")

    print("  checks:")
    for name, value in dict(report["checks"]).items():
        print(f"    {name}: {value}")
    print(f"  report:                            {report['report_path']}")
    print(f"  production ML writes:              {report['production_ml_writes']}")
    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 11-C dataset materialization: FAIL")
    print("  Historical Backfill Gate 11-C lineage-controlled dataset materialization: PASS")
    print("  Historical Backfill Gate 11-C independent dataset validation: CURRENT")


if __name__ == "__main__":
    main()
