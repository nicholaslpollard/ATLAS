from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase30_development import (
    Phase30DevelopmentError,
    Phase30DevelopmentStudy,
)
from packages.backtesting.phase30_policy import (
    PHASE30_CANDIDATES,
    PHASE30_CURRENT_REACTION_FIELD,
    PHASE30_MIN_DIRECTION_ROWS_PER_SESSION,
    PHASE30_MULTIPLE_TESTING_METHOD,
    PHASE30_SIGNAL_TAIL_FRACTION,
    phase30_policy_fingerprint,
)
from packages.core.settings import load_settings


def _fmt(value: object) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.8f}"
    return str(value)


def main() -> int:
    print("ATLAS Phase 30 — Development-Only News-Shock Selection + Internal Validation")
    print(f"Frozen Phase30 policy fingerprint: {phase30_policy_fingerprint()}")
    print(f"Scientific hypotheses: FROZEN ({len(PHASE30_CANDIDATES)} total)")
    print(f"Current reaction field: {PHASE30_CURRENT_REACTION_FIELD}")
    print(
        "Frozen signal selection: "
        f"minimum {PHASE30_MIN_DIRECTION_ROWS_PER_SESSION} rows per session/direction; "
        f"top {PHASE30_SIGNAL_TAIL_FRACTION:.0%} news-surprise tail"
    )
    print(f"Multiple testing: {PHASE30_MULTIPLE_TESTING_METHOD}")
    print("Development outcomes: AUTHORIZED / READ IN THIS STEP")
    print("Protected candidates/returns: FORBIDDEN / UNREAD")
    print("Broker/order/PAPER/LIVE activity: DISABLED")
    print()

    settings = load_settings()
    try:
        report = Phase30DevelopmentStudy(settings).run()
    except (Phase30DevelopmentError, OSError, ValueError) as exc:
        print("Phase 30 development-only study: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("Protected candidate/return evidence was not read and no trading authority was granted.")
        return 2

    print("Phase 30 development-only study: PASS")
    print(
        "Joined development population rows/tickers/sessions: "
        f"{report['development_population_rows']} / "
        f"{report['development_population_tickers']} / "
        f"{report['development_population_sessions']}"
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
    for candidate in PHASE30_CANDIDATES:
        candidate_id = candidate.candidate_id
        metrics = selection_metrics[candidate_id]
        checks = selection_checks[candidate_id]
        failed = [name for name, passed in checks.items() if not passed]
        holm_row = holm[candidate_id]
        print(
            f"  {candidate_id}: rows={metrics['raw_rows']} "
            f"sessions={metrics['signal_sessions']} "
            f"mean10={_fmt(metrics['primary_mean_return'])} "
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
                f"mean10={_fmt(metrics['primary_mean_return'])} "
                f"lcb={_fmt(metrics['primary_lcb'])} "
                f"checks={'PASS' if not failed else 'FAIL[' + ','.join(failed) + ']'}"
            )
    else:
        print("Internal-validation results: none (no selection winner qualified)")

    print(f"Frozen finalists: {report['finalist_ids']}")
    print(f"Development target rows read: {report['development_target_rows_read']}")
    print(f"Protected candidate rows read: {report['protected_candidate_rows_read']}")
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {report['protected_holdout_consumed']}")
    print("Provider/broker/order/PAPER/LIVE activity: 0 / 0 / 0 / 0 / 0")
    print(f"Development report: {report['report_path']}")
    if report["finalist_ids"]:
        print(
            "Next scientific action: independent blindness audit and immutable finalist-only "
            "protected-read plan. Protected returns remain unread in this step."
        )
    else:
        print(
            "Next scientific action: independent reconstruction/closeout as accepted negative; "
            "protected returns remain unread and the holdout stays unconsumed."
        )
    print(f"Pass: {report['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
