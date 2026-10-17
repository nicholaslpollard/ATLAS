from __future__ import annotations

"""Offline source-demand census: many option underlyings, not just SPY."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import load_settings
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.options_multi_underlying_source_inventory_v1 import (
    build_multi_underlying_source_demand_inventory,
)

MAX_INPUT_BYTES = 48 * 1024 * 1024
MAX_REPORT_BYTES = 512 * 1024


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-plan", type=Path, required=True)
    parser.add_argument("--save-report", action="store_true")
    args = parser.parse_args(argv)
    print("ATLAS MULTI-UNDERLYING HISTORICAL OPTION SOURCE DEMAND INVENTORY V1", flush=True)
    print("  Reads ONE frozen 2021-2025 09:35 CALL source plan; no SPY price/option/event scans.", flush=True)
    print("  Does not read option quotes, authorize ThetaData requests, or extend the 10:00 SPY pilot.", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        if args.save_report:
            settings.assert_external_storage_binding("research_evidence")
        settings.assert_external_storage_binding("options")
        source = args.source_plan if args.source_plan.is_absolute() else settings.resolved_path(args.source_plan)
        if (source.is_symlink() or not source.is_file() or
                not (0 < source.stat().st_size <= MAX_INPUT_BYTES) or
                not source.name.startswith("thetadata_candidate_surface_source_plan_v1_")
                or source.suffix.lower() != ".json"):
            raise ValueError("frozen multi-symbol options source plan path/size invalid")
        plan = _read_object(source)
        report = build_multi_underlying_source_demand_inventory(plan)
        inventory = report["source_inventory"]
        print(f"  planned stock/ETF underlyings: {inventory['unique_underlyings']}", flush=True)
        print(f"  planned CALL surfaces: {inventory['unique_symbol_day_0935_call_surfaces']}", flush=True)
        print(f"  source case memberships: {inventory['underlying_case_members']}", flush=True)
        print(f"  decision dates: {inventory['date_min']} to {inventory['date_max']}", flush=True)
        print(f"  by year: {inventory['requests_by_year']}", flush=True)
        print("  top symbols by planned coverage (illustrative worklist, NOT option price availability):", flush=True)
        for row in sorted(inventory["underlyings"],
                          key=lambda item: (-item["planned_call_surface_requests"], item["symbol"]))[:12]:
            print(f"    {row['symbol']}: {row['planned_call_surface_requests']} planned CALL surfaces", flush=True)
        print("  Historical CALL/PUT quotes, event timing, option selection, fills and returns: UNQUALIFIED", flush=True)
        if args.save_report:
            output = settings.resolved_path("data/research/options_multi_underlying_source_inventory_v1") / (
                report["report_fingerprint"][:16] + ".json"
            )
            body = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
            if len(body.encode("utf-8")) > MAX_REPORT_BYTES:
                raise ValueError("multi-underlying summary exceeds bounded JSON")
            if output.is_symlink() or (output.exists() and (
                output.stat().st_size > MAX_REPORT_BYTES
                or output.read_text(encoding="utf-8") != body
            )):
                raise ValueError("retained multi-symbol inventory conflicts with signed source")
            if not output.exists():
                atomic_write_text(output, body, fsync=True)
            print(f"  saved report: {output}", flush=True)
        print(f"  COMPLETE: {report['status']} fingerprint={report['report_fingerprint']}", flush=True)
        return 0
    except (OSError, TypeError, ValueError, KeyError, ArithmeticError) as exc:
        print(f"  BLOCKED: {exc}", flush=True)
        print("  No provider fallback, new option prices, 2026 holdout or simulation access.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
