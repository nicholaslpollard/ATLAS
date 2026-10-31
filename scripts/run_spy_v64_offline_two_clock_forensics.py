from __future__ import annotations

"""V64 offline two-clock option/underlying quote forensics and V63 receipt census.

Original option and stock source SHA receipts are reverified. The V63 query
is inspected by exact V38 query fingerprint in SQLite URI mode=ro; its
FAILED_RETRYABLE state is NOT permission to resend a potentially timed-out
historical provider request. Nothing invokes ThetaData or Alpaca and there
are no broker calls or inferred fills.
"""

import argparse
from contextlib import closing
from datetime import date, datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_on_demand_source_cache_v38 import (
    DB_REL, _unpack, normalize_source_requirement,
    OnDemandSourceError,
)
from packages.simulation.spy_v55_closed_bar_option_replay import (
    _quote,_read_timestamp,V55Error,
)
from scripts.run_spy_v59_offline_quote_forensics import (
    _report,_local_cache_only,
)
from scripts.run_spy_v62_historical_spot_capture import (
    _quote_candidate,_target_clock,_clock_parts,
)
from scripts.run_spy_v62_historical_spot_capture import (
    _original_v61,
)

QUOTE_METHOD="option_at_time_quote_surface"
REQUEST={"symbol":"SPY","date_et":"2025-06-13",
         "time_of_day_et":"09:59:59.000","right":"put",
         "max_dte":1,"strike_range":3}


def verify_stock_page_evidence(path):
    """Return V62 receipt and historical SPY stock quote by 09:59:59.

    Read only exact original raw pages; V62 SHA IDs and rows must match.
    No reliance on the V63 attempted historical provider request.
    """
    import hashlib
    doc=_report(path)
    if (doc.get("contract")!="atlas-v62-bounded-alpaca-spy-historical-nbbo-source-v1"
            or doc.get("session")!="2025-06-13"
            or doc.get("status")!="COMPLETE_SOURCE_WINDOW"
            or doc.get("stock_feed")!="sip"
            or doc.get("source_page_count")!=len(doc.get("original_pages",[]))
            or not doc.get("original_pages")):
        raise V64Error("V64_V62_REPORT_IDENTITY_INVALID")
    cutoff=_target_clock(datetime(2025,6,13,9,59,59,tzinfo=ET))
    low=cutoff-Decimal(2)
    start=_target_clock(datetime.fromisoformat(doc["source_window_start"]))
    end=_target_clock(datetime.fromisoformat(doc["source_window_end"]))
    accepted=[]
    observed=0
    for p in doc["original_pages"]:
        original=Path(p["raw_file"])
        if original.is_symlink() or not original.is_file():
            raise V64Error("V64_ORIGINAL_STOCK_PAGE_NOT_REGULAR")
        blob=original.read_bytes()
        if hashlib.sha256(blob).hexdigest()!=p["raw_sha256"]:
            raise V64Error("V64_STOCK_ORIGINAL_PAGE_SHA_CHANGED")
        raw=json.loads(blob)
        if raw.get("symbol")!="SPY" or len(raw.get("quotes",[]))!=p["row_count"]:
            raise V64Error("V64_STOCK_PAGE_ROW_OR_SYMBOL_DRIFT")
        observed+=len(raw["quotes"])
        for row in raw["quotes"]:
            c,why=_quote_candidate(row,cutoff=cutoff,first=start,last=end)
            if c is not None and _clock_parts(c["original_quote_clock"])>=low:
                accepted.append(c)
    if observed!=doc["original_quote_rows"]:
        raise V64Error("V64_STOCK_ORIGINAL_TOTAL_COUNT_DRIFT")
    return doc,max(accepted,key=lambda q:_clock_parts(q["original_quote_clock"])) if accepted else None

ROOT=Path(__file__).resolve().parents[1]
ET=ZoneInfo("America/New_York")
DAY=date(2025,6,13)
CONTRACT="atlas-v64-v63-timeout-legacy-options-and-spy-two-clock-offline-audit-v1"
CLOCKS=("09:59:59","10:00:00","10:00:01","10:00:02")


class V64Error(ValueError):
    pass


def emit(message):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {message}",flush=True)


def _stamp(clock):
    return datetime.fromisoformat(f"{DAY.isoformat()}T{clock}-04:00")


