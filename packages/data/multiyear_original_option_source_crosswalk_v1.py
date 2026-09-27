from __future__ import annotations

"""Offline crosswalk of ALL accepted 2022 sources and original 2025 pilot.

Original 2022 preferred CALL pointers are already accepted. This crosswalk
resolves the other source memberships without treating an absent preferred
CALL, an existing physical chain, or a 2025 pilot no-data response as evidence
of a newly selected option, a complete market or an executable fill.

Zero provider calls. No repeated conditioning/news/native or 6,398 quote
body scan. The 71 small original 2022 source bundles are SHA checked once.
"""

from collections import Counter, defaultdict
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from packages.core.settings import AtlasSettings
from packages.data import marketdata_additive_2022_shards_v1 as shards
from packages.data import marketdata_accepted_stock_candidate_export_v1 as exporter
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CandidateChainCacheError, _fingerprint,
    _paths as chain_paths, _valid_receipt as chain_receipt,
)
from packages.data.marketdata_candidate_expansion_v1 import (
    _exclusive, _read_object,
)
from packages.data.marketdata_candidate_2025_exact_reference_v1 import (
    read_accepted_shortlist,
)
from packages.data.marketdata_candidate_2025_structural_call_shortlist_v1 import (
    read_frozen_source_closeout,
)
from packages.data.marketdata_2022_broad_quote_campaign_v2 import PLAN_REL
from packages.data.multiyear_native_stock_open_v1 import build_multiyear_native_raw_open_source
from packages.data.multiyear_option_gap_inventory_v1 import (
    ACCEPTED_2022_QUOTE_PLAN,
    AUTHORITY as INVENTORY_AUTHORITY,
    CONTRACT as INVENTORY_CONTRACT,
    _valid_native, build_option_source_gap_inventory,
    original_2022_quote_index,
)

CONTRACT = "atlas-multiyear-original-2022-2025-option-source-crosswalk-v1"
OUTPUT_REL = "data/options/manifests/multiyear_original_option_source_crosswalk_v1"
AUTHORITY = {
    "provider_requests": 0,
    "protected_outcomes_read": 0,
    "new_paid_request_authority": False,
    "original_2022_quote_bodies_reopened": False,
    "original_2022_chain_receipts_reopened": "PILOT_36_ONLY",
    "original_2025_chain_bodies_reopened": False,
    "source_identity_not_option_trade": True,
    "full_market_absence_from_exact_query": False,
    "historical_contract_deliverable_verified": False,
    "2026_native_protected_read": False,
    "paper": False, "live": False,
}

class OriginalCrosswalkError(ValueError):
    pass


def _price_equal(one: object, two: object) -> bool:
    try:
        a, b = Decimal(str(one)), Decimal(str(two))
    except (ValueError, TypeError) as exc:
        raise OriginalCrosswalkError("original source raw price is malformed") from exc
    return a.is_finite() and b.is_finite() and a > 0 and a == b


def _source_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return row["ticker"], row["signal_session"], row["expiration"]


def _member_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return row["ticker"], row["snapshot_date"], row["expiration"]


def _inventory(doc: dict[str, Any]) -> dict[str, Any]:
    unsigned = dict(doc)
    fp = unsigned.pop("inventory_fingerprint", None)
    if (
        fp != _fingerprint(unsigned)
        or doc.get("contract") != INVENTORY_CONTRACT
        or doc.get("status") != "FULL_DENOMINATOR_OPTIONS_SOURCE_GAP_INVENTORY_NO_PAID_GET"
        or doc.get("authority") != INVENTORY_AUTHORITY
        or doc.get("provider_requests") != 0
        or doc.get("new_paid_requests") != 0
        or doc.get("accepted_original_2022_quote_plan_fingerprint")
        != ACCEPTED_2022_QUOTE_PLAN
        or doc.get("case_denominator") != 14902
        or len(doc.get("cases", [])) != 14902
    ):
        raise OriginalCrosswalkError("original 14,902-case source gap inventory changed")
    if len({x["case_id"] for x in doc["cases"]}) != 14902:
        raise OriginalCrosswalkError("original cases not unique")
    return doc


