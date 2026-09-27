from __future__ import annotations

"""Offline, full-denominator historical option-chain source-demand accounting.

A prior physical chain key is not an executable option or a matching historical
bid/ask. The initial request list is a preview; it is NOT provider authority.
Original 2022 and original 2025 source pointers are reused without re-opening
original 2022 quote bodies or spending any provider credits.
"""

from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Callable

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_batch_plan_v1 import _digest
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.marketdata_candidate_expansion_v1 import _exclusive, _read_object
from packages.data.multiyear_option_gap_inventory_v1 import (
    _bounds,
    build_option_source_gap_inventory,
)
from packages.data.multiyear_original_option_source_crosswalk_v1 import (
    AUTHORITY as CROSSWALK_AUTHORITY,
    CONTRACT as CROSSWALK_CONTRACT,
    OriginalCrosswalkError,
    build_original_source_crosswalk,
)

CONTRACT = "atlas-multiyear-physical-chain-source-demand-v1"
OUTPUT_REL = "data/options/manifests/multiyear_physical_chain_source_demand_v1"
CROSSWALK_STATUS = "COMPLETE_ORIGINAL_SOURCE_ACCOUNTING_WITH_EXPLICIT_UNCOVERED_2022_CASES"
SOURCE_PREVIEW = "UNPAID_PHYSICAL_KEY_PREVIEW_NOT_GLOBAL_CACHE_RECONCILED"
EXPECTED_YEAR_CASES = {
    "2021": 5491, "2022": 2900, "2023": 1601,
    "2024": 1390, "2025": 3520, "2026": 0,
}
AUTHORITY = {
    "provider_requests": 0,
    "paid_request_authority": False,
    "quote_body_reopened": False,
    "source_gaps_are_not_provider_market_absence": True,
    "option_selection_or_fills": False,
    "protected_2026_outcomes_read": False,
    "paper": False, "live": False,
}


class PhysicalSourceDemandError(ValueError):
    pass


def _validated_inputs(crosswalk: dict[str, Any], inventory: dict[str, Any]) -> None:
    original = dict(crosswalk)
    fp = original.pop("crosswalk_fingerprint", None)
    old_inventory = dict(inventory)
    inventory_fp = old_inventory.pop("inventory_fingerprint", None)
    if (
        fp != _fingerprint(original)
        or inventory_fp != _fingerprint(old_inventory)
        or crosswalk.get("contract") != CROSSWALK_CONTRACT
        or crosswalk.get("status") != CROSSWALK_STATUS
        or crosswalk.get("authority") != CROSSWALK_AUTHORITY
        or crosswalk.get("source_inventory_fingerprint") != inventory_fp
        or crosswalk.get("case_denominator") != 14902
        or inventory.get("case_denominator") != 14902
        or len(crosswalk.get("cases", [])) != 14902
        or len(inventory.get("cases", [])) != 14902
        or crosswalk.get("provider_requests") != 0
        or crosswalk.get("new_paid_requests") != 0
        or inventory.get("provider_requests") != 0
        or inventory.get("new_paid_requests") != 0
    ):
        raise PhysicalSourceDemandError("original crosswalk or inventory lineage changed")
    if any(
        any(row.get(k) != value for k, value in original_row.items())
        for row, original_row in zip(crosswalk["cases"], inventory["cases"])
    ):
        raise PhysicalSourceDemandError("original stock case source/order changed")
    ids = [r["case_id"] for r in crosswalk["cases"]]
    if len(set(ids)) != 14902:
        raise PhysicalSourceDemandError("frozen accepted stock case IDs differ")
    counts = Counter(row["year"] for row in crosswalk["cases"])
    if dict(counts) != {k:v for k,v in EXPECTED_YEAR_CASES.items() if v}:
        raise PhysicalSourceDemandError(f"frozen stock signal year denominator drift: {dict(counts)}")
    unresolved = crosswalk.get("2022_unmatched_original_source_cases")
    if (
        crosswalk.get("2022_unmatched_cases_remaining") != 3
        or not isinstance(unresolved, list) or len(unresolved) != 3
        or not all(x.get("classification") == "ORIGINAL_2022_NO_ORIGINAL_PHYSICAL_CHAIN_KEY"
                   and x.get("same_key_existing_physical_representatives") == []
                   for x in unresolved)
        or crosswalk.get("2022_total_original_cases_reconciled") != 2900
        or crosswalk.get("2022_pilot_same_key_other_cases") != 0
        or crosswalk.get("2025_original_pilot_matched_cases") != 12
        or crosswalk.get("2022_original_additive_representatives") != 2812
        or crosswalk.get("2022_original_additive_same_key_members") != 29
        or crosswalk.get("2022_gap_linked_same_key_member_count") != 2
        or crosswalk.get("existing_2022_quote_series_plan_count") != 6398
        or inventory.get("provisional_group_count") != 7654
        or len(inventory.get("provisional_chain_groups", [])) != 7654
    ):
        raise PhysicalSourceDemandError("accepted original physical source evidence changed")