def _signed(data):
    return {**data,"fingerprint":_fingerprint(data)}


def _receipt_row(settings, *, reader=None):
    """Only readonly SQLite. No V38 cache read-through or request dispatch."""
    requirement=normalize_source_requirement(QUOTE_METHOD,dict(REQUEST))
    qid=_fingerprint(requirement)
    if reader is not None:
        row=reader(qid)
    else:
        db=settings.resolved_path(DB_REL)
        if db.is_symlink() or not db.is_file():
            row=None
        else:
            with closing(sqlite3.connect(db.resolve().as_uri()+"?mode=ro",
                                         uri=True,timeout=15)) as con:
                row=con.execute(
                    "SELECT query_id,request_json,state,touched,source_sha,"
                    "gzip_sha,stored_path,source_rows FROM sources WHERE query_id=?",
                    (qid,)).fetchone()
    if row is None:
        return {
            "exact_query_id":qid,"state":"NO_V38_RECORD",
            "query_is_not_proven_never_dispatched":True,
            "provider_dispatch_outcome":"UNOBSERVED",
            "safe_to_retry_same_exact_query":False,
            "source_sha256":None,"observed_row_count":None,
            "last_touched_utc":None,"original_archive_integrity":"NOT_AVAILABLE",
        }
    if len(row)!=8 or row[0]!=qid:
        raise V64Error("V64_READ_ONLY_RECEIPT_ROW_IDENTITY_INVALID")
    parsed=json.loads(row[1])
    if parsed!=requirement or _fingerprint(parsed)!=qid:
        raise V64Error("V64_V63_RECEIPT_QUERY_IDENTITY_DRIFT")
    state=row[2]
    if state not in {
        "ARCHIVED","NO_DATA_EXPLICIT","IN_FLIGHT","FAILED_RETRYABLE"
    }:
        raise V64Error("V64_UNRECOGNIZED_V38_STATE")
    audit="NOT_ARCHIVED"
    if state=="ARCHIVED" and reader is None:
        # _unpack checks both canonical raw SHA and gz SHA, no provider calls.
        archived=_unpack(settings,row,requirement)
        if archived["status"]!="CACHE_HIT":
            raise V64Error("V64_V63_CACHED_ARCHIVE_NOT_VERIFIED")
        audit="VERIFIED_BY_V38_ORIGINAL_ARCHIVE_READER"
    elif state=="ARCHIVED":
        audit="ARCHIVED_METADATA_ONLY_INJECTED_TEST"
    touched=datetime.fromtimestamp(float(row[3]),tz=timezone.utc).isoformat()
    return {
        "exact_query_id":qid,"state":state,
        "query_is_not_proven_never_dispatched":True,
        "provider_dispatch_outcome":"UNKNOWN_AFTER_EXCEPTION" if
        state in ("IN_FLIGHT","FAILED_RETRYABLE") else
        "ORIGINAL_ARCHIVE_PRESENT" if state=="ARCHIVED" else
        "EXPLICIT_NO_DATA_RECEIPT",
        "safe_to_retry_same_exact_query":False,
        "v38_automatic_retry_risk":state=="FAILED_RETRYABLE",
        "source_sha256":row[4],
        "observed_row_count":row[7],
        "last_touched_utc":touched,
        "original_archive_integrity":audit,
    }


