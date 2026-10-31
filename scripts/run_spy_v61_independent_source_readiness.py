from __future__ import annotations

"""V61 source-readiness audit: exact original quote versus independent model inputs.

This read-only audit distinguishes verified one-minute SPY bars from a verified
fresh underlying tick at the decision second. It discovers other historical
option-source receipts but *never* treats them as independent IV estimates.
No provider methods, no broker, no simulation, no historical BSM fair value.
"""

import argparse
from collections import Counter
from contextlib import closing
from datetime import date,datetime,timedelta
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

from packages.core.settings import load_settings
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.intraday_semantics_audit import (
    _sample_rows,discover_minute_units,validate_minute_rows,
)
from packages.data.spy_v51_native_minute_orb_inventory import (
    _verify_monthly_unit_with_progress,
)
from packages.data.options_on_demand_source_cache_v38 import DB_REL
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v55_event_journal import verify_journal
from scripts.run_spy_v59_offline_quote_forensics import _report

ET=ZoneInfo("America/New_York")
ROOT=Path(__file__).resolve().parents[1]
CONTRACT="atlas-v61-independent-action-side-source-readiness-v1"
ORIGINAL="atlas-v56-spy-multi-session-closed-bar-quote-account-v1"


class ReadinessError(ValueError):
    pass


def print_progress(s):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {s}",flush=True)


def _signed(row):
    return {**row,"fingerprint":_fingerprint(row)}


def _original_decision(parent,day,root,verify):
    receipt=next((x for x in parent.get("sessions",[])
                  if x.get("session")==day),None)
    if receipt is None:
        raise ReadinessError("V61_DATE_NOT_IN_V56_PARENT")
    local=_report(root/f"{day}.json")
    j=verify(root/f"{day}.jsonl")
    if (local["fingerprint"]!=receipt["report_fingerprint"]
            or local["session"]!=day
            or j["tip_sha256"]!=receipt["event_journal_tip"]
            or j["report_fingerprint"]!=local["fingerprint"]):
        raise ReadinessError("V61_ORIGINAL_DAY_OR_JOURNAL_DISAGREES")
    action=next((x for x in local["events"]
                 if x.get("type")=="ORDER_ACTION_QUOTE_REFERENCE"),None)
    order=action.get("order") if action is not None else None
    action_quote=action.get("action") if action is not None else None
    result={
        "day":day,"original_status":local["status"],
        "original_censor_reason":local["censor_reason"],
        "selected_contract":local["signal"]["selected_contract"],
        "original_report_fingerprint":local["fingerprint"],
        "original_journal_sha_tip":j["tip_sha256"],
        "source_query_id":local["source_query_id"],
        "source_sha256":local["source_sha256"],
        "signal_decision_at_et":local["signal"]["decision_at_et"],
        "order_quote":order,"action_quote":action_quote,
        "action_adverse_ask_change_pct":action.get("adverse_ask_change_pct")
                                         if action else None,
        "action_side":"ASK_FOR_LONG_ENTRY",
        "source_missing_if_no_order_event":action is None,
    }
    return result


