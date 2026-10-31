from __future__ import annotations

"""V58 paired V56 baseline versus V57 independent-cash adaptive quote exits.

Strictly offline, source-fingerprint and per-day SHA-journal checked.
An adaptive position requiring quotes after the V56 baseline stops is CENSORED,
never awarded a fabricated exit or profit. The V57 policy was chosen after
seeing June 9, 2025: all historical evaluation remains developmental/in-sample.
"""

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v55_event_journal import verify_journal
from packages.simulation.spy_v57_causal_exit_shadow import replay_adaptive_shadow

CONTRACT="atlas-v58-independent-adaptive-cohort-audit-v1"
PARENT_CONTRACT="atlas-v56-spy-multi-session-closed-bar-quote-account-v1"
ET=ZoneInfo("America/New_York")


class CohortError(ValueError):
    pass


def announce(message):
    t=datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S %Z")
    print(f"[{t}] {message}",flush=True)


def _signed(doc):
    return {**doc,"fingerprint":_fingerprint(doc)}


def _money(value):
    return str(Decimal(value).quantize(Decimal(".01")))


def _verify_signed(doc,expected=None):
    if not isinstance(doc,dict):
        raise CohortError("NOT_JSON_OBJECT")
    expected_actual=_fingerprint({k:v for k,v in doc.items() if k!="fingerprint"})
    if doc.get("fingerprint")!=expected_actual:
        raise CohortError("FINGERPRINT_MISMATCH")
    if expected is not None and expected_actual!=expected:
        raise CohortError("FINGERPRINT_RECEIPT_MISMATCH")
    return doc


def _read_json(path):
    if path.is_symlink() or not path.is_file():
        raise CohortError("MISSING_OR_SYMLINKED_INPUT")
    with path.open("r",encoding="utf-8") as f:
        return _verify_signed(json.load(f))