def _source_request_lookup(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for req in plan["requests"]:
        for oid in req["opportunity_ids"]:
            if oid in by_id:
                raise OriginalCrosswalkError("original source ID has conflicting request")
            by_id[oid] = req
    return by_id



def _partition_prior_same_key_members(
    same_key: dict[str, dict[str, Any]],
    inventory: dict[str, Any],
    *, represented_ids: set[str], pilot_ids: set[str],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Account for every prior membership without widening the accepted cohort.

    An old source-only ID may be outside the current frozen stock census, but an
    in-census alternative with a different status, or a dual physical role, is
    evidence drift. Neither is silently counted or discarded.
    """
    inventory = _inventory(inventory)
    entire_census = {row["case_id"]: row for row in inventory["cases"]}
    current = {oid: row for oid, row in entire_census.items() if row["year"] == "2022"}
    expected = {
        oid for oid, row in current.items()
        if row["source_disposition"] == "ORIGINAL_2022_SAME_KEY_RECONCILIATION_REQUIRED"
    }
    observed = set(same_key)
    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)
    role_overlap = sorted(observed & (represented_ids | pilot_ids))
    in_census_elsewhere = [
        (oid, entire_census[oid]["year"], entire_census[oid]["source_disposition"])
        for oid in unexpected if oid in entire_census
    ]
    if (
        len(current) != 2900 or len(expected) != 27 or len(observed) != 29
        or len(unexpected) != 2 or missing or role_overlap or in_census_elsewhere
    ):
        details = [{
            "case_id": oid,
            "census_disposition": entire_census[oid]["source_disposition"] if oid in entire_census
                                  else "ABSENT_FROM_ACCEPTED_2022_CENSUS",
            "source_key": list(same_key[oid]["source_key"]),
            "representative_id": same_key[oid]["representative_id"],
            "shard_index": same_key[oid]["shard_index"],
        } for oid in unexpected]
        raise OriginalCrosswalkError(
            "original 2022 alternate membership mismatch; "
            f"expected={len(expected)} observed={len(observed)} "
            f"missing={missing} physical_role_overlap={role_overlap} "
            f"unexpected_in_census={in_census_elsewhere} extra_members={details}"
        )
    legacy = [{
        "case_id": oid,
        "status": "PRIOR_SOURCE_ONLY_NOT_IN_FROZEN_ACCEPTED_STOCK_CENSUS",
        "source_key": list(same_key[oid]["source_key"]),
        "representative_id": same_key[oid]["representative_id"],
        "source_sha256": same_key[oid]["source_sha256"],
        "shard_index": same_key[oid]["shard_index"],
    } for oid in unexpected]
    return {oid: same_key[oid] for oid in sorted(expected)}, legacy


def read_2022_original_memberships(
    settings: AtlasSettings,
    quote_plan: dict[str, Any], *,
    inventory: dict[str, Any],
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Read 71 source bundles plus 36 original pilot receipts; NOT quote bodies."""
    preferred = original_2022_quote_index(quote_plan)
    prior, original_ids, original_keys = shards._prior(settings)
    if (
        prior["plan_fingerprint"] != shards.FROZEN_PRIOR_PLAN
        or len(original_ids) != 36
        or len(prior["requests"]) != 36
    ):
        raise OriginalCrosswalkError("original 2022 pilot identity changed")
    pilot_path = settings.resolved_path(
        f"{exporter.BUNDLE_SUBDIR}/{shards.FROZEN_PRIOR_COHORT}.json"
    )
    pilot_bundle = _read_object(pilot_path)
    if (
        pilot_bundle.get("year") != 2022
        or len(pilot_bundle.get("rows", [])) != 36
        or {r["opportunity_id"] for r in pilot_bundle["rows"]} != original_ids
    ):
        raise OriginalCrosswalkError("original 2022 pilot source bundle changed")
    pilot_by_id = {r["opportunity_id"]: r for r in pilot_bundle["rows"]}
    pilot_by_key: dict[tuple[str,str,str], dict[str,Any]] = {}
    pilot_by_req = _source_request_lookup(prior)
    pilot_status: dict[str,dict[str,Any]] = {}
    for oid, row in pilot_by_id.items():
        req = pilot_by_req[oid]
        receipt = chain_receipt(
            chain_paths(settings, req["request_identity"]), req,
            expected_plan_fingerprint=shards.FROZEN_PRIOR_PLAN,
        )
        if receipt is None or receipt["status"] not in {"COMPLETE","VERIFIED_NO_DATA"}:
            raise OriginalCrosswalkError("original 2022 pilot physical receipt is incomplete")
        key = _member_key(row)
        if key in pilot_by_key:
            raise OriginalCrosswalkError("original pilot key was not unique")
        pilot_by_key[key] = {
            "representative_id": oid,
            "request_identity": req["request_identity"],
            "source_status": receipt["status"],
            "strike_window": req["params"]["strike"],
            "original_chain_sha256": receipt["body_sha256"],
        }
        pilot_status[oid] = {
            **pilot_by_key[key], "raw_open": row["raw_underlying_price"],
        }
    if set(pilot_by_key) != original_keys:
        raise OriginalCrosswalkError("original pilot selected key ledger differs")

    represented: dict[str,dict[str,Any]] = {}
    same_key: dict[str,dict[str,Any]] = {}
    gaps: dict[str,str] = {}
    no_data: dict[str,str] = {}
    original_plan_rows = quote_plan.get("source_plans")
    if (
        not isinstance(original_plan_rows,list)
        or len(original_plan_rows)!=71
        or [x["shard_index"] for x in original_plan_rows]!=list(range(71))
    ):
        raise OriginalCrosswalkError("frozen original shard source order changed")
    gap_by_request: dict[tuple[int,str],str] = {}
    gap_by_id: dict[tuple[int,str],str] = {}
    for gap in quote_plan["source_gaps"]:
        shard = gap["shard_index"]
        if "opportunity_id" in gap:
            k=(shard,gap["opportunity_id"])
            if k in gap_by_id or gap.get("classification")!="NO_CALL_IN_COMPLETED_CHAIN":
                raise OriginalCrosswalkError("original no-CALL gap metadata changed")
            gap_by_id[k]="NO_CALL_IN_COMPLETED_CHAIN"
        else:
            k=(shard,gap["chain_request_identity"])
            if k in gap_by_request or not gap.get("exact_no_data_proof"):
                raise OriginalCrosswalkError("original 2022 exact-query no-data proof changed")
            gap_by_request[k]=gap["exact_no_data_proof"]
    consumed_gaps: set[tuple[str,int,str]] = set()

    for i in range(71):
        plan,path,binding=shards._read_bound(settings,i,shards.FROZEN_PRIOR_PLAN)
        info=original_plan_rows[i]
        if (
            binding["source_sha256"]!=info["source_sha256"]
            or plan["plan_fingerprint"]!=info["chain_plan_fingerprint"]
        ):
            raise OriginalCrosswalkError("original 2022 selected shard SHA differs")
        source=_read_object(path)
        if (
            source.get("year")!=2022 or source.get("shard_index")!=i
            or source.get("original_prior_plan_fingerprint")!=shards.FROZEN_PRIOR_PLAN
            or source.get("protected_master_return_rows_read")!=0
            or len(source["rows"])!=plan["opportunities"]
        ):
            raise OriginalCrosswalkError("original source shard scope or selected rows changed")
        requests=_source_request_lookup(plan)
        by_id={r["opportunity_id"]:r for r in source["rows"]}
        if set(requests)!=set(by_id):
            raise OriginalCrosswalkError("original source shard request case IDs changed")
        for oid,row in by_id.items():
            if oid in represented or oid in pilot_by_id:
                raise OriginalCrosswalkError("duplicate original 2022 physical representative")
            req=requests[oid]
            if (
                req["ticker"]!=row["ticker"]
                or req["params"]["date"]!=row["snapshot_date"]
                or req["params"]["expiration"]!=row["expiration"]
                or (row["ticker"],row["snapshot_date"],row["expiration"]) in original_keys
            ):
                raise OriginalCrosswalkError("original physical request/source key drifted")
            represented[oid]={
                "source_key": _member_key(row),
                "raw_open": row["raw_underlying_price"],
                "chain_request_identity": req["request_identity"],
                "chain_strike_window": req["params"]["strike"],
                "source_sha256": binding["source_sha256"],
                "shard_index": i,
            }
            if (i,oid) in gap_by_id:
                gaps[oid]="NO_CALL_IN_COMPLETED_CHAIN"
                consumed_gaps.add(("case",i,oid))
            elif (i,req["request_identity"]) in gap_by_request:
                gaps[oid]="EXACT_QUERY_NO_DATA"
                no_data[oid]=gap_by_request[(i,req["request_identity"])]
                consumed_gaps.add(("request",i,req["request_identity"]))
            elif oid not in preferred["rank_zero"]:
                raise OriginalCrosswalkError("original 2022 representative has no preferred CALL/gap")
        for group in source["chosen_key_member_ids"]:
            key=(group["ticker"],group["snapshot_date"],group["expiration"])
            members=group["all_accepted_member_ids"]
            representatives=[oid for oid in members if oid in by_id]
            if len(representatives)!=1 or by_id[representatives[0]]["ticker"]!=key[0]:
                raise OriginalCrosswalkError("original same-key representative identity changed")
            rep=represented[representatives[0]]
            if rep["source_key"]!=key or len(set(members))!=len(members):
                raise OriginalCrosswalkError("same-key original source key/membership drifted")
            for oid in members:
                if oid==representatives[0]:
                    continue
                if oid in represented or oid in pilot_by_id or oid in same_key:
                    raise OriginalCrosswalkError("same-key member overlaps physical representative")
                same_key[oid]={
                    **rep,"representative_id":representatives[0],
                    "member_source_key":key,
                }
        if progress and (i+1)%10==0 or progress and i==70:
            progress({"stage":"ORIGINAL_2022_SOURCE_SHARDS_REBOUND",
                      "verified_shards":i+1,"total_shards":71,
                      "source_representatives":len(represented),
                      "same_key_members":len(same_key),"provider_requests":0})
    claimed={("case",i,oid) for (i,oid) in gap_by_id}
    claimed.update({("request",i,rid) for (i,rid) in gap_by_request})
    if consumed_gaps!=claimed:
        raise OriginalCrosswalkError("original no-CALL/exact-no-data gap ledger cannot be mapped")
    in_scope_same_key, prior_only = _partition_prior_same_key_members(
        same_key, inventory, represented_ids=set(represented),
        pilot_ids=set(pilot_by_id),
    )
    if progress:
        progress({"stage":"ORIGINAL_2022_PRIOR_ONLY_MEMBERS_AUDITED",
                  "prior_only_count":len(prior_only),
                  "case_ids":[x["case_id"] for x in prior_only],
                  "accepted_same_key_members":len(in_scope_same_key),
                  "provider_requests":0})
    if (
        len(represented)!=2812 or len(in_scope_same_key)!=27
        or len(gaps)!=169 or len(preferred["rank_zero"])!=2643
        or set(gaps)!=set(represented)-set(preferred["rank_zero"])
        or set(in_scope_same_key)&set(represented)
        or set(represented)&set(pilot_by_id)
    ):
        raise OriginalCrosswalkError(
            f"original 2022 source census differs: reps={len(represented)} "
            f"alternates={len(in_scope_same_key)} prior_only={len(prior_only)} gaps={len(gaps)} "
            f"preferred={len(preferred['rank_zero'])}"
        )
    return {
        "pilot_members":pilot_status,
        "pilot_by_key":pilot_by_key,
        "additive_representatives":represented,
        "additive_same_key":in_scope_same_key,
        "prior_only_same_key_members":prior_only,
        "additive_gaps":gaps,
        "additive_exact_no_data_proofs":no_data,
        "original_preferred_calls":preferred["rank_zero"],
        "original_2022_quote_plan_fingerprint":quote_plan["plan_fingerprint"],
        "original_pilot_plan_fingerprint":prior["plan_fingerprint"],
    }


def _strike_coverage(window: str, opening: object) -> str:
    try:
        lo,hi=(Decimal(v) for v in window.split("-"))
        price=Decimal(str(opening))
        desired_lo=max(Decimal("0.01"),(price*Decimal("0.92")).quantize(
            Decimal("0.01"),rounding="ROUND_FLOOR"))
        desired_hi=(price*Decimal("1.08")).quantize(
            Decimal("0.01"),rounding="ROUND_CEILING")
    except (ValueError,TypeError) as exc:
        raise OriginalCrosswalkError("old physical query strike envelope malformed") from exc
    if not all(x.is_finite() for x in (lo,hi,price)) or not 0<lo<=hi or price<=0:
        raise OriginalCrosswalkError("invalid old physical query strike envelope")
    return ("ORIGINAL_STRIKE_ENVELOPE_COVERS_8PCT" if
            lo<=desired_lo and hi>=desired_hi else
            "ORIGINAL_STRIKE_ENVELOPE_PARTIAL_FOR_THIS_RAW_OPEN")


def reconcile_original_sources(
    inventory: dict[str,Any], sources: dict[str,Any], shortlist: dict[str,Any],
    closeout: dict[str,Any], *, native: dict[str,Any],
    progress: Callable[[dict[str,Any]],None]|None=None,
) -> dict[str,Any]:
    inventory=_inventory(inventory)
    native=_valid_native(native)
    if (
        native["source_fingerprint"]!=inventory["original_native_stock_source_fingerprint"]
        or len(native["rows"])!=len(inventory["cases"])
        or [x["case_id"] for x in native["rows"]] != [x["case_id"] for x in inventory["cases"]]
    ):
        raise OriginalCrosswalkError("original native case identities/lineage changed")
    native_by_id={x["case_id"]:x for x in native["rows"]}
    if (
        shortlist.get("stock_opportunities")!=12
        or shortlist.get("provisional_structural_symbols")!=11
        or closeout.get("verified_opportunities")!=12
        or closeout.get("plan_fingerprint")!=shortlist.get("source_plan_fingerprint")
    ):
        raise OriginalCrosswalkError("original 2025 pilot source/shortlist differ")
    pilot25={x["opportunity_id"]:x for x in shortlist["opportunities"]}
    close25={x["opportunity_id"]:x for x in closeout["opportunities"]}
    if len(pilot25)!=12 or set(pilot25)!=set(close25):
        raise OriginalCrosswalkError("original 2025 pilot case IDs differ")
    original25status=Counter()
    by_year={str(year):Counter() for year in range(2021,2027)}
    out=[]
    reconciled_2022=set()
    used25=set()
    prior_key_colliders=set()
    all2022=set()
    for idx,row in enumerate(inventory["cases"],1):
        oid=row["case_id"];year=row["year"];pre=row["source_disposition"]
        classification=pre
        linked:dict[str,Any]|None=None
        if year=="2022":
            all2022.add(oid)
            key=(row["ticker"],row["signal_session"],row["expiration"])
            if pre=="ORIGINAL_2022_PREFERRED_CALL_PLAN_MATCH":
                source=sources["additive_representatives"].get(oid)
                preferred=sources["original_preferred_calls"].get(oid)
                if (
                    source is None or preferred is None
                    or source["source_key"]!=key
                    or not _price_equal(source["raw_open"],_case_raw_price(native_by_id,oid))
                    or source["chain_request_identity"]!=preferred["original_chain_request_identity"]
                ):
                    raise OriginalCrosswalkError("accepted 2022 preferred source member drifted")
                classification="ORIGINAL_2022_PREFERRED_CALL_PLAN_POINTER_REUSED"
                linked={**source,"option_symbol_pointer":preferred["option_symbol"]}
                reconciled_2022.add(oid)
            elif pre=="ORIGINAL_2022_SAME_KEY_RECONCILIATION_REQUIRED":
                source=sources["additive_same_key"].get(oid)
                if source is None or source["source_key"]!=key:
                    raise OriginalCrosswalkError("accepted 2022 same-key source member drifted")
                classification="ORIGINAL_2022_SAME_KEY_CHAIN_REUSED_OWN_RANK_NOT_SELECTED"
                linked={**source,"strike_coverage":
                    _strike_coverage(source["chain_strike_window"],_case_raw_price(native_by_id,oid))}
                reconciled_2022.add(oid)
            elif pre=="ORIGINAL_2022_CHAIN_RECONCILIATION_REQUIRED":
                if oid in sources["additive_representatives"]:
                    source=sources["additive_representatives"][oid]
                    if (
                        oid not in sources["additive_gaps"] or source["source_key"]!=key
                        or not _price_equal(source["raw_open"],_case_raw_price(native_by_id,oid))
                    ):
                        raise OriginalCrosswalkError("old 2022 source gap has no matching original evidence")
                    classification="ORIGINAL_2022_"+sources["additive_gaps"][oid]
                    linked={**source,"exact_query_no_data_proof":
                        sources["additive_exact_no_data_proofs"].get(oid)}
                elif oid in sources["pilot_members"]:
                    source=sources["pilot_members"][oid]
                    if (
                        sources["pilot_by_key"].get(key) is None
                        or not _price_equal(source["raw_open"],_case_raw_price(native_by_id,oid))
                    ):
                        raise OriginalCrosswalkError("original 2022 pilot member changed")
                    classification="ORIGINAL_2022_PILOT_"+source["source_status"]
                    linked={**source,"original_source_policy":"FROZEN_FIRST_THREE_PER_MONTH"}
                elif key in sources["pilot_by_key"]:
                    source=sources["pilot_by_key"][key]
                    classification="ORIGINAL_2022_PILOT_KEY_OTHER_CASE_OWN_RANK_REQUIRED"
                    prior_key_colliders.add(oid)
                    linked={**source,"strike_coverage":_strike_coverage(
                        source["strike_window"],_case_raw_price(native_by_id,oid))}
                else:
                    raise OriginalCrosswalkError("unexplained 2022 case outside all original physical source keys")
                reconciled_2022.add(oid)
            elif pre=="NO_BOUNDED_MONTHLY_EXPIRATION":
                classification="ORIGINAL_2022_FROZEN_MONTHLY_EXPIRY_GAP"
                if oid in sources["additive_representatives"] or oid in sources["pilot_members"]:
                    raise OriginalCrosswalkError("no-expiry case unexpectedly has original monthly chain")
                reconciled_2022.add(oid)
            else:
                raise OriginalCrosswalkError("unexpected original 2022 source disposition")
        elif year=="2025" and pre=="ORIGINAL_2025_PILOT_RECONCILIATION_REQUIRED":
            pilot=pilot25.get(oid)
            if pilot is not None:
                original=close25[oid]
                if (
                    pilot["ticker"]!=row["ticker"]
                    or pilot["chain_snapshot_date"]!=row["signal_session"]
                    or pilot["expiration"]!=row["expiration"]
                    or pilot["stock_decision_at_utc"]!=row["decision_at_utc"]
                    or original["request_identity"]!=pilot["request_identity"]
                    or not _price_equal(pilot["accepted_raw_stock_open"],
                                         _case_raw_price(native_by_id,oid))
                ):
                    raise OriginalCrosswalkError("2025 original pilot no longer matches full accepted stock source")
                if pilot["source_status"]=="EXACT_QUERY_NO_DATA":
                    if (
                        row["ticker"]!="FSLY"
                        or pilot["provisional_nearest_atm_call"] is not None
                        or original["source_coverage"]!="SOURCE_NO_DATA_VERIFIED"
                    ):
                        raise OriginalCrosswalkError("pilot exact-query FSLY gap changed")
                    classification="ORIGINAL_2025_PILOT_EXACT_QUERY_NO_DATA"
                elif pilot["source_status"]=="COMPLETE_ORIGINAL_CHAIN":
                    if (
                        pilot["provisional_nearest_atm_call"] is None
                        or original["source_coverage"]!="REUSED_VERIFIED"
                    ):
                        raise OriginalCrosswalkError("pilot original complete-chain status changed")
                    classification="ORIGINAL_2025_PILOT_PREFERRED_CALL_POINTER_REUSED"
                else:
                    raise OriginalCrosswalkError("unexpected original 2025 pilot source status")
                used25.add(oid)
                original25status[classification]+=1
                linked={
                    "original_chain_request_identity":pilot["request_identity"],
                    "original_chain_body_sha256":pilot["source_chain_body_sha256"],
                    "original_provisional_call_symbol":pilot["provisional_nearest_atm_call"],
                    "structural_call_count":pilot["structural_call_count"],
                    "historical_quote_or_fill_price_validated":False,
                }
            else:
                classification="ORIGINAL_2025_NOT_IN_TWELVE_CASE_PILOT"
        by_year[year][classification]+=1
        if linked is not None:
            # Original source-key tuples must be JSON arrays before a signed,
            # byte-reverified immutable D: artifact is written.
            linked=json.loads(json.dumps(linked,sort_keys=True))
        out.append({
            **row,
            "original_reconciliation":classification,
            "original_source_pointer":linked,
            "new_paid_request_authority":False,
            "new_2022_chain_get_needed_proven":False,
            "historical_option_fill_verified":False,
        })
        if progress and (idx%2500==0 or idx==len(inventory["cases"])):
            progress({"stage":"ORIGINAL_CROSS_YEAR_SOURCE_RECONCILIATION",
                      "cases_processed":idx,"total_cases":len(inventory["cases"]),
                      "provider_requests":0})
    if (
        len(all2022)!=2900 or len(reconciled_2022)!=2900
        or len(prior_key_colliders)!=5
        or len(used25)!=12
        or original25status!={
            "ORIGINAL_2025_PILOT_PREFERRED_CALL_POINTER_REUSED":11,
            "ORIGINAL_2025_PILOT_EXACT_QUERY_NO_DATA":1,
        }
        or {row["case_id"] for row in out} != {row["case_id"] for row in inventory["cases"]}
        or sum(sum(x.values()) for x in by_year.values())!=14902
    ):
        raise OriginalCrosswalkError(
            "complete original source crosswalk not yet reconciled: "
            f"2022={len(reconciled_2022)}, pilot2022_alternates={len(prior_key_colliders)}, "
            f"pilot2025={dict(original25status)}"
        )
    result={
        "contract":CONTRACT,
        "status":"COMPLETE_ORIGINAL_2022_2025_SOURCE_IDENTITY_RECONCILIATION_ONLY",
        "source_inventory_fingerprint":inventory["inventory_fingerprint"],
        "original_2022_quote_plan_fingerprint":sources["original_2022_quote_plan_fingerprint"],
        "original_2022_pilot_plan_fingerprint":sources["original_pilot_plan_fingerprint"],
        "original_2025_source_closeout_fingerprint":closeout["closeout_fingerprint"],
        "original_2025_structural_shortlist_fingerprint":shortlist["shortlist_fingerprint"],
        "case_denominator":14902,
        "2022_total_original_cases_reconciled":len(reconciled_2022),
        "2022_unmatched_cases_remaining":2900-len(reconciled_2022),
        "2022_pilot_same_key_other_cases":len(prior_key_colliders),
        "2025_original_pilot_matched_cases":len(used25),
        "2025_original_pilot_source_statuses":dict(sorted(original25status.items())),
        "2022_original_additive_representatives":len(sources["additive_representatives"]),
        "2022_original_additive_same_key_members":len(sources["additive_same_key"]),
        "2022_prior_only_same_key_members":sources["prior_only_same_key_members"],
        "2022_prior_only_same_key_member_count":len(sources["prior_only_same_key_members"]),
        "2022_original_additive_source_abstentions":len(sources["additive_gaps"]),
        "2022_original_pilot_representatives":len(sources["pilot_members"]),
        "existing_2022_quote_series_plan_count":6398,
        "provisional_groups_before_physical_reconciliation":inventory["provisional_group_count"],
        "provisional_groups_after_physical_reconciliation":None,
        "new_paid_requests":0,
        "provider_requests":0,
        "authority":AUTHORITY,
        "by_year":{k:dict(sorted(v.items())) for k,v in by_year.items()},
        "cases":out,
    }
    result["crosswalk_fingerprint"]=_fingerprint(result)
    return result


def _case_raw_price(native_by_id: dict[str,dict[str,Any]], case_id: str) -> str:
    original=native_by_id.get(case_id)
    if original is None or original["raw_underlying_price"] is None:
        raise OriginalCrosswalkError("original verified native raw stock price missing")
    return original["raw_underlying_price"]


def _target(settings: AtlasSettings, inventory: dict[str,Any]) -> Path:
    return settings.resolved_path(
        f"{OUTPUT_REL}_{inventory['inventory_fingerprint'][:16]}.json"
    )


def _verified_existing(path: Path, inventory: dict[str,Any]) -> dict[str,Any]|None:
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise OriginalCrosswalkError("existing source crosswalk is not a regular file")
    doc=_read_object(path)
    unsigned=dict(doc)
    fp=unsigned.pop("crosswalk_fingerprint",None)
    if (
        fp!=_fingerprint(unsigned)
        or doc.get("contract")!=CONTRACT
        or doc.get("status")!="COMPLETE_ORIGINAL_2022_2025_SOURCE_IDENTITY_RECONCILIATION_ONLY"
        or doc.get("source_inventory_fingerprint")!=inventory["inventory_fingerprint"]
        or doc.get("case_denominator")!=14902
        or len(doc.get("cases",[]))!=14902
        or doc.get("authority")!=AUTHORITY
        or doc.get("provider_requests")!=0
        or doc.get("new_paid_requests")!=0
    ):
        raise OriginalCrosswalkError("existing original-source crosswalk has changed")
    return doc


def build_original_source_crosswalk(
    settings: AtlasSettings, *, progress: Callable[[dict[str,Any]],None]|None=None,
) -> tuple[dict[str,Any],Path,str]:
    settings.assert_external_storage_binding("options")
    settings.assert_external_storage_binding("research_evidence")
    inventory,_,action=build_option_source_gap_inventory(settings,progress=progress)
    inventory=_inventory(inventory)
    if progress:
        progress({"stage":"REUSE_EXISTING_FULL_CASE_INVENTORY",
                  "action":action,"cases":inventory["case_denominator"],
                  "provider_requests":0})
    path=_target(settings,inventory)
    existing=_verified_existing(path,inventory)
    if existing is not None:
        return existing,path,"REUSED_VERIFIED_ORIGINAL_SOURCE_CROSSWALK_NO_RESOURCES_REOPENED"
    plan_path=settings.resolved_path(f"{PLAN_REL}/through_shard_070.json")
    if plan_path.is_symlink() or not plan_path.is_file():
        raise OriginalCrosswalkError("original accepted 2022 source plan missing")
    plan=_read_object(plan_path)
    sources=read_2022_original_memberships(settings,plan,inventory=inventory,progress=progress)
    shortlist=read_accepted_shortlist(settings)
    closeout=read_frozen_source_closeout(settings)
    native,_,native_action=build_multiyear_native_raw_open_source(settings,progress=progress)
    if progress:
        progress({"stage":"REUSE_ORIGINAL_NATIVE_PRICE_IDENTITY",
                  "action":native_action,"cases":native["case_denominator"],
                  "provider_requests":0})
    result=reconcile_original_sources(
        inventory,sources,shortlist,closeout,native=native,progress=progress
    )
    _exclusive(path,result)
    if _verified_existing(path,inventory)!=result:
        raise OriginalCrosswalkError("new original source crosswalk readback differs")
    return result,path,"WRITTEN_NEW_ORIGINAL_SOURCE_CROSSWALK"