def _prior_completed_spy_bar(rows,target):
    """Only a completed 1-minute OHLC; cannot prove exact second-level spot."""
    stamp=datetime.fromisoformat(target).astimezone(ET)
    selected=None
    for bar in rows:
        value=bar.get("timestamp_utc")
        if isinstance(value,str):
            start=datetime.fromisoformat(value.replace("Z","+00:00")).astimezone(ET)
        elif isinstance(value,datetime):
            if value.tzinfo is None:
                raise ReadinessError("V61_MINUTE_BAR_WITHOUT_TIMEZONE")
            start=value.astimezone(ET)
        else:
            raise ReadinessError("V61_MINUTE_BAR_NO_TIMESTAMP")
        # A 09:59 UTC-local minute bar does not exist until 10:00 ET.
        finish=start+timedelta(minutes=1)
        if finish>stamp:
            continue
        if selected is None or start>selected[0]:
            selected=(start,finish,bar)
    if selected is None:
        return {"available":False,
                "reason":"NO_COMPLETED_SPY_BAR_BY_DECISION_SECOND",
                "second_level_spot_price_proven":False}
    st,finish,bar=selected
    return {
        "available":True,
        "original_bar_start_et":st.isoformat(),
        "bar_complete_no_earlier_than_et":finish.isoformat(),
        "last_bar_close":str(bar["close"]),
        "last_bar_high":str(bar["high"]),
        "last_bar_low":str(bar["low"]),
        "last_bar_open":str(bar["open"]),
        "minutes_since_bar_complete":(stamp-finish).total_seconds()/60,
        "spot_basis":"LAST_COMPLETED_1MIN_OHLC_NOT_TRADABLE_TICK",
        "second_level_spot_price_proven":False,
        "bar_close_first_publication_latency_proven":False,
        "market_price_at_exact_action_second_known":False,
    }


def _inventory_existing_option_receipts(settings,day,target_query):
    """Read source index in ro mode. An archived candidate is NOT calibrated IV."""
    db=settings.resolved_path(DB_REL)
    if not db.is_file() or db.is_symlink():
        return {"state":"V38_INDEX_UNAVAILABLE",
                "candidate_receipts":[],"candidate_counts":{},
                "independent_prior_volatility_verified":False}
    try:
        with closing(sqlite3.connect(db.resolve().as_uri()+"?mode=ro",
                                     uri=True,timeout=20)) as connection:
            raw=connection.execute(
                "SELECT query_id,request_json,state,source_sha,source_rows "
                "FROM sources WHERE request_json LIKE ? ORDER BY query_id",
                ("%"+day+"%",)).fetchall()
    except sqlite3.Error as exc:
        raise ReadinessError("V61_SOURCE_INDEX_READ_ONLY_ERROR") from exc
    if len(raw)>10000:
        raise ReadinessError("V61_TOO_MANY_EXACT_DATE_INDEX_ROWS")
    hits=[]
    state_count=Counter()
    for qid,request_json,state,sha,count in raw:
        try:
            request=json.loads(request_json)
        except (ValueError,TypeError) as exc:
            raise ReadinessError("V61_INVALID_SOURCE_REQUEST_JSON") from exc
        p=request.get("kwargs") or {}
        if p.get("date_et")!=day or p.get("symbol")!="SPY":
            continue
        state_count[state]+=1
        hits.append({
            "source_query_id":qid,
            "is_original_acted_option_source":qid==target_query,
            "method":request.get("method"),"provider":request.get("provider"),
            "status":state,
            "contract":{k:p.get(k) for k in ("symbol","date_et","expiration",
                                             "strike","right","interval")},
            "source_sha256":sha,"source_rows":count,
            "does_not_establish_independent_prior_iv":True,
        })
    return {
        "state":"READ_ONLY_RECEIPT_INDEX_INVENTORY",
        "candidate_receipts":hits,"candidate_counts":dict(sorted(state_count.items())),
        "independent_prior_volatility_verified":False,
        "source_archives_not_read_or_mutated":True,
    }


