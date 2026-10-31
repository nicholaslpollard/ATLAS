from __future__ import annotations

"""V65: complete independent June weekday opportunity/source matrix, OFFLINE.

Reuse V55 signal and replay unchanged. Read native SPY minute bars and the V38
source index only. ARCHIVED original options sources must pass original V38 SHA
verification; all missing, ambiguous or failed sources abstain without retries.
A standalone per-day replay with fixed $25k does NOT reconstruct a cumulative
account or demonstrate any broker fills or validated historical profitability.
"""

import argparse
from collections import Counter
from contextlib import closing
from datetime import date,datetime,timedelta
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

from packages.core.settings import load_settings
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.intraday_semantics_audit import (
    B34_MAX_SAMPLE_DATE,_sample_rows,discover_minute_units,validate_minute_rows,
)
from packages.data.spy_v51_native_minute_orb_inventory import (
    _verify_monthly_unit_with_progress,
)
from packages.data.options_on_demand_source_cache_v38 import (
    DB_REL, normalize_source_requirement,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v55_closed_bar_option_replay import (
    closed_bar_signal,replay_source,
)
from scripts.run_spy_v59_offline_quote_forensics import _local_cache_only
from scripts.run_spy_v56_multi_session_quote_replay import dates_in_window

ROOT=Path(__file__).resolve().parents[1]
ET=ZoneInfo("America/New_York")
CONTRACT="atlas-v65-full-horizon-spy-closed-bar-offline-source-gate-v1"


class V65Error(ValueError):
    pass


def announce(s):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {s}",
          flush=True)


def _signed(doc):
    return {**doc,"fingerprint":_fingerprint(doc)}


def _lookup_source_receipt(settings,requirement,*,reader=None):
    """The ONLY allowed cache interaction is read-only exact-key inventory."""
    qid=_fingerprint(requirement)
    if reader is not None:
        row=reader(qid)
    else:
        db=settings.resolved_path(DB_REL)
        if db.is_symlink():
            raise V65Error("V65_SOURCE_REGISTRY_SYMLINK")
        if not db.is_file():
            row=None
        else:
            try:
                with closing(sqlite3.connect(db.resolve().as_uri()+"?mode=ro",
                                             uri=True,timeout=15)) as con:
                    row=con.execute(
                        "SELECT query_id,request_json,state,source_sha,source_rows "
                        "FROM sources WHERE query_id=?",
                        (qid,)).fetchone()
            except sqlite3.Error as exc:
                raise V65Error("V65_SOURCE_INDEX_READ_ONLY_ERROR") from exc
    if row is None:
        return {"query_id":qid,"state":"NOT_REGISTERED",
                "archive_sha256":None,"recorded_rows":None,
                "same_query_retry_permitted":False,
                "provider_dispatch_outcome":"UNKNOWN_IF_EVER_DISPATCHED"}
    if len(row)!=5 or row[0]!=qid:
        raise V65Error("V65_INVALID_EXACT_SOURCE_ROW")
    try:
        request=json.loads(row[1])
    except (ValueError,TypeError) as exc:
        raise V65Error("V65_INVALID_SOURCE_REQUEST_JSON") from exc
    if request!=requirement or _fingerprint(request)!=qid:
        raise V65Error("V65_SOURCE_EXACT_IDENTITY_CHANGED")
    if row[2] not in ("ARCHIVED","NO_DATA_EXPLICIT","FAILED_RETRYABLE","IN_FLIGHT"):
        raise V65Error("V65_UNKNOWN_SOURCE_STATE")
    return {
        "query_id":qid,"state":row[2],
        "archive_sha256":row[3],"recorded_rows":row[4],
        "same_query_retry_permitted":False,
        "provider_dispatch_outcome":(
            "ORIGINAL_ARCHIVE_POSSIBLE" if row[2]=="ARCHIVED" else
            "CERTIFIED_NO_DATA" if row[2]=="NO_DATA_EXPLICIT" else
            "UNKNOWN_AFTER_FAILED_OR_INFLIGHT_DISPATCH"
        ),
    }


