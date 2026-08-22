from __future__ import annotations

import argparse

from packages.core.settings import load_settings
from packages.ml.historical_backfill_closeout import HistoricalBackfillCloseout
from packages.ml.historical_backfill_model_benchmark import HistoricalBackfillModelBenchmark
from packages.ml.historical_backfill_model_benchmark_validation import (
    HistoricalBackfillModelBenchmarkValidator,
)
from packages.ml.historical_backfill_model_evaluation_design import (
    HistoricalBackfillModelEvaluationDesign,
)


def _print_aggregate(label: str, item: dict[str, object]) -> None:
    print(
        f"    {label}: logloss={float(item['weighted_log_loss']):.6f} "
        f"brier={float(item['weighted_multiclass_brier']):.6f} "
        f"accuracy={float(item['weighted_accuracy']):.6f} "
        f"auc={float(item['weighted_macro_ovr_auc']):.6f} "
        f"ece={float(item['weighted_macro_ece']):.6f} rows={int(item['test_rows']):,}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the complete ATLAS historical-extension model evaluation and closeout batch."
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Skip model fitting and revalidate existing benchmark artifacts before closeout.",
    )
    args = parser.parse_args()
    settings = load_settings()

    print("ATLAS Historical Extension Phase-Level Closeout")
    print("  safety: isolated historical evidence only; no production ML replacement; no broker writes")

    design = HistoricalBackfillModelEvaluationDesign(settings).run()
    if design.get("pass") is not True:
        raise SystemExit("  accepted evaluation design: FAIL")
    print(f"  accepted design fingerprint: {design['source_fingerprint']}")

    benchmark_runner = HistoricalBackfillModelBenchmark(settings)
    if args.validate_only:
        print("  benchmark: using existing persisted benchmark (--validate-only)")
    else:
        print("  benchmark: running paired fixed-budget B vs C plus nested-history sensitivity")
        benchmark_runner.run(progress=lambda message: print(f"    {message}"))

    validation = HistoricalBackfillModelBenchmarkValidator(settings).run()
    if validation.get("pass") is not True:
        raise SystemExit("  independent benchmark validation: FAIL")
    print(f"  independent validation fingerprint: {validation['source_fingerprint']}")

    closeout = HistoricalBackfillCloseout(settings).run()
    if closeout.get("pass") is not True:
        raise SystemExit("  historical extension final acceptance: FAIL")

    aggregates = dict(closeout["aggregates"])
    print("  aggregate paired evidence:")
    _print_aggregate("B fixed 1M", dict(aggregates["B_FIXED_1M"]))
    _print_aggregate("C fixed 1M", dict(aggregates["C_FIXED_1M"]))
    _print_aggregate("C nested", dict(aggregates["C_NESTED_B_PLUS_PRESEAM"]))

    selection = dict(closeout["primary_selection"])
    nested = dict(closeout["nested_history_attribution"])
    disposition = dict(closeout["final_disposition"])
    print("  primary fixed-budget comparison:")
    print(f"    C-B logloss delta: {float(selection['C_minus_B_log_loss']):+.9f}")
    print(f"    C-B brier delta:   {float(selection['C_minus_B_multiclass_brier']):+.9f}")
    print(f"    C improves both:   {selection['C_improves_both_primary_scores']}")
    print(f"    decision:          {selection['decision']}")
    print("  nested-history attribution only:")
    print(f"    nested-B logloss delta: {float(nested['nested_minus_B_log_loss']):+.9f}")
    print(f"    nested-B brier delta:   {float(nested['nested_minus_B_multiclass_brier']):+.9f}")
    print(f"    can promote model:      {nested['can_promote_model']}")
    print("  production disposition:")
    print(f"    Phase 10 model remains authoritative: {disposition['accepted_phase10_production_model_remains_authoritative']}")
    print(f"    accepted model id:                  {disposition['accepted_phase10_model_id']}")
    print(f"    historical C challenger evidence:   {disposition['historical_C_challenger_evidence_registered']}")
    print(f"    historical C is production:         {disposition['historical_C_challenger_is_production']}")
    print(f"    next phase:                          {disposition['next_phase']}")
    print("  final checks:")
    for name, value in dict(closeout["checks"]).items():
        print(f"    {name}: {value}")
    print(f"  final acceptance report: {closeout['report_path']}")
    print("  Historical extension phase-level closeout: PASS")
    print("  Phase 11 Strategy Evaluation and Regime Routing: NEXT")


if __name__ == "__main__":
    main()
