from __future__ import annotations

"""V62 narrowly scoped SPY historical stock NBBO archive for V60 validation.

The original Alpaca response bytes are saved unchanged and SHA-256 linked.
Every page is fetched at most once per run; a missing page censors the source.
The selected underlying NBBO is strictly at or BEFORE the option decision.
No options source GET, no synthetic IV, no trading orders, no broker fills.
"""

import argparse
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.providers.alpaca.client import AlpacaMarketDataClient, AlpacaApiPage
from scripts.run_spy_v59_offline_quote_forensics import _report

ROOT=Path(__file__).resolve().parents[1]
ET=ZoneInfo("America/New_York")
CONTRACT="atlas-v62-bounded-alpaca-spy-historical-nbbo-source-v1"
V61="atlas-v61-independent-action-side-source-readiness-v1"
MAX_PAGES=12
PAGE_LIMIT=10000
MAX_BODY_BYTES=12*1024*1024
MAX_SPOT_AGE_SECONDS=Decimal("2")
STAMP_PATTERN=re.compile(
    r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d{1,9}))?(Z|[+-]\d\d:\d\d)$"
)


class StockQuoteSourceError(ValueError):
    pass


def info(message):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {message}",
          flush=True)


def _signed(x):
    return {**x,"fingerprint":_fingerprint(x)}


def _clock_parts(value):
    """Nanosecond-aware UTC source order; no truncation at decision boundary."""
    if not isinstance(value,str):
        raise StockQuoteSourceError("QUOTE_TIMESTAMP_NOT_STRING")
    m=STAMP_PATTERN.fullmatch(value)
    if m is None:
        raise StockQuoteSourceError("QUOTE_TIMESTAMP_NOT_RFC3339")
    whole,fract,offset=m.groups()
    try:
        base=datetime.fromisoformat(whole+("+00:00" if offset=="Z" else offset))
    except ValueError as exc:
        raise StockQuoteSourceError("QUOTE_TIMESTAMP_CALENDAR_INVALID") from exc
    unix_sec=int(base.astimezone(timezone.utc).timestamp())
    frac=Decimal("0."+fract) if fract else Decimal(0)
    return Decimal(unix_sec)+frac


def _target_clock(x):
    if not isinstance(x,datetime) or x.tzinfo is None or x.utcoffset() is None:
        raise StockQuoteSourceError("ACTION_TIME_NOT_AWARE")
    epoch=x.astimezone(timezone.utc)
    return Decimal(int(epoch.timestamp()))+Decimal(epoch.microsecond)/Decimal(10**6)


def _quote_candidate(row, *, cutoff, first, last):
    if not isinstance(row,dict):
        raise StockQuoteSourceError("PROVIDER_STOCK_QUOTE_NOT_OBJECT")
    stamp=_clock_parts(row.get("t"))
    if not first<=stamp<=last:
        raise StockQuoteSourceError("HISTORICAL_QUOTE_OUTSIDE_EXACT_REQUEST_WINDOW")
    age=cutoff-stamp
    if age<0 or age>MAX_SPOT_AGE_SECONDS:
        return None, "FUTURE_OR_STALE_QUOTE"
    try:
        bp=Decimal(str(row["bp"]))
        ap=Decimal(str(row["ap"]))
        bs=int(row["bs"])
        az=int(row["as"])
        flags=row["c"]
        bid_exchange=row["bx"]
        ask_exchange=row["ax"]
    except (KeyError,TypeError,ValueError) as exc:
        return None, "MISSING_QUOTE_PRICE_SIZE_OR_CONDITION" 
    if (not bp.is_finite() or not ap.is_finite() or not 0<bp<=ap
            or type(row["bs"]) is not int or type(row["as"]) is not int
            or bs<=0 or az<=0
            or not isinstance(flags,list)
            or not isinstance(bid_exchange,str)
            or not isinstance(ask_exchange,str)):
        return None, "INVALID_PRICE_OR_SIDE_SIZE"
    return {
        "original_quote_clock":row["t"],
        "age_seconds_at_decision":str(age),
        "bid":str(bp),"ask":str(ap),
        "bid_size_native":bs,"ask_size_native":az,
        "quote_conditions":flags,"bid_exchange":bid_exchange,
        "ask_exchange":ask_exchange,
        "indicative_mid_not_executable":str((bp+ap)/2),
        "same_source_bid_ask_spread_pct":str((ap-bp)*200/(ap+bp)),
        "quote_age_test_only_not_actual_publication_lag":True,
    }, None


