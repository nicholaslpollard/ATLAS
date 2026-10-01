from __future__ import annotations

"""Resume the reset-day multiyear source sweep after paid acquisition, offline only.

This entrypoint never calls a provider. It discovers the exact signed additive
quote plan and recovery overlay already persisted by the acquisition-day sweep,
then rebuilds handoff -> option timeline -> native CLOSE source -> casebook ->
readiness -> execution-proof demand.

Protected 2026 native stock CLOSE requests remain in lineage but are dispositioned
as WITHHELD_NOT_READ. They never open the protected native stock source.
"""

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_additive_quote_plan_v1 import CONTRACT as ADDITIVE_CONTRACT
from packages.data.multiyear_demand_quote_cache_v1 import run_demand_cache
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
    _check_signature, assemble_quote_reuse_handoff, persist_quote_reuse_handoff,
)
from packages.data.multiyear_option_stock_eod_preflight_v1 import (
    build_native_eod_needs, persist_source_needs,
)
from packages.data.multiyear_quote_tail_recovery_v1 import OVERLAY_CONTRACT
from packages.data.multiyear_verified_stock_option_source_casebook_v1 import (
    build_verified_source_casebook, persist_source_casebook,
)
from packages.simulation.multiyear_account_readiness_v1 import (
    build_replay_readiness, persist_replay_readiness,
)
from packages.simulation.multiyear_historical_execution_requirements_v1 import (
    build_execution_proof_demand, persist_execution_proof_demand,
)

BASE_PLAN = Path(
    "data/options/manifests/"
    "multiyear_demand_quote_v1_dbe759955e48946b.json"
)


class OfflineContinuationError(ValueError):
    pass


def _manifest_root(settings) -> Path:
    return settings.resolved_path("data/options/manifests")


def _find_additive_plan(
    settings, base_plan: dict[str, Any], selection: dict[str, Any],
    acquisition_day_et: date,
) -> tuple[Path, dict[str, Any]]:
    matches: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(_manifest_root(settings).glob("multiyear_demand_quote_v1_*.json")):
        try:
            doc = _read_object(path)
            if (
                doc.get("additive_contract") != ADDITIVE_CONTRACT
                or doc.get("base_quote_plan_fingerprint")
                    != base_plan["plan_fingerprint"]
                or doc.get("expanded_selection_fingerprint")
                    != selection["selection_fingerprint"]
                or doc.get("additive_planning_day_et")
                    != acquisition_day_et.isoformat()
            ):
                continue
            _check_signature(doc, "plan_fingerprint")
        except (OSError, ValueError, TypeError, KeyError):
            continue
        if (
            doc.get("status") != "SOURCE_DEMAND_FROZEN_NO_PROVIDER_READS"
            or doc.get("provider_requests") != 0
            or doc.get("strategy_authority") is not False
            or doc.get("historical_fill_or_pnl_authority") is not False
            or doc.get("prior_selected_contracts_changed") != 0
            or doc.get("base_exact_windows_preserved") is not True
        ):
            raise OfflineContinuationError("matching additive plan authority changed")
        matches.append((path, doc))
    if len(matches) != 1:
        raise OfflineContinuationError(
            f"expected exactly one additive plan for {acquisition_day_et.isoformat()}, "
            f"found {len(matches)}"
        )
    return matches[0]


