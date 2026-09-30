from __future__ import annotations

"""One zero-provider rebuild from verified quote caches through replay proof demand."""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_demand_quote_cache_v1 import run_demand_cache
from packages.data.multiyear_native_eod_close_source_v1 import (
    persist_native_eod_closes, resolve_native_eod_closes,
)
from packages.data.multiyear_observed_option_quote_timeline_v1 import (
    build_observed_option_timeline, local_verified_quote_reader,
    persist_observed_option_timeline,
)
from packages.data.multiyear_option_quote_bridge_v1 import NATIVE_REL
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

SELECTION = Path(
    "data/options/manifests/"
    "multiyear_pit_selected_option_quotes_v1_3fa478312734f9c2.json"
)
PLAN = Path(
    "data/options/manifests/"
    "multiyear_demand_quote_v1_dbe759955e48946b.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refresh signed option/native/account source evidence from local caches only"
    )
    parser.add_argument("--selection", type=Path, default=SELECTION)
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--as-of-utc",
                        help="Aware current timestamp; recovery plan is stable per ET day")
    parser.add_argument("--native-workers", type=int, default=3)
    args = parser.parse_args()

    print("ATLAS MULTIYEAR SOURCE REFRESH AFTER QUOTE CACHE — ZERO PROVIDER GETs",
          flush=True)
    try:
        settings = load_settings(ROOT, "development")
        for category in ("options", "research_evidence"):
            settings.assert_external_storage_binding(category)
        selection = _read_object(args.selection)
        plan = _read_object(args.plan)
        native = _read_object(settings.resolved_path(NATIVE_REL))
        at = (
            datetime.fromisoformat(args.as_of_utc)
            if args.as_of_utc else datetime.now(UTC)
        )
        if at.tzinfo is None:
            raise ValueError("as-of must be timezone-aware")

        print("  stage=VERIFY_CURRENT_LOCAL_QUOTE_CACHE", flush=True)
        census = run_demand_cache(
            settings, plan,
            progress=lambda row: print(
                "    " + " ".join(f"{k}={v}" for k, v in row.items()), flush=True
            ),
        )
        print(f"    original_2022_reused={census['reused_original_2022']}", flush=True)
        print(f"    exact_cache_complete={census['new_cache_complete']}", flush=True)
        print(f"    exact_source_gaps={census['exact_source_gaps']}", flush=True)
        print(f"    original_pending={census['pending']}", flush=True)

        print("  stage=VERIFY_CLIPPED_2021_TAIL_CACHE", flush=True)
        recovery_plan = build_tail_recovery_plan(plan, census, asof_utc=at)
        rp, rps = persist_tail_recovery_plan(settings, recovery_plan)
        recovery_census = run_demand_cache(
            settings, recovery_plan,
            progress=lambda row: print(
                "    recovery_" + " ".join(f"{k}={v}" for k, v in row.items()),
                flush=True,
            ),
        )
        overlay = build_recovery_overlay(plan, recovery_plan, recovery_census)
        op, ops = persist_recovery_overlay(settings, overlay)
        print(f"    recovery_plan={rps} / {rp}", flush=True)
        print(f"    recovery_floor_et={recovery_plan['rolling_five_year_floor']}", flush=True)
        print(f"    recovery_distinct_queries={recovery_plan['distinct_recovery_queries']}",
              flush=True)
        print(f"    recovery_complete={overlay['complete_recovery_queries']}", flush=True)
        print(f"    recovery_gaps={overlay['recovery_query_gaps']}", flush=True)
        print(f"    recovery_pending={overlay['pending_recovery_queries']}", flush=True)
        print(f"    recovery_overlay={ops} / {op}", flush=True)

        print("  stage=BUILD_FRESH_FULL_CASE_QUOTE_HANDOFF", flush=True)
        handoff = assemble_quote_reuse_handoff(
            selection, plan, census, recovery_overlay=overlay,
        )
        hp, hps = persist_quote_reuse_handoff(settings, handoff)
        print(f"    handoff={hps} / {hp}", flush=True)
        print(f"    handoff_fingerprint={handoff['handoff_fingerprint']}", flush=True)
        print(f"    verified_original_2022_queries={handoff['reused_original_2022_queries']}",
              flush=True)
        print(f"    verified_exact_cache_queries={handoff['verified_demand_cache_queries']}",
              flush=True)
        print(f"    recovered_original_queries={handoff['recovered_original_quote_queries']}",
              flush=True)
        print(f"    remaining_pending_queries={handoff['pending_unique_quote_queries']}",
              flush=True)

        print("  stage=DECODE_VERIFIED_OPTION_TIMELINES", flush=True)
        timeline = build_observed_option_timeline(
            selection, plan, handoff,
            read_verified_observations=local_verified_quote_reader(settings, plan),
        )
        tp, tps = persist_observed_option_timeline(settings, timeline)
        print(f"    timeline={tps} / {tp}", flush=True)
        print(f"    physical_histories_decoded="
              f"{timeline['unique_verified_physical_histories_decoded']}", flush=True)
        for year, counts in timeline["by_year"].items():
            print(f"    quote_{year}={counts}", flush=True)

        print("  stage=REBUILD_NATIVE_CLOSE_DEMAND_AND_VERIFY_LOCAL_STOCK_SOURCE", flush=True)
        needs = build_native_eod_needs(native, selection, timeline)
        np, nps = persist_source_needs(settings, needs)
        print(f"    native_demand={nps} / {np}", flush=True)
        print(f"    unique_native_close_requests="
              f"{needs['unique_native_raw_eod_close_requests']}", flush=True)
        closes = resolve_native_eod_closes(
            settings, native, needs, workers=args.native_workers,
            progress=lambda row: print(
                "    native_" + " ".join(f"{k}={v}" for k, v in row.items()),
                flush=True,
            ),
        )
        cp, cps = persist_native_eod_closes(settings, closes)
        print(f"    native_source={cps} / {cp}", flush=True)
        print(f"    exact_native_closes={closes['verified_exact_native_raw_closes']}",
              flush=True)
        print(f"    native_daily_gaps={closes['exact_daily_bar_gaps']}", flush=True)

        print("  stage=BUILD_FRESH_SIGNED_SOURCE_CASEBOOK", flush=True)
        casebook = build_verified_source_casebook(handoff, timeline, needs, closes)
        bp, bps = persist_source_casebook(settings, casebook)
        print(f"    casebook={bps} / {bp}", flush=True)
        print(f"    casebook_fingerprint={casebook['casebook_fingerprint']}", flush=True)
        print(f"    dated_option_and_stock_source_rights="
              f"{casebook['dated_option_and_stock_source_rights']}", flush=True)
        for year, counts in casebook["by_year"].items():
            print(f"    casebook_{year}={counts}", flush=True)

        print("  stage=REPLAY_READINESS_AND_EXECUTION_PROOF_DEMAND", flush=True)
        readiness = build_replay_readiness(
            casebook, expected_source_fp=None,
        )
        ap, aps = persist_replay_readiness(settings, readiness)
        proof = build_execution_proof_demand(casebook, readiness)
        pp, pps = persist_execution_proof_demand(settings, proof)
        print(f"    replay_readiness={aps} / {ap}", flush=True)
        print(f"    readiness_fingerprint={readiness['readiness_fingerprint']}",
              flush=True)
        print(f"    historical_executable_option_trades="
              f"{readiness['actual_executable_option_trades']}", flush=True)
        print(f"    dated_pair_clock_proof_work_items={proof['dated_pair_work_items']}",
              flush=True)
        print(f"    distinct_option_mark_proof_targets="
              f"{proof['distinct_option_observations']}", flush=True)
        print(f"    distinct_native_close_clock_proof_targets="
              f"{proof['distinct_original_native_close_queries']}", flush=True)
        print(f"    execution_proof_demand={pps} / {pp}", flush=True)
        print(f"    execution_proof_demand_fingerprint="
              f"{proof['proof_demand_fingerprint']}", flush=True)
        print(
            "  COMPLETE: zero provider GETs in refresh. No 09:35 backfill, "
            "same-clock claim, historical fill, deliverable inference or account P&L.",
            flush=True,
        )
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(f"SOURCE REFRESH STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print(
            "  Existing raw quotes/native stock and immutable receipts remain unchanged; "
            "no provider fallback.",
            flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