def _atomic(path,doc):
    path.parent.mkdir(parents=True,exist_ok=True)
    scratch=path.with_name(path.name+".writing")
    if scratch.exists() or scratch.is_symlink() or path.is_symlink():
        raise CohortError("UNSAFE_OUTPUT_PATH")
    with scratch.open("x",encoding="utf-8") as f:
        json.dump(doc,f,sort_keys=True,indent=2,allow_nan=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(scratch,path)


def _windows(pairs,key):
    groups=defaultdict(list)
    for r in pairs:
        d=date.fromisoformat(r["session"])
        if key=="weekly":
            w=d.isocalendar()
            period=f"{w.year}-W{w.week:02d}"
        elif key=="monthly":
            period=f"{d.year}-{d.month:02d}"
        else:
            period=str(d.year)
        groups[period].append(r)
    results=[]
    for period,rows in sorted(groups.items()):
        matched=[r for r in rows if r["paired_comparison_eligible"]]
        a=sum((Decimal(r["adaptive_net_pnl"]) for r in matched),Decimal(0))
        b=sum((Decimal(r["baseline_net_pnl"]) for r in matched),Decimal(0))
        results.append({
            "period":period,"evaluated_days":len(rows),"matched_closed_trades":len(matched),
            "candidate_only_censored":sum(r["adaptive_status"].startswith("CENSORED") for r in rows),
            "matched_candidate_net_pnl":_money(a),
            "matched_baseline_net_pnl":_money(b),
            "matched_candidate_minus_baseline":_money(a-b),
            "independent_holdout":False,"broker_fills_verified":False,
        })
    return results


def _cohort_snapshot(parent,rows,*,starting,cash,blocker):
    baseline_closed=[x for x in rows if x["baseline_status"]=="CLOSED_QUOTE_REFERENCE"]
    paired=[x for x in rows if x["paired_comparison_eligible"]]
    delta=sum((Decimal(x["delta_net_pnl"]) for x in paired),Decimal(0))
    statuses=Counter(x["adaptive_status"] for x in rows)
    peaks=starting
    dd=Decimal(0)
    curve=[]
    for r in rows:
        if r["adaptive_equity_after"] is None:
            curve.append({"session":r["session"],"adaptive_cash":None,
                          "drawdown_usd":None})
            continue
        b=Decimal(r["adaptive_equity_after"])
        peaks=max(peaks,b)
        dd=max(dd,peaks-b)
        curve.append({"session":r["session"],"adaptive_cash":str(b),
                      "drawdown_usd":_money(peaks-b)})
    doc={
        "contract":CONTRACT,"v56_parent_fingerprint":parent["fingerprint"],
        "cohort_start":parent["cohort_start"],"cohort_end":parent["cohort_end"],
        "original_parent_sessions":len(parent["sessions"]),
        "sessions_evaluated":len(rows),
        "starting_cash":str(starting),
        "account_status":("INCOMPLETE_CENSORED_OR_UNRESOLVED" if blocker else
                          "INDEPENDENT_ADAPTIVE_QUOTE_REFERENCE_DEV"),
        "blocker":blocker,
        "adaptive_terminal_equity_if_complete":str(cash) if not blocker else None,
        "original_v56_baseline_terminal_equity_if_complete":parent["terminal_equity_if_complete"],
        "original_v56_baseline_net_pnl":parent["closed_net_pnl"],
        "baseline_closed_trades":len(baseline_closed),
        "paired_closed_trades":len(paired),
        "paired_adaptive_win_count":sum(Decimal(x["adaptive_net_pnl"])>0 for x in paired),
        "paired_baseline_win_count":sum(Decimal(x["baseline_net_pnl"])>0 for x in paired),
        "paired_candidate_minus_baseline":_money(delta),
        "paired_improved":sum(Decimal(x["delta_net_pnl"])>0 for x in paired),
        "paired_worsened":sum(Decimal(x["delta_net_pnl"])<0 for x in paired),
        "paired_unchanged":sum(Decimal(x["delta_net_pnl"])==0 for x in paired),
        "paired_only_not_a_full_cohort_performance_claim":True,
        "shadow_status_counts":dict(sorted(statuses.items())),
        "max_adaptive_realized_drawdown_usd":_money(dd),
        "independent_adaptive_account_curve":curve,
        "weekly":_windows(rows,"weekly"),
        "monthly":_windows(rows,"monthly"),
        "annual":_windows(rows,"annual"),
        "sessions":rows,
        "rule_hyperparameters_fit_on_prior_folds":False,
        "v57_selected_after_observing_original_june_9_day":True,
        "published_original_tick_strategy_reproduced":False,
        "actual_broker_fills":0,"historical_profitability_validated":False,
        "theta_data_requests":0,"broker_requests":0,
    }
    return _signed(doc)


def evaluate(cohort_dir,outdir,*,verify=verify_journal,emit=announce):
    emit(f"START V58 independent adaptive multi-session shadow"
         f" cohort={cohort_dir} paid_requests=0 broker_requests=0")
    if outdir.exists() or outdir.is_symlink():
        raise CohortError("IMMUTABLE_OUTPUT_DIR_ALREADY_EXISTS")
    emit("STAGE_START verify_v56_account_summary")
    parent=_read_json(cohort_dir/"summary.json")
    if parent.get("contract")!=PARENT_CONTRACT:
        raise CohortError("V56_ACCOUNT_CONTRACT_MISMATCH")
    days=parent.get("sessions")
    if not isinstance(days,list) or not days:
        raise CohortError("EMPTY_OR_INVALID_V56_COHORT")
    if len(days)!=parent.get("sessions_evaluated"):
        raise CohortError("V56_SESSION_COUNT_MISMATCH")
    if len({d.get("session") for d in days})!=len(days):
        raise CohortError("DUPLICATE_V56_DAY")
    if [d["session"] for d in days]!=sorted(d["session"] for d in days):
        raise CohortError("NONCHRONOLOGICAL_V56_DAYS")
    starting=Decimal(parent["starting_cash"])
    cash=starting
    if starting<=0:
        raise CohortError("NONPOSITIVE_ACCOUNT_START")
    emit(f"STAGE_PASS verify_v56_account_summary days={len(days)}"
         f" summary_fp={parent['fingerprint']}")
    outdir.mkdir(parents=True,exist_ok=False)
    rows=[]
    blocker=None
    next_milestone=10
    baseline_cash=starting
    for i,day in enumerate(days,1):
        sid=day["session"]
        parsed=date.fromisoformat(sid)
        if not (date.fromisoformat(parent["cohort_start"])<=parsed
                <=date.fromisoformat(parent["cohort_end"])):
            raise CohortError("V56_DAY_OUTSIDE_COHORT")
        emit(f"STAGE_START verify_day_and_replay day={sid} completed={i-1}/{len(days)}"
             f" independent_equity={cash}")
        source=_read_json(cohort_dir/f"{sid}.json")
        _verify_signed(source,day["report_fingerprint"])
        receipt=verify(cohort_dir/f"{sid}.jsonl")
        if (receipt["report_fingerprint"]!=source["fingerprint"]
                or receipt["tip_sha256"]!=day["event_journal_tip"]):
            raise CohortError("V56_DAY_JOURNAL_AND_RECEIPT_DISAGREE")
        if (source["session"]!=sid or source["status"]!=day["status"]
                or source.get("source_query_id")!=day.get("source_query_id")
                or source.get("source_sha256")!=day.get("source_sha256")
                or Decimal(source["starting_cash"])!=baseline_cash):
            raise CohortError("V56_DAY_SOURCE_OR_EQUITY_MISMATCH")
        if (source["terminal_equity_if_resolved"] is not None):
            baseline_cash=Decimal(source["terminal_equity_if_resolved"])
        elif source["status"] not in ("NO_SIGNAL","NO_ENTRY"):
            # Source-blocked V56 cannot establish downstream baseline cash.
            blocker={"session":sid,"reason":"BASELINE_CASH_UNRESOLVED"}
        if source["status"] in ("NO_SIGNAL","NO_ENTRY"):
            # A baseline cash rejection may differ under the adaptive account:
            # do not silently assert an equal ability to enter.
            if source.get("censor_reason")=="PREMIUM_CAP_CASH_OR_ASK_SIZE_INSUFFICIENT":
                blocker={"session":sid,"reason":"CASH_DEPENDENT_BASELINE_NO_ENTRY"}
        adaptive=replay_adaptive_shadow(source,starting_cash_override=str(cash))
        closed=adaptive["status"]=="CLOSED_ADAPTIVE_QUOTE_REFERENCE"
        bclosed=source["status"]=="CLOSED_QUOTE_REFERENCE"
        if closed:
            cash=Decimal(adaptive["terminal_equity_if_resolved"])
        elif adaptive["status"]!="NO_ENTRY_IN_PARENT":
            blocker={"session":sid,"reason":adaptive["status"]}
        paired=closed and bclosed and not blocker
        bnet=source["trade_net_pnl"] if bclosed else None
        anet=adaptive["net_pnl"] if closed else None
        delta=_money(Decimal(anet)-Decimal(bnet)) if paired else None
        r={
            "session":sid,"baseline_status":source["status"],
            "adaptive_status":adaptive["status"],
            "baseline_starting_cash":source["starting_cash"],
            "independent_adaptive_starting_cash":adaptive["independent_account_cash_override"],
            "baseline_net_pnl":bnet,"adaptive_net_pnl":anet,
            "delta_net_pnl":delta,"paired_comparison_eligible":paired,
            "adaptive_equity_after":str(cash) if not blocker else None,
            "exit_reason":adaptive["exit_reason"],
            "quote_decisions_reviewed":adaptive["observed_quotes"],
            "source_report_fingerprint":source["fingerprint"],
            "source_journal_sha_tip":receipt["tip_sha256"],
            "adaptive_report_fingerprint":adaptive["fingerprint"],
            "adaptive_report_path":str(outdir/f"{sid}.json"),
            "historical_alpha_validated":False,
        }
        rows.append(r)
        with (outdir/f"{sid}.json").open("x",encoding="utf-8") as f:
            json.dump(adaptive,f,sort_keys=True,indent=2,allow_nan=False)
            f.write("\n")
        _atomic(outdir/"checkpoint.json",_cohort_snapshot(
            parent,rows,starting=starting,cash=cash,blocker=blocker))
        emit(f"STAGE_PASS verified_and_shadowed date={sid}"
             f" baseline={source['status']} adaptive={adaptive['status']}"
             f" adaptive_net={anet} paired_delta={delta}"
             f" independent_cash={cash}")
        while next_milestone<=100 and i*100>=next_milestone*len(days):
            emit(f"PROGRESS_{next_milestone}PCT"
                 f" completed={i}/{len(days)}"
                 f" last_date={sid} independent_cash={cash}"
                 f" paired_trades={sum(x['paired_comparison_eligible'] for x in rows)}")
            next_milestone+=10
        if blocker is not None:
            emit(f"STAGE_STOP incomplete_cash_or_quote_evidence"
                 f" date={sid} reason={blocker['reason']}"
                 " no_assumed_following_trade_returns")
            break
    result=_cohort_snapshot(parent,rows,starting=starting,cash=cash,blocker=blocker)
    _atomic(outdir/"summary.json",result)
    emit(f"COMPLETE V58 status={result['account_status']}"
         f" days={len(rows)}/{len(days)}"
         f" paired={result['paired_closed_trades']}"
         f" paired_difference={result['paired_candidate_minus_baseline']}"
         f" adaptive_equity={result['adaptive_terminal_equity_if_complete']}"
         f" output={outdir/'summary.json'} provider_calls=0 broker_orders=0")
    return 0 if blocker is None else 2


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cohort-dir",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        return evaluate(args.cohort_dir,args.output_dir)
    except Exception as exc:
        announce(f"STOPPED V58 type={type(exc).__name__}"
                 " archived_outputs_kept=True no_provider_calls=True")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
