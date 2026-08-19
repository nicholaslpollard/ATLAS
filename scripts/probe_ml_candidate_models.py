from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.ml.candidate_model_probe import MLCandidateModelProbe


def main() -> int:
    settings = load_settings(PROJECT_ROOT)
    report = MLCandidateModelProbe(settings).run()

    print("ATLAS Phase 10 Gate 9 Candidate Model Feasibility Probe")
    print(f"  contract:                    {report.contract_version}")
    print(f"  status:                      {report.status}")
    print(f"  dataset:                     {report.dataset_id}")
    print(f"  fold:                        {report.fold_index}")
    print(
        "  train sample:                "
        f"{report.sampled_train_rows:,} / {report.full_train_rows:,} rows "
        f"(target {report.sample_target_rows:,})"
    )
    print(
        "  validation:                  "
        f"{report.validation_start} -> {report.validation_end} / {report.validation_rows:,} rows"
    )
    prior = report.prior_validation_metrics
    print(
        "  prior validation:            "
        f"logloss={prior.log_loss:.6f} brier={prior.multiclass_brier:.6f} "
        f"auc={prior.macro_ovr_auc:.6f} ece={prior.macro_ece:.6f}"
    )
    print("  candidate evidence:")
    for item in report.candidates:
        metrics = item.validation_metrics
        print(
            f"    {item.name}: logloss={metrics.log_loss:.6f} "
            f"brier={metrics.multiclass_brier:.6f} auc={metrics.macro_ovr_auc:.6f} "
            f"ece={metrics.macro_ece:.6f} fit={item.fit_seconds:.2f}s "
            f"predict={item.predict_seconds:.2f}s"
        )
    print(f"  fold test accessed:           {report.test_accessed}")
    print(f"  final holdout accessed:       {report.final_holdout_accessed}")
    print(f"  wall time:                   {report.wall_seconds:.3f}s")
    print(f"  report:                      {report.report_path}")
    print("  result:                      EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
