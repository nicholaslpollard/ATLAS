from __future__ import annotations

"""V63 exact at-time 0DTE option surface for *independent* prior-IV candidates.

V62 proves a separate underlying stock quote source. This acquires one
read-only ThetaData historical option surface from V38 cache with timestamp
09:59:59 ET, TWO SECONDS before the 10:00:01 suspect PUT 598 sell quote.
Never uses the suspect put 598 as a calibration input, never estimates IV
without verified PIT rate/dividend and prior option quotes, no broker orders.
"""

import argparse
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_on_demand_source_cache_v38 import (
    read_through_historical_options,
)
from packages.simulation.spy_v55_closed_bar_option_replay import _read_timestamp
from scripts.run_spy_v59_offline_quote_forensics import _report
from scripts.run_spy_v62_historical_spot_capture import (
    _quote_candidate, _target_clock, _clock_parts,
)

ROOT=Path(__file__).resolve().parents[1]
ET=ZoneInfo("America/New_York")
CONTRACT="atlas-v63-independent-prior-spy-option-surface-input-v1"
V62="atlas-v62-bounded-alpaca-spy-historical-nbbo-source-v1"
QUOTE_METHOD="option_at_time_quote_surface"
REQUEST={"symbol":"SPY","date_et":"2025-06-13",
         "time_of_day_et":"09:59:59.000","right":"put",
         "max_dte":1,"strike_range":3}
TARGET=datetime(2025,6,13,10,0,1,tzinfo=ET)
CALIBRATE=datetime(2025,6,13,9,59,59,tzinfo=ET)


class PriorOptionSourceError(ValueError):
    pass


def progress(msg):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {msg}",flush=True)


def signed(doc):
    return {**doc,"fingerprint":_fingerprint(doc)}


def verify_stock_page_evidence(summary_path):
    """Reverify exact V62 raw stock source and derive only PRIOR spot reference."""
    doc=_report(summary_path)
    if (doc.get("contract")!=V62
            or doc.get("session")!="2025-06-13"
            or doc.get("status")!="COMPLETE_SOURCE_WINDOW"
            or doc.get("stock_feed")!="sip"
            or doc.get("parent_v61_report_fingerprint") is None
            or doc.get("source_page_count")!=len(doc.get("original_pages",[]))
            or doc.get("target_decision_at_et")!=TARGET.isoformat()):
        raise PriorOptionSourceError("V63_V62_ORIGINAL_STOCK_RECEIPT_NOT_QUALIFIED")
    if not doc["original_pages"]:
        raise PriorOptionSourceError("V63_NO_IMMUTABLE_STOCK_QUOTE_PAGES")
    cutoff=_target_clock(CALIBRATE)
    low=_target_clock(CALIBRATE-timedelta(seconds=2))
    request_start=_target_clock(datetime.fromisoformat(doc["source_window_start"]))
    request_end=_target_clock(datetime.fromisoformat(doc["source_window_end"]))
    accepted=[]
    original_rows=0
    for ordinal,page in enumerate(doc["original_pages"],1):
        if page["page_ordinal"]!=ordinal:
            raise PriorOptionSourceError("V63_STOCK_PAGE_ORDINAL_DRIFT")
        raw_path=Path(page["raw_file"])
        if raw_path.is_symlink() or not raw_path.is_file():
            raise PriorOptionSourceError("V63_STOCK_ORIGINAL_PAGE_MISSING")
        original=raw_path.read_bytes()
        if (sha256(original).hexdigest()!=page["raw_sha256"]
                or len(original)!=page["original_raw_bytes"]):
            raise PriorOptionSourceError("V63_STOCK_ORIGINAL_SHA_CHANGED")
        data=json.loads(original)
        if data.get("symbol")!="SPY" or not isinstance(data.get("quotes"),list):
            raise PriorOptionSourceError("V63_STOCK_PAGE_SYMBOL_OR_SCHEMA_CHANGED")
        if len(data["quotes"])!=page["row_count"]:
            raise PriorOptionSourceError("V63_STOCK_ORIGINAL_PAGE_ROW_COUNT_CHANGED")
        original_rows+=len(data["quotes"])
        for row in data["quotes"]:
            candidate,why=_quote_candidate(
                row,cutoff=cutoff,first=request_start,last=request_end)
            if candidate is not None and _clock_parts(candidate["original_quote_clock"])>=low:
                accepted.append(candidate)
    if original_rows!=doc["original_quote_rows"]:
        raise PriorOptionSourceError("V63_STOCK_ORIGINAL_ROW_TOTAL_CHANGED")
    if not accepted:
        return doc,None
    ref=max(accepted,key=lambda c:_clock_parts(c["original_quote_clock"]))
    return doc,ref


