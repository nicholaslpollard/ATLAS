from __future__ import annotations

"""Use one reset-day provider budget across stale tails, PIT chains and new exact quotes."""

import argparse
import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_chain_campaign_v1 import (
    MAX_NEW_REQUESTS as MAX_CHAIN_REQUESTS,
    MultiYearChainCampaignError,
    run_campaign,
)
from packages.data.multiyear_demand_quote_cache_v1 import (
    MultiYearQuoteCacheError,
    PLAN_REL,
    _write_new,
    freeze_quote_demand,
    run_demand_cache,
)
from packages.data.multiyear_option_quote_bridge_v1 import (
    MultiYearQuoteBridgeError,
    build_local_bridge,
    write_local_bridge,
)
from packages.data.multiyear_quote_tail_recovery_v1 import (
    QuoteTailRecoveryError,
    build_tail_recovery_plan,
    persist_tail_recovery_plan,
)
from scripts.refresh_multiyear_sources_after_quote_cache_v1 import main as refresh_main

ORIGINAL_PLAN = Path(
    "data/options/manifests/"
    "multiyear_demand_quote_v1_dbe759955e48946b.json"
)


def _load_runtime():
    """Load the repository-root .env before resolving provider credentials."""
    settings = load_settings(ROOT, "development")
    token = os.getenv("MARKETDATA_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "MARKETDATA_TOKEN is not configured in the ATLAS root .env or process environment"
        )
    return settings, token


def _remaining_after(
    asserted: int, observed_remaining: object, observed_credits: object,
) -> int:
    if type(observed_remaining) is int:
        return min(asserted, max(0, observed_remaining))
    if type(observed_credits) is int:
        return max(0, asserted - observed_credits)
    return asserted


def _persist_quote_plan(settings, plan: dict) -> Path:
    path = settings.resolved_path(
        f"{PLAN_REL}_{plan['plan_fingerprint'][:16]}.json"
    )
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or _read_object(path) != plan:
            raise MultiYearQuoteBridgeError("existing exact quote plan differs")
    else:
        _write_new(path, plan)
    return path


