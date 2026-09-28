from __future__ import annotations

"""Offline physical-key reuse audit for a frozen multiyear chain-demand preview.

Read small chain-cache receipt/attempt metadata once, validate raw bytes only
for relevant overlapping historical chain sources, and never make a GET.
An exact-query 404 is not proof that a different strike window lacks options.
"""

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from typing import Any, Callable

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_batch_plan_v1 import _digest
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CACHE_SUBDIR, CONTRACT as CHAIN_CONTRACT, CandidateChainCacheError,
    _fingerprint, _paths, _valid_receipt,
)
from packages.data.marketdata_candidate_expansion_v1 import _exclusive, _read_object
from packages.data.marketdata_candidate_2025_structural_call_shortlist_v1 import (
    read_frozen_source_closeout,
)
from packages.data.marketdata_candidate_2025_source_closeout_v1 import (
    FROZEN_PLAN as ACCEPTED_2025_PLAN,
)
from packages.data.multiyear_physical_chain_source_demand_v1 import (
    AUTHORITY as DEMAND_AUTHORITY,
    CONTRACT as DEMAND_CONTRACT,
    build_physical_chain_source_demand,
)

CONTRACT="atlas-multiyear-global-chain-cache-overlap-v1"
OUTPUT_REL="data/options/manifests/multiyear_global_chain_cache_overlap_v1"
PREVIEW_STATUS="FROZEN_OFFLINE_FULL_DENOMINATOR_CHAIN_SOURCE_DEMAND_PREVIEW"
REUSE="REUSED_VERIFIED_LOCAL_COMPLETE_CHAIN_FULL_STRIKE_COVERAGE"
PARTIAL="LOCAL_COMPLETE_CHAIN_PARTIAL_STRIKE_COVERAGE_ONLY"
EXACT_GAP="VERIFIED_NO_DATA_FOR_EXACT_ORIGINAL_QUERY_ONLY"
UNRESOLVED="UNRESOLVED_PRIOR_ATTEMPT_OR_QUARANTINE_NO_RETRY"
MISSING="NO_LOCAL_MATCHING_PHYSICAL_CHAIN_SOURCE"
AUTHORITY={
    "provider_requests":0,"paid_request_authority":False,
    "historical_option_trade_or_fill":False,
    "option_contract_selected":False,
    "2026_protected_outcomes_read":False,
    "historical_quote_bodies_reopened":False,
    "no_data_scope":"EXACT_QUERY_ONLY",
    "paper":False,"live":False,
}


class GlobalChainOverlapError(ValueError):
    pass


def _window(raw:object)->tuple[Decimal,Decimal]:
    if not isinstance(raw,str):
        raise GlobalChainOverlapError("strike window must be explicit decimal text")
    parts=raw.split("-")
    if len(parts)!=2:
        raise GlobalChainOverlapError("strike window must have exact low-high bounds")
    try:
        left,right=(Decimal(v) for v in parts)
    except (InvalidOperation,ValueError) as exc:
        raise GlobalChainOverlapError("malformed original strike bounds") from exc
    if (not left.is_finite() or not right.is_finite() or
        left<=0 or left>right or right>Decimal("1000000")):
        raise GlobalChainOverlapError("unsafe physical strike bounds")
    return left,right


def _key(row:dict[str,Any])->tuple[str,str,str]:
    params=row["params"]
    key=(row["ticker"],params["date"],params["expiration"])
    try:
        date.fromisoformat(key[1])
        date.fromisoformat(key[2])
    except (TypeError,ValueError) as exc:
        raise GlobalChainOverlapError("malformed physical historical session/expiration") from exc
    if not all(isinstance(x,str) and x for x in key) or key[1]>=key[2]:
        raise GlobalChainOverlapError("invalid original physical key")
    return key


def _identity(row:dict[str,Any])->str:
    return _digest({"ticker":row["ticker"],"params":row["params"],
                    "mode":"HISTORICAL_EOD"})


