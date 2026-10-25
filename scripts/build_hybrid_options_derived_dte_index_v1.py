from __future__ import annotations

"""V14 offline source-linked DTE index verification.

Default is no-write preview. --write-indexes writes immutable positional
reference metadata ONLY (never duplicates provider quotes, revises original
archives, contacts ThetaData, or enables simulator execution). Safe to rerun
because existing matching indices are verified and reused, never overwritten.
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
from packages.data.hybrid_options_derived_dte_index_v1 import (
    build_dte_reference_indices,
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
    parser.add_argument("--write-indexes", action="store_true")
    args = parser.parse_args(argv)
    print("ATLAS VERIFIED LOCAL ORIGINAL-ROW DTE REFERENCE INDEX V14", flush=True)
    print(
        "  mode=" + ("WRITE_IMMUTABLE_REFERENCE_INDEX_ONLY"
                   if args.write_indexes else "READ_ONLY_REFERENCE_PREVIEW")
        + " provider_calls=0 price_payload_copies=0",
        flush=True,
    )
    try:
        settings = load_settings(ROOT, "development")
        result = build_dte_reference_indices(
            settings, args.manifest, args.candidate_plan,
            write_indexes=args.write_indexes,
        )
        print(
            f"  original_sources={result['original_archives_scanned']}"
            f" selected_in_dte_row_refs={result['in_requested_dte_references']}"
            f" excluded_out_of_dte_rows={result['outside_requested_dte_rows_not_indexed']}",
            flush=True,
        )
        print(
            f"  existing_verified_indices={result['already_immutable_indices']}"
            f" newly_written_indices={result['new_immutable_indices']}"
            f" index_bytes={result['estimated_all_index_bytes']}",
            flush=True,
        )
        print(
            f"  status={result['status']}"
            f" fingerprint={result['fingerprint']}",
            flush=True,
        )
        print(
            "  COMPLETE: original_sources_unchanged=True"
            " provider_requests=0 broker_requests=0 simulations_run=0"
            " source_chain_completeness_proven=False"
            " option_execution_admissible=False simulator_ready=False",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            "  BLOCKED: " + type(exc).__name__
            + " provider_calls=0 original_source_modified=False",
            flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
