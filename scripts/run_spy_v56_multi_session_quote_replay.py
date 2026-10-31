from __future__ import annotations

"""V56 multi-session native SPY 0DTE quote-reference simulator.

Reuses V55's unchanged, versioned trading policy. Dynamically chooses each
date's contract based only on its completed SPY bars, reads exact 1-second
historical option quotes through the original V38 cache, and advances one
chronological, fee-aware account only after a resolved session. Full per-day
immutable event journals are saved before the cumulative portfolio receipt.
Historical quote-reference P&L is NOT broker fills or validated alpha.
"""

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
import json
import os
from pathlib import Path
import sys
import time
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
if __name__=="__main__" and not __package__:
    sys.path.insert(0,str(ROOT))

from packages.core.settings import load_settings
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.intraday_semantics_audit import (
    B34_MAX_SAMPLE_DATE, _sample_rows, discover_minute_units, validate_minute_rows,
)
from packages.data.spy_v51_native_minute_orb_inventory import _verify_monthly_unit_with_progress
from packages.data.options_on_demand_source_cache_v38 import read_through_historical_options
from packages.simulation.spy_v55_closed_bar_option_replay import (
    CONTRACT as DAY_CONTRACT, STRATEGY, closed_bar_signal, replay_source,
)
from packages.simulation.spy_v55_event_journal import save_journal, verify_journal
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

CONTRACT="atlas-v56-spy-multi-session-closed-bar-quote-account-v1"
ET=ZoneInfo("America/New_York")


def announce(message):
    timestamp=datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S %Z")
    print(f"[{timestamp}] {message}",flush=True)


def dates_in_window(start,end):
    if start>end or end>B34_MAX_SAMPLE_DATE:
        raise ValueError("V56_RANGE_INVALID_OR_PROTECTED_SOURCE")
    date_cursor=start
    while date_cursor<=end:
        if date_cursor.weekday()<5:
            yield date_cursor
        date_cursor+=timedelta(days=1)


def _report_atomic(path, document):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink():
        raise ValueError("V56_OUTPUT_SYMLINK_REJECTED")
    scratch=path.with_name(path.name+".writing")
    if scratch.exists() or scratch.is_symlink():
        raise ValueError("V56_STALE_CHECKPOINT_WRITING_FILE")
    data=json.dumps(document,sort_keys=True,indent=2,allow_nan=False)+"\n"
    with scratch.open("x",encoding="utf-8") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(scratch,path)


def _windows(rows, key):
    groups=defaultdict(list)
    for item in rows:
        day=date.fromisoformat(item["session"])
        if key=="week":
            iso=day.isocalendar()
            group=f"{iso.year}-W{iso.week:02d}"
        elif key=="month":
            group=f"{day.year}-{day.month:02d}"
        else:
            group=str(day.year)
        groups[group].append(item)
    windows=[]
    for label,items in sorted(groups.items()):
        valid=[x for x in items if x["status"]=="CLOSED_QUOTE_REFERENCE"]
        net=sum((Decimal(x["trade_net_pnl"]) for x in valid),Decimal(0))
        fees=sum((Decimal(x["estimated_commissions"]) for x in valid),Decimal(0))
        windows.append({
            "period":label,"evaluated_sessions":len(items),
            "closed_trades":len(valid),
            "winning_trades":sum(Decimal(x["trade_net_pnl"])>0 for x in valid),
            "no_signal":sum(x["status"]=="NO_SIGNAL" for x in items),
            "no_entry":sum(x["status"]=="NO_ENTRY" for x in items),
            "unresolved":sum(x["status"]=="UNRESOLVED_POSITION" for x in items),
            "net_closed_quote_reference_pnl":str(net.quantize(Decimal(".01"))),
            "gross_closed_quote_reference_pnl":str((net+fees).quantize(Decimal(".01"))),
            "modeled_commissions":str(fees.quantize(Decimal(".01"))),
            "historical_profitability_validated":False,
        })
    return windows