def _validate_demand(doc:dict[str,Any])->None:
    unsigned=dict(doc)
    signature=unsigned.pop("demand_fingerprint",None)
    requests=doc.get("requests")
    if (
        signature!=_fingerprint(unsigned)
        or doc.get("contract")!=DEMAND_CONTRACT
        or doc.get("status")!=PREVIEW_STATUS
        or doc.get("case_denominator")!=14902
        or doc.get("new_stock_source_case_denominator_needing_preview")!=7838
        or doc.get("unique_unreconciled_physical_preview_queries")!=7646
        or doc.get("authority")!=DEMAND_AUTHORITY
        or doc.get("provider_requests")!=0
        or doc.get("new_paid_requests_proven")!=0
        or not isinstance(requests,list) or len(requests)!=7646
    ):
        raise GlobalChainOverlapError("accepted full-scope source preview changed")
    seen=set()
    cases=set()
    years=Counter()
    for row in requests:
        key=_key(row)
        rid=row.get("physical_request_identity")
        members=row.get("member_case_ids")
        if (
            row.get("endpoint")!=f"options/chain/{key[0]}/"
            or set(row["params"])!={"date","expiration","strike"}
            or rid!=_identity(row) or rid in seen
            or row.get("source_status")!="UNPAID_PHYSICAL_KEY_PREVIEW_NOT_GLOBAL_CACHE_RECONCILED"
            or row.get("global_cache_receipt_reconciled") is not False
            or row.get("new_paid_request_proven") is not False
            or row.get("historical_option_fill_verified") is not False
            or not isinstance(members,list) or not members
            or members!=sorted(set(members))
        ):
            raise GlobalChainOverlapError("original physical query preview is not intact")
        _window(row["params"]["strike"])
        for cid in members:
            if cid in cases:
                raise GlobalChainOverlapError("accepted stock case assigned to more than one source query")
            cases.add(cid)
        years[key[1][:4]]+=len(members)
        seen.add(rid)
    if len(cases)!=7838 or dict(years)!={
        "2021":1353,"2022":3,"2023":1601,"2024":1390,"2025":3491,
    }:
        raise GlobalChainOverlapError("multi-year source membership denominator changed")


def _receipt_metadata(
    path:Path, *, root:Path,
)->dict[str,Any]:
    if path.is_symlink() or not path.is_file():
        raise GlobalChainOverlapError("historical cache receipt is linked or non-file")
    try:
        item=_read_object(path)
        unsigned=dict(item)
        signature=unsigned.pop("receipt_fingerprint")
        params=item["params"]
        rid=item["request_identity"]
        source={"ticker":item["endpoint"].removeprefix("options/chain/").removesuffix("/"),
                "params":params}
        expected=_identity(source)
        canonical=_paths_root(root,rid)
    except (OSError,ValueError,TypeError,KeyError,AttributeError) as exc:
        raise GlobalChainOverlapError("unreadable existing historical chain metadata") from exc
    if (
        item.get("contract")!=CHAIN_CONTRACT
        or signature!=_fingerprint(unsigned)
        or not isinstance(params,dict)
        or set(params)!={"date","expiration","strike"}
        or rid!=expected
        or item.get("endpoint")!=f"options/chain/{source['ticker']}/"
        or path!=canonical.receipt
        or item.get("status") not in {"COMPLETE","QUARANTINED"}
        or type(item.get("body_bytes")) is not int
        or item["body_bytes"]<0
        or type(item.get("row_count")) is not int or item["row_count"]<0
    ):
        raise GlobalChainOverlapError(f"original cache receipt structure changed: {path.name}")
    key=_key(source)
    lo,hi=_window(params["strike"])
    return {
        "request_identity":rid,"ticker":key[0],"key":key,
        "strike_window":(lo,hi),"receipt_fingerprint":signature,
        "original_status":item["status"],
        "body_sha256":item["body_sha256"],
        "body_bytes":item["body_bytes"],
        "row_count":item["row_count"],
        "path":path,
    }


def _paths_root(root:Path,identity:str):
    # The existing source cache's hash-distributed layout is immutable.
    from packages.data.marketdata_candidate_chain_cache_v1 import ChainCachePaths
    folder=root/identity[:2]
    return ChainCachePaths(
        body=folder/f"{identity}.json",
        receipt=folder/f"{identity}.receipt.json",
        attempt=folder/f"{identity}.attempt.json",
        recovery=folder/f"{identity}.recovery.json",
    )


