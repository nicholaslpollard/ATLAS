from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase32_development import (
    PHASE32_TARGET_INDEPENDENT_ACCEPTANCE_FINGERPRINT,
    Phase32DevelopmentError,
    Phase32DevelopmentStudy,
)
from packages.backtesting.phase32_policy import (
    PHASE32_CANDIDATES,
    PHASE32_MULTIPLE_TESTING_METHOD,
    PHASE32_PRIMARY_COST_BPS,
    PHASE32_STRESS_COST_BPS,
    phase32_policy_fingerprint,
)
from packages.backtesting.phase32_predictor_acceptance import (
    PHASE32_TARGET_ACQUISITION_FILING_ENTITY_SHA256,
    PHASE32_TARGET_ACQUISITION_PREDICTOR_SHA256,
)
from packages.core.settings import load_settings


def _fmt(value: object) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.8f}"
    return str(value)


def _progress(message: str) -> None:
    print(f"Phase32 development: {message}")


def main() -> int:
    print("ATLAS Phase 32 — Development-Only SEC 8-K Performance Evaluation")
    print(f"Frozen scientific policy fingerprint: {phase32_policy_fingerprint()}")
    print(f"Scientific hypotheses: FROZEN ({len(PHASE32_CANDIDATES)} total)")
    print(f"Independent predictor/source acceptance: {PHASE32_TARGET_INDEPENDENT_ACCEPTANCE_FINGERPRINT}")
    print(f"Frozen predictor SHA-256: {PHASE32_TARGET_ACQUISITION_PREDICTOR_SHA256}")
    print(f"Frozen filing-entity SHA-256: {PHASE32_TARGET_ACQUISITION_FILING_ENTITY_SHA256}")
    print("Outcome: decision-session OPEN -> T+5 CLOSE; SPY-relative primary")
    print(f"Costs: primary={PHASE32_PRIMARY_COST_BPS:g} bps; stress={PHASE32_STRESS_COST_BPS:g} bps")
    print(f"Multiple testing: {PHASE32_MULTIPLE_TESTING_METHOD}")
    print("Development market outcomes: AUTHORIZED / READ IN THIS STEP")
    print("Protected predictor metadata: ALLOWED by frozen policy / source-only")
    print("Protected stock/SPY returns: FORBIDDEN / UNREAD")
    print("Provider network / broker / order / PAPER / LIVE / automation: DISABLED")
    print()

    try:
        report = Phase32DevelopmentStudy(load_settings(), progress_callback=_progress).run()
    except (Phase32DevelopmentError, OSError, ValueError) as exc:
        print("Phase 32 development-only study: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("Stop here. Do not open protected returns or alter the frozen scientific policy.")
        return 2

    print()
    print("Phase 32 development-only study: PASS")
    print(
        "Development predictor rows read / usable outcome rows: "
        f"{report['development_target_rows_read']} / {report['development_usable_outcome_rows']}"
    )
    exclusions = report["outcome_path_exclusions"]
    print(
        "Outcome path exclusions: "
        f"missing_exact_stock_path={exclusions['exact_stock_path_missing_rows']} "
        f"split_crossing={exclusions['split_crossing_censored_rows']}"
    )
    states = report["state_diagnostics"]
    print(
        "Prior-state diagnostics: "
        f"market_missing={states['prior_market_state_missing_rows']} "
        f"ticker_missing={states['prior_ticker_state_missing_rows']}"
    )
    boundaries = report["boundaries"]
    print(
        "Chronology: "
        f"selection={boundaries['selection_start']}..{boundaries['selection_end']} "
        f"purge={','.join(boundaries['purge_sessions'])} "
        f"internal={boundaries['internal_start']}..{boundaries['internal_end']}"
    )
    print()
    print("Selection results:")
    selection_metrics = report["selection_metrics"]
    selection_checks = report["selection_checks"]
    holm = report["holm_bonferroni"]
    for candidate in PHASE32_CANDIDATES:
        candidate_id = candidate.candidate_id
        metrics = selection_metrics[candidate_id]
        checks = selection_checks[candidate_id]
        failed = [name for name, passed in checks.items() if not passed]
        holm_row = holm[candidate_id]
        print(
            f"  {candidate_id}: rows={metrics['raw_rows']} "
            f"sessions={metrics['signal_sessions']} "
            f"instruments={metrics['unique_instruments']} "
            f"mean10={_fmt(metrics['primary_mean_return'])} "
            f"unhedged10={_fmt(metrics['unhedged_primary_mean_return'])} "
            f"lcb={_fmt(metrics['primary_lcb'])} "
            f"p={_fmt(metrics['primary_bootstrap_p_value'])} "
            f"holm_reject={holm_row['rejected_null']} "
            f"checks={'PASS' if not failed else 'FAIL[' + ','.join(failed) + ']'}"
        )

    print(f"Selection survivors: {report['selection_survivor_ids']}")
    print(f"Selection winners: {report['selection_winner_ids']}")
    internal_metrics = report["internal_metrics"]
    internal_checks = report["internal_checks"]
    if internal_metrics:
        print("Internal-validation results:")
        for candidate_id in report["selection_winner_ids"]:
            metrics = internal_metrics[candidate_id]
            checks = internal_checks[candidate_id]
            failed = [name for name, passed in checks.items() if not passed]
            print(
                f"  {candidate_id}: rows={metrics['raw_rows']} "
                f"sessions={metrics['signal_sessions']} "
                f"instruments={metrics['unique_instruments']} "
                f"mean10={_fmt(metrics['primary_mean_return'])} "
                f"unhedged10={_fmt(metrics['unhedged_primary_mean_return'])} "
                f"lcb={_fmt(metrics['primary_lcb'])} "
                f"checks={'PASS' if not failed else 'FAIL[' + ','.join(failed) + ']'}"
            )
    else:
        print("Internal-validation results: none (no selection winner qualified)")

    print(f"Frozen finalists: {report['finalist_ids']}")
    print(
        "Protected predictor rows observed for partition validation: "
        f"{report['protected_predictor_rows_read_for_partition_validation']}"
    )
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {report['protected_holdout_consumed']}")
    print("Provider network/broker/order/PAPER/LIVE/automation activity: 0 / 0 / 0 / 0 / 0 / 0")
    print(f"Development report: {report['report_path']}")
    if report["finalist_ids"]:
        print(
            "Next scientific action: independent blindness/lineage audit, then an immutable "
            "finalist-only protected-return plan. Protected returns remain unread."
        )
    else:
        print(
            "Next scientific action: independent negative closeout. Protected returns remain unread "
            "and the holdout stays unconsumed."
        )
    print(f"Pass: {report['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
