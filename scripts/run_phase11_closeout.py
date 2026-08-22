from __future__ import annotations

import argparse
from datetime import date

from packages.backtesting.phase11_closeout import Phase11Closeout
from packages.core.settings import load_settings


def _fmt(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):+.6f}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the complete ATLAS Phase 11 strategy evaluation/regime-routing closeout."
    )
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=None,
        help="Optional current-candidate session (YYYY-MM-DD). Defaults to latest complete upstream session.",
    )
    args = parser.parse_args()
    settings = load_settings()

    print("ATLAS Phase 11 Strategy Evaluation and Regime Routing Closeout")
    print(
        "  safety: research/setup evidence only; accepted Phase 10 ML remains authoritative; "
        "no trade geometry; no production ML writes; no broker writes"
    )

    closeout = Phase11Closeout(settings).run(
        as_of_date=args.as_of,
        progress=lambda message: print(f"  {message}"),
    )
    if closeout.get("pass") is not True:
        raise SystemExit("  Phase 11 closeout: FAIL")

    print("  historical strategy support (10 bps development + chronological halves):")
    for item in closeout["strategy_support_evidence"]:
        print(
            f"    {item['strategy_id']}: {item['status']} rows={int(item['development_rows']):,} "
            f"dev={_fmt(item['development_mean_return'])} "
            f"first={_fmt(item['first_half_mean_return'])} "
            f"second={_fmt(item['second_half_mean_return'])}"
        )

    print("  support disposition:")
    print(f"    status counts: {closeout['support_status_counts']}")
    print(f"    supported strategies: {closeout['supported_strategy_ids']}")
    print(f"    protected slice role: {closeout['protected_holdout_role']}")

    print("  current candidate materialization:")
    print(f"    as-of:                         {closeout['current_candidate_as_of']}")
    print(
        f"    WARM/HOT directional cases:    "
        f"{int(closeout['considered_warm_hot_directional']):,}"
    )
    print(f"    promoted research candidates: {int(closeout['promoted_count']):,}")
    print(f"    promoted tickers:              {closeout['promoted_tickers']}")
    print(f"    ranking policy:                {closeout['candidate_ranking_policy']}")
    print(f"    sector context:                {closeout['sector_context_policy']}")

    print("  independent final checks:")
    for name, value in closeout["checks"].items():
        print(f"    {name}: {value}")

    disposition = closeout["final_disposition"]
    print("  final disposition:")
    print(f"    Phase 11 accepted:                     {disposition['phase11_accepted']}")
    print(
        "    Phase 10 model remains authoritative: "
        f"{disposition['accepted_phase10_model_remains_authoritative']}"
    )
    print(
        "    promoted candidates are orders:       "
        f"{not disposition['promoted_candidates_are_research_cases_not_orders']}"
    )
    print(f"    next phase:                            {disposition['next_phase']}")
    print(f"  final acceptance report: {closeout['report_path']}")
    print("  Phase 11 Strategy Evaluation and Regime Routing: PASS")
    print("  Phase 12 Deep Candidate Research: NEXT")


if __name__ == "__main__":
    main()
