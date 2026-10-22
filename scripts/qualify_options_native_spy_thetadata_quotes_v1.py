from __future__ import annotations

"""Review the frozen 10:00 SPY CALL+PUT qualifier, optionally run paid probes.

Default is a zero-provider plan inspection. The three flags deliberately
require affirmative action before 25 bounded quote method calls.
"""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.options_native_spy_thetadata_quote_qualification_v1 import (
    QUOTE_REQUEST_CAP, quote_design, run_pilot_quote_source_gate,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true",
                        help="Print complete outcome-blind design without provider reads.")
    parser.add_argument("--authorize-provider-reads", action="store_true",
                        help="Explicitly authorize the bounded paid quote-source method calls.")
    parser.add_argument("--confirm-thetadata-standard", action="store_true",
                        help="Confirm actual activated entitlement, not planned subscription.")
    parser.add_argument("--acknowledge-25-quote-method-call-cap", action="store_true",
                        help="Acknowledge a maximum of 25 distinct paid quote method calls.")
    args = parser.parse_args(argv)
    print("ATLAS OPTIONS-NATIVE SPY 10:00 CALL+PUT SOURCE GATE V1", flush=True)
    try:
        design = quote_design()
        print(f"  pilot_design={design['design_fingerprint']} "
              f"anchors=24 repeat=1 maximum_quote_calls={QUOTE_REQUEST_CAP}",
              flush=True)
        print(f"  years={design['years']} "
              "clock=10:00:00.000 right=both max_dte=45 strike_range=2", flush=True)
        print("  Frozen 411 SPY weekly source demands and all protected outcomes untouched.", flush=True)
        enabled = (
            args.authorize_provider_reads and args.confirm_thetadata_standard
            and args.acknowledge_25_quote_method_call_cap
        )
        if not enabled:
            if args.json:
                print(json.dumps(design, sort_keys=True, indent=2, allow_nan=False))
            if (args.authorize_provider_reads or args.confirm_thetadata_standard
                    or args.acknowledge_25_quote_method_call_cap):
                print("  BLOCKED_PARTIAL_PROVIDER_AUTHORIZATION — no requests.", flush=True)
                return 2
            print("  COMPLETE status=DESIGN_ONLY_ZERO_PROVIDER_REQUESTS "
                  "source_accepted=False provider_requests=0", flush=True)
            print("  Paid quote source probing is separate; no requests authorized by design inspection.", flush=True)
            return 0
        print("  AUTHORIZED by supplied flags: bounded at-time source reads only, "
              "no Greeks/OI/execution/fills/strategy outcomes.", flush=True)
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        report = run_pilot_quote_source_gate(
            settings,
            authorize_provider_reads=args.authorize_provider_reads,
            confirm_thetadata_standard=args.confirm_thetadata_standard,
            acknowledge_25_quote_method_call_cap=args.acknowledge_25_quote_method_call_cap,
        )
        print(f"  source_calls={report['requests_attempted']}/25 "
              f"statuses={report['status_counts']}", flush=True)
        print(f"  repeat_equal={report['repeat_surface_equal']} "
              f"raw_bytes_equal={report['repeat_sdk_normalized_raw_bytes_equal']} "
              f"all_24_anchors_observed={report['all_24_anchor_surfaces_observed']} "
              f"all_years_observed={report['all_years_observed']}", flush=True)
        print(f"  retained_report={report['report_path']}", flush=True)
        print("  COMPLETE status=BOUNDED_SOURCE_DIAGNOSTIC_NO_TRADING_AUTHORITY "
              "source_accepted=False protected_outcomes_read=0", flush=True)
        return 0 if report["requests_attempted"] == QUOTE_REQUEST_CAP else 4
    except Exception as exc:
        print(f"  STOP failure_type={type(exc).__name__}. "
              "No retries, acquisition or research promotion.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
