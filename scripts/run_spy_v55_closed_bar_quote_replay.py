from __future__ import annotations

"""One-command V55 development quote-reference run: SPY minute source -> 0DTE option tape -> account.

Makes a dynamic exact provider request only after the selected contract is
fixed by a completed historical SPY 1m close. No broker requests or actual fills.
"""

import argparse
from datetime import date, datetime
import json
from pathlib import Path
import sys
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.intraday_semantics_audit import (
    _sample_rows, discover_minute_units, validate_minute_rows,
    B34_MAX_SAMPLE_DATE,
)
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.spy_v51_native_minute_orb_inventory import (
    _verify_monthly_unit_with_progress,
)
from packages.data.options_on_demand_source_cache_v38 import read_through_historical_options
from packages.simulation.spy_v55_closed_bar_option_replay import (
    CONTRACT, closed_bar_signal, replay_source,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v55_event_journal import save_journal


def progress(message):
    stamp = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S %Z")
    print(f"[{stamp}] {message}", flush=True)


def _save_report(output, report):
    progress(f"STAGE_START save_immutable_full_development_report path={output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    progress(f"STAGE_PASS saved path={output} fingerprint={report['fingerprint']}")


def run(date_et, *, output, lag_seconds=1, max_adverse_pct="1",
        emit=progress, source_get=read_through_historical_options):
    began = time.monotonic()
    emit(f"START V55 SPY completed-bar 0DTE developmental account replay"
         f" date={date_et} lag_seconds={lag_seconds} max_adverse_pct={max_adverse_pct}"
         " native_SHA=REQUIRED provider=cache_first_exact_contract broker_requests=0")
    session = date.fromisoformat(date_et)
    if session > B34_MAX_SAMPLE_DATE:
        raise ValueError("V55_REFUSES_MASTER_HOLDOUT_OR_FUTURE_SOURCE")
    if output.exists() or output.is_symlink():
        raise ValueError("V55_OUTPUT_ALREADY_EXISTS")
    emit("STAGE_START discover_original_monthly_SPY_native_source")
    units = discover_minute_units(V2Layout.beneath(ROOT / "data"))
    matching = [x for x in units if (x.year, x.month) == (session.year,session.month)
                and "SPY" in x.symbols]
    if len(matching) != 1:
        raise ValueError("V55_EXACT_ONE_COMPLETED_SPY_NATIVE_MONTH_REQUIRED")
    unit = matching[0]
    emit(f"STAGE_PASS selected_source_unit={unit.unit_id}"
         f" candidate_month={session.year}-{session.month:02d}")
    integrity = _verify_monthly_unit_with_progress(unit, emit)
    if not integrity["accepted"]:
        raise ValueError("V55_NATIVE_ORIGINAL_SHA_UNQUALIFIED")
    emit(f"STAGE_START read_one_session_SPY_minute_parquet date={date_et}")
    rows = _sample_rows(unit.canonical_path, symbol="SPY", session_date=session)
    emit(f"STAGE_PASS native_rows={len(rows)}")
    if not rows:
        raise ValueError("V55_SPY_MINUTE_SOURCE_EMPTY")
    emit(f"STAGE_START validate_native_SPY_minute_geometry rows={len(rows)}")
    v = validate_minute_rows(rows, sample_class="SPY_0DTE_ORB_SOURCE_PREVIEW",
                             symbol="SPY", session_date=session)
    if not v["accepted"]:
        raise ValueError("V55_NATIVE_MINUTE_GEOMETRY_REJECTED")
    emit(f"STAGE_PASS native_geometry warnings={len(v['warnings'])}")
    emit("STAGE_START select_first_completed_candle_close_signal")
    signal = closed_bar_signal(rows,session=session,source_sha256=unit.canonical_sha256,
                               source_unit_id=unit.unit_id)
    emit(f"STAGE_PASS signal_status={signal['signal_status']}"
         f" contract={signal['selected_contract']}"
         " first_tick_source_claimed=False")
    if signal["selected_contract"] is None:
        replay = replay_source(signal,None,lag_seconds=lag_seconds,
                               max_adverse_pct=max_adverse_pct)
        replay["observed_provider_requests"]=0
    else:
        contract=signal["selected_contract"]
        # Read from the decision onward: no future result or price can select
        # the option right, expiration, strike, or first request clock.
        at = datetime.fromisoformat(signal["decision_at_et"])
        kwargs = {
            **contract,
            "start_time_et": at.strftime("%H:%M:%S") + ".000",
            "end_time_et": "15:30:00.000",
            "interval": "1s",
        }
        emit(f"STAGE_START exact_selected_contract_intraday_quote_source"
             f" {contract['symbol']}:{contract['expiration']}:{contract['strike']}:{contract['right']}"
             f" from={kwargs['start_time_et']} to={kwargs['end_time_et']}"
             " cache_first_provider_if_missing=YES"
             " completion_fraction=UNKNOWN broker_calls=0")
        try:
            settings = load_settings(ROOT,"development")
            source = source_get(settings,"option_history_exact_quote_tape",kwargs)
            provider_attempts = int(source["status"] in
                                    ("FETCHED_AND_ARCHIVED","FETCHED_EXPLICIT_NO_DATA"))
            emit(f"STAGE_PASS source_status={source['status']}"
                 f" quote_rows={len(source['source_rows'])}"
                 f" new_provider_requests={provider_attempts} cache_hits={int(source['status']=='CACHE_HIT')}"
                 f" source_query_id={source['query_id']} elapsed={time.monotonic()-began:.1f}s")
            emit(f"STAGE_START chronological_quote_reference_replay rows={len(source['source_rows'])}")
            replay = replay_source(signal,source,lag_seconds=lag_seconds,
                                   max_adverse_pct=max_adverse_pct,progress=emit)
            replay["observed_provider_requests"] = provider_attempts
        except Exception as exc:
            # Never make up an exit/zero settlement; persist the decision.
            emit(f"STAGE_ERROR source_or_replay_failed type={type(exc).__name__}"
                 " all_missing_prices_censored=True no_broker_orders=True")
            replay = replay_source(signal,{"status":"SOURCE_OR_SCHEMA_ERROR"},
                                   lag_seconds=lag_seconds,max_adverse_pct=max_adverse_pct)
            replay["source_stage_failure_type"] = type(exc).__name__
            replay["observed_provider_requests"] = None
        emit(f"STAGE_PASS replay_disposition={replay['status']}"
             f" net_pnl={replay['trade_net_pnl']}"
             f" quote_reference_only=True")
    # The actual run includes original source SHA and exact selected demand,
    # not raw chain duplication; the cached original remains authoritative.
    replay["native_unit_checkpoint"] = str(unit.checkpoint_path)
    replay["native_source_warning_codes"] = v["warnings"]
    replay["run_elapsed_seconds"] = round(time.monotonic()-began,3)
    replay["fingerprint"] = _fingerprint({k:x for k,x in replay.items() if k!="fingerprint"})
    journal_path=output.with_suffix(".jsonl")
    emit(f"STAGE_START save_and_verify_immutable_hash_chained_journal"
         f" events={len(replay['events'])} path={journal_path}")
    receipt=save_journal(journal_path,replay,progress=emit)
    emit(f"STAGE_PASS journal_records={receipt['journal_rows']}"
         f" journal_tip={receipt['tip_sha256']}")
    emit(f"STAGE_START save_full_quote_source_and_decision_audit events={len(replay['events'])}")
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x",encoding="utf-8") as f:
        json.dump(replay,f,sort_keys=True,indent=2,allow_nan=False)
        f.write("\n")
    emit(f"COMPLETE result={replay['status']} event_count={len(replay['events'])}"
         f" net_pnl={replay['trade_net_pnl']}"
         f" terminal_cash={replay['terminal_equity_if_resolved']}"
         f" source_fingerprint={replay['fingerprint']}"
         f" elapsed={time.monotonic()-began:.1f}s saved={output} journal={journal_path}")
    return (0 if replay["status"] in ("CLOSED_QUOTE_REFERENCE","NO_SIGNAL","NO_ENTRY")
            and "source_stage_failure_type" not in replay
            and replay.get("censor_reason") != "OPTION_SOURCE_MISSING_OR_UNQUALIFIED"
            else 2)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date",default="2025-06-09")
    p.add_argument("--lag-seconds",type=int,choices=(1,3),default=1)
    p.add_argument("--max-adverse-pct",choices=("0.5","1","2"),default="1")
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        return run(args.date,output=args.output,lag_seconds=args.lag_seconds,
                   max_adverse_pct=args.max_adverse_pct)
    except Exception as exc:
        progress(f"STOPPED V55 type={type(exc).__name__}"
                 " inspect_source_environment_or_report no_broker_orders=True")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
