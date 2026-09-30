from __future__ import annotations

"""Spend one reset-day budget across missing 2021 tails, PIT chains and new quote histories.

Sequence is deliberately local-cache-first and causal:
1) recover still-entitled suffixes of old exact 2021 quote requests;
2) fill missing PIT chain sources with a bounded year-balanced campaign;
3) rebuild structural option identities and ADD only newly selected quote demand;
4) spend the reserved/remaining budget on those new exact quote histories;
5) rebuild the signed source casebook and simulator proof demand offline.

No stage authorizes a historical fill, 09:35 backfill, account P&L, deliverable
assumption, protected-2026 replay or strategy promotion.
"""

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.market_calendar import get_market_calendar
from packages.core.settings import load_settings
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_additive_quote_plan_v1 import (
    build_additive_quote_plan, persist_additive_quote_plan,
)
from packages.data.multiyear_chain_campaign_v1 import (
    MAX_NEW_REQUESTS as MAX_CHAIN_REQUESTS, run_campaign,
)
from packages.data.multiyear_demand_quote_cache_v1 import (
    MAX_REQUESTS as MAX_QUOTE_REQUESTS, run_demand_cache,
)
from packages.data.multiyear_native_eod_close_source_v1 import (
    persist_native_eod_closes, resolve_native_eod_closes,
)
from packages.data.multiyear_observed_option_quote_timeline_v1 import (
    build_observed_option_timeline, local_verified_quote_reader,
    persist_observed_option_timeline,
)
from packages.data.multiyear_option_quote_bridge_v1 import (
    NATIVE_REL, build_local_bridge, write_local_bridge,
)
from packages.data.multiyear_option_quote_reuse_handoff_v1 import (
    assemble_quote_reuse_handoff, persist_quote_reuse_handoff,
)
from packages.data.multiyear_option_stock_eod_preflight_v1 import (
    build_native_eod_needs, persist_source_needs,
)
from packages.data.multiyear_quote_tail_recovery_v1 import (
    build_recovery_overlay, build_tail_recovery_plan,
    persist_recovery_overlay, persist_tail_recovery_plan,
)
from packages.data.multiyear_verified_stock_option_source_casebook_v1 import (
    build_verified_source_casebook, persist_source_casebook,
)
from packages.simulation.multiyear_account_readiness_v1 import (
    build_replay_readiness, persist_replay_readiness,
)
from packages.simulation.multiyear_historical_execution_requirements_v1 import (
    build_execution_proof_demand, persist_execution_proof_demand,
)

BASE_SELECTION = Path(
    "data/options/manifests/"
    "multiyear_pit_selected_option_quotes_v1_3fa478312734f9c2.json"
)
BASE_PLAN = Path(
    "data/options/manifests/"
    "multiyear_demand_quote_v1_dbe759955e48946b.json"
)
SUCCESS_CHAIN = {
    "COMPLETE_ELIGIBLE_SOURCE_WORK",
    "PARTIAL_REQUEST_LIMIT_REACHED",
    "PARTIAL_OBSERVED_CREDIT_BUDGET",
    "PARTIAL_PROVIDER_CREDIT_FLOOR",
    "PARTIAL_D_STORAGE_BUDGET",
}


def _last_complete(at: datetime):
    cal = get_market_calendar()
    days = cal.sessions_in_range(at.date() - timedelta(days=15), at.date())
    completed = [day for day in days if cal.regular_open_close(day)[1] <= at]
    if not completed:
        raise ValueError("cannot identify a fully completed market session")
    return completed[-1]


def _progress(prefix: str):
    return lambda row: print(
        "  " + prefix + " " + " ".join(f"{k}={v}" for k, v in row.items()),
        flush=True,
    )


