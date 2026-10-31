from __future__ import annotations

"""V60 one-session alternate quote-admission experiment over immutable V56 sources.

Read-only V38 cache; no ThetaData GET. Explicitly classify isolated untradeable
spread quotes, never interpolate/carry-forward/substitute prices, never count
invalid bids as filled exits, and refuse to skip uncertain stop/target triggers.
Original V55/V56 result remains unchanged and immutable.
"""

import argparse
from bisect import bisect_left
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v55_closed_bar_option_replay import (
    _quote, _read_timestamp, replay_source, V55Error,
)
from packages.simulation.spy_v55_event_journal import save_journal, verify_journal
from packages.simulation.spy_v57_causal_exit_shadow import RISK_SHARE,FEE
from scripts.run_spy_v59_offline_quote_forensics import (
    _local_cache_only,_report,ForensicError,
)

ROOT=Path(__file__).resolve().parents[1]
ET=ZoneInfo("America/New_York")
CONTRACT="atlas-v60-isolated-untradeable-quote-admission-v1"
V56_PARENT="atlas-v56-spy-multi-session-closed-bar-quote-account-v1"
QUALIFIED_SOURCE_STATES={"CACHE_HIT","FETCHED_AND_ARCHIVED"}
MAX_TOTAL_SPREAD_REJECTIONS=10
MAX_CONSECUTIVE_SPREAD_REJECTIONS=2
MAX_ELIGIBLE_QUOTE_GAP_SECONDS=3


class RecoveryError(ValueError):
    pass


def emit(message):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {message}",
          flush=True)


def _signed(doc):
    return {**doc,"fingerprint":_fingerprint(doc)}


