from __future__ import annotations

"""V45 resolve original 09:59 quotes and reconcile V43/V44 two-clock cases.

Never replace a missing early quote with a later 10:01 observation. Access the
exact original-source cache through V39/V38; any missing sources are
automatically fetched and retained, subject to normal storage safety.
This does not claim historically tradable orders, model IV, or profitability.
"""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.spy_unified_two_clock_cohort_v45 import (
    combined_report, original_predecision_demands, verified_v43_v44,
)
from packages.simulation.strategy_options_source_runtime_v39 import resolve_strategy_source_demands
from packages.simulation.strategy_source_progress_v42 import SourceProgressMonitor

MAX_V43_BYTES = 4 * 1024 * 1024
MAX_V44_BYTES = 4 * 1024 * 1024
STRATEGY_VERSION = "spy_v45_original_and_changed_strike_two_clock_cohort"


def load_report(path: Path, limit: int) -> dict:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError(f"V45_REQUIRED_REPORT_MISSING_OR_OVERSIZED:{path.name}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("V45_EXPECTED_JSON_OBJECT")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v43", type=Path, required=True)
    parser.add_argument("--v44", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print("ATLAS V45 SPY UNIFIED 09:59 PREDECISION + 10:01 ORDER SOURCE COHORT", flush=True)
    print("  original_v43=FROZEN alternate_v44=SEPARATE_VARIANT source_cache=AUTOMATIC_ON_MISS", flush=True)
    try:
        if args.output.is_symlink() or args.output.exists():
            raise ValueError("V45_OUTPUT_ALREADY_EXISTS")
        v43 = load_report(args.v43, MAX_V43_BYTES)
        v44 = load_report(args.v44, MAX_V44_BYTES)
        original, recovered = verified_v43_v44(v43, v44)
        original_passing = [c for c in original
                            if c["status"] == "SOURCE_MICROSTRUCTURE_OI_CHECKS_PASS"]
        needed = len(original_passing) * 2
        print(f"  frozen_original_cases={len(original)} original_1001_quality_pass={len(original_passing)}",flush=True)
        print(f"  V44_alternates_two_clock_pass=161 new_original_0959_quote_source_uses={needed}",flush=True)
        settings = load_settings(ROOT, "development")
        received: dict[str, dict] = {}
        def consume(item: dict, source: dict) -> None:
            day = item["kwargs"]["date_et"]
            received.setdefault(day, {})[item["purpose"]] = (item, source)
        print("  PHASE_1: original call and put source receipts at 09:59 (cache or ThetaData)",flush=True)
        with SourceProgressMonitor(expected_source_uses=needed) as progress:
            acquisition = resolve_strategy_source_demands(
                settings, STRATEGY_VERSION,
                original_predecision_demands(original),
                on_source=consume, on_progress=progress.event,
                continue_on_error=True,
            )
        print("  PHASE_2: validate original 09:59 skew and consolidate 361 original-date identities",flush=True)
        result = combined_report(v43, v44, original, recovered, received, acquisition)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        for name, count in result["cohort_status_counts"].items():
            print(f"  {name}={count}", flush=True)
        for name, count in result["cohort_origin_counts"].items():
            print(f"  origin_{name}={count}", flush=True)
        for name, count in result["two_clock_failure_reasons"].items():
            print(f"  reason_{name}={count}", flush=True)
        print(f"  suspected_identical_cross_right_price_snapshots={len(result['suspicious_equal_call_put_quotes'])}",flush=True)
        print(f"  provider_attempts={acquisition['provider_dispatch_attempts']}"
              f" new_archives={acquisition['provider_fetch_successes']}"
              f" cache_hits={acquisition['persisted_cache_hits']}"
              f" source_failures={acquisition['source_uses_failed_or_unresolved']}",flush=True)
        print(f"  fingerprint={result['fingerprint']} saved={args.output}",flush=True)
        print("  COMPLETE: TWO_CLOCK_SOURCE_QUALITY_ONLY; PIT_SOFR_DIVIDENDS_OCC_IV_SIMULATION_BLOCKED",flush=True)
        return 0 if acquisition["source_uses_failed_or_unresolved"] == 0 else 2
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError) as exc:
        print(f"  STOPPED: {type(exc).__name__}: {str(exc)[:350]}",flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
