from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.ml.candidate_model_benchmark import MLCandidateModelBenchmark


def main() -> int:
    settings = load_settings(PROJECT_ROOT)
    benchmark = MLCandidateModelBenchmark(settings)
    print("ATLAS Phase 10 Gate 9 Candidate Model Benchmark")
    print("  running accepted 10-fold nonlinear OOS benchmark...", flush=True)
    report = benchmark.run(progress=lambda message: print(f"  {message}", flush=True))

    print(f"  contract:                    {report.contract_version}")
    print(f"  status:                      {report.status}")
    print(f"  dataset:                     {report.dataset_id}")
    print(f"  walk-forward:                {report.walk_forward_policy_contract}")
    print(f"  sklearn:                     {report.sklearn_version}")
    print(f"  predictors:                  {report.predictor_count}")
    print(f"  models:                      {report.models}")
    print(f"  training cap:                {report.training_cap_rows:,} rows/fold")
    print(f"  OOS folds / rows:            {report.fold_count} / {report.total_test_rows:,}")
    print(f"  accepted fold tests accessed: {report.fold_test_accessed}")
    print(f"  final holdout accessed:       {report.final_holdout_accessed}")
    print("  aggregate OOS evidence:")
    for item in report.aggregate_evidence:
        auc = "n/a" if item.weighted_macro_ovr_auc is None else f"{item.weighted_macro_ovr_auc:.6f}"
        print(
            f"    {item.model_name}: rows={item.test_rows:,} "
            f"logloss={item.weighted_log_loss:.6f} "
            f"brier={item.weighted_multiclass_brier:.6f} "
            f"accuracy={item.weighted_accuracy:.4%} "
            f"auc={auc} ece={item.weighted_macro_ece:.6f}"
        )
        print(
            "      vs prior: "
            f"logloss improvement={item.relative_log_loss_improvement_vs_prior:.3%} "
            f"brier improvement={item.relative_brier_improvement_vs_prior:.3%} "
            f"fold wins={item.log_loss_fold_wins_vs_prior}/10 logloss / "
            f"{item.brier_fold_wins_vs_prior}/10 brier"
        )
    print(
        "  Gate 8 references:           "
        f"prior logloss={report.prior_reference['weighted_log_loss']:.6f} "
        f"prior brier={report.prior_reference['weighted_multiclass_brier']:.6f} "
        f"linear auc={report.linear_reference['weighted_macro_ovr_auc']:.6f}"
    )
    print(f"  wall time:                   {report.wall_seconds:.3f}s")
    print(f"  report:                      {report.report_path}")
    print("  result:                      EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