def _summary(rows, *, start, end, initial, cash, blocked, statuses, elapsed):
    totals=Counter(x["status"] for x in rows)
    trades=[x for x in rows if x["status"]=="CLOSED_QUOTE_REFERENCE"]
    net=sum((Decimal(x["trade_net_pnl"]) for x in trades),Decimal(0))
    fees=sum((Decimal(x["estimated_commissions"]) for x in trades),Decimal(0))
    high=initial
    dd=Decimal(0)
    curve=[]
    for x in rows:
        if x["terminal_equity_if_resolved"] is not None:
            balance=Decimal(x["terminal_equity_if_resolved"])
            high=max(high,balance)
            dd=max(dd,high-balance)
            curve.append({"date":x["session"],"realized_equity":str(balance),
                          "drawdown_from_peak_usd":str(high-balance)})
        else:
            curve.append({"date":x["session"],"realized_equity":None,
                          "drawdown_from_peak_usd":None})
    result={
        "contract":CONTRACT,"strategy_version":STRATEGY,
        "cohort_start":start.isoformat(),"cohort_end":end.isoformat(),
        "starting_cash":str(initial),"terminal_equity_if_complete":str(cash) if not blocked else None,
        "account_status":"CLOSED_QUOTE_REFERENCE_DEV" if not blocked else "UNRESOLVED_OR_SOURCE_BLOCKED",
        "blocker":blocked,"calendar_weekday_sessions_expected":len(list(dates_in_window(start,end))),
        "sessions_evaluated":len(rows),"session_status_counts":dict(sorted(totals.items())),
        "source_counts":dict(sorted(statuses.items())),
        "modeled_completed_trades":len(trades),
        "winning_closed_trades":sum(Decimal(t["trade_net_pnl"])>0 for t in trades),
        "closed_net_pnl":str(net.quantize(Decimal(".01"))),
        "closed_gross_pnl":str((net+fees).quantize(Decimal(".01"))),
        "modeled_commissions":str(fees.quantize(Decimal(".01"))),
        "max_realized_drawdown_dollars":str(dd.quantize(Decimal(".01"))),
        "realized_cash_curve":curve,
        "weekly":_windows(rows,"week"),"monthly":_windows(rows,"month"),
        "annual":_windows(rows,"year"),"sessions":rows,
        "elapsed_seconds":round(elapsed,2),"actual_broker_fills":0,
        "original_tick_strategy_reproduced":False,
        "historical_publication_verified":False,
        "historical_profitability_validated":False,
        "source_only_quote_reference_development":True,
    }
    result["fingerprint"]=_fingerprint(result)
    return result


