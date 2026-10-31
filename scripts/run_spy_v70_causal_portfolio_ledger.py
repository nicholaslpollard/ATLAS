from __future__ import annotations

"""V70: chronological fee-aware cash ledger from SHA-verified V69 simulations.

V69 must have acquired and verified all exact sources first. The original V55
frozen one-second/one-percent quote-reference entries/exits are preserved. A
position with an unqualified exit HALTS cash chaining; later independent days
remain available in V69's source/signal reports, but are not folded into
fictional account equity. This is not broker execution or validated alpha.
"""

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

ET = ZoneInfo("America/New_York")
CONTRACT = "atlas-v70-verified-v69-chronological-quote-cash-ledger-v1"
V69 = "atlas-v69-spy-source-first-multiwindow-exact-options-census-v1"
V65 = "atlas-v65-full-horizon-spy-closed-bar-offline-source-gate-v1"
V39 = "atlas-strategy-options-data-demand-runtime-v39"
V55_POLICY = {"lag_seconds": 1, "max_adverse_pct": "1"}


class V70Error(ValueError):
    pass


def log(message):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {message}",
          flush=True)


def signed(data):
    return {**data, "fingerprint": _fingerprint(data)}


def read_signed(path, contract=None):
    if path.is_symlink() or not path.is_file():
        raise V70Error("V70_ORIGINAL_REPORT_MISSING_OR_SYMLINK")
    doc = json.loads(path.read_text(encoding="utf8"))
    if (not isinstance(doc, dict)
            or doc.get("fingerprint") != _fingerprint({
                k: v for k, v in doc.items() if k != "fingerprint"
            })
            or (contract is not None and doc.get("contract") != contract)):
        raise V70Error("V70_SIGNED_SOURCE_REPORT_CHANGED")
    return doc


