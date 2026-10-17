from __future__ import annotations

"""One-run 33-event SPY historical publication evidence *demand* inventory."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import load_settings
from packages.data.options_native_spy_publication_evidence_demand_v1 import (
    build_spy_publication_evidence_demand,
)

MAX_REPORT_BYTES = 384 * 1024


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline 33-event SPY publication evidence queue")
    parser.add_argument("--save-report", action="store_true")
    args = parser.parse_args(argv)
    print("ATLAS SPY 33-EVENT HISTORICAL PUBLICATION EVIDENCE DEMAND V1", flush=True)
    print("  Three pinned JSON reports only: State Street 33-event cash audit, 411-week prices and 407-week variance.", flush=True)
    print("  No source/price/option/news scans, downloads, broker/provider calls, simulations or protected outcomes.", flush=True)
    print("  Historical articles listed as unretained research leads, NOT accepted PIT timestamps.", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        if args.save_report:
            settings.assert_external_storage_binding("research_evidence")
        result = build_spy_publication_evidence_demand(settings)
        print(f"  issuer events requiring historical publication assessment: {result['event_count']}", flush=True)
        print(f"  publication article leads / original source receipts: {result['events_with_research_publication_lead']} / "
              f"{result['events_with_original_pit_source_receipt']}", flush=True)
        print(f"  physical-price complete weeks: {result['price_complete_cases']} / 411", flush=True)
        print(f"  retrospective dividend-exposed price-complete weeks: {result['price_complete_cases_exposed_to_dividends']}", flush=True)
        print(f"  incomplete-price weeks: {result['price_incomplete_cases']}", flush=True)
        print(f"  issuer distributions unused by frozen weekly prior windows: "
              f"{result['events_with_no_registered_lookback_usage']}", flush=True)
        for event in result["events"]:
            if event["external_historical_announcement_lead"]:
                print(f"  research lead {event['ex_date']}: "
                      f"first_decision={event['first_dependent_decision_utc']} "
                      f"lead_before_first={event['lead_displayed_earlier_than_first_relevant_decision']} "
                      f"archive_receipt=False", flush=True)
        print("  Historical event announcement/revisions, split or no-action completeness, option premiums/trading: UNQUALIFIED", flush=True)
        if args.save_report:
            target = settings.resolved_path(
                "data/research/options_native_spy_publication_evidence_demand_v1"
            ) / (result["report_fingerprint"][:16] + ".json")
            body = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
            if len(body.encode("utf-8")) > MAX_REPORT_BYTES:
                raise ValueError("33-event evidence demand report exceeds bounded size")
            if target.is_symlink() or (target.exists() and (
                target.stat().st_size > MAX_REPORT_BYTES
                or target.read_text(encoding="utf-8") != body
            )):
                raise ValueError("existing signed evidence demand differs; original preserved")
            if not target.exists():
                atomic_write_text(target, body, fsync=True)
            print(f"  saved report: {target}", flush=True)
        print(f"  COMPLETE: {result['status']} fingerprint={result['report_fingerprint']}", flush=True)
        return 0
    except (OSError, TypeError, KeyError, ValueError, ArithmeticError) as exc:
        print(f"  BLOCKED: {exc}", flush=True)
        print("  Source originals unchanged. No external download, alternative provider or backtest enabled.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