def _attempt_metadata(path:Path,*,root:Path)->dict[str,Any]:
    if path.is_symlink() or not path.is_file():
        raise GlobalChainOverlapError("original attempt is linked or non-file")
    try:
        item=_read_object(path)
        unsigned=dict(item)
        signature=unsigned.pop("intent_fingerprint")
        params=item["params"]
        rid=item["request_identity"]
        endpoint=item["endpoint"]
        ticker=endpoint.removeprefix("options/chain/").removesuffix("/")
        source={"ticker":ticker,"params":params}
    except (OSError,TypeError,ValueError,KeyError,AttributeError) as exc:
        raise GlobalChainOverlapError("unreadable historical provider attempt") from exc
    if (
        item.get("contract")!=CHAIN_CONTRACT
        or item.get("status")!="REQUEST_STARTED_CHARGE_UNKNOWN_UNTIL_RECEIPT"
        or signature!=_fingerprint(unsigned)
        or rid!=_identity(source)
        or path!=_paths_root(root,rid).attempt
        or endpoint!=f"options/chain/{ticker}/"
        or item.get("automatic_retry_permitted") is not False
    ):
        raise GlobalChainOverlapError("original paid attempt provenance invalid")
    key=_key(source)
    return {"request_identity":rid,"key":key,
            "strike_window":_window(params["strike"]),
            "intent_fingerprint":signature}


def _metadata_index(
    root:Path, *,progress:Callable[[dict[str,Any]],None]|None=None,
)->tuple[dict[tuple[str,str,str],list[dict[str,Any]]],dict[str,dict[str,Any]],str,dict[str,int]]:
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise GlobalChainOverlapError("existing chain root is not a regular directory")
    receipts=sorted(root.rglob("*.receipt.json")) if root.exists() else []
    attempts=sorted(root.rglob("*.attempt.json")) if root.exists() else []
    by_key:dict[tuple[str,str,str],list[dict[str,Any]]]=defaultdict(list)
    index:dict[str,dict[str,Any]]={}
    signatures=[]
    for i,path in enumerate(receipts,1):
        item=_receipt_metadata(path,root=root)
        if item["request_identity"] in index:
            raise GlobalChainOverlapError("duplicate original receipt identity")
        index[item["request_identity"]]=item
        by_key[item["key"]].append(item)
        signatures.append(["receipt",item["request_identity"],item["receipt_fingerprint"]])
        if progress and (i%500==0 or i==len(receipts)):
            progress({"stage":"EXISTING_CHAIN_RECEIPT_METADATA_INDEX",
                      "receipt_metadata_checked":i,"total":len(receipts),
                      "raw_chain_bodies_reopened":0,"provider_requests":0})
    pending:dict[str,dict[str,Any]]={}
    for path in attempts:
        item=_attempt_metadata(path,root=root)
        rid=item["request_identity"]
        if rid in pending:
            raise GlobalChainOverlapError("duplicate original attempt identity")
        if rid not in index:
            pending[rid]=item
        signatures.append(["attempt",rid,item["intent_fingerprint"]])
    for key in by_key:
        by_key[key].sort(key=lambda x:x["request_identity"])
    catalog=_fingerprint({
        "contract":CONTRACT,"source_cache_dir":CACHE_SUBDIR,
        "signed_metadata":sorted(signatures),
    })
    counts={"receipts":len(receipts),"attempts":len(attempts),
            "orphan_attempts":len(pending)}
    return by_key,pending,catalog,counts


