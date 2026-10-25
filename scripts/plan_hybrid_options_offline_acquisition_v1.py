from __future__ import annotations

"""V7 zero-provider historical quote demand reconciliation and reservation.

Default is read-only. --reserve explicitly writes bounded immutable NO_CALL
intent receipts, but NEVER invokes the ThetaData SDK, opens broker interfaces,
fetches market data, marks a provider attempt, or starts a simulation.
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.hybrid_options_acquisition_reservations_v1 import (
    DEFAULT_BATCH_MIB, DEFAULT_PER_QUERY_MIB,
    plan_acquisition_reservations,
)
from packages.data.hybrid_options_gap_planner_v1 import (
    demo_batch, load_batch_file,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--demo", action="store_true")
    inputs.add_argument("--requirements", type=Path)
    parser.add_argument(
        "--reserve", action="store_true",
        help="Explicitly write immutable NO_CALL reservations for eligible queries",
    )
    parser.add_argument(
        "--per-request-mib", type=int, default=DEFAULT_PER_QUERY_MIB,
    )
    parser.add_argument(
        "--batch-budget-mib", type=int, default=DEFAULT_BATCH_MIB,
    )
    args = parser.parse_args(argv)
    print("ATLAS HYBRID OPTIONS OFFLINE REQUEST QUEUE V7", flush=True)
    print(
        "  SOURCE_ONLY read V4/V6 verified gzip; NO API calls, "
        "broker requests or simulator runs",
        flush=True,
    )
    try:
        settings = load_settings(ROOT, "development")
        batch = demo_batch() if args.demo else load_batch_file(args.requirements)
        report = plan_acquisition_reservations(
            settings, batch, reserve=args.reserve,
            per_request_mib=args.per_request_mib,
            batch_budget_mib=args.batch_budget_mib,
        )
        print(
            f"  uses={report['requirement_uses']} "
            f"unique_queries={report['unique_queries']} "
            f"deduplicated_uses={report['deduplicated_uses']}",
            flush=True,
        )
        print(
            f"  local_verified={report['verified_local_queries']} "
            f"missing={report['missing_exact_queries']} "
            f"adapter_blocked={report['blocked_adapter_queries']} "
            f"budget_deferred={report['deferred_budget_queries']}",
            flush=True,
        )
        s = report["storage"]
        print(
            f"  storage={s['storage_mode']} "
            f"free_gib={s['disk_free_gib']:.2f} "
            f"hybrid_gib={s['hybrid_source_and_catalog_gib']:.5f} "
            f"other_candidate_gib={s['other_candidate_cache_gib']:.3f} "
            f"safe_available_gib={s['remaining_safe_unreserved_gib']:.3f}",
            flush=True,
        )
        print(
            f"  per_query_mib={args.per_request_mib} "
            f"batch_budget_mib={args.batch_budget_mib} "
            f"newly_reservable={report['newly_reservable_queries']} "
            f"newly_reserved={report['new_reservations']}",
            flush=True,
        )
        for item in sorted(
            report["queries"], key=lambda r: (
                r["query"]["date_et"], r["query"]["symbol"], r["query"]["interval"]
            ),
        ):
            q = item["query"]
            print(
                f"  {q['date_et']} {q['symbol']} {q['interval']} "
                f"{q['right']} state={item['status']} "
                f"sources={len(item['verified_sources'])} "
                f"uses={len(item['uses'])}",
                flush=True,
            )
        print(f"  report_fingerprint={report['report_fingerprint']}", flush=True)
        print(
            "  COMPLETE: NO_PROVIDER_ATTEMPTS_NO_SIMULATION "
            "provider_requests=0 broker_requests=0 simulations_run=0 "
            "paid_authority=False",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            "  BLOCKED: " + type(exc).__name__
            + "; no provider fallback, automatic retry or simulation",
            flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
