from __future__ import annotations

"""Recover only currently entitled suffixes of stale 2021 exact quote requests."""

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_demand_quote_cache_v1 import (
    MultiYearQuoteCacheError, run_demand_cache,
)
from packages.data.multiyear_quote_tail_recovery_v1 import (
    QuoteTailRecoveryError, build_tail_recovery_plan,
    persist_tail_recovery_plan,
)

PLAN = Path(
    "data/options/manifests/"
    "multiyear_demand_quote_v1_dbe759955e48946b.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ATLAS stale 2021 exact option quote tail recovery"
    )
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--as-of-utc",
                        help="Aware ISO timestamp; defaults to current UTC")
    parser.add_argument("--max-new-requests", type=int, default=0)
    parser.add_argument("--max-observed-credits", type=int, default=0)
    parser.add_argument("--user-asserted-remaining", type=int)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--min-remaining-credits", type=int, default=500)
    parser.add_argument("--authorize-provider", action="store_true")
    parser.add_argument("--confirm-paid-starter", action="store_true")
    parser.add_argument("--confirm-private-internal-use", action="store_true")
    args = parser.parse_args()

    print("ATLAS STALE 2021 OPTION QUOTE TAIL RECOVERY V1", flush=True)
    print("  Original exact requests remain immutable; only entitled suffixes may be fetched.",
          flush=True)
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        original = _read_object(args.plan)
        original_census = run_demand_cache(
            settings, original,
            progress=lambda row: print(
                "  original_" + " ".join(f"{k}={v}" for k, v in row.items()),
                flush=True,
            ),
        )
        at = (
            datetime.fromisoformat(args.as_of_utc)
            if args.as_of_utc else datetime.now(UTC)
        )
        if at.tzinfo is None:
            raise QuoteTailRecoveryError("as-of timestamp must be timezone-aware")
        recovery = build_tail_recovery_plan(
            original, original_census, asof_utc=at,
        )
        plan_path, plan_action = persist_tail_recovery_plan(settings, recovery)
        print(f"  original_plan_fingerprint={original['plan_fingerprint']}", flush=True)
        print(f"  original_pending_queries={recovery['original_pending_queries']}", flush=True)
        print(f"  current_floor_et={recovery['rolling_five_year_floor']}", flush=True)
        print(f"  original_stale_queries={recovery['original_stale_queries']}", flush=True)
        print(f"  recoverable_original_queries={recovery['recoverable_stale_queries']}", flush=True)
        print(f"  distinct_recovery_queries={recovery['distinct_recovery_queries']}", flush=True)
        print(f"  expired_before_floor={recovery['expired_before_current_floor_queries']}", flush=True)
        print(f"  recovery_plan={plan_action} / {plan_path}", flush=True)
        print(f"  recovery_plan_fingerprint={recovery['plan_fingerprint']}", flush=True)

        paid = args.max_new_requests > 0
        token = os.getenv("MARKETDATA_TOKEN", "") if paid else None
        report = run_demand_cache(
            settings, recovery,
            max_new_requests=args.max_new_requests,
            max_observed_credits=args.max_observed_credits,
            user_asserted_remaining=args.user_asserted_remaining,
            workers=args.workers,
            min_remaining_credits=args.min_remaining_credits,
            authorize_provider=args.authorize_provider,
            confirm_paid_starter=args.confirm_paid_starter,
            confirm_private_internal_use=args.confirm_private_internal_use,
            token=token,
            progress=lambda row: print(
                "  recovery_" + " ".join(f"{k}={v}" for k, v in row.items()),
                flush=True,
            ),
        )
        for key in (
            "status", "new_cache_complete", "exact_source_gaps", "pending",
            "rolling_floor_stale_pending", "new_provider_attempts",
            "observed_credits", "last_observed_provider_remaining",
            "report_fingerprint",
        ):
            print(f"  recovery_{key}={report[key]}", flush=True)
        print(
            "  Missing 2021 prefix remains explicit. No historical fill, P&L, "
            "contract-deliverable or synchronized-clock authority.",
            flush=True,
        )
        return 0
    except (QuoteTailRecoveryError, MultiYearQuoteCacheError, OSError,
            ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(
            f"TAIL RECOVERY STOPPED: {type(exc).__name__}: {exc}", flush=True
        )
        print(
            "  Preserve original and recovery receipts/attempts; do not retry an "
            "uncertain paid request automatically.",
            flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
