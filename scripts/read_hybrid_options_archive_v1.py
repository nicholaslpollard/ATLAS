from __future__ import annotations

"""Read ONE archived historical quote source through its indexed source ID.

Source-only inspection. Prints identity, quote counts, and clock coverage,
never trades or executable historical fills. No provider requests.
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.hybrid_options_archive_reader_v1 import (
    load_verified_archived_option_quotes,
)

SPY_SOURCE_ID = (
    "606ee2f25dcbaa2c017c04cd2c703d8e6784cc9c7d8ccb807319ed7455415f90"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-id", default=SPY_SOURCE_ID,
                        help="Existing indexed source ID")
    args = parser.parse_args(argv)
    print("ATLAS HYBRID OPTIONS VERIFIED ARCHIVE READER V1", flush=True)
    print("  ARCHIVE_AND_CATALOG_READ_ONLY no source original reads or API calls",
          flush=True)
    try:
        settings = load_settings(ROOT, "development")
        info = load_verified_archived_option_quotes(settings, args.source_id)
        print(
            f"  symbol={info['symbol']} session={info['session_et']} "
            f"interval={info['interval']}", flush=True,
        )
        print(
            f"  recovered_quotes={info['quote_rows']} "
            f"unique_contracts={info['unique_contracts']} "
            f"rights={info['rights_observed']}", flush=True,
        )
        print(
            f"  compressed_bytes={info['compressed_bytes']} "
            f"restored_bytes={info['restored_original_bytes']}",
            flush=True,
        )
        print(
            f"  clock_min={info['observed_timestamp_min']} "
            f"clock_max={info['observed_timestamp_max']}", flush=True,
        )
        print(
            f"  retrieved_from={info['retrieved_from']} "
            f"original_source_opened={info['original_uncompressed_source_opened']}",
            flush=True,
        )
        print(
            f"  source_status={info['source_status']} "
            f"simulator_ready={info['simulator_ready']}",
            flush=True,
        )
        print(
            "  COMPLETE: VERIFIED_ARCHIVED_SOURCE_NO_COVERAGE_PROMOTION "
            "provider_requests=0 broker_requests=0 protected_outcomes_read=0",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            "  BLOCKED: " + type(exc).__name__
            + "; no provider fallback or original source mutation",
            flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
