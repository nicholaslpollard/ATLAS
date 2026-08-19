from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.ml.robustness_audit import MLRobustnessAudit


def main() -> int:
    settings = load_settings(PROJECT_ROOT)
    print("ATLAS Phase 10 Gate 11 Regime / Segment Robustness Audit", flush=True)
    print("  auditing frozen raw Gate 9 OOS predictions across point-in-time-safe segments...", flush=True)
    report = MLRobustnessAudit(settings).run(progress=lambda line: print(f"  {line}", flush=True))

    print(f"  contract:                    {report.contract_version}")
    print(f"  status:                      {report.status}")
    print(f"  accepted model:              {report.accepted_model}")
    print(f"  calibration method:          {report.accepted_calibration_method}")
    print(f"  source probabilities:        {report.source_probabilities}")
    print(f"  OOS folds / rows:            {report.fold_count} / {report.total_oos_rows:,}")
    print(
        "  market context coverage:     "
        f"{report.market_context_rows:,} / {report.total_oos_rows:,} "
        f"({report.market_context_fraction:.2%})"
    )
    print(f"  unavailable segments:        {report.unavailable_segments}")
    print(f"  final holdout accessed:       {report.final_holdout_accessed}")
    print("  aggregate segment evidence:")

    current_family = None
    for item in report.aggregate_evidence:
        if item.family != current_family:
            current_family = item.family
            print(f"    [{current_family}]")
        auc = "NA" if item.weighted_macro_ovr_auc is None else f"{item.weighted_macro_ovr_auc:.6f}"
        auc_delta = "NA" if item.auc_delta_vs_global is None else f"{item.auc_delta_vs_global:+.6f}"
        print(
            f"      {item.value}: rows={item.rows:,} folds={item.fold_count} "
            f"support={item.support_status} "
            f"D/N/U={item.down_fraction:.2%}/{item.neutral_fraction:.2%}/{item.up_fraction:.2%} "
            f"logloss={item.weighted_log_loss:.6f} ({item.log_loss_delta_vs_global:+.6f}) "
            f"brier={item.weighted_multiclass_brier:.6f} ({item.brier_delta_vs_global:+.6f}) "
            f"auc={auc} ({auc_delta}) ece={item.weighted_macro_ece:.6f} "
            f"({item.ece_delta_vs_global:+.6f})"
        )

    print(f"  wall time:                   {report.wall_seconds:.3f}s")
    print(f"  report:                      {report.report_path}")
    print("  result:                      EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
