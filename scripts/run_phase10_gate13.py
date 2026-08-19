from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.ml.final_acceptance import MLFinalAcceptance


def _metrics_line(name, metrics) -> str:
    auc = "NA" if metrics.macro_ovr_auc is None else f"{metrics.macro_ovr_auc:.6f}"
    return (
        f"  {name:<12} logloss={metrics.log_loss:.6f} "
        f"brier={metrics.multiclass_brier:.6f} accuracy={metrics.accuracy:.4%} "
        f"auc={auc} ece={metrics.macro_ece:.6f}"
    )


def main() -> int:
    settings = load_settings(PROJECT_ROOT)
    print("ATLAS Phase 10 Gate 13 Final Reproducibility / Holdout Acceptance", flush=True)
    print("  verifying Gate 12 registry and opening the protected holdout for the final acceptance test...", flush=True)
    report = MLFinalAcceptance(settings).run(progress=lambda line: print(f"  {line}", flush=True))

    print(f"  contract:                    {report.contract_version}")
    print(f"  status:                      {report.status}")
    print(f"  accepted:                    {report.accepted}")
    print(f"  model id:                    {report.model_id}")
    print(f"  model fingerprint:           {report.model_fingerprint}")
    print(f"  dataset:                     {report.dataset_id}")
    print(f"  dataset lineage:             {report.dataset_lineage_sha256}")
    print(
        "  final training:              "
        f"{report.train_start}->{report.train_end} full={report.full_train_rows:,} "
        f"sample={report.sampled_train_rows:,} cap={report.training_cap_rows:,}"
    )
    print(f"  purge sessions:              {report.purge_sessions}")
    print(
        "  leakage audit:               "
        f"training endpoints in holdout={report.training_rows_with_future_endpoint_in_holdout}"
    )
    print(
        "  final holdout:               "
        f"{report.holdout_start}->{report.holdout_end} / "
        f"{report.holdout_sessions} sessions / {report.holdout_rows:,} rows"
    )
    print(f"  holdout accessed:             {report.holdout_accessed}")
    print(_metrics_line("train prior:", report.prior_metrics))
    print(_metrics_line("final HGB:", report.model_metrics))
    print(
        "  vs prior:                    "
        f"logloss improvement={report.relative_log_loss_improvement_vs_prior:.3%} "
        f"brier improvement={report.relative_brier_improvement_vs_prior:.3%}"
    )
    print(
        "  deterministic replay:        "
        f"max_abs_probability_diff={report.replay_max_abs_probability_diff:.3e} / "
        f"passed={report.replay_passed}"
    )
    print("  acceptance checks:")
    for name, passed in report.acceptance_checks.items():
        print(f"    {name}: {passed}")
    print(
        "  Gate 12 artifacts verified:  "
        f"{report.gate12_prediction_artifacts_verified}"
    )
    if report.final_model_artifact is not None:
        print(
            "  final model artifact:         "
            f"{report.final_model_artifact.relative_path} / sha256={report.final_model_artifact.sha256}"
        )
    if report.final_prediction_artifact is not None:
        print(
            "  final prediction artifact:    "
            f"rows={report.final_prediction_artifact.row_count:,} / "
            f"sha256={report.final_prediction_artifact.sha256}"
        )
    if report.production_manifest_path is not None:
        print(f"  production manifest:          {report.production_manifest_path}")
    print(f"  wall time:                    {report.wall_seconds:.3f}s")
    print(f"  report:                       {report.report_path}")
    print(f"  result:                       {'ACCEPTED' if report.accepted else 'REJECTED'}")
    return 0 if report.accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
