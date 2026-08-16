from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import load_settings
from packages.instruments.continuity import IdentityContinuityReconciler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reconcile one point-in-time ticker against ATLAS snapshot and ticker-event continuity evidence."
    )
    parser.add_argument("--ticker", required=True, help="Exact provider-native ticker from the reference snapshot.")
    parser.add_argument("--date", required=True, type=date.fromisoformat, help="Reference snapshot date (YYYY-MM-DD).")
    parser.add_argument("--json-out", type=Path, default=None, help="Optional JSON report path.")
    return parser


def _fmt_to(value: date | None) -> str:
    return value.isoformat() if value is not None else "open"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = IdentityContinuityReconciler(load_settings(PROJECT_ROOT)).reconcile_ticker(args.ticker, args.date)

    print(f"ATLAS identity continuity {args.ticker} @ {args.date}")
    print(f"  instrument_id:        {report.instrument_id}")
    print(f"  status:               {report.status}")
    print(f"  continuity confirmed: {str(report.continuity_confirmed).lower()}")
    print(f"  blocking anomaly:     {str(report.blocking_anomaly).lower()}")

    print("  observed snapshot aliases:")
    for item in report.observed_tickers:
        print(
            f"    {item.ticker:12s} {item.first_observed_date} -> {item.last_observed_date} "
            f"({item.observation_count} snapshot observation{'s' if item.observation_count != 1 else ''})"
        )

    print("  authoritative provider events:")
    if not report.authoritative_events:
        print("    (none)")
    else:
        for event in report.authoritative_events:
            print(
                f"    {event.event_date}  {event.ticker:12s} "
                f"[{event.query_identifier_type}; authority={str(event.continuity_authority).lower()}]"
            )

    print("  authoritative ticker intervals [from, to):")
    if not report.authoritative_intervals:
        print("    (none)")
    else:
        for interval in report.authoritative_intervals:
            print(
                f"    {interval.ticker:12s} [{interval.valid_from_date}, "
                f"{_fmt_to(interval.valid_to_date_exclusive)})"
            )

    if report.unresolved_observed_tickers:
        print("  unresolved observed aliases: " + ", ".join(report.unresolved_observed_tickers))
    else:
        print("  unresolved observed aliases: none")

    if report.ticker_reuse_observations:
        print("  ticker-reuse observations:")
        for item in report.ticker_reuse_observations:
            print(
                f"    {item.ticker} -> other {item.other_instrument_id} "
                f"[{item.other_first_observed_date}, {item.other_last_observed_date}] "
                f"observation-range-overlap={str(item.observation_ranges_overlap).lower()}"
            )
    else:
        print("  ticker-reuse observations: none")

    if report.warnings:
        print("  warnings:")
        for warning in report.warnings:
            print(f"    - {warning}")

    if args.json_out is not None:
        atomic_write_text(args.json_out, report.model_dump_json(indent=2) + "\n")
        print(f"  JSON report:          {args.json_out.resolve()}")

    return 2 if report.blocking_anomaly else 0


if __name__ == "__main__":
    raise SystemExit(main())