def _available_assertion(
    user_asserted_remaining: int,
    spent: int,
    reported_remaining: int | None,
) -> int:
    remaining = max(0, user_asserted_remaining - spent)
    if reported_remaining is not None:
        remaining = min(remaining, reported_remaining)
    return remaining


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ATLAS reset-day multiyear source acquisition and offline simulator refresh"
    )
    parser.add_argument("--base-selection", type=Path, default=BASE_SELECTION)
    parser.add_argument("--base-plan", type=Path, default=BASE_PLAN)
    parser.add_argument("--as-of-utc",
                        help="Aware timestamp; defaults to current UTC")
    parser.add_argument("--max-total-observed-credits", type=int, default=0,
                        help="Hard cumulative ATLAS credit ceiling for this command")
    parser.add_argument("--user-asserted-remaining", type=int)
    parser.add_argument("--reserve-for-new-exact-quotes", type=int, default=1500,
                        help="Budget withheld from chain acquisition, then available to new exact histories")
    parser.add_argument("--min-remaining-credits", type=int, default=0)
    parser.add_argument("--quote-workers", type=int, default=8)
    parser.add_argument("--chain-workers", type=int, default=16)
    parser.add_argument("--native-workers", type=int, default=3)
    parser.add_argument("--max-chain-requests", type=int, default=MAX_CHAIN_REQUESTS)
    parser.add_argument("--authorize-provider", action="store_true")
    parser.add_argument("--confirm-paid-starter", action="store_true")
    parser.add_argument("--confirm-private-internal-use", action="store_true")
    args = parser.parse_args()

    live = args.max_total_observed_credits > 0
    if (
        type(args.max_total_observed_credits) is not int
        or not 0 <= args.max_total_observed_credits <= 10000
        or type(args.reserve_for_new_exact_quotes) is not int
        or not 0 <= args.reserve_for_new_exact_quotes <= args.max_total_observed_credits
        or type(args.min_remaining_credits) is not int
        or not 0 <= args.min_remaining_credits <= 10000
        or type(args.max_chain_requests) is not int
        or not 0 <= args.max_chain_requests <= MAX_CHAIN_REQUESTS
    ):
        print("RESET-DAY SWEEP STOPPED: invalid budget/request ceilings", flush=True)
        return 3
    if live and not (
        args.authorize_provider
        and args.confirm_paid_starter
        and args.confirm_private_internal_use
        and type(args.user_asserted_remaining) is int
        and args.user_asserted_remaining
            >= args.max_total_observed_credits + args.min_remaining_credits
    ):
        print(
            "RESET-DAY SWEEP STOPPED: live run requires all paid confirmations "
            "and sufficient user-asserted remaining credits",
            flush=True,
        )
        return 3
    if not live and any((
        args.authorize_provider,
        args.confirm_paid_starter,
        args.confirm_private_internal_use,
    )):
        print("RESET-DAY SWEEP STOPPED: paid flags require a positive total budget",
              flush=True)
        return 3

    print("ATLAS MULTIYEAR RESET-DAY SOURCE SWEEP V1", flush=True)
    print(
        "  Cache-first; cumulative observed-credit bound spans tail recovery, "
        "PIT chains and newly selected exact quote histories.",
        flush=True,
    )
    try:
        at = datetime.fromisoformat(args.as_of_utc) if args.as_of_utc else datetime.now(UTC)
        if at.tzinfo is None:
            raise ValueError("as-of timestamp must be timezone-aware")
        last_complete = _last_complete(at)
        settings = load_settings(ROOT, "development")
        for category in ("options", "research_evidence"):
            settings.assert_external_storage_binding(category)
        token = os.getenv("MARKETDATA_TOKEN", "") if live else None
        if live and not token.strip():
            raise ValueError("MARKETDATA_TOKEN is not configured")

        base_selection = _read_object(args.base_selection)
        base_plan = _read_object(args.base_plan)
        spent = 0
        provider_remaining: int | None = None

        print("  stage=BASE_EXACT_CACHE_CENSUS_ZERO_GET", flush=True)
        base_census = run_demand_cache(
            settings, base_plan, progress=_progress("base_cache"),
        )
        print(
            f"    complete={base_census['new_cache_complete']} "
            f"reused_2022={base_census['reused_original_2022']} "
            f"pending={base_census['pending']}",
            flush=True,
        )

        print("  stage=2021_CLIPPED_TAIL_RECOVERY", flush=True)
        recovery = build_tail_recovery_plan(
            base_plan, base_census, asof_utc=at,
        )
        rp, rps = persist_tail_recovery_plan(settings, recovery)
        print(
            f"    current_floor_et={recovery['rolling_five_year_floor']} "
            f"stale={recovery['original_stale_queries']} "
            f"recoverable={recovery['distinct_recovery_queries']} "
            f"expired={recovery['expired_before_current_floor_queries']}",
            flush=True,
        )
        print(f"    recovery_plan={rps} / {rp}", flush=True)
        recovery_report = run_demand_cache(settings, recovery)
        if live and recovery_report["pending"] > 0:
            tail_requests = min(
                recovery["distinct_recovery_queries"], MAX_QUOTE_REQUESTS
            )
            tail_credit_cap = min(
                args.max_total_observed_credits - spent,
                max(1, tail_requests * 2),
            )
            if tail_requests and tail_credit_cap:
                recovery_report = run_demand_cache(
                    settings, recovery,
                    max_new_requests=tail_requests,
                    max_observed_credits=tail_credit_cap,
                    user_asserted_remaining=_available_assertion(
                        args.user_asserted_remaining, spent, provider_remaining
                    ),
                    authorize_provider=True,
                    confirm_paid_starter=True,
                    confirm_private_internal_use=True,
                    token=token,
                    workers=args.quote_workers,
                    min_remaining_credits=args.min_remaining_credits,
                    progress=_progress("tail_get"),
                )
                spent += recovery_report["observed_credits"]
                if recovery_report["last_observed_provider_remaining"] is not None:
                    provider_remaining = recovery_report[
                        "last_observed_provider_remaining"
                    ]
        print(
            f"    tail_status={recovery_report['status']} "
            f"tail_complete={recovery_report['new_cache_complete']} "
            f"tail_pending={recovery_report['pending']} "
            f"cumulative_observed_credits={spent}",
            flush=True,
        )

        print("  stage=YEAR_BALANCED_PIT_CHAIN_ACQUISITION", flush=True)
        chain_budget = max(
            0,
            args.max_total_observed_credits
            - spent
            - args.reserve_for_new_exact_quotes,
        )
        if live and chain_budget > 0 and args.max_chain_requests > 0:
            chain = run_campaign(
                settings,
                max_new_requests=args.max_chain_requests,
                max_observed_credits=chain_budget,
                workers=args.chain_workers,
                min_remaining_credits=args.min_remaining_credits,
                authorize_provider_reads=True,
                confirm_paid_starter=True,
                confirm_private_internal_use=True,
                token=token,
                progress=_progress("chain_get"),
            )
            if chain["status"] not in SUCCESS_CHAIN:
                raise RuntimeError(
                    f"chain campaign stopped with review-required status {chain['status']}"
                )
            spent += chain["observed_credits"]
            if chain.get("last_reported_remaining") is not None:
                provider_remaining = chain["last_reported_remaining"]
        else:
            chain = run_campaign(settings)
        print(
            f"    chain_status={chain['status']} "
            f"new_chain_complete={chain['new_complete']} "
            f"chain_exact_no_data={chain['exact_no_data']} "
            f"chain_pending_eligible={chain['pending_eligible']} "
            f"rolled_out={chain['rolled_out_of_current_provider_window']} "
            f"cumulative_observed_credits={spent}",
            flush=True,
        )

        print("  stage=REBUILD_PIT_SELECTION_AND_ADDITIVE_QUOTE_PLAN_ZERO_GET", flush=True)
        expanded_selection = build_local_bridge(settings, right="both")
        selection_path, selection_action = write_local_bridge(
            settings, expanded_selection
        )
        additive = build_additive_quote_plan(
            base_selection, base_plan, expanded_selection,
            asof_utc=at, last_completed_session=last_complete,
        )
        if additive["plan_fingerprint"] == base_plan["plan_fingerprint"]:
            plan_path = args.base_plan
            plan_action = "REUSED_UNCHANGED_BASE_QUOTE_PLAN"
        else:
            plan_path, plan_action = persist_additive_quote_plan(settings, additive)
        print(f"    expanded_selection={selection_action} / {selection_path}", flush=True)
        print(
            f"    selected_before={base_selection['selected_case_right_memberships']} "
            f"selected_now={expanded_selection['selected_case_right_memberships']} "
            f"new_selected={expanded_selection['selected_case_right_memberships'] - base_selection['selected_case_right_memberships']}",
            flush=True,
        )
        print(f"    additive_quote_plan={plan_action} / {plan_path}", flush=True)
        if additive.get("additive_contract"):
            print(
                f"    base_physical_queries={additive['base_physical_quote_queries']} "
                f"added_physical_queries={additive['added_physical_quote_queries']} "
                f"total_physical_queries={additive['unique_physical_quote_queries']}",
                flush=True,
            )

        expanded_census = run_demand_cache(
            settings, additive, progress=_progress("expanded_cache"),
        )
        print(
            f"    expanded_cache_complete={expanded_census['new_cache_complete']} "
            f"expanded_reused_2022={expanded_census['reused_original_2022']} "
            f"expanded_pending={expanded_census['pending']}",
            flush=True,
        )

        print("  stage=NEWLY_SELECTED_EXACT_QUOTE_ACQUISITION", flush=True)
        quote_budget = max(0, args.max_total_observed_credits - spent)
        if live and quote_budget > 0 and expanded_census["pending"] > 0:
            asserted_now = _available_assertion(
                args.user_asserted_remaining, spent, provider_remaining
            )
            if asserted_now >= quote_budget + args.min_remaining_credits:
                expanded_paid = run_demand_cache(
                    settings, additive,
                    max_new_requests=MAX_QUOTE_REQUESTS,
                    max_observed_credits=quote_budget,
                    user_asserted_remaining=asserted_now,
                    authorize_provider=True,
                    confirm_paid_starter=True,
                    confirm_private_internal_use=True,
                    token=token,
                    workers=args.quote_workers,
                    min_remaining_credits=args.min_remaining_credits,
                    progress=_progress("expanded_quote_get"),
                )
                spent += expanded_paid["observed_credits"]
                if expanded_paid["last_observed_provider_remaining"] is not None:
                    provider_remaining = expanded_paid[
                        "last_observed_provider_remaining"
                    ]
        expanded_census = run_demand_cache(
            settings, additive, progress=_progress("expanded_final_cache"),
        )
        print(
            f"    final_exact_complete={expanded_census['new_cache_complete']} "
            f"final_reused_2022={expanded_census['reused_original_2022']} "
            f"final_exact_gaps={expanded_census['exact_source_gaps']} "
            f"final_pending={expanded_census['pending']} "
            f"cumulative_observed_credits={spent}",
            flush=True,
        )
        if spent > args.max_total_observed_credits:
            raise RuntimeError("cumulative observed credit ceiling exceeded")

        print("  stage=BUILD_CURRENT_RECOVERY_OVERLAY_ZERO_GET", flush=True)
        current_recovery = build_tail_recovery_plan(
            additive, expanded_census, asof_utc=at,
        )
        crp, crps = persist_tail_recovery_plan(settings, current_recovery)
        current_recovery_census = run_demand_cache(settings, current_recovery)
        overlay = build_recovery_overlay(
            additive, current_recovery, current_recovery_census,
        )
        op, ops = persist_recovery_overlay(settings, overlay)
        print(f"    recovery_plan={crps} / {crp}", flush=True)
        print(
            f"    overlay_complete={overlay['complete_recovery_queries']} "
            f"overlay_gaps={overlay['recovery_query_gaps']} "
            f"overlay_pending={overlay['pending_recovery_queries']}",
            flush=True,
        )
        print(f"    recovery_overlay={ops} / {op}", flush=True)

        print("  stage=FULL_OFFLINE_SOURCE_AND_SIMULATOR_PROOF_REFRESH", flush=True)
        handoff = assemble_quote_reuse_handoff(
            expanded_selection, additive, expanded_census,
            recovery_overlay=overlay,
        )
        hp, hps = persist_quote_reuse_handoff(settings, handoff)
        timeline = build_observed_option_timeline(
            expanded_selection, additive, handoff,
            read_verified_observations=local_verified_quote_reader(
                settings, additive
            ),
        )
        tp, tps = persist_observed_option_timeline(settings, timeline)
        native = _read_object(settings.resolved_path(NATIVE_REL))
        needs = build_native_eod_needs(native, expanded_selection, timeline)
        np, nps = persist_source_needs(settings, needs)
        closes = resolve_native_eod_closes(
            settings, native, needs, workers=args.native_workers,
            progress=_progress("native_verify"),
        )
        cp, cps = persist_native_eod_closes(settings, closes)
        casebook = build_verified_source_casebook(
            handoff, timeline, needs, closes,
        )
        bp, bps = persist_source_casebook(settings, casebook)
        readiness = build_replay_readiness(
            casebook, expected_source_fp=None,
        )
        ap, aps = persist_replay_readiness(settings, readiness)
        proof = build_execution_proof_demand(casebook, readiness)
        pp, pps = persist_execution_proof_demand(settings, proof)

        print(f"    handoff={hps} / {hp}", flush=True)
        print(f"    timeline={tps} / {tp}", flush=True)
        print(f"    native_demand={nps} / {np}", flush=True)
        print(f"    native_source={cps} / {cp}", flush=True)
        print(f"    casebook={bps} / {bp}", flush=True)
        print(f"    replay_readiness={aps} / {ap}", flush=True)
        print(f"    execution_proof_demand={pps} / {pp}", flush=True)
        print(
            f"    physical_histories_decoded={timeline['unique_verified_physical_histories_decoded']} "
            f"dated_option_and_stock_source_rights={casebook['dated_option_and_stock_source_rights']} "
            f"historical_executable_option_trades={readiness['actual_executable_option_trades']}",
            flush=True,
        )
        for year, counts in casebook["by_year"].items():
            print(f"    casebook_{year}={counts}", flush=True)
        print(
            f"  COMPLETE cumulative_observed_credits={spent} "
            f"provider_remaining_last_observed={provider_remaining}",
            flush=True,
        )
        print(
            "  Historical account P&L remains NULL until independent common-clock, "
            "deliverable/multiplier, execution-cost and expiry/exercise gates pass.",
            flush=True,
        )
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(
            f"RESET-DAY SWEEP STOPPED: {type(exc).__name__}: {exc}",
            flush=True,
        )
        print(
            "  Preserve all attempts, receipts and raw bodies. Do not blindly retry "
            "an uncertain paid request.",
            flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