def _stock_by_clock(stock_summary_path, *,verify_stock=verify_stock_page_evidence):
    """Stock source SHA-verified by V63 original-page audit, then reread pages.

    Inputs at 10:00:02 are diagnostic-only, NEVER usable for 10:00:01.
    """
    doc,prior=verify_stock(stock_summary_path)
    if doc["source_page_count"]!=1 and not doc["original_pages"]:
        raise V64Error("V64_STOCK_SOURCE_NO_PAGES")
    rows=[]
    for p in doc["original_pages"]:
        original=Path(p["raw_file"]).read_bytes()
        import hashlib
        if hashlib.sha256(original).hexdigest()!=p["raw_sha256"]:
            raise V64Error("V64_STOCK_ORIGINAL_SHA_MISMATCH")
        body=json.loads(original)
        if len(body.get("quotes",[]))!=p["row_count"]:
            raise V64Error("V64_STOCK_ORIGINAL_COUNT_DRIFT")
        rows.extend(body["quotes"])
    if len(rows)!=doc["original_quote_rows"]:
        raise V64Error("V64_STOCK_TOTAL_COUNT_DRIFT")
    start=_target_clock(datetime.fromisoformat(doc["source_window_start"]))
    end=_target_clock(datetime.fromisoformat(doc["source_window_end"]))
    series={}
    for clock in CLOCKS:
        asof=_stamp(clock)
        cutoff=_target_clock(asof)
        good=[]
        for i,row in enumerate(rows):
            c,why=_quote_candidate(row,cutoff=cutoff,first=start,last=end)
            if c is not None:
                good.append((c,i))
        if good:
            c,i=max(good,key=lambda z:_clock_parts(z[0]["original_quote_clock"]))
            series[clock]={
                **c,"source_index":i,
                "timestamp_not_after_evaluation":True,
                "usable_at_june_13_10_00_01":clock<="10:00:01",
                "source_quote_condition_and_publication_not_independently_certified":True,
            }
        else:
            series[clock]=None
    return doc,series,prior


def _options_by_clock(source,contract):
    if (source["status"]!="CACHE_HIT" or
            source["source_sha256"] is None):
        raise V64Error("V64_ORIGINAL_OPTIONS_SOURCE_NOT_VERIFIED")
    rows=source["source_rows"]
    output={}
    for clock in CLOCKS:
        at=_stamp(clock)
        matched=[(i,r) for i,r in enumerate(rows)
                 if _read_timestamp(r,DAY)==at]
        if len(matched)!=1:
            output[clock]={"status":"MISSING_OR_DUPLICATE_EXACT_SECOND",
                           "raw_row_count":len(matched)}
            continue
        i,r=matched[0]
        try:
            quoted=_quote(r,day=DAY,contract=contract)
            status="QUALIFIED_UNDER_ORIGINAL_V55_15PCT_SPREAD_RULE"
            reason=None
        except (V55Error,KeyError,ValueError,TypeError) as exc:
            quoted=None
            status="ORIGINAL_V55_QUOTE_REJECTED"
            reason=type(exc).__name__+":"+str(exc)
        bid=Decimal(str(r["bid"]))
        ask=Decimal(str(r["ask"]))
        output[clock]={
            "status":status,"original_rejection_reason":reason,
            "raw_source_row_index":i,
            "timestamp_et":at.isoformat(),
            "bid":str(bid),"ask":str(ask),
            "bid_size":r.get("bid_size"),"ask_size":r.get("ask_size"),
            "spread_pct_mid":str((ask-bid)*200/(ask+bid)),
            "original_quote_not_executable_fill":True,
        }
    return output


def _delta_option(options,clock_before,clock_at):
    a=options.get(clock_before) or {}
    b=options.get(clock_at) or {}
    if "bid" not in a or "bid" not in b:
        return None
    before_bid=Decimal(a["bid"])
    after_bid=Decimal(b["bid"])
    before_ask=Decimal(a["ask"])
    after_ask=Decimal(b["ask"])
    return {
        "from":clock_before,"to":clock_at,
        "bid_change_dollars":str(after_bid-before_bid),
        "ask_change_dollars":str(after_ask-before_ask),
        "bid_change_percent":str((after_bid/before_bid-1)*100),
        "ask_change_percent":str((after_ask/before_ask-1)*100),
        "bid_more_negative_than_ask":(after_bid-before_bid)<(after_ask-before_ask),
    }


def _delta_stock(stocks,a,b):
    before=stocks.get(a)
    after=stocks.get(b)
    if not before or not after:
        return None
    m1=Decimal(before["indicative_mid_not_executable"])
    m2=Decimal(after["indicative_mid_not_executable"])
    return {
        "from":a,"to":b,
        "mid_change_dollars":str(m2-m1),
        "mid_change_pct":str(100*(m2/m1-1)),
        "stock_quote_not_option_valuation_or_fill":True,
    }