def _source_requirement(signal):
    contract=signal["selected_contract"]
    if contract is None:
        return None
    t=datetime.fromisoformat(signal["decision_at_et"])
    kwargs={
        **contract,
        "start_time_et":t.strftime("%H:%M:%S")+".000",
        "end_time_et":"15:30:00.000",
        "interval":"1s",
    }
    return normalize_source_requirement("option_history_exact_quote_tape",kwargs)


def _replay(signal,source,*,replay_fn=replay_source):
    original=replay_fn(signal,source,starting_cash="25000",
                       lag_seconds=1,max_adverse_pct="1")
    if original.get("fingerprint")!=_fingerprint({
            k:v for k,v in original.items() if k!="fingerprint"}):
        raise V65Error("V65_STANDALONE_REPLAY_FINGERPRINT_INVALID")
    return original


def inspect(start,end,output,*,discover=discover_minute_units,
            integrity=_verify_monthly_unit_with_progress,
            sample=_sample_rows,validate=validate_minute_rows,
            signal_factory=closed_bar_signal,
            cache_read=_local_cache_only,
            settings_factory=load_settings,receipt_reader=None,
            replay_fn=replay_source,progress=announce):
    if output.exists() or output.is_symlink():
        raise V65Error("V65_IMMUTABLE_OUTPUT_EXISTS")
    days=list(dates_in_window(start,end))
    if not days or len(days)>45:
        raise V65Error("V65_EMPTY_OR_OVERSIZED_DATE_WINDOW")
    progress("START V65 offline full-window SPY signal and source inventory"
             f" days={len(days)} start={start} end={end}"
             " requests=0 brokers=0 no_failure_retries=True")
    settings=settings_factory(ROOT,"development")
    layout=V2Layout.beneath(ROOT/"data")
    by_month={}
    all_rows=[]
    status_counts=Counter()
    source_counts=Counter()
    for idx,day in enumerate(days,1):
        month=(day.year,day.month)
        if month not in by_month:
            units=discover(layout,target_year=day.year,target_month=day.month,
                           progress=progress)
            candidates=[x for x in units if x.year==day.year
                        and x.month==day.month and "SPY" in x.symbols]
            if len(candidates)!=1:
                raise V65Error("V65_EXPECTED_ONE_VERIFIED_SPY_MONTH")
            unit=candidates[0]
            proof=integrity(unit,progress)
            if not proof["accepted"]:
                raise V65Error("V65_ORIGINAL_STOCK_FULL_SHA_UNQUALIFIED")
            by_month[month]=unit
        unit=by_month[month]
        market_rows=[]
        warnings=[]
        if day.weekday() in (0,2,4):
            market_rows=sample(unit.canonical_path,symbol="SPY",session_date=day)
            if market_rows:
                valid=validate(market_rows,
                               sample_class="SPY_0DTE_ORB_SOURCE_PREVIEW",
                               symbol="SPY",session_date=day)
                if not valid["accepted"]:
                    raise V65Error("V65_SPY_ORIGINAL_SESSION_INVALID")
                warnings=list(valid["warnings"])
            else:
                warnings=["NO_SOURCE_BARS_FOR_ELIGIBLE_DAY"]
        signal=signal_factory(market_rows,session=day,
                             source_sha256=unit.canonical_sha256,
                             source_unit_id=unit.unit_id)
        if signal.get("fingerprint")!=_fingerprint({
                k:v for k,v in signal.items() if k!="fingerprint"}):
            raise V65Error("V65_SIGNAL_FINGERPRINT_INVALID")
        requirement=_source_requirement(signal)
        receipt=None
        original=None
        if requirement is not None:
            receipt=_lookup_source_receipt(settings,requirement,
                                          reader=receipt_reader)
            source_counts[receipt["state"]]+=1
            if receipt["state"]=="ARCHIVED":
                acquired=cache_read(settings,receipt["query_id"])
                original=acquired.get("source")
                if (acquired.get("cache_evidence")!="CACHE_HIT"
                        or not isinstance(original,dict)
                        or original.get("source_sha256")!=receipt["archive_sha256"]
                        or original.get("query_id")!=receipt["query_id"]
                        or original.get("exact_requirement")!=requirement):
                    raise V65Error("V65_ORIGINAL_OPTION_ARCHIVE_IDENTITY_CHANGED")
        replay=_replay(signal,original,replay_fn=replay_fn)
        status_counts[replay["status"]]+=1
        row=_signed({
            "session":day.isoformat(),"day_index":idx,
            "weekday":day.strftime("%A"),
            "source_unit_id":unit.unit_id,
            "native_minute_source_sha256":unit.canonical_sha256,
            "original_minute_rows":len(market_rows),
            "native_source_warnings":warnings,
            "signal_status":signal["signal_status"],
            "signal_reason_codes":signal["reason_codes"],
            "signal_decision_at_et":signal["decision_at_et"],
            "selected_contract":signal["selected_contract"],
            "signal_fingerprint":signal["fingerprint"],
            "exact_option_requirement":requirement,
            "exact_option_receipt":receipt,
            "standalone_replay_report":replay,
            "standalone_replay_disposition":replay["status"],
            "standalone_replay_censor_reason":replay["censor_reason"],
            "standalone_replay_events":len(replay["events"]),
            "standalone_replay_is_not_cumulative_or_broker_fill":True,
            "same_query_provider_retry_permitted":False,
        })
        all_rows.append(row)
        progress(f"PROGRESS V65 complete={idx}/{len(days)}"
                 f" session={day} signal={signal['signal_status']}"
                 f" source={receipt['state'] if receipt else 'NOT_REQUIRED'}"
                 f" replay={replay['status']}"
                 " new_provider_requests=0")
    report=_signed({
        "contract":CONTRACT,
        "start":start.isoformat(),"end":end.isoformat(),
        "weekdays_in_calendar_scope":len(days),
        "verified_native_months":[
            {"year":ym[0],"month":ym[1],
             "unit_id":unit.unit_id,
             "canonical_sha256":unit.canonical_sha256,
             "monthly_original_sha_verified":True}
            for ym,unit in sorted(by_month.items())
        ],
        "status_counts":dict(sorted(status_counts.items())),
        "option_source_state_counts":dict(sorted(source_counts.items())),
        "session_reports":all_rows,
        "standalone_cash_not_chained_between_dates":True,
        "missing_source_not_a_zero_return":True,
        "do_not_sum_standalone_pnl_as_account_profits":True,
        "unresolved_position_not_auto_closed":True,
        "no_provider_calls_or_new_provider_clients":True,
        "no_duplicate_exact_historical_query":True,
        "provider_requests":0,"broker_orders":0,
        "historical_profitability_validated":False,
        "single_strategy_completed_bar_not_first_tick":True,
    })
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x",encoding="utf-8") as stream:
        json.dump(report,stream,indent=2,sort_keys=True,allow_nan=False)
        stream.write("\n")
    progress("COMPLETE V65"
             f" calendar_weekdays={len(days)}"
             f" replay_status_counts={dict(status_counts)}"
             f" option_source_status_counts={dict(source_counts)}"
             f" output={output} provider_requests=0")
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start",type=date.fromisoformat,default=date(2025,6,9))
    p.add_argument("--end",type=date.fromisoformat,default=date(2025,6,20))
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        inspect(args.start,args.end,args.output)
        return 0
    except Exception as exc:
        announce(f"STOPPED V65 error={type(exc).__name__}"
                 " source_mutated=False paid_requests=0 brokers=0")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