def _paid_quote_cache(
    settings, plan: dict, *,
    token: str, asserted_remaining: int, max_requests: int,
    workers: int,
    prefix: str,
) -> dict:
    if max_requests <= 0 or asserted_remaining <= 0:
        return run_demand_cache(settings, plan)
    # Two potential credits are reserved per in-flight request. The observed
    # provider header remains the hard authority after the first GET.
    max_credits = min(asserted_remaining, max_requests * 2)
    return run_demand_cache(
        settings, plan,
        max_new_requests=max_requests,
        max_observed_credits=max_credits,
        user_asserted_remaining=asserted_remaining,
        authorize_provider=True,
        confirm_paid_starter=True,
        confirm_private_internal_use=True,
        token=token,
        workers=workers,
        min_remaining_credits=0,
        progress=lambda row: print(
            f"  {prefix}_" + " ".join(f"{k}={v}" for k, v in row.items()),
            flush=True,
        ),
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "ATLAS reset-day multiyear source advance: clipped 2021 tails -> "
            "year-balanced PIT chains -> fresh exact quote histories -> offline refresh"
        )
    )
    p.add_argument("--original-plan", type=Path, default=ORIGINAL_PLAN)
    p.add_argument("--user-asserted-daily-remaining", type=int, required=True)
    p.add_argument("--quote-workers", type=int, default=8)
    p.add_argument("--chain-workers", type=int, default=16)
    p.add_argument("--native-workers", type=int, default=3)
    p.add_argument("--max-tail-requests", type=int, default=487)
    p.add_argument("--max-chain-requests", type=int, default=MAX_CHAIN_REQUESTS)
    p.add_argument("--max-new-quote-requests", type=int, default=10000)
    p.add_argument("--skip-tail", action="store_true")
    p.add_argument("--skip-chains", action="store_true")
    p.add_argument("--skip-new-quotes", action="store_true")
    p.add_argument("--skip-offline-refresh", action="store_true")
    p.add_argument("--authorize-provider", action="store_true")
    p.add_argument("--confirm-paid-starter", action="store_true")
    p.add_argument("--confirm-private-internal-use", action="store_true")
    a = p.parse_args(argv)

    print("ATLAS RESET-DAY MULTI-SOURCE ADVANCE V1 — SUPERSEDED", flush=True)
    print(
        "  No provider call is permitted from this entrypoint. Use "
        "scripts/run_multiyear_reset_day_source_sweep_v1.py, which preserves "
        "accepted exact quote windows and adds only newly PIT-selectable demand.",
        flush=True,
    )
    return 3

    print("ATLAS RESET-DAY MULTI-SOURCE ADVANCE V1", flush=True)
    print(
        "  Order: current exact cache -> clipped 2021 tails -> PIT chains -> "
        "fresh contract selection -> newly exposed exact quote histories -> "
        "zero-provider simulator source rebuild.",
        flush=True,
    )
    try:
        if (
            type(a.user_asserted_daily_remaining) is not int
            or not 1 <= a.user_asserted_daily_remaining <= 10000
            or type(a.max_tail_requests) is not int or not 0 <= a.max_tail_requests <= 10000
            or type(a.max_chain_requests) is not int
            or not 0 <= a.max_chain_requests <= MAX_CHAIN_REQUESTS
            or type(a.max_new_quote_requests) is not int
            or not 0 <= a.max_new_quote_requests <= 10000
            or not 1 <= a.quote_workers <= 24
            or not 1 <= a.chain_workers <= 24
            or not 1 <= a.native_workers <= 24
        ):
            raise ValueError("invalid reset-day explicit budget/concurrency bound")
        if not (
            a.authorize_provider
            and a.confirm_paid_starter
            and a.confirm_private_internal_use
        ):
            raise ValueError("all three provider authorization confirmations required")
        settings, token = _load_runtime()
        settings.assert_external_storage_binding("options")
        original = _read_object(a.original_plan)
        remaining = a.user_asserted_daily_remaining
        now = datetime.now(UTC)

        print("  stage=VERIFY_ORIGINAL_EXACT_CACHE_ZERO_GET", flush=True)
        original_census = run_demand_cache(
            settings, original,
            progress=lambda row: print(
                "    " + " ".join(f"{k}={v}" for k, v in row.items()), flush=True
            ),
        )
        print(
            f"    original_complete={original_census['new_cache_complete']} "
            f"original_2022_reused={original_census['reused_original_2022']} "
            f"original_pending={original_census['pending']}",
            flush=True,
        )

        if not a.skip_tail and original_census["pending"] and remaining:
            print("  stage=RECOVER_STILL_ENTITLED_2021_TAILS", flush=True)
            recovery = build_tail_recovery_plan(
                original, original_census, asof_utc=now,
            )
            recovery_path, recovery_action = persist_tail_recovery_plan(
                settings, recovery
            )
            pending_tail = recovery["distinct_recovery_queries"]
            allowed_tail = min(pending_tail, a.max_tail_requests)
            print(
                f"    recovery_plan={recovery_action} / {recovery_path}",
                flush=True,
            )
            print(
                f"    current_floor_et={recovery['rolling_five_year_floor']} "
                f"recoverable={pending_tail} "
                f"expired_before_floor={recovery['expired_before_current_floor_queries']}",
                flush=True,
            )
            tail = _paid_quote_cache(
                settings, recovery,
                token=token,
                asserted_remaining=remaining,
                max_requests=allowed_tail,
                workers=a.quote_workers,
                prefix="tail",
            )
            remaining = _remaining_after(
                remaining,
                tail.get("last_observed_provider_remaining"),
                tail.get("observed_credits"),
            )
            print(
                f"    tail_complete={tail['new_cache_complete']} "
                f"tail_gaps={tail['exact_source_gaps']} "
                f"tail_pending={tail['pending']} "
                f"tail_credits={tail['observed_credits']} "
                f"provider_remaining={remaining}",
                flush=True,
            )
        else:
            print("  stage=RECOVER_STILL_ENTITLED_2021_TAILS SKIPPED", flush=True)

        if not a.skip_chains and remaining and a.max_chain_requests:
            print("  stage=YEAR_BALANCED_PIT_CHAIN_ACQUISITION", flush=True)
            chain_budget = min(remaining, a.max_chain_requests * 2)
            chains = run_campaign(
                settings,
                max_new_requests=a.max_chain_requests,
                max_observed_credits=chain_budget,
                workers=a.chain_workers,
                min_remaining_credits=0,
                authorize_provider_reads=True,
                confirm_paid_starter=True,
                confirm_private_internal_use=True,
                token=token,
                progress=lambda row: print(
                    "    chain_" + " ".join(f"{k}={v}" for k, v in row.items()),
                    flush=True,
                ),
            )
            remaining = _remaining_after(
                remaining,
                chains.get("last_reported_remaining"),
                chains.get("observed_credits"),
            )
            print(
                f"    chain_status={chains['status']} "
                f"chain_new_complete={chains['new_complete']} "
                f"chain_exact_no_data={chains['exact_no_data']} "
                f"chain_credits={chains['observed_credits']} "
                f"chain_pending_eligible={chains['pending_eligible']} "
                f"provider_remaining={remaining}",
                flush=True,
            )
        else:
            print("  stage=YEAR_BALANCED_PIT_CHAIN_ACQUISITION SKIPPED", flush=True)

        print("  stage=REBUILD_PIT_CONTRACT_SELECTION_AND_EXACT_QUOTE_PLAN_ZERO_GET",
              flush=True)
        selected = build_local_bridge(settings, right="both")
        selection_path, selection_action = write_local_bridge(settings, selected)
        frozen_asof = datetime.fromisoformat(original["asof_utc"])
        frozen_last_complete = date.fromisoformat(original["last_completed_session"])
        fresh_plan = freeze_quote_demand(
            selected["cases"],
            asof_utc=frozen_asof,
            last_completed_session=frozen_last_complete,
        )
        fresh_plan_path = _persist_quote_plan(settings, fresh_plan)
        fresh_preview = run_demand_cache(settings, fresh_plan)
        print(
            f"    selection={selection_action} / {selection_path}",
            flush=True,
        )
        print(
            f"    selected_case_rights={selected['selected_case_right_memberships']} "
            f"unique_exact_histories={fresh_plan['unique_physical_quote_queries']} "
            f"already_complete={fresh_preview['new_cache_complete']} "
            f"original_2022_reused={fresh_preview['reused_original_2022']} "
            f"pending_new_quotes={fresh_preview['pending']}",
            flush=True,
        )
        print(f"    fresh_quote_plan={fresh_plan_path}", flush=True)
        print(f"    fresh_quote_plan_fingerprint={fresh_plan['plan_fingerprint']}",
              flush=True)
        print(
            f"    frozen_research_asof={fresh_plan['asof_utc']} "
            f"frozen_source_floor={fresh_plan['rolling_five_year_floor']} "
            f"current_provider_day={now.date().isoformat()}",
            flush=True,
        )

        # The rebuilt plan is intentionally frozen to the original research
        # date. Any exact request that has rolled out by today is recovered only
        # through a separate clipped-tail request with its own physical identity.
        if not a.skip_tail and fresh_preview["pending"] and remaining:
            print("  stage=RECOVER_FRESH_PLAN_STALE_TAILS", flush=True)
            fresh_recovery = build_tail_recovery_plan(
                fresh_plan, fresh_preview, asof_utc=now,
            )
            frp, fra = persist_tail_recovery_plan(settings, fresh_recovery)
            fresh_tail_requests = min(
                fresh_recovery["distinct_recovery_queries"],
                a.max_tail_requests,
            )
            print(
                f"    fresh_recovery_plan={fra} / {frp} "
                f"recoverable={fresh_recovery['distinct_recovery_queries']} "
                f"expired={fresh_recovery['expired_before_current_floor_queries']}",
                flush=True,
            )
            if fresh_tail_requests:
                fresh_tail = _paid_quote_cache(
                    settings, fresh_recovery,
                    token=token,
                    asserted_remaining=remaining,
                    max_requests=fresh_tail_requests,
                    workers=a.quote_workers,
                    prefix="fresh_tail",
                )
                remaining = _remaining_after(
                    remaining,
                    fresh_tail.get("last_observed_provider_remaining"),
                    fresh_tail.get("observed_credits"),
                )
                print(
                    f"    fresh_tail_complete={fresh_tail['new_cache_complete']} "
                    f"fresh_tail_gaps={fresh_tail['exact_source_gaps']} "
                    f"fresh_tail_pending={fresh_tail['pending']} "
                    f"fresh_tail_credits={fresh_tail['observed_credits']} "
                    f"provider_remaining={remaining}",
                    flush=True,
                )
        final_quote = fresh_preview
        if (
            not a.skip_new_quotes
            and fresh_preview["pending"]
            and remaining
            and a.max_new_quote_requests
        ):
            print("  stage=ACQUIRE_NEWLY_EXPOSED_EXACT_OPTION_QUOTES", flush=True)
            allowed = min(
                fresh_preview["pending"], a.max_new_quote_requests
            )
            final_quote = _paid_quote_cache(
                settings, fresh_plan,
                token=token,
                asserted_remaining=remaining,
                max_requests=allowed,
                workers=a.quote_workers,
                prefix="fresh_quote",
            )
            remaining = _remaining_after(
                remaining,
                final_quote.get("last_observed_provider_remaining"),
                final_quote.get("observed_credits"),
            )
            print(
                f"    fresh_quote_complete={final_quote['new_cache_complete']} "
                f"fresh_quote_gaps={final_quote['exact_source_gaps']} "
                f"fresh_quote_pending={final_quote['pending']} "
                f"fresh_quote_credits={final_quote['observed_credits']} "
                f"provider_remaining={remaining}",
                flush=True,
            )
        else:
            print("  stage=ACQUIRE_NEWLY_EXPOSED_EXACT_OPTION_QUOTES SKIPPED", flush=True)

        if not a.skip_offline_refresh:
            print("  stage=ZERO_PROVIDER_SIMULATOR_SOURCE_REFRESH", flush=True)
            rc = refresh_main([
                "--selection", str(selection_path),
                "--plan", str(fresh_plan_path),
                "--native-workers", str(a.native_workers),
            ])
            if rc != 0:
                raise RuntimeError("offline simulator source refresh stopped")
        else:
            print("  stage=ZERO_PROVIDER_SIMULATOR_SOURCE_REFRESH SKIPPED", flush=True)

        print("ATLAS RESET-DAY SOURCE ADVANCE COMPLETE", flush=True)
        print(f"  provider_remaining_last_observed={remaining}", flush=True)
        print(f"  final_selection={selection_path}", flush=True)
        print(f"  final_quote_plan={fresh_plan_path}", flush=True)
        print(
            "  No provider request was used for stock daily CLOSE verification, "
            "replay P&L, synthetic fills or strategy promotion.",
            flush=True,
        )
        return 0
    except (
        MultiYearChainCampaignError,
        MultiYearQuoteCacheError,
        MultiYearQuoteBridgeError,
        QuoteTailRecoveryError,
        OSError, ValueError, TypeError, KeyError, RuntimeError,
    ) as exc:
        print(
            f"RESET-DAY SOURCE ADVANCE STOPPED: {type(exc).__name__}: {exc}",
            flush=True,
        )
        print(
            "  Preserve all attempts, raw bodies, receipts and manifests. "
            "Do not auto-retry an uncertain paid request.",
            flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
