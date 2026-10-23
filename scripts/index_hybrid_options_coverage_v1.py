from __future__ import annotations

"""Index ONE explicit existing hourly source receipt into the D:-bound catalog.

Default is a zero-write verification preview; --write-catalog enables
idempotent DuckDB registration. Never contacts ThetaData or simulates trades.
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.hybrid_options_coverage_catalog_v1 import (
    inspect_hourly_source, ingest_hourly_source, inspect_exact_hourly_request,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True,
                        help="One exact retained hourly_quote canary summary.json")
    parser.add_argument("--write-catalog", action="store_true",
                        help="Idempotently register verified source on secondary D:")
    args = parser.parse_args(argv)
    print("ATLAS HYBRID OPTIONS HISTORICAL COVERAGE CATALOG V1", flush=True)
    print("  zero ThetaData/broker calls, no source acquisition, no simulations", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        if args.write_catalog:
            result = ingest_hourly_source(settings, args.summary)
        else:
            result = inspect_hourly_source(settings, args.summary)
        print(
            f"  source={result['source_type']} "
            f"source_status={result['source_status']}", flush=True,
        )
        print(
            f"  observed_quotes={result['source_rows']} "
            f"observed_contracts={result['unique_observed_contracts']}",
            flush=True,
        )
        print(
            f"  raw_bytes={result['source_bytes']} "
            f"gzip_9_estimate_bytes={result['gzip_9_estimate_bytes']}",
            flush=True,
        )
        print(f"  fingerprint={result['source_id']}", flush=True)
        if args.write_catalog:
            print(
                f"  catalog_inserted={result['catalog_inserted']} "
                f"catalog_observation_rows={result['catalog_observation_rows']}",
                flush=True,
            )
            print("  catalog_path=" + result["catalog_path"], flush=True)
            local = inspect_exact_hourly_request(
                settings, symbol="SPY", date_et="2025-06-09", right="both",
            )
            print(
                f"  exact_source_present={local['source_present']} "
                f"simulator_ready={local['simulator_ready']}", flush=True,
            )
        else:
            print("  MODE=VERIFY_ONLY; catalog not written", flush=True)
        print(
            "  COMPLETE: PROVENANCE_INDEX_ONLY_NOT_COVERAGE_ACCEPTANCE "
            "provider_requests=0 broker_requests=0 protected_outcomes_read=0",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            "  BLOCKED: " + type(exc).__name__ +
            "; no provider fallback or re-acquisition authorized.", flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
