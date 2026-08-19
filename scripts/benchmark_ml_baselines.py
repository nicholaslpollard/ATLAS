from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.ml.baseline_benchmark import (
    ML_BASELINE_LINEAR_MODEL,
    ML_BASELINE_PRIOR_MODEL,
    MLBaselineBenchmark,
)


def main() -> int:
    settings = load_settings(PROJECT_ROOT)
    report = MLBaselineBenchmark(settings).run()

    print("ATLAS Phase 10 Gate 8 Baseline Probability Benchmark")
    print(f"  contract:                    {report.contract_version}")
    print(f"  status:                      {report.status}")
    print(f"  dataset:                     {report.dataset_id}")
    print(f"  walk-forward:                {report.walk_forward_policy_contract}")
    print(f"  sklearn:                     {report.sklearn_version}")
    print(f"  predictors:                  {report.predictor_count}")
    print(f"  models:                      {report.models}")
    print(f"  final holdout accessed:       {report.final_holdout_accessed}")
    print("  fold evidence:")
    for fold_index in range(1, 11):
        prior = next(
            item for item in report.fold_evidence
            if item.fold_index == fold_index and item.model_name == ML_BASELINE_PRIOR_MODEL
        )
        linear = next(
            item for item in report.fold_evidence
            if item.fold_index == fold_index and item.model_name == ML_BASELINE_LINEAR_MODEL
        )
        print(
            f"    fold {fold_index}: test={linear.test_start}->{linear.test_end} "
            f"rows={linear.test_rows:,} train={linear.train_rows:,}"
        )
        print(
            "      prior:  "
            f"logloss={prior.test_metrics.log_loss:.6f} "
            f"brier={prior.test_metrics.multiclass_brier:.6f} "
            f"auc={prior.test_metrics.macro_ovr_auc:.6f} "
            f"ece={prior.test_metrics.macro_ece:.6f}"
        )
        print(
            "      linear: "
            f"logloss={linear.test_metrics.log_loss:.6f} "
            f"brier={linear.test_metrics.multiclass_brier:.6f} "
            f"auc={linear.test_metrics.macro_ovr_auc:.6f} "
            f"ece={linear.test_metrics.macro_ece:.6f} "
            f"fit={linear.fit_seconds:.2f}s"
        )

    print("  aggregate OOS evidence:")
    for aggregate in report.aggregate_evidence:
        auc = "<NA>" if aggregate.weighted_macro_ovr_auc is None else f"{aggregate.weighted_macro_ovr_auc:.6f}"
        print(
            f"    {aggregate.model_name}: rows={aggregate.test_rows:,} "
            f"logloss={aggregate.weighted_log_loss:.6f} "
            f"brier={aggregate.weighted_multiclass_brier:.6f} "
            f"accuracy={aggregate.weighted_accuracy:.4%} "
            f"auc={auc} ece={aggregate.weighted_macro_ece:.6f}"
        )
    print(
        "  linear vs prior:              "
        f"logloss improvement={report.comparison.relative_log_loss_improvement:.3%} "
        f"brier improvement={report.comparison.relative_brier_improvement:.3%}"
    )
    print(
        "  fold wins:                    "
        f"logloss={report.comparison.linear_log_loss_fold_wins}/10 "
        f"brier={report.comparison.linear_brier_fold_wins}/10"
    )
    print(f"  wall time:                   {report.wall_seconds:.3f}s")
    print(f"  report:                      {report.report_path}")
    print("  result:                      EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
