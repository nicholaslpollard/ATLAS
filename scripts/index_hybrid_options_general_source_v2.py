from __future__ import annotations

"""Provider-free generalized hybrid quote-source store verification.

Preview (default) reads the already accepted V4 compressed SPY canary,
validates the generalized V6 source shape and measures exact new disk use.
--import-verified-v4 separately opts in to create a V6 immutable compressed
copy and generalized DuckDB index, without changing V1-V5 originals.
--check-source verifies a previously indexed V6 source without writes.
None of these modes opens a ThetaData client or runs a simulation.
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
from packages.data.hybrid_options_source_store_v2 import (
    read_historical_quote_source, store_historical_quote_source,
)

SPY_V4_ID = "606ee2f25dcbaa2c017c04cd2c703d8e6784cc9c7d8ccb807319ed7455415f90"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--import-verified-v4", action="store_true",
                      help="Write one immutable V6 copy and general source index")
    mode.add_argument("--check-source", metavar="SOURCE_ID",
                      help="Reverify existing V6 source, no writes")
    args = parser.parse_args(argv)
    print("ATLAS HYBRID GENERALIZED COMPRESSED QUOTE STORE V6", flush=True)
    print("  ZERO provider/broker requests, source promotions and simulations",
          flush=True)
    try:
        settings = load_settings(ROOT, "development")
        if args.check_source:
            report = read_historical_quote_source(settings, args.check_source)
            print(
                f"  id={report['source_id']} quotes={report['quote_rows']} "
                f"retrieved={report['retrieved_from']}", flush=True,
            )
            print(
                f"  status=OBSERVED_ONLY simulator_ready={report['simulator_ready']}",
                flush=True,
            )
        else:
            known = load_verified_archived_option_quotes(settings, SPY_V4_ID)
            report = store_historical_quote_source(
                settings, known["query_scope"], verified_v4=known,
                write=args.import_verified_v4,
            )
            print(
                f"  source_id={report['source_id']} "
                f"symbol={report['query']['symbol']} "
                f"session={report['query']['date_et']} "
                f"interval={report['query']['interval']}", flush=True,
            )
            print(
                f"  observed_quotes={report['diagnostics']['observed_rows']} "
                f"unique_contracts={report['diagnostics']['distinct_contracts']} "
                f"out_of_dte={report['diagnostics']['outside_requested_dte']} "
                f"duplicate_keys={report['diagnostics']['duplicate_observation_keys']}",
                flush=True,
            )
            print(
                f"  gzip_bytes={report['compressed_bytes']} "
                f"source_bytes={report['source_bytes']} "
                f"archived={report['archived']} indexed={report['indexed']}",
                flush=True,
            )
            if args.import_verified_v4:
                retrieved = read_historical_quote_source(
                    settings, report["source_id"],
                )
                if retrieved["quote_rows"] != report["diagnostics"]["observed_rows"]:
                    raise ValueError("V6_INDEXED_ARCHIVE_ROW_COUNT_CHANGED")
                print(
                    "  reverified_from=V6_VERIFIED_GZIP original_v4_untouched=True",
                    flush=True,
                )
        print(
            "  COMPLETE: GENERALIZED_COMPRESSED_SOURCE_DIAGNOSTIC "
            "simulator_ready=False provider_requests=0 "
            "broker_requests=0 simulations_run=0",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            "  BLOCKED: " + type(exc).__name__
            + "; no automatic provider retry or simulator access",
            flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