def write_once(path, doc):
    value = signed(doc)
    with path.open("x", encoding="utf8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return value


def money(x):
    try:
        val = Decimal(str(x))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise V70Error("V70_INVALID_MONEY") from exc
    if not val.is_finite() or val != val.quantize(Decimal("0.01")):
        raise V70Error("V70_UNVERIFIED_MONEY_PRECISION")
    return val


def validated_sessions(v69_folder, *, expected_summary_fingerprint=None):
    summary = read_signed(v69_folder / "summary.json", V69)
    if (expected_summary_fingerprint is not None
            and summary["fingerprint"] != expected_summary_fingerprint):
        raise V70Error("V70_V69_PARENT_NOT_EXPECTED_ACCEPTED_COHORT")
    if (summary.get("broker_orders") != 0
            or summary.get("status") not in (
                "COMPLETE_SOURCE_CENSUS_QUOTE_REFERENCE_ONLY",
                "COMPLETE_SOURCE_CENSUS_WITH_OPEN_POSITIONS",
            )
            or summary.get("unresolved_source_or_underlying_chunks") != 0
            or summary.get("completed_chunk_reports") != summary.get("chunks")
            or summary.get("all_strategy_source_demands_persisted_or_blocker_reported") is not True):
        raise V70Error("V70_UPSTREAM_UNRESOLVED_SOURCE_BLOCKER")
    validated = []
    previous_day = None
    for index, fragment in enumerate(summary["chunk_summaries"], 1):
        if (fragment.get("index") != index or fragment.get("blocked") is not False
                or fragment.get("unresolved_sources") != 0
                or fragment.get("status") != "SOURCE_CHECKED_AND_REPLAYED"):
            raise V70Error("V70_UPSTREAM_CHUNK_NOT_SOURCE_COMPLETE")
        prefix = f"chunk_{index:04d}"
        chunk = read_signed(v69_folder / f"{prefix}.summary.json", V69)
        replay = read_signed(v69_folder / f"{prefix}.replay.json", V65)
        original = read_signed(v69_folder / f"{prefix}.preflight.json", V65)
        source_receipt = read_signed(v69_folder / f"{prefix}.sources.json", V69)
        if (chunk["fingerprint"] != fragment["fingerprint"]
                or chunk["original_v65_preflight_sha"] != original["fingerprint"]
                or chunk["original_v65_post_source_sha"] != replay["fingerprint"]
                or source_receipt["original_preflight_sha"] != original["fingerprint"]
                or source_receipt.get("broker_orders") != 0
                or replay.get("broker_orders") != 0
                or replay.get("provider_requests") != 0
                or source_receipt["runtime_source_receipt"].get("contract") != V39
                or replay.get("option_source_state_counts", {}).get("ARCHIVED", 0)
                    != chunk.get("selected_option_contracts")
                or chunk.get("unresolved_source_requirements")
                or chunk.get("unresolved_positions", -1) != fragment.get("unresolved_positions")):
            raise V70Error("V70_V69_REPORT_CHAIN_INCONSISTENT")
        rows = replay.get("session_reports")
        if (not isinstance(rows, list)
                or chunk["weekdays"] != len(rows)
                or source_receipt["runtime_source_receipt"].get("source_uses_requested")
                    != chunk["selected_option_contracts"]):
            raise V70Error("V70_V69_SESSION_OR_DEMAND_COUNT_CHANGED")
        original_by_day = {row["session"]: row for row in original["session_reports"]}
        if len(original_by_day) != len(rows):
            raise V70Error("V70_V69_ORIGINAL_DAY_DUPLICATED")
        for row in rows:
            day = row["session"]
            if previous_day is not None and day <= previous_day:
                raise V70Error("V70_NONCHRONOLOGICAL_OR_OVERLAPPED_CHUNKS")
            previous_day = day
            if (row["fingerprint"] != _fingerprint({
                    k: v for k, v in row.items() if k != "fingerprint"
                }) or day not in original_by_day
                    or row.get("signal_fingerprint") !=
                        original_by_day[day].get("signal_fingerprint")
                    or row.get("selected_contract") !=
                        original_by_day[day].get("selected_contract")
                    or row.get("exact_option_requirement") !=
                        original_by_day[day].get("exact_option_requirement")
                    or row.get("native_minute_source_sha256") !=
                        original_by_day[day].get("native_minute_source_sha256")):
                raise V70Error("V70_ORIGINAL_SIGNAL_OR_SHA_DRIFT")
            receipt = row.get("exact_option_receipt")
            report = row["standalone_replay_report"]
            if (report.get("fingerprint") != _fingerprint({
                    k: v for k, v in report.items() if k != "fingerprint"
                }) or report.get("status") != row["standalone_replay_disposition"]
                    or report.get("session") != day
                    or report.get("actual_fills") != 0
                    or report.get("quote_reference_not_broker_execution") is not True
                    or report.get("policy", {}).get("lag_seconds") != 1
                    or str(report.get("policy", {}).get("max_adverse_pct")) != "1"):
                raise V70Error("V70_ORIGINAL_QUOTE_REPLAY_NOT_ACCEPTED")
            if row.get("exact_option_requirement") is None:
                if receipt is not None or report["status"] != "NO_SIGNAL":
                    raise V70Error("V70_UNQUALIFIED_NO_SIGNAL")
            else:
                if (not isinstance(receipt, dict)
                        or receipt.get("state") != "ARCHIVED"
                        or receipt.get("query_id") != _fingerprint(
                            row["exact_option_requirement"]
                        )
                        or receipt.get("query_id") != report.get("source_query_id")
                        or receipt.get("archive_sha256") != report.get("source_sha256")):
                    raise V70Error("V70_MISSING_OR_MISMATCHED_ORIGINAL_TAPE")
                if (report["status"] == "NO_ENTRY"
                        and report.get("censor_reason") in (
                            "OPTION_SOURCE_MISSING_OR_UNQUALIFIED",
                            "OPTION_SOURCE_SHA_OR_QUERY_MISSING",
                            "OPTION_SOURCE_EXACT_IDENTITY_INVALID",
                            "OPTION_SOURCE_EMPTY",
                        )):
                    raise V70Error("V70_SOURCE_CENSORED_NO_ENTRY_INVALID")
            validated.append(row)
    if not validated or summary.get("weekdays") != len(validated):
        raise V70Error("V70_FULL_SESSION_COVERAGE_INVALID")
    return summary, validated


def ledger(v69_folder, output_dir, *, expected_summary_fingerprint=None,
           starting_cash="25000", emit=log):
    parent, sessions = validated_sessions(
        v69_folder, expected_summary_fingerprint=expected_summary_fingerprint,
    )
    if output_dir.exists() or output_dir.is_symlink():
        raise V70Error("V70_OUTPUT_IMMUTABLE_ALREADY_EXISTS")
    initial = money(starting_cash)
    if initial <= 0:
        raise V70Error("V70_STARTING_CASH_INVALID")
    output_dir.mkdir(parents=True, exist_ok=False)
    balance = initial
    peak = initial
    drawdown = Decimal("0")
    realized = Decimal("0")
    days = []
    weekly = defaultdict(list)
    counts = Counter()
    blocked = None
    emit(f"START V70 original_sha={parent['fingerprint'][:16]} "
         f"weekdays={len(sessions)} initial={initial:.2f} "
         "source_acquisition=PREVIOUSLY_VERIFIED_V69 broker_orders=0")
    for i, row in enumerate(sessions, 1):
        report = row["standalone_replay_report"]
        status = report["status"]
        day = row["session"]
        events = report["events"]
        entries = [x for x in events if x.get("type") == "MODELED_ENTRY_QUOTE_REFERENCE"]
        exits = [x for x in events if x.get("type") == "MODELED_EXIT_QUOTE_REFERENCE"]
        before = balance
        datum = {
            "contract": CONTRACT, "session": day,
            "original_session_fingerprint": row["fingerprint"],
            "original_replay_fingerprint": report["fingerprint"],
            "original_query_id": report.get("source_query_id"),
            "original_source_sha256": report.get("source_sha256"),
            "status": status, "balance_before": str(before),
            "balance_after": None, "realized_pnl": None,
            "no_broker_execution": True, "original_quote_event_count": len(events),
            "original_quote_replay_policy": V55_POLICY,
            "reason": report.get("censor_reason"),
        }
        if status == "CLOSED_QUOTE_REFERENCE":
            if (len(entries) != 1 or len(exits) != 1
                    or report.get("entry_debit") is None
                    or report.get("exit_credit") is None
                    or report.get("trade_net_pnl") is None):
                raise V70Error("V70_CLOSED_TRADE_EVENT_EVIDENCE_INCOMPLETE")
            debit = money(report["entry_debit"])
            credit = money(report["exit_credit"])
            pnl = money(report["trade_net_pnl"])
            if (debit <= 0 or credit < 0 or pnl != credit - debit
                    or debit != money(entries[0]["debit_plus_entry_fees"])
                    or credit != money(exits[0]["credit_less_exit_fees"])
                    or money(report["terminal_equity_if_resolved"]) !=
                        money(report["starting_cash"]) + pnl
                    or (entries[0].get("qty", 0) <= 0)
                    or entries[0].get("broker_fill_verified") is not False
                    or exits[0].get("broker_fill_verified") is not False
                    or report.get("starting_cash") != "25000.00"):
                raise V70Error("V70_ORIGINAL_FEE_OR_CASH_EVENT_NOT_RECONCILED")
            # V55 caps option premium independently of cash. If a future
            # portfolio balance cannot cover the frozen trade, its quantity
            # must be re-simulated, NOT silently carried from the $25k test.
            if before < debit:
                blocked = {
                    "session": day, "reason": "FROZEN_QUANTITY_REQUIRES_DYNAMIC_CASH_REPLAY",
                    "trade_not_counted": True,
                }
                datum["status"] = "CASH_SIZING_REPLAY_REQUIRED"
            else:
                balance += pnl
                realized += pnl
                datum["balance_after"] = str(balance)
                datum["realized_pnl"] = str(pnl)
                datum["entry_debit"] = str(debit)
                datum["exit_credit"] = str(credit)
                datum["quantity"] = entries[0]["qty"]
        elif status in ("NO_SIGNAL", "NO_ENTRY"):
            if entries or exits or report.get("trade_net_pnl") is not None:
                raise V70Error("V70_NONTRADE_HAS_MODELED_FILL")
            datum["balance_after"] = str(balance)
            datum["realized_pnl"] = "0.00"
        elif status == "UNRESOLVED_POSITION":
            if len(entries) != 1 or exits or report.get("terminal_equity_if_resolved") is not None:
                raise V70Error("V70_UNRESOLVED_POSITION_NOT_PROPERLY_CENSORED")
            blocked = {
                "session": day, "reason": report["censor_reason"],
                "entry_debit_at_risk": report.get("entry_debit"),
                "trade_not_counted": True,
                "future_cash_is_unknown": True,
            }
        else:
            raise V70Error("V70_UNKNOWN_OR_UNSUPPORTED_REPLAY_STATUS")
        if blocked:
            datum["unresolved_portfolio_state"] = blocked
        else:
            counts[status] += 1
            peak = max(peak, balance)
            drawdown = max(drawdown, peak - balance)
            d = date.fromisoformat(day)
            iso = d.isocalendar()
            weekly[f"{iso.year}-W{iso.week:02d}"].append(datum)
        receipt = write_once(output_dir / f"{day}.json", datum)
        days.append({"session": day, "status": datum["status"],
                     "fingerprint": receipt["fingerprint"],
                     "balance_after": datum["balance_after"],
                     "realized_pnl": datum["realized_pnl"]})
        emit(f"PROGRESS V70 completed={i}/{len(sessions)} day={day} "
             f"status={datum['status']} balance={datum['balance_after']}")
        if blocked:
            emit(f"STAGE_BLOCKED V70 day={day} reason={blocked['reason']} "
                 "future_equity_not_invented=True")
            break
    weekly_summary = []
    for week, rows in sorted(weekly.items()):
        idxs = [date.fromisoformat(r["session"]).weekday() for r in rows]
        value = sum(money(r["realized_pnl"]) for r in rows)
        weekly_summary.append({
            "week": week, "days_present": len(rows),
            "all_five_weekdays_in_scope": idxs == list(range(5)),
            "closed_trades": sum(r["status"] == "CLOSED_QUOTE_REFERENCE" for r in rows),
            "realized_pnl": str(value),
            "week_profitability_certified": False,
        })
    complete = blocked is None and len(days) == len(sessions)
    summary = write_once(output_dir / "summary.json", {
        "contract": CONTRACT,
        "status": "COMPLETE_QUOTE_REFERENCE_CASH_LEDGER" if complete
                  else "CENSORED_OR_REPLAY_REQUIRED_CASH_LEDGER",
        "original_v69_fingerprint": parent["fingerprint"],
        "initial_cash": str(initial),
        "terminal_cash_if_fully_resolved": str(balance) if complete else None,
        "realized_trade_pnl_before_any_blocker": str(realized),
        "last_known_settled_cash_before_blocker": str(balance),
        "max_settled_cash_drawdown_before_blocker": str(drawdown),
        "total_sessions_in_original_source_scope": len(sessions),
        "session_reports_saved": len(days),
        "completed_sessions_before_blocker": sum(counts.values()),
        "original_outcome_counts_before_blocker": dict(sorted(counts.items())),
        "blocked_account_at": blocked,
        "daily_reports": days,
        "weekly_partial_observation": weekly_summary,
        "complete_monthly_or_annual_profitability_proven": False,
        "source_data_previously_acquired_by_v69": True,
        "additional_provider_requests": 0,
        "actual_fills": 0, "broker_orders": 0,
        "historical_alpha_validated": False,
        "source_and_cash_censor_conditions_not_zero_returns": True,
    })
    emit(f"COMPLETE V70 status={summary['status']} "
         f"days={len(days)}/{len(sessions)} terminal_cash="
         f"{summary['terminal_cash_if_fully_resolved']} "
         f"summary={output_dir/'summary.json'} broker_orders=0")
    return summary


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v69-folder", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--expected-v69-fingerprint")
    a = p.parse_args(argv)
    try:
        result = ledger(a.v69_folder, a.output_dir,
                        expected_summary_fingerprint=a.expected_v69_fingerprint)
        return 0 if result["status"] == "COMPLETE_QUOTE_REFERENCE_CASH_LEDGER" else 2
    except Exception as exc:
        log(f"STOPPED V70 error_class={type(exc).__name__} "
            "no_provider_requests=True no_broker_orders=True "
            "existing_receipts_not_overwritten=True")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