def classify_option_source_rows(rows):
    """Outcome-blind shape checks; never equate option surface to known IV."""
    categories=Counter()
    examples=[]
    seen_exp=set()
    seen_strikes=set()
    day=CALIBRATE.date()
    for row in rows:
        if not isinstance(row,dict):
            categories["NON_OBJECT_ROW"]+=1
            continue
        if len(examples)<4:
            examples.append(sorted(row))
        try:
            expiration=str(row.get("expiration",""))
            strike=Decimal(str(row["strike"]))
            right=str(row.get("right","")).lower()
            bid=Decimal(str(row["bid"]))
            ask=Decimal(str(row["ask"]))
            sz_b=int(row["bid_size"])
            sz_a=int(row["ask_size"])
        except (KeyError,TypeError,ValueError,ArithmeticError):
            categories["SOURCE_FIELDS_UNQUALIFIED"]+=1
            continue
        if (not strike.is_finite() or not bid.is_finite() or not ask.is_finite()
                or strike<=0 or bid<=0 or ask<bid or sz_b<=0 or sz_a<=0):
            categories["SOURCE_BID_ASK_UNQUALIFIED"]+=1
            continue
        seen_exp.add(expiration)
        seen_strikes.add(str(strike))
        if expiration !=day.isoformat():
            categories["OTHER_EXPIRY_NOT_0DTE"]+=1
            continue
        if right!="put":
            categories["UNEXPECTED_RIGHT"]+=1
            continue
        if strike==Decimal("598"):
            categories["TARGET_PUT_EXCLUDED_FROM_INDEPENDENT_IV"]+=1
            continue
        try:
            stamp=_read_timestamp(row,day)
        except Exception:
            categories["OBSERVATION_CLOCK_UNVERIFIED"]+=1
            continue
        if stamp>CALIBRATE:
            categories["AFTER_PRECALIBRATION_TIMESTAMP"]+=1
            continue
        age=(CALIBRATE-stamp).total_seconds()
        if age>2:
            categories["STALE_PRIOR_QUOTE_OVER_2S"]+=1
            continue
        ratio=(ask-bid)/((ask+bid)/2)
        if ratio>Decimal(".15"):
            categories["WIDE_PRIOR_OPTION_SPREAD"]+=1
            continue
        categories["CANDIDATE_ALTERNATE_PUT_AT_PRIOR_CLOCK"]+=1
    return {
        "row_count":len(rows),"categorization":dict(sorted(categories.items())),
        "observed_expirations":sorted(seen_exp),
        "distinct_strike_count":len(seen_strikes),
        "sample_source_field_names":examples,
        "candidate_rows_do_not_equal_verified_independent_iv":True,
        "provider_option_quote_first_publication_unverified":True,
    }


