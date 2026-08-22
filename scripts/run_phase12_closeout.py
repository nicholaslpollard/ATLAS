from __future__ import annotations

import argparse
from datetime import date

from packages.analogues.phase12_closeout import Phase12Closeout
from packages.core.settings import load_settings


def _fmt(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):+.6f}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the complete ATLAS Phase 12 promoted-only deep candidate research closeout."
    )
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=None,
        help="Optional accepted Phase 11 candidate session (YYYY-MM-DD).",
    )
    args = parser.parse_args()
    settings = load_settings()

    print("ATLAS Phase 12 Deep Candidate Research Closeout")
    print(
        "  safety: promoted-only research evidence; no threshold relaxation; no trade geometry; "
        "no production ML writes; no broker writes"
    )
    closeout = Phase12Closeout(settings).run(
        as_of_date=args.as_of,
        progress=lambda message: print(f"  {message}"),
    )
    if closeout.get("pass") is not True:
        raise SystemExit("  Phase 12 closeout: FAIL")

    print("  research disposition:")
    print(f"    as-of:                      {closeout['as_of_date']}")
    print(f"    Phase 11 promoted inputs:   {int(closeout['phase11_promoted_count']):,}")
    print(f"    deep research cases:        {int(closeout['research_case_count']):,}")
    print(f"    complete research cases:    {int(closeout['research_complete_count']):,}")
    print(f"    limited research cases:     {int(closeout['research_limited_count']):,}")
    print(f"    historical source accessed: {closeout['historical_source_accessed']}")
    print(f"    zero-candidate no-op:        {closeout['zero_candidate_noop']}")

    print("  independent final checks:")
    for name, value in closeout["checks"].items():
        print(f"    {name}: {value}")

    disposition = closeout["final_disposition"]
    print("  final disposition:")
    print(f"    Phase 12 accepted:                       {disposition['phase12_accepted']}")
    print(
        "    Phase 11 candidates remain orders:      "
        f"{not disposition['phase11_promoted_candidates_remain_research_cases_not_orders']}"
    )
    print(
        "    no-candidate threshold relaxation:      "
        f"{not disposition['no_candidates_does_not_trigger_threshold_relaxation']}"
    )
    print(f"    next phase:                              {disposition['next_phase']}")
    print(f"  final acceptance report: {closeout['report_path']}")
    print("  Phase 12 Deep Candidate Research: PASS")
    print("  Phase 13 Context, Instrument, Geometry, and Portfolio Risk: NEXT")


if __name__ == "__main__":
    main()
