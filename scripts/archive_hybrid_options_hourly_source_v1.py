from __future__ import annotations

"""Offline preview or immutable compressed copy of ONE already-indexed quote source.

Does not call ThetaData, modify the original or change backtest readiness.
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.hybrid_options_lossless_archive_v1 import archive_existing_source

FROZEN_HOURLY_SOURCE_ID = (
    "606ee2f25dcbaa2c017c04cd2c703d8e6784cc9c7d8ccb807319ed7455415f90"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-id", default=FROZEN_HOURLY_SOURCE_ID,
                        help="Exact indexed hourly source ID (default frozen SPY canary)")
    parser.add_argument("--write-archive", action="store_true",
                        help="Create one immutable compressed copy if absent")
    args = parser.parse_args(argv)
    print("ATLAS HYBRID OPTIONS LOSSLESS ARCHIVE V1", flush=True)
    print("  zero provider/broker calls, no acquisition or simulation", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        report = archive_existing_source(
            settings, args.source_id, write_archive=args.write_archive,
        )
        print(
            f"  original_bytes={report['original_bytes']} "
            f"compressed_bytes={report['compressed_bytes']} "
            f"saved_percent={100 * report['saved_fraction']:.2f}",
            flush=True,
        )
        print(
            f"  observed_quote_rows={report['observed_quotes']} "
            f"lossless_verified={report['lossless_source_verification']}",
            flush=True,
        )
        print(
            f"  archive_present={report['archive_present']} "
            f"archive_inserted={report['archive_inserted']} "
            f"simulator_ready={report['simulator_ready']}",
            flush=True,
        )
        if args.write_archive:
            print("  archive=" + report["archive_path"], flush=True)
            print("  receipt=" + report["receipt_path"], flush=True)
        else:
            print("  PREVIEW_ONLY no compressed file written", flush=True)
        print(
            "  COMPLETE: LOSSLESS_SOURCE_ARCHIVE_NO_SOURCE_PROMOTION "
            "provider_requests=0 broker_requests=0 simulations_run=0",
            flush=True,
        )
        return 0
    except Exception as exc:
        print("  STOP: " + type(exc).__name__
              + "; original source unchanged, no provider fallback", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
