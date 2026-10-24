from __future__ import annotations

"""Source-only hybrid options simulation-input preflight.

Checks exact-query gaps and independently verifies retained compressed source
archives before any simulation. --require-ready deliberately stops on V1 data.
Does not launch a simulator, make an API call, or write an acquisition queue.
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.hybrid_options_gap_planner_v1 import (
    demo_batch, load_batch_file,
)
from packages.data.hybrid_options_simulation_preflight_v1 import (
    HybridSimulationPreflightError, preflight_simulation_inputs,
    require_qualified_simulation_inputs,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", action="store_true",
                        help="Preflight the frozen five-use demonstration")
    source.add_argument("--requirements", type=Path,
                        help="Explicit V1 JSON requirements batch")
    parser.add_argument("--require-ready", action="store_true",
                        help="Fail closed unless all simulation inputs qualify")
    args = parser.parse_args(argv)

    print("ATLAS HYBRID OPTIONS SIMULATOR INPUT PREFLIGHT V1", flush=True)
    print("  VERIFIED_ARCHIVES_ONLY zero providers/brokers/outcomes/simulations",
          flush=True)
    try:
        settings = load_settings(ROOT, "development")
        batch = demo_batch() if args.demo else load_batch_file(args.requirements)
        result = preflight_simulation_inputs(settings, batch)
        print(
            f"  uses={result['requirement_uses']} "
            f"unique_queries={result['unique_queries']} "
            f"deduplicated_uses={result['deduplicated_uses']}",
            flush=True,
        )
        print(
            f"  verified_archives={result['verified_archives']} "
            f"unqualified_sources={result['unqualified_observed_queries']} "
            f"missing_exact_queries={result['missing_exact_queries']}",
            flush=True,
        )
        for item in result["queries"]:
            q = item["query"]
            print(
                f"  symbol={q['symbol']} date={q['date_et']} "
                f"interval={q['interval']} purpose="
                + ",".join(u["purpose"] for u in item["uses"])
                + f" state={item['readiness']}",
                flush=True,
            )
        print("  report_fingerprint=" + result["report_fingerprint"], flush=True)
        print(
            f"  simulator_run_permitted={result['simulator_run_permitted']} "
            f"frozen_input_created={result['frozen_simulation_dataset_created']}",
            flush=True,
        )
        if args.require_ready:
            require_qualified_simulation_inputs(result)
        print(
            "  COMPLETE: INPUT_GAPS_AND_ARCHIVES_VERIFIED_NO_SIMULATION "
            "provider_requests=0 broker_requests=0 "
            "protected_outcomes_read=0 simulations_run=0",
            flush=True,
        )
        return 0
    except HybridSimulationPreflightError as exc:
        print(
            f"  BLOCKED: {exc}; no simulation or provider fallback", flush=True,
        )
        return 4
    except Exception as exc:
        print(
            "  BLOCKED: " + type(exc).__name__
            + "; no simulation or provider fallback", flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
