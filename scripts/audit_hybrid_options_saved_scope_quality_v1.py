from __future__ import annotations

"""Read-only V13 evidence census for already archived 09:35/10:00 quotes.

No new requests, no source modifications, no derived snapshots, no options
strategy outcome access, no simulation. This does NOT promote returned rows.
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
from packages.data.hybrid_options_saved_scope_quality_v1 import (
    audit_campaign_scope,
)

DEFAULT_MANIFEST = Path(
    "data/options/manifests/hybrid_exact_at_time_research_demand_v1_"
    + PINNED_MANIFEST_FINGERPRINT[:16] + ".json"
)
DEFAULT_SOURCE = Path(
    "data/options/manifests/thetadata_candidate_surface_source_plan_v1_"
    "acc9525a2930fe39.json"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--candidate-plan", type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args(argv)
    print("ATLAS HISTORICAL AT-TIME SAVED SOURCE QUALITY V13", flush=True)
    print("  mode=OFFLINE_VERIFIED_ORIGINAL_ARCHIVE_READ_ONLY provider_calls=0", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        report = audit_campaign_scope(
            settings, args.manifest, args.candidate_plan,
        )
        print(
            f"  archived={report['archived_sources']}"
            f" attempted={report['attempted_source_ids']}"
            f" scope_overruns={report['sources_with_dte_overruns']}"
            f" source_semantic_defects={report['sources_with_non_dte_semantic_defects']}",
            flush=True,
        )
        print(
            f"  original_quote_rows={report['total_original_quote_rows']}"
            f" within_requested_dte={report['observed_in_requested_dte_rows']}"
            f" outside_requested_dte={report['observed_outside_requested_dte_rows']}"
            f" other_invalid={report['observed_other_invalid_rows']}"
            f" positive_two_sided={report['observed_positive_two_sided_rows']}",
            flush=True,
        )
        print(
            f"  raw_bytes={report['original_bytes']}"
            f" gzip_bytes={report['gzip_bytes']}"
            f" saving_pct={report['estimated_compression_savings_percent']}"
            f" dte_buckets={report['dte_buckets']}",
            flush=True,
        )
        for row in report["source_details"]:
            print(
                f"  query={row['session']} {row['symbol']} {row['clock']}"
                f" right={row['requested_right']} max_dte={row['requested_dte']}"
                f" original_rows={row['original_quote_rows']}"
                f" in={row['in_requested_dte']}"
                f" out={row['outside_requested_dte']}"
                f" invalid={row['other_invalid_rows']}"
                f" displayed_two_sided={row['positive_two_sided_displayed_size_rows']}"
                f" oldest_quote_seconds={row['oldest_quote_age_seconds']}"
                f" query_id={row['query_id']}",
                flush=True,
            )
        print(
            f"  report_fingerprint={report['fingerprint']}", flush=True,
        )
        print(
            "  COMPLETE: source_originals_unchanged=True"
            " locally_projected=False completeness_proven=False"
            " simulator_ready=False provider_calls=0 files_written=0",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            "  BLOCKED: " + type(exc).__name__
            + " saved_sources_unchanged=True provider_calls=0",
            flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