def _original_v61(path):
    doc=_report(path)
    if doc.get("contract")!=V61 or doc.get("session")!="2025-06-13":
        raise StockQuoteSourceError("V61_SOURCE_READINESS_IDENTITY_INVALID")
    if doc.get("independent_current_spot_tick_verified") is not False:
        raise StockQuoteSourceError("V61_ALREADY_HAS_DIFFERENT_SPOT_SOURCE")
    if doc.get("side_aware_bsm_reference_status")!="ABSTAIN_MISSING_INDEPENDENT_MODEL_INPUTS":
        raise StockQuoteSourceError("V61_NO_LONGER_ABSTAINS")
    target=datetime.fromisoformat(doc["target_decision_at_et"])
    if target.tzinfo is None or target.utcoffset() is None:
        raise StockQuoteSourceError("V61_TARGET_CLOCK_INVALID")
    if target.astimezone(ET)!=datetime(2025,6,13,10,0,1,tzinfo=ET):
        raise StockQuoteSourceError("V61_TARGET_NOT_JUNE_13_10_00_01")
    return doc,target


def collect(v61_report,outdir,*,feed="sip",client_factory=AlpacaMarketDataClient,
            settings_factory=load_settings,progress=info):
    original,target=_original_v61(v61_report)
    if feed not in ("sip","iex"):
        raise StockQuoteSourceError("V62_UNSUPPORTED_STOCK_FEED")
    if outdir.exists() or outdir.is_symlink():
        raise StockQuoteSourceError("V62_IMMUTABLE_OUTPUT_DIRECTORY_EXISTS")
    start=target-timedelta(seconds=3)
    end=target+timedelta(seconds=1)
    # This is a tiny targeted window rather than a full historical stock tape.
    start_arg=start.isoformat(timespec="seconds")
    end_arg=end.isoformat(timespec="seconds")
    settings=settings_factory(ROOT,"development")
    client=client_factory(settings)
    outdir.mkdir(parents=True,exist_ok=False)
    cutoff=_target_clock(target)
    low=_target_clock(start)
    high=_target_clock(end)
    progress("START V62 historical SPY stock quote narrow source"
             f" from={start_arg} through={end_arg} feed={feed}"
             " max_pages=12 read_only_provider_GET_only=True broker_orders=0")
    page_token=None
    page_tokens=set()
    pages=[]
    all_candidates=[]
    rejects={}
    status="PARTIAL_OR_UNKNOWN"
    max_observed=None
    for i in range(1,MAX_PAGES+1):
        if page_token in page_tokens:
            raise StockQuoteSourceError("V62_DUPLICATE_PAGE_TOKEN")
        if page_token is not None:
            page_tokens.add(page_token)
        page=client.historical_stock_quote_page(
            symbol="SPY",start=start_arg,end=end_arg,feed=feed,
            page_token=page_token,page_limit=PAGE_LIMIT)
        if not isinstance(page,AlpacaApiPage) or page.http_status!=200:
            raise StockQuoteSourceError("V62_ALPACA_STOCK_PAGE_NOT_HTTP_200")
        if (not isinstance(page.raw_body,bytes)
                or not 0<len(page.raw_body)<=MAX_BODY_BYTES):
            raise StockQuoteSourceError("V62_ALPACA_RAW_BODY_SIZE_INVALID")
        response=json.loads(page.raw_body.decode("utf-8"))
        if not isinstance(response,dict) or response!=page.payload:
            raise StockQuoteSourceError("V62_RAW_RESPONSE_DIFFERENT_FROM_DECODED_PAGE")
        if response.get("symbol")!="SPY" or not isinstance(response.get("quotes"),list):
            raise StockQuoteSourceError("V62_STOCK_QUOTE_RESPONSE_IDENTITY_INVALID")
        if len(response["quotes"])>PAGE_LIMIT:
            raise StockQuoteSourceError("V62_QUOTE_PAGE_EXCEEDS_ADVERTISED_LIMIT")
        if page.next_page_token!=response.get("next_page_token"):
            raise StockQuoteSourceError("V62_PAGE_TOKEN_DIFFERENCE")
        raw_path=outdir/f"page_{i:04d}.json"
        with raw_path.open("xb") as handle:
            handle.write(page.raw_body)
            handle.flush()
            os.fsync(handle.fileno())
        raw_sha=sha256(page.raw_body).hexdigest()
        page_record={
            "page_ordinal":i,"raw_file":str(raw_path),
            "raw_sha256":raw_sha,"original_raw_bytes":len(page.raw_body),
            "row_count":len(response["quotes"]),
            "requested_feed":feed,"next_page_token_exists":bool(page.next_page_token),
            "http_status":page.http_status,
        }
        pages.append(page_record)
        progress(f"STAGE_PASS V62 immutable_page index={i}"
                 f" rows={page_record['row_count']}"
                 f" raw_sha={raw_sha} more={bool(page.next_page_token)}")
        for idx,quote in enumerate(response["quotes"]):
            candidate,why=_quote_candidate(quote,cutoff=cutoff,first=low,last=high)
            if why is not None:
                rejects[why]=rejects.get(why,0)+1
            else:
                all_candidates.append({
                    **candidate,"page_ordinal":i,"original_row_index":idx,
                    "raw_page_sha256":raw_sha,
                })
        page_token=page.next_page_token
        if not page_token:
            status="COMPLETE_SOURCE_WINDOW"
            break
        if page_token in page_tokens:
            raise StockQuoteSourceError("V62_REPEATED_NEXT_PAGE_TOKEN")
    if page_token and status!="COMPLETE_SOURCE_WINDOW":
        status="CENSORED_TOO_MANY_HISTORICAL_PAGES"
    selected=None
    if status=="COMPLETE_SOURCE_WINDOW" and all_candidates:
        # Original response time precision retained in original_quote_clock.
        selected=max(all_candidates,key=lambda q:_clock_parts(q["original_quote_clock"]))
    report=_signed({
        "contract":CONTRACT,
        "parent_v61_report_fingerprint":original["fingerprint"],
        "parent_v56_account_fingerprint":original["original_account_report_fingerprint"],
        "session":"2025-06-13",
        "target_decision_at_et":target.isoformat(),
        "source":"alpaca_v2_historical_spy_stock_quotes",
        "stock_feed":feed,
        "source_window_start":start_arg,
        "source_window_end":end_arg,
        "status":status,"completeness_required_for_valuation":True,
        "original_pages":pages,"source_page_count":len(pages),
        "original_quote_rows":sum(x["row_count"] for x in pages),
        "quote_rejection_counts":dict(sorted(rejects.items())),
        "eligible_quote_candidates_in_full_archive":len(all_candidates),
        "latest_past_only_stock_nbbo":selected,
        "latest_stock_quote_is_prior_to_or_at_decision":bool(selected),
        "independent_spot_quote_archive_exists":bool(selected),
        "stock_source_is_distinct_from_option_target":True,
        "stock_exchange_condition_semantics_not_fully_validated":True,
        "first_publication_latency_not_verified":True,
        "independent_iv_from_prior_other_options_not_established":True,
        "historical_rate_dividend_input_not_established":True,
        "historical_bsm_fair_value":None,
        "side_aware_valuation_eligible":False,
        "price_drift_and_historical_fills_not_inferred":True,
        "actual_broker_orders":0,"option_provider_requests":0,
        "alpaca_stock_provider_pages":len(pages),
        "historical_alpha_validated":False,
    })
    with (outdir/"summary.json").open("x",encoding="utf-8") as f:
        json.dump(report,f,indent=2,sort_keys=True,allow_nan=False)
        f.write("\n")
    progress(f"COMPLETE V62 status={status} pages={len(pages)}"
             f" stock_reference={selected['indicative_mid_not_executable'] if selected else None}"
             f" age={selected['age_seconds_at_decision'] if selected else None}"
             f" summary={outdir/'summary.json'} broker_orders=0")
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v61-report",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    p.add_argument("--feed",choices=("sip","iex"),default="sip")
    args=p.parse_args(argv)
    try:
        report=collect(args.v61_report,args.output_dir,feed=args.feed)
        return 0 if report["status"]=="COMPLETE_SOURCE_WINDOW" else 2
    except Exception as exc:
        info(f"STOPPED V62 error_type={type(exc).__name__}"
             " archived_page_files_preserved=True broker_orders=0")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