def _cash(value):
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _sanitize_quote_tape(source,original,*,params=None):
    """Return original row-index mapping plus strictly validated candidate tape.

    This is a non-promoted research alternate. Skip only an isolated post-entry
    spread invalidity where the raw bid does not cross the registered V55 fixed
    stop or take-profit. Strictly forbid ambiguous original stop/target touches.
    """
    params=params or {}
    rows=source.get("source_rows") or ()
    if source.get("status") not in QUALIFIED_SOURCE_STATES:
        raise RecoveryError("V60_SOURCE_ARCHIVE_NOT_QUALIFIED")
    if (source.get("source_sha256")!=original.get("source_sha256")
            or source.get("query_id")!=original.get("source_query_id")):
        raise RecoveryError("V60_EXACT_SOURCE_SHA_OR_QUERY_MISMATCH")
    signal=original.get("signal")
    if not isinstance(signal,dict):
        raise RecoveryError("V60_ORIGINAL_SIGNAL_MISSING")
    contract=signal.get("selected_contract")
    if not isinstance(contract,dict):
        raise RecoveryError("V60_ORIGINAL_CONTRACT_MISSING")
    requirement=source.get("exact_requirement") or {}
    req_kwargs=requirement.get("kwargs") or {}
    if (requirement.get("method")!="option_history_exact_quote_tape"
            or any(str(req_kwargs.get(k))!=str(v)
                   for k,v in contract.items())
            or req_kwargs.get("interval") not in ("1s","tick")):
        raise RecoveryError("V60_ORIGINAL_EXACT_CONTRACT_IDENTITY_MISMATCH")
    action_events=[e for e in original.get("events",[])
                   if e.get("type")=="ORDER_ACTION_QUOTE_REFERENCE"]
    entries=[e for e in original.get("events",[])
             if e.get("type")=="MODELED_ENTRY_QUOTE_REFERENCE"]
    if len(action_events)!=1 or len(entries)!=1:
        raise RecoveryError("V60_ORIGINAL_ENTRY_AUDIT_INVALID")
    entry=entries[0]
    quantity=entry.get("qty")
    if type(quantity) is not int or quantity<=0:
        raise RecoveryError("V60_ORIGINAL_QUANTITY_INVALID")
    ask=Decimal(str(entry["ask"]))
    action_at=datetime.fromisoformat(str(action_events[0]["action"]["timestamp_et"]))
    if action_at.tzinfo is None:
        raise RecoveryError("V60_ACTION_CLOCK_NOT_AWARE")
    if not isinstance(rows,(list,tuple)) or len(rows)<3:
        raise RecoveryError("V60_NO_VERIFIED_SOURCE_ROWS")
    day=date.fromisoformat(original["session"])
    clocks=[_read_timestamp(r,day) for r in rows]
    if clocks!=sorted(clocks) or len(clocks)!=len(set(clocks)):
        raise RecoveryError("V60_SOURCE_CLOCK_OUT_OF_ORDER_OR_DUPLICATE")
    actidx=bisect_left(clocks,action_at)
    if actidx>=len(clocks) or clocks[actidx]!=action_at:
        raise RecoveryError("V60_ACTION_QUOTE_MISSING_FROM_ORIGINAL")
    if _quote(rows[actidx],day=day,contract=contract)["ask"]!=str(ask):
        raise RecoveryError("V60_ORIGINAL_ACTION_PRICE_CHANGED")
    stop=ask/Decimal(2)
    target=ask*2
    # This is only an indicative floor using V56 cash, not independent V58
    # equity: never turn it into a verified V57 exit or net account return.
    baseline_equity=Decimal(str(original["starting_cash"]))
    v57_indicative_floor=max(Decimal(0),ask-
        ((baseline_equity*RISK_SHARE)-(2*FEE*quantity))/(quantity*100))
    skipped=[]
    retained=[]
    index_map=[]
    consecutive=0
    previous_qualified_clock=None
    max_gap=0.0
    max_consecutive=0
    for i,row in enumerate(rows):
        stamp=clocks[i]
        try:
            _quote(row,day=day,contract=contract)
        except (V55Error,KeyError,TypeError,ValueError) as exc:
            error=str(exc)
            if i<=actidx:
                raise RecoveryError("V60_INVALID_PREENTRY_OR_ACTION_QUOTE") from exc
            if error!="QUOTE_SPREAD_ABOVE_15_PERCENT":
                raise RecoveryError("V60_UNREGISTERED_INVALID_QUOTE_TYPE") from exc
            consecutive+=1
            max_consecutive=max(max_consecutive,consecutive)
            if (len(skipped)>=MAX_TOTAL_SPREAD_REJECTIONS
                    or consecutive>MAX_CONSECUTIVE_SPREAD_REJECTIONS):
                raise RecoveryError("V60_EXCESSIVE_UNTRADEABLE_QUOTE_RUN")
            bid=Decimal(str(row.get("bid")))
            bad_ask=Decimal(str(row.get("ask")))
            if not bid.is_finite() or not bad_ask.is_finite() or bid<=0:
                raise RecoveryError("V60_NONFINITE_INVALID_QUOTE_CANNOT_SKIP")
            if bid<=stop or bid>=target:
                raise RecoveryError("V60_AMBIGUOUS_FIXED_EXIT_ON_BAD_SPREAD")
            skipped.append({
                "raw_source_row_index":i,"timestamp_et":stamp.isoformat(),
                "reason":error,"bid_untradeable":str(bid),
                "ask_untradeable":str(bad_ask),
                "bid_size":row.get("bid_size"),"ask_size":row.get("ask_size"),
                "observed_spread_pct":str((bad_ask-bid)*200/(bad_ask+bid)),
                "original_stop_bid":str(stop),
                "original_target_bid":str(target),
                "v57_indicative_risk_floor_bid":str(v57_indicative_floor),
                "potential_v57_risk_crossing":bid<=v57_indicative_floor,
                "never_modeled_as_a_fill":True,
            })
            continue
        consecutive=0
        if previous_qualified_clock is not None:
            gap=(stamp-previous_qualified_clock).total_seconds()
            max_gap=max(max_gap,gap)
            if i>actidx and gap>MAX_ELIGIBLE_QUOTE_GAP_SECONDS:
                raise RecoveryError("V60_ELIGIBLE_PATH_GAP_EXCEEDS_THREE_SECONDS")
        previous_qualified_clock=stamp
        retained.append(row)
        index_map.append(i)
    if not skipped:
        raise RecoveryError("V60_NO_SPREAD_REJECTIONS_TO_DIAGNOSE")
    return {
        "source":{**source,"source_rows":tuple(retained)},
        "original_row_count":len(rows),"retained_row_count":len(retained),
        "original_row_index_map":index_map,
        "skipped":skipped,"max_consecutive_invalid":max_consecutive,
        "max_qualified_observation_gap_seconds":max_gap,
        "original_entry_ask":str(ask),"original_entry_qty":quantity,
        "original_fixed_stop_bid":str(stop),"original_fixed_target_bid":str(target),
        "v57_indicative_risk_floor_bid":str(v57_indicative_floor),
        "v57_risk_crossed_at_invalid_quote":any(
            s["potential_v57_risk_crossing"] for s in skipped),
        "source_was_never_modified":True,
    }


