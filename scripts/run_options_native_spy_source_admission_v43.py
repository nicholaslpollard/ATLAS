from __future__ import annotations

"""V43 validate 10:01 SPY original option quote liquidity and decision morning OI.

V38/V39 dynamic read-through: cached sources reused, absent sources automatically
requested and archived. Not an IV estimate or broker-executable fill claim.
"""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.options_native_spy_dynamic_source_acquisition_v40 import source_demands_for_entries
from packages.data.options_native_spy_source_admission_v43 import assess_case, build_report, validate_source_pair_reports
from packages.simulation.strategy_options_source_runtime_v39 import resolve_strategy_source_demands
from packages.simulation.strategy_source_progress_v42 import SourceProgressMonitor

MAX_V37_BYTES = 2 * 1024 * 1024
MAX_V40_BYTES = 64 * 1024
STRATEGY_VERSION = "spy_v43_original_source_quality_admission"


def _report(path: Path, limit: int) -> dict:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError(f"V43_INPUT_MISSING_OR_OVERSIZED:{path.name}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("V43_INPUT_NOT_JSON_OBJECT")
    return obj


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v37", type=Path, required=True)
    parser.add_argument("--v40", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print("ATLAS V43 ORIGINAL SPY 10:01 QUOTE + DECISION MORNING OI QUALITY")
    print("  cache=EXACT_SOURCE_REUSE provider=AUTOMATIC_ON_MISS original_trade_outcomes=UNUSED")
    try:
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("V43_OUTPUT_ALREADY_PRESENT")
        v37 = _report(args.v37, MAX_V37_BYTES)
        v40 = _report(args.v40, MAX_V40_BYTES)
        selected = validate_source_pair_reports(v37, v40)
        lookup = {row["original_entry_date_et"]: row for row in selected}
        print("  original_selected_pairs=361 original_source_requirements=1083")
        print("  eligibility=QUOTE_FRESHNESS_SPREAD_SIZE_PAIR_SKEW_AND_ORIGINAL_OI_ONLY")
        settings = load_settings(ROOT, "development")

        # Keep at most one OI surface in memory; save only exact call/put
        # matches, never the 1.6 million other source rows in the report.
        current_date = None
        current_sources = {}
        completed = {}

        def finalize(day):
            nonlocal current_sources, current_date
            if day is not None and day not in completed:
                completed[day] = assess_case(lookup[day], current_sources)
            current_date, current_sources = None, {}

        def receive(item, source):
            nonlocal current_date, current_sources
            day = item["kwargs"]["date_et"]
            if current_date is not None and day != current_date:
                finalize(current_date)
            current_date = day
            current_sources[item["purpose"]] = (item, source)
            if item["purpose"] == "put_1001_quote":
                finalize(day)

        with SourceProgressMonitor(expected_source_uses=len(selected) * 3) as progress:
            acquisition = resolve_strategy_source_demands(
                settings, STRATEGY_VERSION,
                source_demands_for_entries(selected),
                on_source=receive,
                on_progress=progress.event,
                continue_on_error=True,
            )
        if current_date is not None:
            finalize(current_date)
        for row in selected:
            day = row["original_entry_date_et"]
            if day not in completed:
                completed[day] = assess_case(row, {})
        result = build_report(
            v37, v40, [completed[day] for day in sorted(completed)], acquisition,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as out:
            json.dump(result, out, indent=2, sort_keys=True, allow_nan=False)
            out.write("\n")
        print("  cases=361 actual_strategy_entries=UNQUALIFIED")
        for key, value in sorted(result["case_counts"].items()):
            print(f"  {key}={value}")
        for key, value in sorted(result["reason_counts"].items()):
            print(f"  reason_{key}={value}")
        print(
            f"  provider_attempts_this_run={acquisition['provider_dispatch_attempts']}"
            f" cached_sources_reused={acquisition['persisted_cache_hits']}"
            f" newly_archived={acquisition['provider_fetch_successes']}"
            f" unresolved_source_uses={acquisition['source_uses_failed_or_unresolved']}"
        )
        print(f"  report_sha={result['fingerprint']} saved={args.output}")
        print("  COMPLETE: SOURCE_QUALITY_EVIDENCE_ONLY; PIT_RATES_DIVIDENDS_IV_FILL_NOT_PROVEN")
        return 0 if acquisition["source_uses_failed_or_unresolved"] == 0 else 2
    except (OSError, ValueError, TypeError, KeyError, ArithmeticError) as exc:
        print(f"  STOPPED: {type(exc).__name__}: {str(exc)[:300]}", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
