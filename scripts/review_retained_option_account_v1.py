from __future__ import annotations

"""Inspect the original V2 account/scenario; never rerun the simulation."""

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import ConfigurationError, load_settings
from packages.simulation.retained_option_account_review_v1 import (
    DEFAULT_BINDING, review_retained_option_account,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ATLAS retained option account ledger/evidence review")
    parser.add_argument("--save-report", action="store_true")
    args = parser.parse_args(argv)
    print("ATLAS RETAINED OPTION ACCOUNT REVIEW V1", flush=True)
    print("  Two named retained JSON reports; zero provider requests, source scans and simulations.", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        print(f"  account: {DEFAULT_BINDING.replay_relative_path}", flush=True)
        print(f"  scenario: {DEFAULT_BINDING.scenario_relative_path}", flush=True)
        print("  verifying signatures, populations, cash/fees and unresolved memberships", flush=True)
        report = review_retained_option_account(settings)
        print(f"  original / admitted / completed / unresolved: {report['original_cases']:,} / "
              f"{report['admitted']:,} / {report['completed']:,} / {report['unresolved']:,}", flush=True)
        print(f"  recorded cash: ${report['cash']}; modeled realized P&L: ${report['modeled_realized_pnl']}", flush=True)
        print(f"  open committed entry cash (including fees): ${report['committed_open_entry_cash_including_fees']}", flush=True)
        print(f"  reserved exit fees: ${report['reserved_exit_fees']}; cash after fee reserve: "
              f"${report['cash_available_after_exit_fee_reserve']}", flush=True)
        print("  equity / total return / terminal valuation clock: UNKNOWN", flush=True)
        print(f"  unresolved reasons: {report['unresolved_by_reason']}", flush=True)
        print(f"  unresolved entry years: {report['unresolved_by_entry_year']}", flush=True)
        for row in report["unresolved_positions"]:
            print(f"    {row['option_symbol']} | {row['contracts']} contracts | entry {row['entry_at_utc']} | "
                  f"expiry encoded {row['expiration']} | {row['source_gap_reason']} | "
                  f"committed ${row['committed_entry_cash_including_fee']} / fees ${row['reserved_exit_fee']}", flush=True)
        print("  evidence demand: exact deliverables/adjustments, original exit-clock source, explicit terminal clock, "
              "exercise/expiry outcome, historical settlement cash/share movements, and surviving-position marks", flush=True)
        print("  original V2 remains closed; this review creates no retry policy, settlement or capital release.", flush=True)
        if args.save_report:
            directory = settings.resolved_path("data/research/retained_option_account_review_v1")
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            target = directory / f"{stamp}_{uuid.uuid4().hex[:8]}.json"
            atomic_write_text(target, json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", fsync=True)
            print(f"  saved report: {target}", flush=True)
        print(f"  replay fingerprint: {report['source_replay_fingerprint']}", flush=True)
        print(f"  scenario fingerprint: {report['source_scenario_fingerprint']}", flush=True)
        print(f"  COMPLETE: {report['status']}; report fingerprint: {report['report_fingerprint']}", flush=True)
        return 0
    except (ConfigurationError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"  BLOCKED: {exc}", flush=True)
        print("  Original evidence retained. No source rebuild, newer-run fallback or paid request was attempted.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