def simulate(start,end,*,outdir,lag_seconds=1,max_adverse_pct="1",
             emit=announce, source_get=read_through_historical_options,
             discover=discover_minute_units, integrity=_verify_monthly_unit_with_progress,
             sample=_sample_rows,validate=validate_minute_rows,
             settings_factory=load_settings):
    begun=time.monotonic()
    sessions=list(dates_in_window(start,end))
    emit(f"START V56 SPY full historical multi-session quote-account"
         f" dates={start}..{end} weekday_sessions={len(sessions)}"
         f" lag_seconds={lag_seconds} max_adverse_pct={max_adverse_pct}"
         " mode=DEVELOPMENT start_cash=25000"
         " dynamic_exact_provider_GET_allowed=YES broker_orders=0")
    if not sessions:
        raise ValueError("V56_NO_MARKET_WEEKDAYS_IN_REQUESTED_RANGE")
    if outdir.is_symlink() or outdir.exists():
        raise ValueError("V56_IMMUTABLE_OUTPUT_DIR_ALREADY_EXISTS")
    outdir.mkdir(parents=True,exist_ok=False)
    initial=Decimal("25000.00")
    cash=initial
    rows=[]
    statuses=Counter()
    blocked=None
    by_month={}
    current_month=None
    milestone=10
    elapsed=lambda: max(time.monotonic()-begun,.001)
    # Resolve settings only if there is an actual selected options contract;
    # an offline no-signal day must not authenticate or issue provider calls.
    settings=None
    for i,day in enumerate(sessions,1):
        mon=(day.year,day.month)
        emit(f"STAGE_START session_begin completed={i-1}/{len(sessions)}"
             f" date={day} cash={cash} source_month={mon}")
        if mon not in by_month:
            emit(f"STAGE_START month_scoped_checkpoint_lookup month={mon}")
            units=discover(V2Layout.beneath(ROOT/"data"),
                          target_year=day.year,target_month=day.month,progress=emit)
            matches=[x for x in units if (x.year,x.month)==mon and "SPY" in x.symbols]
            if len(matches)!=1:
                raise ValueError(f"V56_EXPECTED_ONE_NATIVE_SPY_SOURCE month={mon}")
            unit=matches[0]
            emit(f"STAGE_PASS month_scoped_checkpoint_lookup"
                 f" month={mon} source_unit={unit.unit_id} matches={len(matches)}")
            emit(f"STAGE_START original_SHA_once_per_month month={mon}")
            checked=integrity(unit,emit)
            if not checked["accepted"]:
                raise ValueError("V56_FULL_ORIGINAL_MONTHLY_SHA_UNQUALIFIED")
            emit(f"STAGE_PASS original_SHA_once_per_month"
                 f" month={mon} original_sha={unit.canonical_sha256}")
            by_month[mon]=unit
        unit=by_month[mon]
        if day.weekday() not in (0,2,4):
            # Policy exclusion is known before reading that date's OHLC.
            signal=closed_bar_signal([],session=day,
                         source_sha256=unit.canonical_sha256,source_unit_id=unit.unit_id)
            warnings=[]
            emit(f"STAGE_PASS predeclared_weekday_filter date={day} excluded=True")
        else:
            emit(f"STAGE_START read_original_SPY_minute_session date={day}")
            dayrows=sample(unit.canonical_path,symbol="SPY",session_date=day)
            emit(f"STAGE_PASS read_original_SPY_minute_session date={day} bars={len(dayrows)}")
            if dayrows:
                emit(f"STAGE_START validate_minute_session_geometry date={day} bars={len(dayrows)}")
                v=validate(dayrows,sample_class="SPY_0DTE_ORB_SOURCE_PREVIEW",
                           symbol="SPY",session_date=day)
                if not v["accepted"]:
                    raise ValueError(f"V56_NATIVE_BAR_GEOMETRY_INVALID date={day}")
                warnings=v["warnings"]
                emit(f"STAGE_PASS validate_minute_session_geometry date={day}"
                     f" warnings={len(warnings)}")
            else:
                warnings=["NO_COMPLETED_MARKET_SESSION_BARS"]
            signal=closed_bar_signal(dayrows,session=day,
                         source_sha256=unit.canonical_sha256,source_unit_id=unit.unit_id)
        emit(f"STAGE_PASS chronological_signal date={day}"
             f" status={signal['signal_status']}"
             f" selected_contract={signal['selected_contract']}")
        source=None
        source_error=None
        if signal["selected_contract"] is not None:
            if settings is None:
                emit("STAGE_START validate_options_external_storage_binding")
                settings=settings_factory(ROOT,"development")
                emit("STAGE_PASS validate_options_external_storage_binding")
            at=datetime.fromisoformat(signal["decision_at_et"])
            kwargs={**signal["selected_contract"],
                    "start_time_et":at.strftime("%H:%M:%S")+".000",
                    "end_time_et":"15:30:00.000","interval":"1s"}
            emit(f"STAGE_START dynamic_exact_option_source date={day}"
                 f" contract={kwargs['symbol']}:{kwargs['expiration']}:{kwargs['strike']}:{kwargs['right']}"
                 f" start_et={kwargs['start_time_et']}"
                 " on_miss_provider_GET=AUTHORIZED completion_fraction=UNKNOWN")
            try:
                source=source_get(settings,"option_history_exact_quote_tape",kwargs)
                statuses[source["status"]]+=1
                emit(f"STAGE_PASS dynamic_exact_option_source date={day}"
                     f" status={source['status']} rows={len(source['source_rows'])}"
                     f" query_id={source['query_id']}")
            except Exception as exc:
                # No fabricated price/mark; stop this cumulative account
                # rather than asserting a safely resolved source opportunity.
                source_error=type(exc).__name__
                statuses["PROVIDER_OR_ARCHIVE_ERROR"]+=1
                emit(f"STAGE_ERROR dynamic_exact_option_source date={day}"
                     f" error_type={source_error} no_estimated_fill_or_pnl")
        emit(f"STAGE_START one_session_option_quote_replay date={day}")
        replay=replay_source(signal,source,starting_cash=str(cash),
                             lag_seconds=lag_seconds,max_adverse_pct=max_adverse_pct,
                             progress=emit)
        replay["native_unit_checkpoint"]=str(unit.checkpoint_path)
        replay["native_source_warning_codes"]=warnings
        if source_error:
            replay["source_error_type"]=source_error
        replay["fingerprint"]=_fingerprint({k:x for k,x in replay.items() if k!="fingerprint"})
        emit(f"STAGE_PASS one_session_option_quote_replay date={day}"
             f" disposition={replay['status']}"
             f" net_pnl={replay['trade_net_pnl']}"
             f" terminal_equity={replay['terminal_equity_if_resolved']}")
        # Persist per-session source provenance, events and chain before
        # advancing the account. On interruption, completed days survive.
        path=outdir/f"{day.isoformat()}.json"
        journal_path=outdir/f"{day.isoformat()}.jsonl"
        emit(f"STAGE_START persist_and_verify_session_journal date={day}"
             f" event_count={len(replay['events'])}")
        receipt=save_journal(journal_path,replay,progress=emit)
        emit(f"STAGE_PASS persist_and_verify_session_journal"
             f" records={receipt['journal_rows']} sha_tip={receipt['tip_sha256']}")
        emit(f"STAGE_START persist_immutable_session_report date={day}")
        with path.open("x",encoding="utf-8") as stream:
            json.dump(replay,stream,sort_keys=True,indent=2,allow_nan=False)
            stream.write("\n")
        emit(f"STAGE_PASS persist_immutable_session_report path={path}")
        if replay["terminal_equity_if_resolved"] is not None:
            cash=Decimal(replay["terminal_equity_if_resolved"])
        closed=replay["status"]=="CLOSED_QUOTE_REFERENCE"
        entry=next((x for x in replay["events"] if x["type"]=="MODELED_ENTRY_QUOTE_REFERENCE"),None)
        quantity=entry["qty"] if entry and closed else 0
        fees=(Decimal("1.30")*quantity).quantize(Decimal(".01"))
        row={
            "session":day.isoformat(),"status":replay["status"],
            "signal_status":signal["signal_status"],
            "selected_contract":signal["selected_contract"],
            "decision_at_et":signal["decision_at_et"],
            "source_query_id":replay["source_query_id"],
            "source_sha256":replay["source_sha256"],
            "source_status":replay["source_status"],
            "source_error_type":source_error,
            "trade_net_pnl":replay["trade_net_pnl"],
            "estimated_commissions":str(fees),
            "entry_debit":replay["entry_debit"],
            "exit_credit":replay["exit_credit"],
            "terminal_equity_if_resolved":replay["terminal_equity_if_resolved"],
            "censor_reason":replay["censor_reason"],
            "report_path":str(path),
            "report_fingerprint":replay["fingerprint"],
            "event_journal_path":str(journal_path),
            "event_journal_tip":receipt["tip_sha256"],
            "historical_fills":0,
        }
        rows.append(row)
        if source_error or replay["status"]=="UNRESOLVED_POSITION" or (
                signal["selected_contract"] is not None
                and replay["censor_reason"]=="OPTION_SOURCE_MISSING_OR_UNQUALIFIED"):
            blocked={"session":day.isoformat(),
                     "status":replay["status"],
                     "reason":source_error or replay["censor_reason"]}
        summary=_summary(rows,start=start,end=end,initial=initial,cash=cash,
                         blocked=blocked,statuses=statuses,elapsed=elapsed())
        emit(f"STAGE_START persist_atomic_account_checkpoint days={i}/{len(sessions)}")
        _report_atomic(outdir/"checkpoint.json",summary)
        emit(f"STAGE_PASS persist_atomic_account_checkpoint"
             f" completed_days={i} report={outdir/'checkpoint.json'}")
        while milestone<=100 and 100*i>=milestone*len(sessions):
            rate=i/elapsed()
            eta=(len(sessions)-i)/rate
            emit(f"PROGRESS_{milestone}PCT phase=chronological_weekday_sessions"
                 f" completed={i}/{len(sessions)}"
                 f" percent={100*i/len(sessions):.1f}"
                 f" last_date={day} net_closed={summary['closed_net_pnl']}"
                 f" source_statuses={dict(statuses)}"
                 f" elapsed={elapsed():.1f}s throughput_days_s={rate:.4f}"
                 f" eta_rough_s={eta:.1f}")
            milestone+=10
        if blocked:
            emit(f"STAGE_STOP unresolved_or_source_blocked"
                 f" date={day} reason={blocked['reason']}"
                 " future_cash_unknown_no_false_pnl")
            break
    result=_summary(rows,start=start,end=end,initial=initial,cash=cash,
                    blocked=blocked,statuses=statuses,elapsed=elapsed())
    emit(f"STAGE_START finalize_immutable_cohort_report sessions={len(rows)}")
    _report_atomic(outdir/"summary.json",result)
    emit(f"COMPLETE V56 status={result['account_status']}"
         f" evaluated={len(rows)}/{len(sessions)}"
         f" closed_trades={result['modeled_completed_trades']}"
         f" net_pnl={result['closed_net_pnl']}"
         f" terminal_equity={result['terminal_equity_if_complete']}"
         f" elapsed={elapsed():.1f}s summary={outdir/'summary.json'}"
         f" fingerprint={result['fingerprint']} broker_orders=0")
    return 0 if not blocked else 2


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start",default="2025-06-09")
    p.add_argument("--end",default="2025-06-20")
    p.add_argument("--lag-seconds",type=int,choices=(1,3),default=1)
    p.add_argument("--max-adverse-pct",choices=("0.5","1","2"),default="1")
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        return simulate(date.fromisoformat(args.start),date.fromisoformat(args.end),
            outdir=args.output_dir,lag_seconds=args.lag_seconds,
            max_adverse_pct=args.max_adverse_pct)
    except Exception as exc:
        announce(f"STOPPED V56 type={type(exc).__name__}"
                 " no_broker_orders=True existing_daily_receipts_preserved=True")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