def acquire(stock_summary,output,*,get=read_through_historical_options,
            settings_factory=load_settings,emit=progress):
    if output.exists() or output.is_symlink():
        raise PriorOptionSourceError("V63_IMMUTABLE_OUTPUT_ALREADY_EXISTS")
    emit("START V63 independently calibrated prior quote source"
         " stock_page_verify=True historical_provider_get_only=True"
         " broker_orders=0")
    parent,spot=verify_stock_page_evidence(stock_summary)
    emit("STAGE_PASS V62 immutable stock raw page SHA verification"
         f" pages={parent['source_page_count']}"
         f" spot_at_precalibration={spot['original_quote_clock'] if spot else None}")
    if spot is None:
        status="ABSTAIN_NO_PRIOR_SPY_SPOT_AT_PRECALIBRATION"
        source=None
        categorized=None
    else:
        emit(f"STAGE_START V63 v38 REUSE_OR_FETCH_ARCHIVE theta_method={QUOTE_METHOD}"
             f" time={REQUEST['time_of_day_et']}"
             " max_dte=1 strike_range=3 right=put")
        settings=settings_factory(ROOT,"development")
        source=get(settings,QUOTE_METHOD,dict(REQUEST))
        if not isinstance(source,dict) or source.get("exact_requirement",{}).get("method")!=QUOTE_METHOD:
            raise PriorOptionSourceError("V63_V38_SOURCE_REQUEST_IDENTITY_INVALID")
        kw=source["exact_requirement"].get("kwargs",{})
        if any(kw.get(k)!=v for k,v in REQUEST.items()):
            raise PriorOptionSourceError("V63_V38_SOURCE_PARAMETERS_CHANGED")
        categorized=classify_option_source_rows(source["source_rows"])
        status=("SOURCE_RECORDED_PRIOR_IV_NOT_YET_ESTIMATED" if
                source["status"] in ("CACHE_HIT","FETCHED_AND_ARCHIVED")
                else "ABSTAIN_PRIOR_SURFACE_NO_CERTIFIED_DATA")
        emit("STAGE_PASS V63 option source archived"
             f" source={source['status']} original_rows={categorized['row_count']}"
             f" possible_alternate_puts={categorized['categorization'].get('CANDIDATE_ALTERNATE_PUT_AT_PRIOR_CLOCK',0)}"
             f" query={source['query_id']}")
    doc=signed({
        "contract":CONTRACT,"status":status,
        "target_decision_at_et":TARGET.isoformat(),
        "source_option_asof_et":CALIBRATE.isoformat(),
        "source_option_scope":dict(REQUEST),
        "v62_parent_report_fingerprint":parent["fingerprint"],
        "v62_spy_raw_bid_ask_for_prior_iv":spot,
        "v62_spy_spot_reference_available":spot is not None,
        "v38_query_id":source["query_id"] if source else None,
        "v38_source_sha256":source["source_sha256"] if source else None,
        "v38_source_status":source["status"] if source else None,
        "v38_source_row_classification":categorized,
        "target_put_598_calibration_excluded":True,
        "volatility_calibration_status":"NOT_YET_CALIBRATED",
        "historical_rate_and_dividend_provenance":"NOT_YET_QUALIFIED",
        "option_0dte_expiry_clock":"NOT_YET_QUALIFIED",
        "black_scholes_value_from_this_request":None,
        "acted_side_bid_fairness_proven":False,
        "original_option_trade_status_unchanged":True,
        "source_bytes_in_original_v38_archive_not_copied":True,
        "alpaca_provider_requests":0,
        "theta_option_requests":"CACHE_HIT_OR_ONE_READ_ONLY_HISTORICAL_SOURCE_GET",
        "broker_orders":0,"real_fills":0,
        "historical_alpha_validated":False,
    })
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x",encoding="utf-8") as stream:
        json.dump(doc,stream,indent=2,sort_keys=True,allow_nan=False)
        stream.write("\n")
    emit(f"COMPLETE V63 status={status} output={output}"
         " original_sources_untouched=True broker_orders=0")
    return doc


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v62-summary",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args(argv)
    try:
        acquire(a.v62_summary,a.output)
        return 0
    except Exception as exc:
        progress(f"STOPPED V63 exception={type(exc).__name__}"
                 " no_replay_or_price_substitution=True broker_orders=0")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
