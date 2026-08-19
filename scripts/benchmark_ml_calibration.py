from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.ml.calibration_benchmark import MLCalibrationBenchmark


def main() -> int:
    settings = load_settings(PROJECT_ROOT)
    print("ATLAS Phase 10 Gate 10 Probability Calibration Benchmark")
    print("  fitting calibrators on each fold validation window and scoring frozen test predictions...")
    report = MLCalibrationBenchmark(settings).run(progress=lambda line: print(f"  {line}"))

    print(f"  contract:                    {report.contract_version}")
    print(f"  status:                      {report.status}")
    print(f"  accepted model:              {report.accepted_model}")
    print(f"  methods:                     {report.methods}")
    print(f"  validation-only fit:         {report.validation_only_fit}")
    print(f"  test-only score:             {report.test_only_score}")
    print(f"  OOS folds / rows:            {report.fold_count} / {report.total_test_rows:,}")
    print(f"  final holdout accessed:       {report.final_holdout_accessed}")
    print("  aggregate OOS evidence:")
    for item in report.aggregate_evidence:
        print(
            f"    {item.method}: rows={item.test_rows:,} logloss={item.weighted_log_loss:.6f} "
            f"brier={item.weighted_multiclass_brier:.6f} accuracy={item.weighted_accuracy:.4%} "
            f"auc={item.weighted_macro_ovr_auc:.6f} ece={item.weighted_macro_ece:.6f}"
        )
        if item.method != "raw":
            print(
                "      vs raw: "
                f"logloss improvement={item.relative_log_loss_improvement_vs_raw:.3%} "
                f"brier improvement={item.relative_brier_improvement_vs_raw:.3%} "
                f"fold wins={item.log_loss_fold_wins_vs_raw}/10 logloss / "
                f"{item.brier_fold_wins_vs_raw}/10 brier"
            )
    print(f"  wall time:                   {report.wall_seconds:.3f}s")
    print(f"  report:                      {report.report_path}")
    print("  result:                      EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
