from __future__ import annotations

from packages.core.settings import load_settings
from packages.ml.historical_backfill_model_evaluation_design import (
    HistoricalBackfillModelEvaluationDesign,
)


def _pct(numerator: int, denominator: int) -> str:
    return "0.000000%" if denominator <= 0 else f"{100.0 * numerator / denominator:.6f}%"


def main() -> None:
    report = HistoricalBackfillModelEvaluationDesign(load_settings()).run()
    experiment = dict(report["experiment"])
    paired = dict(report["paired_evaluation"])
    folds = list(report["folds"])

    print("ATLAS Historical Backfill Gate 11-D B-vs-C Model Evaluation Design")
    print("  safety: design/preflight only; no model fitting and no production ML writes")
    print(f"  contract:                         {report['contract_version']}")
    print(f"  source fingerprint:               {report['source_fingerprint']}")
    print(f"  fingerprint scope:                {report['fingerprint_scope']}")
    print(f"  Gate 11-C builder fingerprint:    {report['gate11c_builder_fingerprint']}")
    print(f"  Gate 11-C validation fingerprint: {report['gate11c_validation_fingerprint']}")
    print(f"  as-of date:                       {report['as_of_date']}")

    print("  locked experiment:")
    print(f"    model family:                    {experiment['model_family']}")
    print(f"    model name:                      {experiment['model_name']}")
    print(f"    predictor count:                 {int(experiment['predictor_count'])}")
    print(f"    walk-forward policy:             {experiment['walk_forward_policy']}")
    print(f"    accepted candidate:              {experiment['walk_forward_candidate']}")
    print(
        "    train/validation/test/step:     "
        f"{int(experiment['minimum_train_sessions'])}/"
        f"{int(experiment['validation_sessions'])}/"
        f"{int(experiment['test_sessions'])}/"
        f"{int(experiment['step_sessions'])} sessions"
    )
    print(
        "    purge / extra embargo:          "
        f"{int(experiment['purge_sessions'])} / {int(experiment['additional_embargo_sessions'])} sessions"
    )
    print(f"    fold count:                      {int(experiment['fold_count'])}")
    print(
        "    protected final holdout:        "
        f"{experiment['final_holdout_start']} -> {experiment['final_holdout_end']}"
    )
    print(f"    final holdout used for selection:{experiment['final_holdout_used_for_selection']}")
    print(f"    model training allowed here:     {experiment['model_training_allowed_in_gate11d']}")

    fixed = dict(experiment["primary_fixed_budget"])
    nested = dict(experiment["nested_history_sensitivity"])
    print("  comparison roles:")
    print(f"    primary:                         {fixed['role']}")
    print(f"      budget:                        {int(fixed['training_budget_rows_per_fold']):,} rows/candidate/fold")
    print(f"      sampling:                      {fixed['sampling']}")
    print(f"      interpretation:                {fixed['interpretation']}")
    print(f"      selection metrics:             {fixed['selection_metrics']}")
    print(f"      diagnostics:                   {fixed['diagnostic_metrics']}")
    print(f"      rule:                          {fixed['selection_rule']}")
    print(f"    sensitivity:                     {nested['role']}")
    print(f"      B base:                        {nested['B_base_sample']}")
    print(f"      extension cap:                 {int(nested['extension_cap_rows_per_fold']):,} rows/fold")
    print(f"      interpretation:                {nested['interpretation']}")
    print(f"      can promote model:             {nested['can_promote_model']}")

    print("  paired evaluation proof:")
    print(f"    folds:                           {int(paired['folds'])}")
    print(f"    first validation:                {paired['first_validation']}")
    print(f"    last test:                       {paired['last_test']}")
    print(f"    all B/C validation+test keys exact: {paired['all_pairs_exact']}")
    print(f"    final-holdout overlap windows:   {int(paired['final_holdout_overlap_windows'])}")

    print("  per-fold training/evaluation design:")
    for item in folds:
        fixed_fold = dict(item["fixed_budget"])
        nested_fold = dict(item["nested_history_sensitivity"])
        print(
            f"    fold {int(item['fold_index']):02d}: "
            f"train_end={item['accepted_train_end']} "
            f"val={item['validation_start']}->{item['validation_end']} "
            f"test={item['test_start']}->{item['test_end']}"
        )
        print(
            "      full train B / extension / C: "
            f"{int(item['B_full_train_rows']):,} / "
            f"{int(item['C_extension_full_train_rows']):,} / "
            f"{int(item['C_full_train_rows']):,}"
        )
        print(
            "      fixed samples B / C(B+x):     "
            f"{int(fixed_fold['B_sample_rows']):,} / "
            f"{int(fixed_fold['C_sample_rows']):,} "
            f"({int(fixed_fold['C_B_component_rows']):,}+{int(fixed_fold['C_extension_component_rows']):,})"
        )
        print(
            "      nested B + extension / total: "
            f"{int(nested_fold['B_base_sample_rows']):,} + "
            f"{int(nested_fold['extension_sample_rows']):,} = "
            f"{int(nested_fold['C_nested_sample_rows']):,}"
        )
        print(
            "      validation B/C rows exact:    "
            f"{int(item['B_validation_rows']):,}/{int(item['C_validation_rows']):,} "
            f"hash_equal={item['validation_key_hash_equal']}"
        )
        print(
            "      test B/C rows exact:          "
            f"{int(item['B_test_rows']):,}/{int(item['C_test_rows']):,} "
            f"hash_equal={item['test_key_hash_equal']}"
        )

    print("  checks:")
    for name, value in dict(report["checks"]).items():
        print(f"    {name}: {value}")
    print(f"  report:                            {report['report_path']}")
    print(f"  production ML writes:              {report['production_ml_writes']}")
    if report.get("pass") is not True:
        raise SystemExit("Historical Backfill Gate 11-D model evaluation design: FAIL")
    print("  Historical Backfill Gate 11-D B-vs-C model evaluation design: PASS")
    print("  Historical Backfill Gate 11-E paired fixed-budget + nested-history benchmark: CURRENT")


if __name__ == "__main__":
    main()
