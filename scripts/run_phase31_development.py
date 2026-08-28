from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase31_development import (
    Phase31DevelopmentError,
    Phase31DevelopmentStudy,
)
from packages.backtesting.phase31_policy import (
    PHASE31_CANDIDATES,
    PHASE31_MULTIPLE_TESTING_METHOD,
    PHASE31_PRIMARY_COST_BPS,
    PHASE31_STRESS_COST_BPS,
    phase31_policy_fingerprint,
)
from packages.backtesting.phase31_predictor_evidence import (
    PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_SHA256,
    PHASE31_PREDICTOR_EVIDENCE_PROTECTED_SHA256,
)
from packages.core.settings import load_settings


def _fmt(value: object) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.8f}"
    return str(value)


def main() -> int:
    print("ATLAS Phase 31 — Development-Only Form-4 Performance Evaluation")
    print(f"Frozen scientific policy fingerprint: {phase31_policy_fingerprint()}")
    print(f"Scientific hypotheses: FROZEN ({len(PHASE31_CANDIDATES)} total)")
    print(
        "Frozen predictor SHA256: "
        f"development={PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_SHA256}"
    )
    print(
        "Protected predictor SHA256 (hash binding only; rows not parsed): "
        f"{PHASE31_PREDICTOR_EVIDENCE_PROTECTED_SHA256}"
    )
    print("Outcome: decision-session OPEN -> T+20 CLOSE; SPY-relative primary")
    print(
        f"Costs: primary={PHASE31_PRIMARY_COST_BPS:g} bps; "
        f"stress={PHASE31_STRESS_COST_BPS:g} bps"
    )
    print(f"Multiple testing: {PHASE31_MULTIPLE_TESTING_METHOD}")
    print("Development market outcomes: AUTHORIZED / READ IN THIS STEP")
    print("Protected candidate rows/returns: FORBIDDEN / UNREAD")
    print("Provider/broker/order/PAPER/LIVE/automation: DISABLED")
    print()

    settings = load_settings()
    try:
        report = Phase31DevelopmentStudy(settings).run()
    except (Phase31DevelopmentError, OSError, ValueError) as exc:
        print("Phase 31 development-only study: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print(
            "Protected candidate/return evidence was not read and no trading authority was granted."
        )
        return 2

    print("Phase 31 development-only study: PASS")
    print(
        "Development predictor rows read / usable outcome rows: "
        f"{report['development_target_rows_read']} / "
        f"{report['development_usable_outcome_rows']}"
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
    for candidate in PHASE31_CANDIDATES:
        candidate_id = candidate.candidate_id
        metrics = selection_metrics[candidate_id]
        checks = selection_checks[candidate_id]
        failed = [name for name, passed in checks.items() if not passed]
        holm_row = holm[candidate_id]
        print(
            f"  {candidate_id}: rows={metrics['raw_rows']} "
            f"sessions={metrics['signal_sessions']} "
            f"tickers={metrics['unique_tickers']} "
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
                f"tickers={metrics['unique_tickers']} "
                f"mean10={_fmt(metrics['primary_mean_return'])} "
                f"unhedged10={_fmt(metrics['unhedged_primary_mean_return'])} "
                f"lcb={_fmt(metrics['primary_lcb'])} "
                f"checks={'PASS' if not failed else 'FAIL[' + ','.join(failed) + ']'}"
            )
    else:
        print("Internal-validation results: none (no selection winner qualified)")

    print(f"Frozen finalists: {report['finalist_ids']}")
    print(f"Protected artifact hash reads: {report['protected_artifact_hash_reads']}")
    print(f"Protected candidate rows read: {report['protected_candidate_rows_read']}")
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {report['protected_holdout_consumed']}")
    print("Provider/broker/order/PAPER/LIVE/automation activity: 0 / 0 / 0 / 0 / 0 / 0")
    print(f"Development report: {report['report_path']}")
    if report["finalist_ids"]:
        print(
            "Next scientific action: independent blindness/lineage audit, then an "
            "immutable finalist-only protected-return plan. Protected returns remain unread."
        )
    else:
        print(
            "Next scientific action: independent negative closeout. Protected returns "
            "remain unread and the holdout stays unconsumed."
        )
    print(f"Pass: {report['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