def _candidate(
    request:dict[str,Any], candidate:dict[str,Any], *,
    settings:AtlasSettings,
    accepted25:dict[str,dict[str,Any]],
    validated:dict[str,dict[str,Any]],
)->dict[str,Any]:
    rid=candidate["request_identity"]
    if rid in validated:
        proof=validated[rid]
    else:
        source={
            "ticker":candidate["ticker"],
            "endpoint":f"options/chain/{candidate['ticker']}/",
            "params":{
                "date":candidate["key"][1],
                "expiration":candidate["key"][2],
                "strike":f"{candidate['strike_window'][0]:.2f}-{candidate['strike_window'][1]:.2f}",
            },
            "request_identity":rid,
        }
        paths=_paths(settings,rid)
        if (
            candidate["original_status"]=="QUARANTINED"
            and not paths.recovery.exists()
            and not paths.receipt.with_name(
                paths.receipt.name.replace(".receipt.json",".no_data.json")
            ).exists()
        ):
            # An old quarantined attempt is not a reusable source and must not
            # be retried. Preserve the exact identity in the blocker report.
            proof={"status":"UNRESOLVED_QUARANTINED_ORIGINAL",
                   "body_sha256":None}
        else:
            try:
                proof=_valid_receipt(paths,source)
            except (CandidateChainCacheError,OSError,ValueError,TypeError,KeyError) as exc:
                raise GlobalChainOverlapError(
                    f"intersecting historical source {rid} is incomplete or quarantined; no retry"
                ) from exc
            if proof is None:
                raise GlobalChainOverlapError(
                    f"original indexed receipt vanished before verification: {rid}"
                )
        old25=accepted25.get(rid)
        if old25 is not None:
            if (
                proof["body_sha256"]!=old25["raw_body_sha256"]
                or proof["status"]!=(
                    "VERIFIED_NO_DATA" if old25["status"]=="SOURCE_NO_DATA_VERIFIED"
                    else "COMPLETE"
                )
                or (proof["status"]=="VERIFIED_NO_DATA"
                    and proof["no_data_proof"]!=old25["proof_fingerprint"])
            ):
                raise GlobalChainOverlapError("accepted original 2025 pilot receipt drift")
        validated[rid]=proof
    return {
        "source_request_identity":rid,"source_status":proof["status"],
        "source_body_sha256":proof["body_sha256"],
        "source_receipt_fingerprint":candidate["receipt_fingerprint"],
        "source_strike_window":[str(v) for v in candidate["strike_window"]],
        "original_receipt_claimed_rows":candidate["row_count"],
        "original_receipt_claimed_bytes":candidate["body_bytes"],
        "source_raw_body_verified":proof["status"] in {"COMPLETE","VERIFIED_NO_DATA"},
        "source_2025_pilot":rid in accepted25,
        "original_2025_no_data_proof":proof.get("no_data_proof"),
    }


