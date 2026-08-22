from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from packages.core.settings import load_settings
from packages.portfolio.phase13_closeout import Phase13Closeout


def _correlation_evidence(path: Path | None) -> dict[str, float] | None:
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("correlation evidence must be a JSON object keyed by instrument_id")
    return {str(key): float(value) for key, value in payload.items()}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the complete ATLAS Phase 13 context/instrument/geometry/portfolio-risk closeout."
    )
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=None,
        help="Optional accepted Phase 12 date (YYYY-MM-DD). Defaults to accepted Phase 12 closeout.",
    )
    parser.add_argument(
        "--portfolio-snapshot",
        type=Path,
        default=None,
        help="Optional broker-neutral portfolio snapshot JSON. Not required for the zero-case acceptance path.",
    )
    parser.add_argument(
        "--correlation-evidence",
        type=Path,
        default=None,
        help="Optional JSON mapping instrument_id to identity-safe max absolute return correlation.",
    )
    args = parser.parse_args()
    settings = load_settings()
    correlations = _correlation_evidence(args.correlation_evidence)

    print("ATLAS Phase 13 Context, Instrument, Geometry, and Portfolio Risk Closeout")
    print(
        "  safety: accepted Phase 12 cases only; equity primary; reference geometry only; "
        "broker-neutral proposed sizing; no production ML writes; no broker/order writes"
    )
    closeout = Phase13Closeout(settings).run(
        as_of_date=args.as_of,
        portfolio_snapshot_path=args.portfolio_snapshot,
        correlation_evidence=correlations,
        progress=lambda message: print(f"  {message}"),
    )
    if closeout.get("pass") is not True:
        raise SystemExit("  Phase 13 closeout: FAIL")

    print("  case-plan disposition:")
    print(f"    as-of:                       {closeout['as_of_date']}")
    print(f"    accepted Phase 12 cases:     {int(closeout['phase12_case_count']):,}")
    print(f"    Phase 13 case files:          {int(closeout['case_file_count']):,}")
    print(f"    Phase 14 review-ready cases:  {int(closeout['phase14_review_ready_count']):,}")
    print(f"    provider initialized:         {closeout['provider_initialized']}")
    print(f"    news provider calls:          {int(closeout['news_provider_calls']):,}")
    print(f"    option-chain provider calls:  {int(closeout['option_chain_provider_calls']):,}")
    print(f"    portfolio snapshot reads:     {int(closeout['portfolio_snapshot_reads']):,}")
    print(f"    zero-case no-op:               {closeout['zero_case_noop']}")

    print("  independent final checks:")
    for name, value in closeout["checks"].items():
        print(f"    {name}: {value}")

    disposition = closeout["final_disposition"]
    print("  final disposition:")
    print(f"    Phase 13 accepted:                      {disposition['phase13_accepted']}")
    print(f"    case files are orders:                  {not disposition['case_files_are_plans_not_orders']}")
    print(
        "    equity primary until option RV model:  "
        f"{disposition['equity_primary_until_option_relative_value_model_accepted']}"
    )
    print(
        "    reference entry is assumed fill:       "
        f"{not disposition['reference_entry_is_not_assumed_fill']}"
    )
    print(
        "    missing evidence is guessed:           "
        f"{not disposition['missing_context_or_portfolio_evidence_is_not_guessed']}"
    )
    print(f"    next phase:                             {disposition['next_phase']}")
    print(f"  final acceptance report: {closeout['report_path']}")
    print("  Phase 13 Context, Instrument, Geometry, and Portfolio Risk: PASS")
    print("  Phase 14 Independent AI Audit and Alerting: NEXT")


if __name__ == "__main__":
    main()
