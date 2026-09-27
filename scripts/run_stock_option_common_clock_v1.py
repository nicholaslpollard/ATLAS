from __future__ import annotations

"""Offline same-clock research scenario runner for already prepared case evidence."""

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.simulation.stock_option_common_clock_v1 import (
    CommonClockScenarioError, SameClockCase, TimedMark, compare_cases,
)


def _mark(value: object) -> TimedMark | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise CommonClockScenarioError("mark must be a JSON object or null")
    return TimedMark(
        session=date.fromisoformat(value["session"]),
        observed_at_utc=datetime.fromisoformat(value["observed_at_utc"]),
        per_share=value["per_share"],
        source_sha256=value["source_sha256"],
        source_kind=value["source_kind"],
    )


def _case(value: object) -> SameClockCase:
    if not isinstance(value, dict):
        raise CommonClockScenarioError("case must be a JSON object")
    return SameClockCase(
        case_id=value["case_id"], year=value["year"], ticker=value["ticker"],
        original_signal_utc=datetime.fromisoformat(value["original_signal_utc"]),
        selected_option_at_utc=datetime.fromisoformat(value["selected_option_at_utc"]),
        news_cutoff_utc=datetime.fromisoformat(value["news_cutoff_utc"]),
        prior_24h_article_count=value["prior_24h_article_count"],
        prior_7d_article_count=value["prior_7d_article_count"],
        option_symbol=value["option_symbol"],
        option_expiration=(date.fromisoformat(value["option_expiration"])
                           if value["option_expiration"] else None),
        option_right=value["option_right"],
        option_multiplier=value["option_multiplier"],
        standard_deliverable_verified=value["standard_deliverable_verified"],
        stock_raw_price_basis_verified=value["stock_raw_price_basis_verified"],
        stock_entry=_mark(value["stock_entry"]), stock_exit=_mark(value["stock_exit"]),
        option_entry_ask=_mark(value["option_entry_ask"]),
        option_exit_bid=_mark(value["option_exit_bid"]),
        option_reference_status=value["option_reference_status"],
        source_lineage_fingerprint=value["source_lineage_fingerprint"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="ATLAS local same-clock source scenario")
    parser.add_argument("--cases", required=True, type=Path,
                        help="Prepared JSON containing a cases array; no network fallback")
    parser.add_argument("--allocation", type=float, default=10000.0)
    args = parser.parse_args()
    print("ATLAS Stock vs Option Same-Clock Reference Scenario / OFFLINE", flush=True)
    try:
        if not args.cases.is_file() or args.cases.stat().st_size > 128 * 1024 * 1024:
            raise CommonClockScenarioError("prepared cases file missing or oversized")
        payload = json.loads(args.cases.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
            raise CommonClockScenarioError("prepared cases array is required")
        if not 1 <= len(payload["cases"]) <= 100000:
            raise CommonClockScenarioError("case count must remain 1..100000")
        result = compare_cases([_case(value) for value in payload["cases"]],
                               allocation=args.allocation)
        print(f"  full signal denominator: {result['full_signal_denominator']}", flush=True)
        print(f"  same-clock observed-reference pairs: {result['paired_reference_count']}",
              flush=True)
        for year, row in result["by_calendar_year"].items():
            print(f"  {year}: original cases={row['full_signal_denominator']} "
                  f"paired={row['paired_eod_reference_count']} "
                  f"source statuses={row['option_statuses']}", flush=True)
        print(f"  reference fingerprint: {result['report_fingerprint']}", flush=True)
        print("  NO fill, account-level return, qualifying PAPER, LIVE or promotion; "
              "stock EOD marks and option ask/bid are illustrative research references.",
              flush=True)
        print("  provider requests: 0", flush=True)
        return 0
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"COMMON-CLOCK SCENARIO STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  No provider request or alternative contract fallback.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
