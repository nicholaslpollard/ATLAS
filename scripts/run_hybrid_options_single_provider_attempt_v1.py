from __future__ import annotations

"""V8 guarded historical option quote provider attempt.

--demo or --requirements FILE *without* paid flags is zero-provider preview.
A real single hourly method call requires an exact frozen requirement query
ID, an existing immutable V7 reservation and BOTH explicit authorization
flags. It records a durable attempt marker before calling ThetaData, and
never silently retries after any ambiguous result.
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.hybrid_options_acquisition_reservations_v1 import (
    _adapter_status, plan_acquisition_reservations,
)
from packages.data.hybrid_options_gap_planner_v1 import (
    demo_batch, load_batch_file,
)
from packages.data.hybrid_options_provider_attempt_v1 import (
    acquire_one_hourly_source, inspect_single_attempt,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--demo", action="store_true")
    inputs.add_argument("--requirements", type=Path)
    parser.add_argument("--query-id", type=str,
                        help="Exact 64-character query identifier")
    parser.add_argument(
        "--authorize-paid-single-hourly-request",
        action="store_true",
        help="Consent to ONE provider quote-method request, not a batch",
    )
    parser.add_argument(
        "--acknowledge-no-retry-after-ambiguous-attempt",
        action="store_true",
        help="Accept that a saved attempt marker blocks automatic reattempts",
    )
    args = parser.parse_args(argv)
    requested = (
        args.authorize_paid_single_hourly_request or
        args.acknowledge_no_retry_after_ambiguous_attempt
    )
    if requested and (
        args.demo or args.requirements is None
        or not args.query_id
        or not args.authorize_paid_single_hourly_request
        or not args.acknowledge_no_retry_after_ambiguous_attempt
    ):
        parser.error(
            "paid execution requires --requirements FILE, --query-id "
            "and BOTH single-attempt authorization flags"
        )
    print("ATLAS HYBRID HISTORICAL OPTIONS SINGLE-ATTEMPT GATE V8",
          flush=True)
    print(
        "  mode=" + ("EXPLICIT_ONE_PROVIDER_ATTEMPT" if requested
                    else "OFFLINE_PREVIEW_NO_API_CALLS"),
        flush=True,
    )
    try:
        settings = load_settings(ROOT, "development")
        batch = demo_batch() if args.demo else load_batch_file(
            args.requirements
        )
        if requested:
            report = acquire_one_hourly_source(
                settings, batch, args.query_id,
                authorize_paid_single_request=True,
                acknowledge_ambiguous_request_no_retry=True,
            )
            print(
                f"  query={report['query_id']} state={report['result_state']}"
                f" source={report['stored_source']['source_id'] if report['stored_source'] else 'NONE'}",
                flush=True,
            )
            print(
                f"  provider_requests_maximum={report['provider_requests_maximum']}"
                " automatic_retry_authorized=False simulator_ready=False",
                flush=True,
            )
            return 0 if report["result_state"] == "SOURCE_ARCHIVED_DIAGNOSTIC" else 4

        overview = plan_acquisition_reservations(settings, batch)
        for item in sorted(
            overview["queries"],
            key=lambda r: (
                r["query"]["date_et"], r["query"]["symbol"],
                r["query_id"],
            ),
        ):
            if args.query_id and args.query_id != item["query_id"]:
                continue
            q = item["query"]
            if _adapter_status(q) == "HOURLY_SDK_ADAPTER_MATCH":
                state = inspect_single_attempt(
                    settings, batch, item["query_id"],
                )["state"]
            else:
                state = "EXACT_PROVIDER_ADAPTER_UNAVAILABLE_NO_API"
            print(
                f"  date={q['date_et']} symbol={q['symbol']} "
                f"interval={q['interval']} right={q['right']} "
                f"query_id={item['query_id']} state={state}",
                flush=True,
            )
        if args.query_id and not any(
            r["query_id"] == args.query_id for r in overview["queries"]
        ):
            raise ValueError("EXACT_QUERY_ID_NOT_IN_REQUIREMENTS")
        print(
            "  COMPLETE: PROVIDER_REQUESTS=0 "
            "SIMULATIONS=0 PAID_AUTHORITY=False NO_FILES_WRITTEN",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            "  BLOCKED: " + type(exc).__name__
            + "; no automated provider retry or simulation",
            flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