def freeze_global_overlap(
    preview:dict[str,Any],
    by_key:dict[tuple[str,str,str],list[dict[str,Any]]],
    orphan:dict[str,dict[str,Any]], *,
    verify_source:Callable[[dict[str,Any]],dict[str,Any]],
    catalog_fingerprint:str,
    metadata_counts:dict[str,int],
)->dict[str,Any]:
    """One preview member remains one source accounting row; no provider action."""
    _validate_demand(preview)
    orphan_by_key:dict[tuple[str,str,str],list[dict[str,Any]]]=defaultdict(list)
    for attempt in orphan.values():
        orphan_by_key[attempt["key"]].append(attempt)
    statuses=Counter()
    yearly={str(y):Counter() for y in range(2021,2027)}
    cases_by_year={str(y):Counter() for y in range(2021,2027)}
    rows=[]
    source_ids=set()
    matched_sources=set()
    for request in preview["requests"]:
        key=_key(request)
        low,high=_window(request["params"]["strike"])
        same_key=by_key.get(key,[])
        overlapping=[
            x for x in same_key
            if x["strike_window"][0]<=high and x["strike_window"][1]>=low
        ]
        exact=next((x for x in same_key if
                    x["request_identity"]==request["physical_request_identity"]),None)
        blocked=[
            x for x in orphan_by_key.get(key,[])
            if x["strike_window"][0]<=high and x["strike_window"][1]>=low
        ]
        # A complete covering original chain is reusable even if a different
        # exact query was uncertain. No original attempt is retried.
        verified=[]
        for item in overlapping:
            pointer=verify_source(item)
            verified.append({**pointer,
                "full_window":item["strike_window"][0]<=low and
                              item["strike_window"][1]>=high,
                "exact_requested_query":
                    item["request_identity"]==request["physical_request_identity"],
            })
            matched_sources.add(item["request_identity"])
        full=sorted(
            [x for x in verified if x["source_status"]=="COMPLETE" and x["full_window"]],
            key=lambda x:x["source_request_identity"],
        )
        exact_gap=next((x for x in verified if
            x["source_status"]=="VERIFIED_NO_DATA" and x["exact_requested_query"]),None)
        partial=sorted(
            [x for x in verified if x["source_status"]=="COMPLETE" and not x["full_window"]],
            key=lambda x:x["source_request_identity"],
        )
        quarantined=[
            x for x in overlapping if x["original_status"]=="QUARANTINED"
            and not any(v["source_request_identity"]==x["request_identity"]
                        and v["source_status"]=="VERIFIED_NO_DATA" for v in verified)
        ]
        if full:
            state=REUSE
            chosen=full[0]
        elif blocked or quarantined:
            state=UNRESOLVED
            chosen=None
        elif exact_gap:
            state=EXACT_GAP
            chosen=exact_gap
        elif partial:
            state=PARTIAL
            chosen=None
        else:
            state=MISSING
            chosen=None
        # No proof of absence for broader/different strike windows.
        statuses[state]+=1
        year=key[1][:4]
        yearly[year][state]+=1
        cases_by_year[year][state]+=len(request["member_case_ids"])
        rows.append({
            "physical_request_identity":request["physical_request_identity"],
            "key":list(key),
            "requested_strike_window":[str(low),str(high)],
            "case_ids":list(request["member_case_ids"]),
            "source_status":state,
            "reused_physical_source":chosen if state==REUSE else None,
            "verified_existing_overlaps":verified,
            "intersecting_orphan_attempt_ids":
                sorted(x["request_identity"] for x in blocked),
            "eligible_for_automatic_paid_retry":False,
            "provider_market_absence_proven":False,
            "historical_option_fill_verified":False,
        })
        source_ids.add(request["physical_request_identity"])
    if len(rows)!=7646 or len(source_ids)!=7646 or sum(statuses.values())!=7646:
        raise GlobalChainOverlapError("source coverage count no longer matches accepted preview")
    if sum(sum(x.values()) for x in cases_by_year.values())!=7838:
        raise GlobalChainOverlapError("source case membership count changed")
    if dict({k:sum(v.values()) for k,v in cases_by_year.items() if v})!={
        "2021":1353,"2022":3,"2023":1601,"2024":1390,"2025":3491
    }:
        raise GlobalChainOverlapError("source coverage changed original year denominators")
    doc={
        "contract":CONTRACT,
        "status":"COMPLETE_OFFLINE_GLOBAL_CHAIN_RECEIPT_OVERLAP_AUDIT",
        "source_demand_fingerprint":preview["demand_fingerprint"],
        "local_cache_metadata_catalog_fingerprint":catalog_fingerprint,
        "accepted_case_denominator":14902,
        "candidate_case_memberships":7838,
        "unique_physical_preview_queries":7646,
        "source_cache_metadata_counts":metadata_counts,
        "relevant_intersecting_source_identity_count":len(matched_sources),
        "by_status":dict(sorted(statuses.items())),
        "by_year_query_status":{k:dict(sorted(v.items())) for k,v in yearly.items()},
        "by_year_case_status":{k:dict(sorted(v.items())) for k,v in cases_by_year.items()},
        "rows":rows,
        "provider_requests":0,"new_paid_requests_authorized":0,
        "original_2022_quote_histories_reopened":0,
        "authority":AUTHORITY,
    }
    doc["overlap_fingerprint"]=_fingerprint(doc)
    return doc


def _target(settings:AtlasSettings,preview:dict[str,Any],catalog:str)->Path:
    return settings.resolved_path(
        f"{OUTPUT_REL}_{preview['demand_fingerprint'][:16]}_{catalog[:16]}.json"
    )


