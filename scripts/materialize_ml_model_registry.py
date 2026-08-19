from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.ml.model_registry import MLModelRegistryMaterializer


def main() -> int:
    settings = load_settings(PROJECT_ROOT)
    report = MLModelRegistryMaterializer(settings).materialize()

    print("ATLAS Phase 10 Gate 12 Model Registry / Immutable Prediction Materialization")
    print(f"  registry contract:           {report.contract_version}")
    print(f"  prediction contract:         {report.prediction_contract_version}")
    print(f"  model id:                    {report.model_id}")
    print(f"  model fingerprint:           {report.model_fingerprint}")
    print(f"  status:                      {report.status}")
    print(f"  model:                       {report.model_name} / {report.model_family}")
    print(f"  sklearn:                     {report.sklearn_version}")
    print(f"  dataset:                     {report.dataset_id}")
    print(f"  dataset lineage:             {report.dataset_lineage_sha256}")
    print(f"  feature count:               {report.feature_count}")
    print(f"  calibration:                 {report.calibration_method}")
    print(f"  OOS folds / rows:            {report.oos_fold_count} / {report.oos_rows:,}")
    print(f"  prediction artifacts:        {len(report.prediction_artifacts)}")
    for item in report.prediction_artifacts:
        print(
            f"    fold {item.fold_index}: rows={item.row_count:,} "
            f"sha256={item.sha256}"
        )
    print(f"  final fit artifact present:  {report.final_fit_artifact_present}")
    print(f"  final holdout accessed:       {report.final_holdout_accessed}")
    print(f"  wall time:                   {report.wall_seconds:.3f}s")
    print(f"  manifest:                    {report.report_path}")
    print("  result:                      MATERIALIZED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
