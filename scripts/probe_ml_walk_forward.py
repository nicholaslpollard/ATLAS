from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.ml.walk_forward_probe import MLWalkForwardProbe


def main() -> int:
    settings = load_settings(PROJECT_ROOT)
    report = MLWalkForwardProbe(settings).run()

    print("ATLAS Phase 10 Gate 7 Walk-Forward / Purge Probe")
    print(f"  contract:                    {report.contract_version}")
    print(f"  dataset id:                  {report.dataset_id}")
    print(f"  dataset lineage:             {report.dataset_lineage_sha256}")
    print(f"  probe status:                {report.probe_status}")
    print(f"  split unit:                  {report.split_unit}")
    print(f"  random row split:            {report.random_row_split_allowed}")
    print(f"  label horizon:               {report.label_horizon_sessions} sessions")
    print(f"  boundary purge:              {report.purge_sessions} sessions")
    print(f"  additional embargo:          {report.additional_embargo_sessions} sessions")
    print(
        "  dataset sessions/rows:       "
        f"{report.dataset_sessions:,} / {report.dataset_rows:,}"
    )
    print(
        "  dataset observation range:   "
        f"{report.dataset_first_session} -> {report.dataset_last_session}"
    )
    print(
        "  final untouched holdout:      "
        f"{report.final_holdout_start} -> {report.final_holdout_end} "
        f"({report.final_holdout_sessions} sessions / {report.final_holdout_rows:,} rows)"
    )
    print(
        "  holdout classes:              "
        f"DOWN={report.final_holdout_down_fraction:.2%} "
        f"NEUTRAL={report.final_holdout_neutral_fraction:.2%} "
        f"UP={report.final_holdout_up_fraction:.2%}"
    )
    print("  candidate evidence:")
    for candidate in report.candidates:
        print(
            f"    {candidate.name}: train>={candidate.minimum_train_sessions} "
            f"val={candidate.validation_sessions} test={candidate.test_sessions} "
            f"step={candidate.step_sessions} sessions"
        )
        print(
            f"      folds={candidate.fold_count} "
            f"test={candidate.first_test_date} -> {candidate.last_test_date} "
            f"distinct-test-sessions={candidate.distinct_test_sessions:,} "
            f"test-rows={candidate.total_test_rows:,}"
        )
        print(
            f"      train-row range={candidate.minimum_train_rows:,} -> "
            f"{candidate.maximum_train_rows:,}"
        )
        print(
            "      test class-fraction ranges: "
            f"DOWN={candidate.test_down_fraction_range:.2%} "
            f"NEUTRAL={candidate.test_neutral_fraction_range:.2%} "
            f"UP={candidate.test_up_fraction_range:.2%}"
        )
        for fold in candidate.folds:
            print(
                f"        fold {fold.fold_index}: "
                f"train={fold.train_start}->{fold.train_end} ({fold.train_sessions} sessions / {fold.train_rows:,}) | "
                f"val={fold.validation_start}->{fold.validation_end} ({fold.validation_rows:,}) | "
                f"test={fold.test_start}->{fold.test_end} ({fold.test_rows:,}) "
                f"D/N/U={fold.test_down_fraction:.2%}/{fold.test_neutral_fraction:.2%}/{fold.test_up_fraction:.2%}"
            )
    print(f"  walk-forward policy:         {'LOCKED' if report.walk_forward_policy_locked else 'NOT YET LOCKED'}")
    print(f"  wall time:                   {report.wall_seconds:.3f}s")
    print(f"  report:                      {report.report_path}")
    print("  result:                      EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
