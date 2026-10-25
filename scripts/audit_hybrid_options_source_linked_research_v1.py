from __future__ import annotations

"""V15 offline read-only source-linked causal option-chain diagnostics.

Replays original V12 SHA-verified archives via exactly the existing V14
reference indices, without any request, file write, simulator activity,
reconstructed complete chain, assumed execution prices or outcome access.
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.hybrid_options_at_time_one_call_v1 import (
    PINNED_MANIFEST_FINGERPRINT,
)
from packages.data.hybrid_options_source_linked_research_reader_v1 import (
    audit_frozen_indexed_chains,
)

DEFAULT_MANIFEST = Path(
    "data/options/manifests/hybrid_exact_at_time_research_demand_v1_"
    + PINNED_MANIFEST_FINGERPRINT[:16] + ".json"
)
DEFAULT_CANDIDATE = Path(
    "data/options/manifests/thetadata_candidate_surface_source_plan_v1_"
    "acc9525a2930fe39.json"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--candidate-plan", type=Path, default=DEFAULT_CANDIDATE)
    args = parser.parse_args(argv)
    print("ATLAS SOURCE-LINKED CAUSAL OPTIONS CHAIN READER V15", flush=True)
    print("  mode=READ_ONLY_ORIGINAL_PROVENANCE_CHAIN_DIAGNOSTIC_NO_PROVIDER", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        report = audit_frozen_indexed_chains(
            settings, args.manifest, args.candidate_plan,
        )
        print(
            f"  indexed_archives={report['sources_inspected']}"
            f" original_rows={report['original_rows']}"
            f" v14_in_dte_rows={report['v14_selected_rows']}"
            f" research_14_45_dte_rows={report['research_14_45_dte_observed_rows']}",
            flush=True,
        )
        print(
            f"  window_stale_over_60s={report['research_14_45_dte_stale_rows']}"
            f" wide_spread_over_15pct={report['research_14_45_dte_wide_spread_rows']}"
            f" observed_call_put_pairs={report['observed_call_put_strike_pairs']}"
            f" fresh_tight_pairs={report['pairs_passing_freshness_and_spread_only']}",
            flush=True,
        )
        for row in report["per_source"]:
            print(
                f"  source={row['session_et']} {row['symbol']}"
                f" clock={row['decision_clock_et']}"
                f" v14_selected={row['v14_in_range_source_rows']}"
                f" research_dte_14_45={row['research_window_observed_rows']}"
                f" expirations={row['observed_expirations']}"
                f" call_put_pairs={row['observed_call_put_strike_pairs']}"
                f" tight_fresh_pairs={row['observed_pairs_passing_freshness_spread_only'] if 'observed_pairs_passing_freshness_spread_only' in row else row['observed_pairs_passing_freshness_spread_only']}"
                f" query_id={row['query_id']}",
                flush=True,
            )
        print(f"  report_fingerprint={report['fingerprint']}", flush=True)
        print(
            "  COMPLETE: source_chain_completeness_proven=False"
            " option_execution_admissible=False simulator_ready=False"
            " provider_requests=0 simulations_run=0 files_written=0",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            "  BLOCKED: " + type(exc).__name__
            + " provider_requests=0 files_written=0",
            flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