def probe(cohort_dir,output,*,day="2025-06-13",
          decision_time="10:00:01",verify=verify_journal,
          discover=discover_minute_units,integrity=_verify_monthly_unit_with_progress,
          sample=_sample_rows,validate=validate_minute_rows,
          settings_factory=load_settings,source_inventory=_inventory_existing_option_receipts,
          progress=print_progress):
    if output.exists() or output.is_symlink():
        raise ReadinessError("V61_IMMUTABLE_OUTPUT_EXISTS")
    target=datetime.fromisoformat(day+"T"+decision_time).replace(tzinfo=ET)
    parent=_report(cohort_dir/"summary.json")
    if parent.get("contract")!=ORIGINAL:
        raise ReadinessError("V61_V56_PARENT_CONTRACT_MISMATCH")
    progress("STAGE_START V61 original day + SHA linked journal")
    original=_original_decision(parent,day,cohort_dir,verify)
    progress("STAGE_PASS V61 verified original"
             f" day={day} status={original['original_status']}"
             f" rejection={original['original_censor_reason']}")
    progress("STAGE_START V61 verify already archived stock minute SHA")
    layout=V2Layout.beneath(ROOT/"data")
    units=discover(layout,target_year=target.year,target_month=target.month,
                   progress=progress)
    matches=[x for x in units if x.year==target.year and
             x.month==target.month and "SPY" in x.symbols]
    if len(matches)!=1:
        raise ReadinessError("V61_EXPECTED_ONE_NATIVE_SPY_MONTH")
    unit=matches[0]
    check=integrity(unit,progress)
    if not check["accepted"]:
        raise ReadinessError("V61_ORIGINAL_STOCK_MINUTE_SHA_REJECTED")
    rows=sample(unit.canonical_path,symbol="SPY",session_date=date.fromisoformat(day))
    if rows:
        valid=validate(rows,sample_class="SPY_0DTE_ORB_SOURCE_PREVIEW",
                       symbol="SPY",session_date=date.fromisoformat(day))
        if not valid["accepted"]:
            raise ReadinessError("V61_SPY_MINUTE_GEOMETRY_REJECTED")
    spot=_prior_completed_spy_bar(rows,target.isoformat())
    spot["monthly_unit_id"]=unit.unit_id
    spot["monthly_unit_source_sha256"]=unit.canonical_sha256
    spot["monthly_unit_checkpoint"]=str(unit.checkpoint_path)
    progress("STAGE_PASS V61 minute source verified"
             f" bars={len(rows)} completed_spot_bar={spot.get('last_bar_close')}"
             " one_second_stock_quote_evidence=False")
    progress("STAGE_START V61 inventory preexisting option receipts read_only")
    settings=settings_factory(ROOT,"development")
    prior=source_inventory(settings,day,original["source_query_id"])
    progress("STAGE_PASS V61 option receipt inventory"
             f" indexed={len(prior['candidate_receipts'])} independently_derived_iv=False")
    result=_signed({
        "contract":CONTRACT,"session":day,"target_decision_at_et":target.isoformat(),
        "original_report":original,
        "original_account_report_fingerprint":parent["fingerprint"],
        "historical_stock_bar_evidence":spot,
        "cached_options_receipt_inventory":prior,
        "independent_current_spot_tick_verified":False,
        "historical_independent_iv_band_verified":False,
        "historical_rate_asof_verified":False,
        "historical_dividend_asof_verified":False,
        "side_aware_bsm_reference_status":"ABSTAIN_MISSING_INDEPENDENT_MODEL_INPUTS",
        "no_black_scholes_fair_value_computed_from_suspect_mid":True,
        "cash_pnl_or_execution_changed":False,
        "no_theta_data_requests":True,
        "provider_requests":0,"broker_orders":0,
        "model_policy_promoted":False,"historical_alpha_validated":False,
    })
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x",encoding="utf-8") as f:
        json.dump(result,f,sort_keys=True,indent=2,allow_nan=False)
        f.write("\n")
    progress("COMPLETE V61 source-readiness"
             f" day={day} original_status={original['original_status']}"
             f" spot_source_minute={spot['available']}"
             f" result={result['side_aware_bsm_reference_status']}"
             f" output={output} provider_calls=0")
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort-dir",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--day",default="2025-06-13")
    parser.add_argument("--decision-time",default="10:00:01")
    args=parser.parse_args(argv)
    try:
        probe(args.cohort_dir,args.output,day=args.day,
              decision_time=args.decision_time)
        return 0
    except Exception as exc:
        print_progress(f"STOPPED V61 error_class={type(exc).__name__}"
                       " provider_requests=0 broker_orders=0 source_modified=False")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
