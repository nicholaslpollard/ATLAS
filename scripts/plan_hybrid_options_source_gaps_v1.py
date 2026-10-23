from __future__ import annotations

"""Offline historical quote-demand versus cached-source gap preview.

--demo exercises repeated SPY 1h historical demand, separate SPY 1m,
QQQ hourly, and older SPY year without provider or simulated trades.
--requirements accepts a bounded explicit JSON batch with same contract.
Neither mode downloads data, writes the catalog, or authorizes backtests.
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.hybrid_options_gap_planner_v1 import (
    demo_batch, load_batch_file, plan_missing_sources,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--demo", action="store_true",
                       help="Read only the existing catalog against 5 frozen sample uses")
    group.add_argument("--requirements", type=Path,
                       help="JSON file of explicit bounded historical source requirements")
    args = parser.parse_args(argv)
    print("ATLAS HYBRID OPTIONS REQUIREMENT GAP PLANNER V1", flush=True)
    print("  READ_ONLY_CATALOG no provider, broker, source-bar or simulation calls", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        batch = demo_batch() if args.demo else load_batch_file(args.requirements)
        result = plan_missing_sources(settings, batch)
        print(
            f"  requirements={result['total_requirement_uses']} "
            f"unique_queries={result['unique_exact_queries']} "
            f"deduplicated_uses={result['deduplicated_uses']}",
            flush=True,
        )
        print(
            f"  local_source_diagnostics={result['exact_sources_observed_not_qualified']} "
            f"missing_exact_local_sources={result['queries_missing_exact_local_source']} "
            f"simulator_ready={result['qualified_for_simulator']}",
            flush=True,
        )
        for query in result["queries"]:
            q = query["query"]
            strategy_uses = ",".join(
                r["strategy_key"] for r in query["uses"]
            )
            count = sum(s["observed_rows"] for s in query["exact_sources"])
            print(
                f"  symbol={q['symbol']} date={q['date_et']} "
                f"interval={q['interval']} right={q['right']} "
                f"state={query['source_state']} "
                f"observed_rows={count} uses={strategy_uses}",
                flush=True,
            )
        print("  report_fingerprint=" + result["report_fingerprint"], flush=True)
        print(
            "  COMPLETE status=OFFLINE_GAP_DIAGNOSTIC_NO_PROVIDER_AUTHORITY "
            "provider_requests=0 data_downloads=0 source_files_scanned=0 "
            "simulation_runs=0",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            "  BLOCKED " + type(exc).__name__
            + "; no provider fallback or source mutation", flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
