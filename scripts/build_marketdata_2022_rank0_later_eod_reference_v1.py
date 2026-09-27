from __future__ import annotations

"""Read only original EOD rows; produce descriptive later-session price references."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError
from packages.data.marketdata_2022_rank0_later_eod_reference_v1 import (
    build_rank0_later_eod_reference, write_rank0_later_eod_reference,
)
from packages.data.research_storage import ResearchStorageError


def main() -> int:
    print("ATLAS 2022 Rank-Zero CALL: Original EOD Bid/Ask Reference Paths V1", flush=True)
    print("  ZERO provider requests, NO executable 09:35/EOD fill, cash P&L or portfolio authority", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        project_options, physical_options = settings.external_storage_binding_paths("options")
        settings.assert_external_storage_binding("options")
        print(f"  logical options path: {project_options}", flush=True)
        print(f"  physical options path: {physical_options}", flush=True)
        print("  both paths point to the SAME bound directory on D:", flush=True)
        result = build_rank0_later_eod_reference(
            settings,
            progress=lambda row: print(
                "  " + " ".join(f"{key}={value}" for key, value in row.items()), flush=True
            ),
        )
        logical_path, action = write_rank0_later_eod_reference(settings, result)
        physical_path = physical_options / logical_path.relative_to(project_options)
        print(f"  status: {result['status']}", flush=True)
        for key in (
            "structural_rank_zero_opportunities", "unique_original_rank_zero_histories",
            "no_later_two_sided_reference",
            "entry_reference_only_no_subsequent_reference",
            "entry_and_next_reference_available",
            "entry_reference_with_positive_reported_volume",
            "next_reference_with_positive_reported_volume",
            "median_hypothetical_ask_to_next_bid_reference_fraction",
            "provider_requests", "original_receipts_modified",
            "reference_fingerprint",
        ):
            print(f"  {key}: {result[key]}", flush=True)
        print(f"  derived artifact: {action} / {physical_path}", flush=True)
        print("  Values are retrospective observed EOD-source bid/ask references, not fills, deliverable-adjusted option P&L, 09:35 execution, PAPER or LIVE.", flush=True)
        return 0
    except (CandidateChainCacheError, ResearchStorageError,
            OSError, ValueError, TypeError, KeyError) as exc:
        print(f"LATER EOD PRICE REFERENCE STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  Preserve original source/quote receipts; no new paid request or automatic retry.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