def recover(cohort_dir,output_dir,*,target_session="2025-06-13",
            verify=verify_journal,cache_reader=None,settings_factory=load_settings,
            progress=emit):
    progress(f"START V60 isolated-spread quote admission"
             f" target={target_session} paid_provider_calls=0 broker_orders=0")
    if output_dir.exists() or output_dir.is_symlink():
        raise RecoveryError("V60_IMMUTABLE_OUTPUT_ALREADY_EXISTS")
    parent=_report(cohort_dir/"summary.json")
    if parent.get("contract")!=V56_PARENT:
        raise RecoveryError("V60_V56_PARENT_CONTRACT_INVALID")
    original_row=next((x for x in parent["sessions"]
                       if x["session"]==target_session),None)
    if original_row is None:
        raise RecoveryError("V60_TARGET_NOT_IN_FROZEN_ACCOUNT")
    if (original_row["status"]!="UNRESOLVED_POSITION"
            or original_row.get("censor_reason")!="UNQUALIFIED_EXIT_QUOTE_PATH"):
        raise RecoveryError("V60_WRONG_ORIGINAL_BLOCKER_TYPE")
    path=cohort_dir/f"{target_session}.json"
    original=_report(path)
    if (original["fingerprint"]!=original_row["report_fingerprint"]
            or original["session"]!=target_session
            or original["status"]!="UNRESOLVED_POSITION"
            or original["censor_reason"]!="UNQUALIFIED_EXIT_QUOTE_PATH"):
        raise RecoveryError("V60_ORIGINAL_DAY_DISAGREES_WITH_PARENT")
    journal_receipt=verify(cohort_dir/f"{target_session}.jsonl")
    if (journal_receipt["report_fingerprint"]!=original["fingerprint"]
            or journal_receipt["tip_sha256"]!=original_row["event_journal_tip"]):
        raise RecoveryError("V60_ORIGINAL_JOURNAL_RECEIPT_INVALID")
    progress(f"STAGE_PASS verify_original_sha_journal"
             f" day={target_session} event_count={journal_receipt['runtime_events']}")
    qid=original.get("source_query_id")
    if qid is None:
        raise RecoveryError("V60_ORIGINAL_SOURCE_QUERY_MISSING")
    if cache_reader is not None:
        archive=cache_reader(qid)
    else:
        settings=settings_factory(ROOT,"development")
        archive=_local_cache_only(settings,qid)
    source=archive.get("source")
    if source is None:
        raise RecoveryError("V60_REQUIRED_ORIGINAL_SOURCE_ARCHIVE_MISSING")
    progress(f"STAGE_PASS verify_original_cache"
             f" status={archive['cache_evidence']} rows={len(source['source_rows'])}")
    cleaned=_sanitize_quote_tape(source,original)
    progress(f"STAGE_PASS qualify_nonexecutable_quote_rejections"
             f" original_rows={cleaned['original_row_count']}"
             f" ineligible={len(cleaned['skipped'])}"
             f" qualified={cleaned['retained_row_count']}"
             f" max_quote_gap={cleaned['max_qualified_observation_gap_seconds']}"
             f" v57_bad_quote_might_touch_stop={cleaned['v57_risk_crossed_at_invalid_quote']}")
    replay=replay_source(
        original["signal"],cleaned["source"],
        starting_cash=original["starting_cash"],
        lag_seconds=original["policy"]["lag_seconds"],
        max_adverse_pct=original["policy"]["max_adverse_pct"],
        progress=progress)
    entry=[e for e in replay["events"] if e["type"]=="MODELED_ENTRY_QUOTE_REFERENCE"]
    if len(entry)!=1 or (entry[0]["qty"]!=cleaned["original_entry_qty"]
                           or Decimal(entry[0]["ask"])!=Decimal(cleaned["original_entry_ask"])):
        raise RecoveryError("V60_REPLAY_CHANGES_FROZEN_ENTRY")
    if replay["entry_debit"]!=original["entry_debit"]:
        raise RecoveryError("V60_REPLAY_ENTRY_CASH_CHANGED")
    for e in replay["events"]:
        if "row" in e:
            idx=e["row"]
            if type(idx) is not int or idx>=len(cleaned["original_row_index_map"]):
                raise RecoveryError("V60_DERIVED_ROW_OUTSIDE_ORIGINAL")
            e["original_source_row_index"]=cleaned["original_row_index_map"][idx]
    # Preserve V55's exact strategy mechanics while versioning the new
    # admission policy and retaining the *full* omitted quote evidence.
    replay["quote_hygiene_variant_contract"]=CONTRACT
    replay["parent_v56_fingerprint"]=parent["fingerprint"]
    replay["parent_original_day_fingerprint"]=original["fingerprint"]
    replay["parent_original_journal_tip"]=journal_receipt["tip_sha256"]
    replay["original_source_sha256"]=source["source_sha256"]
    replay["original_source_query_id"]=source["query_id"]
    replay["source_quote_admission_policy"]={
        "mode":"POTENTIAL_ONLY_ISOLATED_UNTRADEABLE_SPREAD_QUOTE_SKIP",
        "max_source_spread_pct":15,
        "max_invalid_quote_count":MAX_TOTAL_SPREAD_REJECTIONS,
        "max_consecutive_invalid":MAX_CONSECUTIVE_SPREAD_REJECTIONS,
        "max_qualified_gap_seconds":MAX_ELIGIBLE_QUOTE_GAP_SECONDS,
        "original_exit_threshold_crossing_on_skipped_bid_is_censored":True,
        "interpolate_or_replace_quote":False,
        "use_for_validated_historical_alpha":False,
        "policy_developed_after_observing_june_13":True,
    }
    replay["original_row_count"]=cleaned["original_row_count"]
    replay["modeled_row_count"]=cleaned["retained_row_count"]
    replay["excluded_untradeable_source_quotes"]=cleaned["skipped"]
    replay["qualified_max_quote_gap_seconds"]=cleaned["max_qualified_observation_gap_seconds"]
    replay["independent_v57_possible_risk_touch_on_untradeable_quote"]=cleaned[
        "v57_risk_crossed_at_invalid_quote"]
    replay["independent_v57_net_pnl_not_inferable_from_this_baseline"] = True
    replay["source_rows_were_filtered_for_developmental_alternate_only"]=True
    replay["fingerprint"]=_fingerprint({k:v for k,v in replay.items()
                                         if k!="fingerprint"})
    output_dir.mkdir(parents=True,exist_ok=False)
    rpt=output_dir/f"{target_session}.json"
    logpath=output_dir/f"{target_session}.jsonl"
    receipt=save_journal(logpath,replay,progress=progress)
    with rpt.open("x",encoding="utf-8") as out:
        json.dump(replay,out,sort_keys=True,indent=2,allow_nan=False)
        out.write("\n")
    summary=_signed({
        "contract":CONTRACT,"target_session":target_session,
        "parent_v56_account_fingerprint":parent["fingerprint"],
        "parent_report_fingerprint":original["fingerprint"],
        "parent_journal_tip":journal_receipt["tip_sha256"],
        "original_status":original["status"],
        "original_censor_reason":original["censor_reason"],
        "original_terminal_equity":original["terminal_equity_if_resolved"],
        "source_sha256":source["source_sha256"],
        "source_query_id":source["query_id"],
        "original_source_rows":cleaned["original_row_count"],
        "derived_qualified_rows":cleaned["retained_row_count"],
        "source_spread_rejections":cleaned["skipped"],
        "derived_max_gap_seconds":cleaned["max_qualified_observation_gap_seconds"],
        "derived_status":replay["status"],
        "derived_censor_reason":replay["censor_reason"],
        "derived_pnl_if_resolved":replay["trade_net_pnl"],
        "derived_terminal_equity_if_resolved":replay["terminal_equity_if_resolved"],
        "derived_report_path":str(rpt),"derived_report_fingerprint":replay["fingerprint"],
        "derived_sha_journal_path":str(logpath),
        "derived_sha_journal_tip":receipt["tip_sha256"],
        "risk_touch_on_untradeable_quote_for_v57_indicative_floor":cleaned[
            "v57_risk_crossed_at_invalid_quote"],
        "v57_net_return_assigned":False,
        "actual_broker_fills":0,"provider_requests":0,"broker_requests":0,
        "independent_holdout_valid":False,
        "quote_variant_selected_after_source_review":True,
        "historical_alpha_validated":False,
    })
    out=output_dir/"summary.json"
    with out.open("x",encoding="utf-8") as stream:
        json.dump(summary,stream,sort_keys=True,indent=2,allow_nan=False)
        stream.write("\n")
    progress(f"COMPLETE V60 recovered={replay['status']=='CLOSED_QUOTE_REFERENCE'}"
             f" state={replay['status']}"
             f" pnl={replay['trade_net_pnl']}"
             f" skipped={len(cleaned['skipped'])}"
             f" risk_touch_v57={cleaned['v57_risk_crossed_at_invalid_quote']}"
             f" summary={out} provider_calls=0 broker_orders=0")
    return 0 if replay["status"]=="CLOSED_QUOTE_REFERENCE" else 2


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort-dir",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--target-session",default="2025-06-13")
    args=parser.parse_args(argv)
    try:
        return recover(args.cohort_dir,args.output_dir,target_session=args.target_session)
    except Exception as exc:
        emit(f"STOPPED V60 type={type(exc).__name__}"
             " source_immutable=True no_provider_get=True broker_orders=0")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
