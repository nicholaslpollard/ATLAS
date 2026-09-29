from __future__ import annotations

"""Preview source demand; optionally acquire exact missing EOD series with hard cap."""

import argparse
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.market_calendar import get_market_calendar
from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_demand_quote_cache_v1 import (
    CACHE_REL, CONTRACT, PLAN_REL, MultiYearQuoteCacheError,
    freeze_quote_demand, run_demand_cache, _write_new,
)
from packages.data.marketdata_candidate_expansion_v1 import _read_object


def _last_complete(at: datetime):
    cal = get_market_calendar()
    days = cal.sessions_in_range(at.date() - timedelta(days=15), at.date())
    completed = [day for day in days if cal.regular_open_close(day)[1] <= at]
    if not completed:
        raise MultiYearQuoteCacheError("cannot find last fully completed market session")
    return completed[-1]


def _freeze_or_read(settings, args, asof):
    if args.plan:
        plan = _read_object(args.plan)
        return plan, args.plan, "REUSED_OPERATOR_SUPPLIED_PLAN"
    if not args.selected:
        raise MultiYearQuoteCacheError("--selected or --plan required")
    if not args.selected.is_file() or args.selected.stat().st_size > 64 * 1024 * 1024:
        raise MultiYearQuoteCacheError("selected case evidence missing/oversized")
    input_doc = _read_object(args.selected)
    if not isinstance(input_doc.get("cases"), list):
        raise MultiYearQuoteCacheError("selected file needs a cases array")
    plan = freeze_quote_demand(
        input_doc["cases"], asof_utc=asof, last_completed_session=_last_complete(asof)
    )
    settings.assert_external_storage_binding("options")
    target = settings.resolved_path(f"{PLAN_REL}_{plan['plan_fingerprint'][:16]}.json")
    if target.exists() or target.is_symlink():
        if _read_object(target) != plan:
            raise MultiYearQuoteCacheError("existing exact frozen demand plan differs")
        return plan, target, "REUSED_IDENTICAL_SOURCE_DEMAND_PLAN"
    _write_new(target, plan)
    return plan, target, "WRITTEN_NEW_SOURCE_DEMAND_PLAN"


def main() -> int:
    parser = argparse.ArgumentParser(description="ATLAS 2021-2026 on-demand EOD source cache")
    options = parser.add_mutually_exclusive_group(required=True)
    options.add_argument("--selected", type=Path, help="Accepted stock-signal selection JSON")
    options.add_argument("--plan", type=Path, help="Previously frozen exact plan on D:")
    parser.add_argument("--as-of-utc", help="Aware ISO-8601 UTC timestamp for plan freeze")
    parser.add_argument("--max-new-requests", type=int, default=0)
    parser.add_argument("--max-observed-credits", type=int, default=0)
    parser.add_argument("--user-asserted-remaining", type=int)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--min-remaining-credits", type=int, default=500,
                        help="Explicit minimum credits to retain (default 500; 0 only by choice)")
    parser.add_argument("--authorize-provider", action="store_true")
    parser.add_argument("--confirm-paid-starter", action="store_true")
    parser.add_argument("--confirm-private-internal-use", action="store_true")
    args = parser.parse_args()
    print("ATLAS 2021-2026 Exact Option EOD Quote Demand Cache V1", flush=True)
    print("  Default: ZERO provider GETs. Paid source-only and NO strategy/fill authority.", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        at = datetime.fromisoformat(args.as_of_utc) if args.as_of_utc else datetime.now(UTC)
        if at.tzinfo is None:
            raise MultiYearQuoteCacheError("as-of timestamp must be timezone-aware")
        plan, path, action = _freeze_or_read(settings, args, at)
        print(f"  plan: {action} / {path}", flush=True)
        print(f"  original case denominator: {plan['requested_case_denominator']}", flush=True)
        print(f"  unique exact source queries: {plan['unique_physical_quote_queries']}", flush=True)
        print(f"  rolling window floor: {plan['rolling_five_year_floor']}", flush=True)
        paid = args.max_new_requests > 0
        token = os.getenv("MARKETDATA_TOKEN", "") if paid else None
        report = run_demand_cache(
            settings, plan, max_new_requests=args.max_new_requests,
            max_observed_credits=args.max_observed_credits,
            user_asserted_remaining=args.user_asserted_remaining,
            authorize_provider=args.authorize_provider,
            confirm_paid_starter=args.confirm_paid_starter,
            confirm_private_internal_use=args.confirm_private_internal_use,
            token=token, workers=args.workers,
            min_remaining_credits=args.min_remaining_credits,
            progress=lambda row: print(
                "  " + " ".join(f"{k}={v}" for k, v in row.items()), flush=True
            ),
        )
        for key in (
            "status", "ineligible_original_cases", "reused_original_2022",
            "new_cache_complete", "exact_source_gaps", "pending",
            "rolling_floor_stale_pending", "current_paid_rolling_floor_et",
            "new_provider_attempts", "observed_credits",
            "last_observed_provider_remaining", "report_fingerprint",
        ):
            print(f"  {key}: {report[key]}", flush=True)
        print("  Source bytes retained on D: under subscription terms; "
              "offline replay never invokes this paid acquire command.", flush=True)
        return 0
    except (MultiYearQuoteCacheError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"MULTIYEAR QUOTE DEMAND STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  Preserve original receipts/attempts; no automatic provider retry.",
              flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