def audit(stock_summary,v61_report,output,*,settings_factory=load_settings,
          cache_read=_local_cache_only,receipt_read=None,stock_read=_stock_by_clock,
          log=emit):
    if output.exists() or output.is_symlink():
        raise V64Error("V64_IMMUTABLE_OUTPUT_ALREADY_EXISTS")
    original=_report(v61_report)
    if original.get("contract")!="atlas-v61-independent-action-side-source-readiness-v1":
        raise V64Error("V64_ORIGINAL_V61_CONTRACT_MISMATCH")
    settings=settings_factory(ROOT,"development")
    log("STAGE_START V64 exact V63 query registry lookup SQLite mode=ro no_provider")
    receipt=_receipt_row(settings,reader=receipt_read)
    log(f"STAGE_PASS V64 V63_query={receipt['exact_query_id'][:12]}"
        f" state={receipt['state']}"
        f" retry_prohibited={not receipt['safe_to_retry_same_exact_query']}")
    stock_doc,stocks,prior=stock_read(stock_summary)
    if stock_doc["parent_v61_report_fingerprint"]!=original["fingerprint"]:
        raise V64Error("V64_V61_V62_PARENT_DISAGREEMENT")
    log("STAGE_PASS V64 original Alpaca full raw-page SHA"
        f" original_rows={stock_doc['original_quote_rows']}")
    cache=cache_read(settings,original["original_report"]["source_query_id"])
    source=cache.get("source")
    if source is None:
        raise V64Error("V64_ORIGINAL_V56_OPTIONS_ARCHIVE_ABSENT")
    if source["source_sha256"]!=original["original_report"]["source_sha256"]:
        raise V64Error("V64_ORIGINAL_OPTION_SOURCE_SHA_MISMATCH")
    options=_options_by_clock(source,original["original_report"]["selected_contract"])
    log("STAGE_PASS V64 immutable option exact tape SHA"
        f" options_source_rows={len(source['source_rows'])}")
    early="10:00:00"
    suspect="10:00:01"
    result=_signed({
        "contract":CONTRACT,
        "session":DAY.isoformat(),
        "target_option":"SPY 598 PUT 2025-06-13 0DTE",
        "target_action":"SELL_BID_TO_CLOSE_EXISTING_PUT",
        "target_cutoff_et":_stamp(suspect).isoformat(),
        "v61_fingerprint":original["fingerprint"],
        "v62_fingerprint":stock_doc["fingerprint"],
        "original_option_query_id":source["query_id"],
        "original_option_source_sha256":source["source_sha256"],
        "v63_exact_request":dict(REQUEST),
        "v63_exact_cache_receipt":receipt,
        "v63_original_error_message_logged":"ThetaDataError_ONLY",
        "theta_worker_default_response_timeout_seconds":180,
        "v63_provider_reached_or_request_processed":"UNDETERMINED",
        "stock_nbbo_asof_clock":stocks,
        "option_quote_asof_clock":options,
        "option_price_change_1000_1001":_delta_option(options,early,suspect),
        "stock_mid_change_1000_1001":_delta_stock(stocks,early,suspect),
        "first_past_only_stock_for_precalibration":prior,
        "suspect_quote_price_replaced":False,
        "future_100002_used_to_authorize_100001":False,
        "fair_value_derived_from_suspect_quote":False,
        "independent_iv_estimated":False,
        "black_scholes_bid_ask_side_certification":"NOT_AVAILABLE",
        "action_side_rescued":False,
        "historical_fills":0,
        "cash_equity_modified":False,
        "source_files_changed":False,
        "provider_requests":0,"broker_orders":0,
        "historical_alpha_validated":False,
    })
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x",encoding="utf-8") as stream:
        json.dump(result,stream,indent=2,sort_keys=True,allow_nan=False)
        stream.write("\n")
    log("COMPLETE V64 independent two-clock source forensics"
        f" v63_state={receipt['state']}"
        f" option_bid_change={(result['option_price_change_1000_1001'] or {}).get('bid_change_dollars')}"
        f" stock_mid_change={(result['stock_mid_change_1000_1001'] or {}).get('mid_change_dollars')}"
        f" output={output} new_requests=0")
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v62-summary",type=Path,required=True)
    p.add_argument("--v61-report",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args(argv)
    try:
        audit(a.v62_summary,a.v61_report,a.output)
        return 0
    except Exception as exc:
        emit(f"STOPPED V64 error_type={type(exc).__name__} source_mutated=False"
             " provider_calls=0")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
