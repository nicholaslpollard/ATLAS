from __future__ import annotations

"""One-pass, zero-provider 2018-2025 SPY retrospective dividend variance grid."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import load_settings
from packages.data.options_native_spy_full_period_retrospective_dividend_variance_v1 import (
    build_full_period_retrospective_grid,
)

MAX_REPORT = 768 * 1024


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Full pilot retrospective dividend variance diagnostic")
    parser.add_argument("--save-report", action="store_true")
    args = parser.parse_args(argv)
    print("ATLAS SPY FULL-PERIOD RETROSPECTIVE DIVIDEND VARIANCE GRID V1", flush=True)
    print("  Four pinned accepted JSON reports + fixed 33-row retrospective US SPY distribution table.", flush=True)
    print("  NO historical source-unit, option, provider, broker, action-ledger or outcome scans.", flush=True)
    print("  Not an admissible PIT predictor, option-implied variance test or backtest.", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        if args.save_report:
            settings.assert_external_storage_binding("research_evidence")
        report = build_full_period_retrospective_grid(settings)
        print(f"  independent retrospective dividends / archived: 33 / {report['archive_reconciliation']['archived_event_count']}", flush=True)
        print(f"  known missing ex-dates: {report['archive_reconciliation']['known_missing_ex_dates']}", flush=True)
        print(f"  rounding-only differences: {report['archive_reconciliation']['rounded_rate_residuals']}", flush=True)
        print(f"  complete prior-window computations: {report['physically_price_complete_decisions']}/411", flush=True)
        print(f"  retrospective dividend-affected windows: {report['retrospective_dividend_touched_decisions']}", flush=True)
        print(f"  omitted 2018 dividend affected windows: {report['known_archivally_omitted_dividend_affected_decisions']}", flush=True)
        print(f"  missing-price windows: {report['price_incomplete_decisions']}", flush=True)
        print("  Historic publication, revisions, complete split/adjustment source and trading: UNQUALIFIED", flush=True)
        if args.save_report:
            target = settings.resolved_path("data/research/options_native_spy_full_period_retrospective_dividend_variance_v1") / (
                report["report_fingerprint"][:16] + ".json"
            )
            encoded = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
            if len(encoded.encode("utf-8")) > MAX_REPORT:
                raise ValueError("retrospective grid exceeds bounded report capacity")
            if target.is_symlink() or (target.exists() and (
                target.stat().st_size > MAX_REPORT or target.read_text(encoding="utf-8") != encoded
            )):
                raise ValueError("existing report differs; preserved")
            if not target.exists():
                atomic_write_text(target, encoded, fsync=True)
            print(f"  saved report: {target}", flush=True)
        print(f"  COMPLETE: {report['status']} fingerprint={report['report_fingerprint']}", flush=True)
        return 0
    except (OSError, ValueError, TypeError, KeyError, ArithmeticError) as exc:
        print(f"  BLOCKED: {exc}", flush=True)
        print("  Original reports untouched; no fallback providers, action repair or trading.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