def _existing(path:Path,preview:dict[str,Any],catalog:str)->dict[str,Any]|None:
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise GlobalChainOverlapError("existing global overlap manifest is linked/non-file")
    doc=_read_object(path)
    unsigned=dict(doc)
    fp=unsigned.pop("overlap_fingerprint",None)
    if (
        fp!=_fingerprint(unsigned)
        or doc.get("contract")!=CONTRACT
        or doc.get("status")!="COMPLETE_OFFLINE_GLOBAL_CHAIN_RECEIPT_OVERLAP_AUDIT"
        or doc.get("source_demand_fingerprint")!=preview["demand_fingerprint"]
        or doc.get("local_cache_metadata_catalog_fingerprint")!=catalog
        or doc.get("accepted_case_denominator")!=14902
        or doc.get("candidate_case_memberships")!=7838
        or doc.get("unique_physical_preview_queries")!=7646
        or len(doc.get("rows",[]))!=7646
        or doc.get("authority")!=AUTHORITY
        or doc.get("provider_requests")!=0
        or doc.get("new_paid_requests_authorized")!=0
    ):
        raise GlobalChainOverlapError("existing source overlap manifest changed")
    return doc


def build_global_chain_cache_overlap(
    settings:AtlasSettings,*,
    progress:Callable[[dict[str,Any]],None]|None=None,
)->tuple[dict[str,Any],Path,str]:
    settings.assert_external_storage_binding("options")
    preview,_,action=build_physical_chain_source_demand(settings,progress=progress)
    _validate_demand(preview)
    if progress:
        progress({"stage":"REUSE_ACCEPTED_PHYSICAL_PREVIEW","action":action,
                  "physical_keys":7646,"provider_requests":0})
    # A frozen closeout is small and contains accepted 2025 original 11+1
    # source hashes. No original chain/quote bodies are reopened just to plan.
    closeout=read_frozen_source_closeout(settings)
    accepted25={x["request_identity"]:x for x in closeout["requests"]}
    if (
        len(accepted25)!=12
        or closeout["plan_fingerprint"]!=ACCEPTED_2025_PLAN
        or sum(x["status"]=="REUSED_VERIFIED" for x in accepted25.values())!=11
        or sum(x["status"]=="SOURCE_NO_DATA_VERIFIED" for x in accepted25.values())!=1
    ):
        raise GlobalChainOverlapError("frozen original 2025 pilot closeout changed")
    root=settings.resolved_path(CACHE_SUBDIR)
    by_key,pending,catalog,counts=_metadata_index(root,progress=progress)
    path=_target(settings,preview,catalog)
    old=_existing(path,preview,catalog)
    if old is not None:
        return old,path,"REUSED_IDENTICAL_SIGNED_LOCAL_CACHE_OVERLAP"
    verified:dict[str,dict[str,Any]]={}
    inspected=0
    def verify(item:dict[str,Any])->dict[str,Any]:
        nonlocal inspected
        prior=len(verified)
        result=_candidate(
            {},item,settings=settings,
            accepted25=accepted25,validated=verified,
        )
        if len(verified)!=prior and result["source_raw_body_verified"]:
            inspected+=1
            if progress and inspected%25==0:
                progress({"stage":"RELEVANT_CHAIN_BODY_VALIDATION",
                          "verified_relevant_source_bodies":inspected,
                          "all_cache_receipt_bodies_reread":False,
                          "provider_requests":0})
        return result
    doc=freeze_global_overlap(
        preview,by_key,pending,verify_source=verify,
        catalog_fingerprint=catalog,metadata_counts=counts,
    )
    doc["source_bodies_or_no_data_proofs_inspected_for_relevant_overlaps"]=inspected
    # Re-sign after adding a verified diagnostic, keeping originals immutable.
    doc.pop("overlap_fingerprint")
    doc["overlap_fingerprint"]=_fingerprint(doc)
    _exclusive(path,doc)
    if _existing(path,preview,catalog)!=doc:
        raise GlobalChainOverlapError("new immutable cache overlap readback changed")
    if progress:
        progress({"stage":"GLOBAL_PHYSICAL_CACHE_OVERLAP_COMPLETE",
                  "metadata_receipts":counts["receipts"],
                  "relevant_source_bodies_verified":inspected,
                  "physical_previews":7646,"by_status":doc["by_status"],
                  "provider_requests":0})
    return doc,path,"WRITTEN_NEW_GLOBAL_LOCAL_SOURCE_REUSE_AUDIT"