def _request(ticker: str, snapshot: str, expiry: str, envelope: str,
             members: list[str], lineage: str) -> dict[str, Any]:
    lo,hi = (float(s) for s in envelope.split("-"))
    if not 0 < lo <= hi:
        raise PhysicalSourceDemandError("invalid source strike preview envelope")
    params = {"date": snapshot, "expiration": expiry, "strike": envelope}
    identity = _digest({"ticker": ticker, "params": params, "mode": "HISTORICAL_EOD"})
    return {
        "physical_request_identity": identity,
        "ticker": ticker, "snapshot_date": snapshot, "expiration": expiry,
        "endpoint": f"options/chain/{ticker}/", "params": params,
        "member_case_ids": sorted(members),
        "source_lineage": lineage, "source_status": SOURCE_PREVIEW,
        "request_sides": ["call", "put"], "provider_requests": 0,
        "global_cache_receipt_reconciled": False,
        "new_paid_request_proven": False,
        "historical_option_fill_verified": False,
    }


def freeze_physical_chain_source_demand(
    crosswalk: dict[str, Any], inventory: dict[str, Any],
    *, progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Account for all original signals; preserve every missing source ID.

    Query preview grouping was frozen before future option liquidity was seen.
    The remaining pilot and original-source receipt overlap must be checked in
    a distinct physical cache stage BEFORE paid authorization.
    """
    _validated_inputs(crosswalk, inventory)
    by_id = {x["case_id"]:x for x in crosswalk["cases"]}
    by_year: dict[str, Counter[str]] = {
        k: Counter() for k in EXPECTED_YEAR_CASES
    }
    statuses: dict[str, str] = {}
    for row in crosswalk["cases"]:
        cid,year,original = row["case_id"],row["year"],row["original_reconciliation"]
        if original == "DECISION_OUTSIDE_ROLLING_PROVIDER_WINDOW":
            state = "2021_BEFORE_FROZEN_FIVE_YEAR_PROVIDER_FLOOR"
        elif original == "DEFERRED_2026_NATIVE_ENTRY":
            state = "2025_SIGNAL_2026_NATIVE_ENTRY_NOT_READ"
        elif original in {
            "NO_BOUNDED_MONTHLY_EXPIRATION",
            "ORIGINAL_2022_FROZEN_MONTHLY_EXPIRY_GAP",
        }:
            state = "NO_ORIGINAL_MONTHLY_EXPIRATION"
        elif original == "ORIGINAL_2022_NO_ORIGINAL_PHYSICAL_CHAIN_KEY":
            state = "2022_EXACT_OLD_SOURCE_KEY_ABSENT_PREVIEW_ONLY"
        elif original.startswith("ORIGINAL_2022_"):
            state = "2022_EXISTING_ORIGINAL_PHYSICAL_SOURCE_OR_EXACT_GAP"
        elif original.startswith("ORIGINAL_2025_PILOT_"):
            state = "2025_VERIFIED_ORIGINAL_PILOT_SOURCE_OR_EXACT_GAP"
        elif original in {
            "PIT_CHAIN_SOURCE_REQUEST_CANDIDATE",
            "ORIGINAL_2025_NOT_IN_TWELVE_CASE_PILOT",
        }:
            state = "HISTORICAL_SOURCE_QUERY_PREVIEW_PENDING_LOCAL_RECEIPT_RECONCILIATION"
        else:
            raise PhysicalSourceDemandError(
                f"unrecognized accepted source disposition: {cid} {original}"
            )
        if year not in by_year or cid in statuses:
            raise PhysicalSourceDemandError("duplicate or wrong-year original stock case")
        statuses[cid] = state
        by_year[year][state] += 1
    preview_needed = {
        cid for cid,state in statuses.items()
        if state == "HISTORICAL_SOURCE_QUERY_PREVIEW_PENDING_LOCAL_RECEIPT_RECONCILIATION"
    }
    original_groups = inventory["provisional_chain_groups"]
    assigned: set[str] = set()
    requests: list[dict[str, Any]] = []
    identities: set[str] = set()
    for idx,group in enumerate(original_groups,1):
        if group.get("source_status") != "PROVISIONAL_UNPAID_CHAIN_QUERY_NEEDS_RECEIPT_RECONCILIATION":
            raise PhysicalSourceDemandError("original provisional chain group changed")
        raw_ids = group["member_case_ids"]
        if len(raw_ids) != group["original_case_count"] or len(raw_ids) != len(set(raw_ids)):
            raise PhysicalSourceDemandError("original source group membership changed")
        allowed = []
        for cid in raw_ids:
            row = by_id.get(cid)
            if (
                row is None or row["ticker"] != group["ticker"]
                or row["signal_session"] != group["snapshot_date"]
                or row["expiration"] != group["expiration"]
                or row["year"] != group["year"]
            ):
                raise PhysicalSourceDemandError("original physical preview key/membership mismatch")
            if cid in preview_needed:
                if cid in assigned:
                    raise PhysicalSourceDemandError("accepted original source case assigned twice")
                assigned.add(cid)
                allowed.append(cid)
            elif statuses[cid] != "2025_VERIFIED_ORIGINAL_PILOT_SOURCE_OR_EXACT_GAP":
                raise PhysicalSourceDemandError("original source preview contains unexpected status")
        if allowed:
            left,right=group["strike_window"].split(",")
            lo,hi=float(left),float(right)
            envelope=f"{lo:.2f}-{hi:.2f}"
            ticket = _request(group["ticker"],group["snapshot_date"],
                              group["expiration"],envelope,allowed,
                              "FROZEN_ORIGINAL_NATIVE_PIT_8PCT_GROUP_PREVIEW")
            if ticket["physical_request_identity"] in identities:
                raise PhysicalSourceDemandError("duplicate physical preview request identity")
            identities.add(ticket["physical_request_identity"])
            requests.append(ticket)
        if progress and idx%1500==0:
            progress({"stage":"SOURCE_PREVIEW_GROUPS","groups_checked":idx,
                      "total_original_groups":len(original_groups),
                      "cases_assigned":len(assigned),"provider_requests":0})
    if assigned != preview_needed:
        raise PhysicalSourceDemandError(
            "not all original PIT source cases are assigned: "
            f"missing={sorted(preview_needed-assigned)[:20]} "
            f"extra={sorted(assigned-preview_needed)[:20]}"
        )
    gaps = crosswalk["2022_unmatched_original_source_cases"]
    uncovered = {
        row["case_id"] for row in crosswalk["cases"]
        if row["original_reconciliation"] == "ORIGINAL_2022_NO_ORIGINAL_PHYSICAL_CHAIN_KEY"
    }
    if uncovered != {r["case_id"] for r in gaps} or len(uncovered)!=3:
        raise PhysicalSourceDemandError("accepted original 2022 uncovered identities differ")
    for gap in gaps:
        row=by_id[gap["case_id"]]
        if (
            row["year"]!="2022" or row["ticker"]!=gap["ticker"]
            or row["signal_session"]!=gap["signal_session"]
            or row["expiration"]!=gap["expiration"]
            or row["decision_at_utc"]!=gap["decision_at_utc"]
            or row["original_source_pointer"]["original_physical_query_found"] is not False
        ):
            raise PhysicalSourceDemandError("uncovered original exact case identity drifted")
        price=row["original_source_pointer"]["member_native_raw_open"]
        lo,hi=_bounds(price)
        envelope=f"{lo:.2f}-{hi:.2f}"
        ticket=_request(row["ticker"],row["signal_session"],row["expiration"],
                        envelope,[row["case_id"]],
                        "ACCEPTED_2022_DECEMBER_SOURCE_KEY_ABSENT_OLD_2022_COHORT")
        if ticket["physical_request_identity"] in identities:
            raise PhysicalSourceDemandError("uncovered original case duplicates another physical query")
        identities.add(ticket["physical_request_identity"])
        requests.append(ticket)
    expected_preview = {
        "2021":1353,"2022":3,"2023":1601,"2024":1390,"2025":3491
    }
    count_preview = Counter()
    for ticket in requests:
        for cid in ticket["member_case_ids"]:
            count_preview[by_id[cid]["year"]] += 1
    if dict(count_preview) != expected_preview:
        raise PhysicalSourceDemandError(f"yearly original demand count drifted: {dict(count_preview)}")
    all_members = [cid for ticket in requests for cid in ticket["member_case_ids"]]
    if len(set(all_members)) != len(all_members) or len(all_members) != 7838:
        raise PhysicalSourceDemandError("provisional multi-year physical source membership drifted")
    # Keep the 2021 pre-entitlement and 2026 native-source cases explicit.
    status_totals = Counter(statuses.values())
    if (
        status_totals["2021_BEFORE_FROZEN_FIVE_YEAR_PROVIDER_FLOOR"]!=4138
        or status_totals["2025_SIGNAL_2026_NATIVE_ENTRY_NOT_READ"]!=17
        or status_totals["NO_ORIGINAL_MONTHLY_EXPIRATION"]!=20
        or status_totals["2022_EXISTING_ORIGINAL_PHYSICAL_SOURCE_OR_EXACT_GAP"]!=2877
        or status_totals["2025_VERIFIED_ORIGINAL_PILOT_SOURCE_OR_EXACT_GAP"]!=12
        or sum(status_totals.values())!=14902
    ):
        raise PhysicalSourceDemandError(f"full source-case partition differs: {dict(status_totals)}")
    requests.sort(key=lambda x:(x["snapshot_date"],x["ticker"],
                                x["expiration"],x["params"]["strike"]))
    doc={
        "contract":CONTRACT,
        "status":"FROZEN_OFFLINE_FULL_DENOMINATOR_CHAIN_SOURCE_DEMAND_PREVIEW",
        "crosswalk_fingerprint":crosswalk["crosswalk_fingerprint"],
        "source_inventory_fingerprint":inventory["inventory_fingerprint"],
        "accepted_native_stock_source_fingerprint":
            inventory["original_native_stock_source_fingerprint"],
        "case_denominator":14902,
        "original_2022_exact_quote_histories_reused_by_pointer_only":6398,
        "historical_provider_floor_frozen":inventory["rolling_five_year_floor"],
        "2026_accepted_new_stock_signal_cases":0,
        "2026_deferred_2025_signal_native_entry_cases":17,
        "2021_before_five_year_floor_cases":4138,
        "original_2022_no_monthly_expiration_cases":20,
        "original_2022_uncovered_physical_query_case_ids":sorted(uncovered),
        "original_2022_old_source_key_absence_count":len(uncovered),
        "original_2022_pilot_representative_cases":36,
        "original_2025_pilot_case_count":12,
        "original_2025_pilot_unavailable_exact_query_cases":1,
        "new_stock_source_case_denominator_needing_preview":len(all_members),
        "unique_unreconciled_physical_preview_queries":len(requests),
        "by_year":{k:dict(sorted(v.items())) for k,v in by_year.items()},
        "by_year_preview_case_memberships":dict(sorted(count_preview.items())),
        "case_coverage":[{"case_id":r["case_id"],"year":r["year"],
                          "source_status":statuses[r["case_id"]]}
                         for r in crosswalk["cases"]],
        "requests":requests,
        "provider_requests":0,"new_paid_requests_proven":0,
        "authority":AUTHORITY,
        "source_selection_not_option_trade":True,
        "chain_contains_both_rights_without_picking_future_liquid_option":True,
    }
    doc["demand_fingerprint"]=_fingerprint(doc)
    return doc


def _target(settings:AtlasSettings,crosswalk:dict[str,Any])->Path:
    return settings.resolved_path(
        f"{OUTPUT_REL}_{crosswalk['crosswalk_fingerprint'][:16]}.json"
    )


def _existing(path:Path,crosswalk:dict[str,Any],inventory:dict[str,Any])->dict[str,Any]|None:
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise PhysicalSourceDemandError("existing physical source demand path is linked/nonfile")
    doc=_read_object(path)
    unsigned=dict(doc)
    fp=unsigned.pop("demand_fingerprint",None)
    if (
        fp!=_fingerprint(unsigned)
        or doc.get("contract")!=CONTRACT
        or doc.get("status")!="FROZEN_OFFLINE_FULL_DENOMINATOR_CHAIN_SOURCE_DEMAND_PREVIEW"
        or doc.get("crosswalk_fingerprint")!=crosswalk["crosswalk_fingerprint"]
        or doc.get("source_inventory_fingerprint")!=inventory["inventory_fingerprint"]
        or doc.get("case_denominator")!=14902
        or len(doc.get("case_coverage",[]))!=14902
        or doc.get("authority")!=AUTHORITY
        or doc.get("provider_requests")!=0
        or doc.get("new_paid_requests_proven")!=0
        or len(doc.get("requests",[]))!=doc.get("unique_unreconciled_physical_preview_queries")
    ):
        raise PhysicalSourceDemandError("original physical source-demand manifest changed")
    return doc


def build_physical_chain_source_demand(
    settings:AtlasSettings,*,
    progress:Callable[[dict[str,Any]],None]|None=None,
)->tuple[dict[str,Any],Path,str]:
    settings.assert_external_storage_binding("options")
    settings.assert_external_storage_binding("research_evidence")
    crosswalk,_,old_action=build_original_source_crosswalk(settings,progress=progress)
    if progress:
        progress({"stage":"REUSE_ACCEPTED_ORIGINAL_SOURCE_CROSSWALK",
                  "action":old_action,"cases":crosswalk["case_denominator"],
                  "provider_requests":0})
    inventory,_,inventory_action=build_option_source_gap_inventory(
        settings,progress=progress
    )
    _validated_inputs(crosswalk,inventory)
    path=_target(settings,crosswalk)
    old=_existing(path,crosswalk,inventory)
    if old is not None:
        return old,path,"REUSED_VERIFIED_PHYSICAL_DEMAND_NO_REBUILD"
    if progress:
        progress({"stage":"REUSE_ACCEPTED_INVENTORY",
                  "action":inventory_action,"original_preview_groups":
                    len(inventory["provisional_chain_groups"]),"provider_requests":0})
    doc=freeze_physical_chain_source_demand(
        crosswalk,inventory,progress=progress,
    )
    _exclusive(path,doc)
    if _existing(path,crosswalk,inventory)!=doc:
        raise PhysicalSourceDemandError("new physical source demand readback changed")
    return doc,path,"WRITTEN_NEW_PHYSICAL_SOURCE_DEMAND_PREVIEW"
