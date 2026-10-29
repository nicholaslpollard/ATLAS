from __future__ import annotations

"""V40 SPY full-cohort dynamic historical source acquisition.

Newly needed original-contract quote and previous-session OI data are
retrieved automatically if missing from the shared persistent cache.
No hard-coded provider request count or lifetime candidate limit.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.options_native_spy_dynamic_source_acquisition_v40 import (
    CONTRACT, validate_v37_source_packet, source_demands_for_entries,
    count_source_observation, source_evidence_summary,
)
from packages.simulation.strategy_options_source_runtime_v39 import (
    resolve_strategy_source_demands,
)
from packages.simulation.strategy_source_progress_v42 import SourceProgressMonitor

MAX_INPUT_BYTES = 2 * 1024 * 1024
STRATEGY_VERSION = "spy_original_v37_feature_inputs_v40"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v37", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--heartbeat-seconds", type=float, default=15.0,
                        help="Print a timestamped heartbeat while a provider call is in progress.")
    parser.add_argument("--progress-every", type=int, default=25,
                        help="Also print progress after every N resolved sources.")
    parser.add_argument(
        "--strategy-version", default=STRATEGY_VERSION,
        help="Cache-use lineage version, not a fixed restriction on source candidates.",
    )
    args = parser.parse_args(argv)
    print("ATLAS V40 SPY HISTORICAL ENTRY + PREVIOUS OI DYNAMIC SOURCE ACQUISITION")
    print("  cache=VERIFY_AND_REUSE provider=FETCH_MISSING_AND_ARCHIVE", flush=True)
    try:
        if (args.v37.is_symlink() or not args.v37.is_file()
                or not 0 < args.v37.stat().st_size < MAX_INPUT_BYTES
                or args.output.exists() or args.output.is_symlink()):
            raise ValueError("V40_INPUT_NOT_PRESENT_OR_OUTPUT_NOT_NEW")
        report = json.loads(args.v37.read_text(encoding="utf-8"))
        entries = validate_v37_source_packet(report)
        print(f"  validated_2018_2025_original_pairs={len(entries)}"
              " each=decision_morning_prior_session_open_interest,10:01_call,10:01_put")
        settings = load_settings(ROOT, "development")
        evidence = Counter()
        # The runtime fetches what the source generator needs, archives each
        # successful response and records every use in durable SQLite. Missing
        # source receipts stay retryable rather than deleting candidate trades.
        log_path = args.output.with_suffix(".progress.log")
        print(f"  progress_log={log_path} heartbeat={args.heartbeat_seconds}s"
              f" every={args.progress_every} source_uses"
              f" original_cohort_requirements={len(entries) * 3}", flush=True)
        with SourceProgressMonitor(
            log_path, expected_source_uses=len(entries) * 3,
            heartbeat_seconds=args.heartbeat_seconds, every=args.progress_every,
        ) as monitor:
            acquisition = resolve_strategy_source_demands(
                settings,
                args.strategy_version,
                source_demands_for_entries(entries),
                on_source=lambda item, src: count_source_observation(item, src, evidence),
                on_progress=monitor.event,
                continue_on_error=True,
            )
        result = source_evidence_summary(report, acquisition, evidence)
        if result["contract"] != CONTRACT:
            raise ValueError("V40_OUTPUT_CONTRACT_CHANGED")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as out:
            json.dump(result, out, indent=2, sort_keys=True, allow_nan=False)
            out.write("\n")
        c = result["source_demand_counts"]
        print(
            f"  source_needs={c['source_uses_requested']}"
            f" archived_or_reused={c['source_uses_resolved']}"
            f" no_data={c['source_uses_explicit_no_data']}"
            f" failed_or_unresolved={c['source_uses_failed_or_unresolved']}"
        )
        print(
            f"  actual_provider_calls_attempted={c['provider_dispatch_attempts']}"
            f" newly_archived_or_no_data={c['provider_fetch_successes']}"
            f" cache_hits={c['persisted_cache_hits']}"
        )
        for name, value in sorted(result["source_evidence_counts"].items()):
            if name.startswith(("exact_contract_", "archive_present_")):
                print(f"  {name}={value}")
        print("  STATUS=" + acquisition["status"])
        print("  PIT_SIGNAL_AND_REAL_EXECUTION_NOT_YET_QUALIFIED")
        print("  saved=" + str(args.output), flush=True)
        print("  timestamped_progress_log=" + str(log_path), flush=True)
        return 0 if acquisition["status"] == "ALL_REQUESTED_SOURCES_PRESENT" else 2
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError) as exc:
        print(f"  STOPPED: {type(exc).__name__}: {str(exc)[:350]}", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