def _find_recovery_overlay(
    settings, plan: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    matches: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(
        _manifest_root(settings).glob(
            "multiyear_stale_quote_recovery_overlay_v1_*.json"
        )
    ):
        try:
            doc = _read_object(path)
            if (
                doc.get("contract") != OVERLAY_CONTRACT
                or doc.get("original_plan_fingerprint")
                    != plan["plan_fingerprint"]
                or doc.get("current_floor_et")
                    != plan["rolling_five_year_floor"]
            ):
                continue
            _check_signature(doc, "overlay_fingerprint")
        except (OSError, ValueError, TypeError, KeyError):
            continue
        if (
            doc.get("provider_requests") != 0
            or doc.get("original_window_fully_reconstructed") is not False
            or doc.get("historical_fill_or_pnl_authority") is not False
        ):
            raise OfflineContinuationError("matching recovery overlay authority changed")
        matches.append((path, doc))
    if len(matches) != 1:
        raise OfflineContinuationError(
            f"expected exactly one recovery overlay for additive plan, found {len(matches)}"
        )
    return matches[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Resume accepted multiyear source refresh from local receipts only"
    )
    parser.add_argument(
        "--acquisition-day-et", type=date.fromisoformat, required=True,
        help="ET calendar day of the paid additive sweep, e.g. 2026-09-30",
    )
    parser.add_argument("--base-plan", type=Path, default=BASE_PLAN)
    parser.add_argument("--native-workers", type=int, default=4)
    args = parser.parse_args(argv)

    print("ATLAS MULTIYEAR OFFLINE SOURCE REFRESH CONTINUATION V1", flush=True)
    print(
        "  ZERO provider GETs. Reuses signed paid receipts already persisted on D:.",
        flush=True,
    )
    try:
        if not 1 <= args.native_workers <= 4:
            raise OfflineContinuationError("native workers must remain within 1..4")
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        base_plan = _read_object(args.base_plan)
        _check_signature(base_plan, "plan_fingerprint")

        print("  stage=REBUILD_CURRENT_PIT_SELECTION_ZERO_GET", flush=True)
        selection = build_local_bridge(settings, right="both")
        selection_path, selection_action = write_local_bridge(settings, selection)
        print(f"    selection={selection_action} / {selection_path}", flush=True)
        print(
            f"    selection_fingerprint={selection['selection_fingerprint']} "
            f"selected_case_rights={selection['selected_case_right_memberships']}",
            flush=True,
        )

        print("  stage=DISCOVER_EXACT_ACQUISITION_DAY_ADDITIVE_PLAN", flush=True)
        plan_path, plan = _find_additive_plan(
            settings, base_plan, selection, args.acquisition_day_et,
        )
        print(f"    additive_plan={plan_path}", flush=True)
        print(f"    additive_plan_fingerprint={plan['plan_fingerprint']}", flush=True)
        print(
            f"    base_physical_queries={plan['base_physical_quote_queries']} "
            f"added_physical_queries={plan['added_physical_quote_queries']} "
            f"total_physical_queries={plan['unique_physical_quote_queries']}",
            flush=True,
        )

        print("  stage=VERIFY_LOCAL_EXACT_QUOTE_CACHE_ZERO_GET", flush=True)
        census = run_demand_cache(
            settings, plan,
            progress=lambda row: print(
                "    quote_cache_" + " ".join(f"{k}={v}" for k, v in row.items()),
                flush=True,
            ),
        )
        if (
            census.get("new_provider_attempts") != 0
            or census.get("observed_credits") != 0
        ):
            raise OfflineContinuationError("offline cache census attempted provider work")
        print(
            f"    reused_original_2022={census['reused_original_2022']} "
            f"exact_cache_complete={census['new_cache_complete']} "
            f"exact_source_gaps={census['exact_source_gaps']} "
            f"pending={census['pending']}",
            flush=True,
        )

        print("  stage=REUSE_ACQUISITION_DAY_RECOVERY_OVERLAY", flush=True)
        overlay_path, overlay = _find_recovery_overlay(settings, plan)
        print(f"    recovery_overlay={overlay_path}", flush=True)
        print(
            f"    overlay_complete={overlay['complete_recovery_queries']} "
            f"overlay_gaps={overlay['recovery_query_gaps']} "
            f"overlay_pending={overlay['pending_recovery_queries']}",
            flush=True,
        )

        print("  stage=BUILD_HANDOFF_AND_OPTION_TIMELINE_ZERO_GET", flush=True)
        handoff = assemble_quote_reuse_handoff(
            selection, plan, census, recovery_overlay=overlay,
        )
        hp, hps = persist_quote_reuse_handoff(settings, handoff)
        timeline = build_observed_option_timeline(
            selection, plan, handoff,
            read_verified_observations=local_verified_quote_reader(settings, plan),
        )
        tp, tps = persist_observed_option_timeline(settings, timeline)
        print(f"    handoff={hps} / {hp}", flush=True)
        print(f"    timeline={tps} / {tp}", flush=True)
        print(
            f"    physical_histories_decoded="
            f"{timeline['unique_verified_physical_histories_decoded']}",
            flush=True,
        )

        print("  stage=VERIFY_PRE2026_NATIVE_CLOSES_WITHHOLD_2026", flush=True)
        native = _read_object(settings.resolved_path(NATIVE_REL))
        needs = build_native_eod_needs(native, selection, timeline)
        np, nps = persist_source_needs(settings, needs)
        closes = resolve_native_eod_closes(
            settings, native, needs, workers=args.native_workers,
            progress=lambda row: print(
                "    native_" + " ".join(f"{k}={v}" for k, v in row.items()),
                flush=True,
            ),
        )
        cp, cps = persist_native_eod_closes(settings, closes)
        print(f"    native_demand={nps} / {np}", flush=True)
        print(f"    native_source={cps} / {cp}", flush=True)
        print(
            f"    exact_native_closes={closes['verified_exact_native_raw_closes']} "
            f"native_daily_gaps={closes['exact_daily_bar_gaps']} "
            f"protected_2026_withheld="
            f"{closes['protected_2026_native_closes_withheld']} "
            f"protected_2026_outcomes_read={closes['protected_2026_outcomes_read']}",
            flush=True,
        )

        print("  stage=SOURCE_CASEBOOK_READINESS_AND_EXECUTION_PROOF", flush=True)
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
        print(f"    casebook={bps} / {bp}", flush=True)
        print(f"    replay_readiness={aps} / {ap}", flush=True)
        print(f"    execution_proof_demand={pps} / {pp}", flush=True)
        print(
            f"    dated_option_and_stock_source_rights="
            f"{casebook['dated_option_and_stock_source_rights']} "
            f"protected_2026_withheld_rights="
            f"{casebook['protected_2026_native_close_withheld_rights']} "
            f"historical_executable_option_trades="
            f"{readiness['actual_executable_option_trades']}",
            flush=True,
        )
        print(
            f"    readiness_protected_2026_blocker="
            f"{readiness['by_blocker'].get('PROTECTED_2026_NATIVE_CLOSE_WITHHELD', 0)}",
            flush=True,
        )
        print(
            f"    proof_work_items={proof['dated_pair_work_items']} "
            f"proof_option_observations={proof['distinct_option_observations']} "
            f"proof_native_close_targets={proof['distinct_original_native_close_queries']}",
            flush=True,
        )
        for year, counts in casebook["by_year"].items():
            print(f"    casebook_{year}={counts}", flush=True)
        print(
            "  COMPLETE: zero provider requests/credits. Protected 2026 native "
            "stock outcomes remained unread. Historical P&L remains NULL.",
            flush=True,
        )
        return 0
    except (
        OSError, ValueError, TypeError, KeyError, RuntimeError,
        OfflineContinuationError,
    ) as exc:
        print(
            f"OFFLINE SOURCE REFRESH STOPPED: {type(exc).__name__}: {exc}",
            flush=True,
        )
        print(
            "  No paid fallback is authorized. Preserve all existing source receipts.",
            flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
