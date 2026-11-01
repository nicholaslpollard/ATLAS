from __future__ import annotations

"""V103 read-only, one-slot cash chain over immutable signed V65 ORB reports.

This *is not* the V51 first-tick ORB. Original minute-close V55 source,
entry, fill assumptions and exit rules are unchanged. Missing exact source
is censored, NOT a flat no-trade day. A censored 0DTE exit freezes the
continuous cash chain; later independently inspected days stay diagnostic.
"""
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

CONTRACT = "atlas-v103-multimonth-source-linked-closed-minute-orb-one-slot-cash-v1"
V65 = "atlas-v65-full-horizon-spy-closed-bar-offline-source-gate-v1"
V55 = "atlas-v55-spy-0dte-closed-minute-option-quote-replay-v1"
START = Decimal("25000.00")
REAL_NO_ENTRIES = frozenset({
    "ACTION_ASK_PRICE_CHANGE_OVER_LIMIT",
    "PREMIUM_CAP_CASH_OR_ASK_SIZE_INSUFFICIENT",
})


class V103Error(ValueError):
    pass


def money(raw):
    try:
        n = Decimal(str(raw))
    except (ValueError, TypeError, InvalidOperation) as exc:
        raise V103Error("V103_CASH_NOT_NUMERIC") from exc
    if not n.is_finite() or n.as_tuple().exponent < -2:
        raise V103Error("V103_CASH_PRECISION_OR_FINITE_INVALID")
    return n.quantize(Decimal(".01"))


def signed(obj):
    return {**obj, "fingerprint": _fingerprint(obj)}


def verify(doc):
    return (isinstance(doc, dict)
            and doc.get("fingerprint") == _fingerprint({
                k: v for k, v in doc.items() if k != "fingerprint"}))


def classify(row, session):
    """Never convert missing stock/option observations into a no-signal."""
    if not verify(row) or row.get("session") != session.isoformat():
        raise V103Error("V103_ORIGINAL_SIGNED_SESSION_INVALID")
    report = row.get("standalone_replay_report")
    if (not verify(report) or report.get("contract") != V55
            or report.get("session") != session.isoformat()
            or report.get("actual_fills") != 0):
        raise V103Error("V103_ORIGINAL_V55_REPORT_INVALID")
    if row.get("standalone_replay_disposition") != report["status"]:
        raise V103Error("V103_V65_REPLAY_DISPOSITION_DRIFT")
    signal = report.get("signal")
    if (not verify(signal) or signal.get("fingerprint") != row["signal_fingerprint"]
            or signal.get("session") != session.isoformat()):
        raise V103Error("V103_ORIGINAL_MINUTE_SIGNAL_INVALID")
    if session.weekday() not in (0, 2, 4):
        if signal["signal_status"] != "WEEKDAY_OUTSIDE_MWF_VERSION":
            raise V103Error("V103_EXCLUDED_WEEKDAY_DRIFT")
        return "POLICY_EXCLUDED", None
    if signal["signal_status"] in ("MISSING_OPENING_MINUTE",
                                   "MISSING_MINUTE_BEFORE_SIGNAL"):
        return "STOCK_SOURCE_CENSORED", signal["signal_status"]
    if signal["signal_status"] == "NO_COMPLETED_BAR_CLOSE_BREAKOUT":
        if report["status"] != "NO_SIGNAL" or signal["selected_contract"] is not None:
            raise V103Error("V103_FALSE_NO_SIGNAL")
        return "VERIFIED_NO_SIGNAL", None
    if signal["signal_status"] != "COMPLETED_BAR_BREAKOUT_DEVELOPMENT":
        return "STOCK_SOURCE_CENSORED", signal["signal_status"]
    receipt = row.get("exact_option_receipt")
    required = row.get("exact_option_requirement")
    if (not isinstance(required, dict) or not isinstance(receipt, dict)
            or required.get("method") != "option_history_exact_quote_tape"
            or receipt.get("query_id") != _fingerprint(required)):
        return "OPTION_SOURCE_CENSORED", "EXACT_ORIGINAL_QUERY_OR_RECEIPT_MISSING"
    if receipt["state"] != "ARCHIVED":
        return "OPTION_SOURCE_CENSORED", receipt["state"]
    if (not receipt.get("archive_sha256")
            or receipt["archive_sha256"] != report.get("source_sha256")
            or report.get("source_query_id") != receipt["query_id"]):
        raise V103Error("V103_VERIFIED_OPTION_SOURCE_SHA_DRIFT")
    if report["status"] == "CLOSED_QUOTE_REFERENCE":
        debit, credit, pnl = (money(report[k]) for k in (
            "entry_debit", "exit_credit", "trade_net_pnl"))
        if (debit <= 0 or credit < 0 or credit - debit != pnl
                or money(report["starting_cash"]) != START
                or money(report["terminal_equity_if_resolved"]) != START + pnl):
            raise V103Error("V103_ORIGINAL_CLOSED_CASH_DRIFT")
        return "CLOSED_QUOTE_REFERENCE", {"debit": str(debit), "credit": str(credit),
                                          "net_pnl": str(pnl)}
    if report["status"] == "UNRESOLVED_POSITION":
        if report["terminal_equity_if_resolved"] is not None:
            raise V103Error("V103_UNRESOLVED_ASSIGNED_FINAL_EQUITY")
        return "UNKNOWN_EXIT_CENSORED", report.get("censor_reason")
    if report["status"] == "NO_ENTRY":
        if report.get("censor_reason") in REAL_NO_ENTRIES:
            if report.get("trade_net_pnl") is not None:
                raise V103Error("V103_REJECTED_ENTRY_HAS_PNL")
            return "SOURCE_VERIFIED_ENTRY_REJECTED", report["censor_reason"]
        return "OPTION_SOURCE_CENSORED", report.get("censor_reason")
    raise V103Error("V103_UNEXPECTED_ORIGINAL_REPLAY_STATUS")


def chain_months(months, *, calendar_sessions, initial=START):
    """Chain observed sessions; no lookahead, guessed source or recovery."""
    cash = money(initial)
    if cash <= 0:
        raise V103Error("V103_NONPOSITIVE_STARTING_ACCOUNT")
    if calendar_sessions != sorted(set(calendar_sessions)):
        raise V103Error("V103_CALENDAR_DUPLICATE_OR_ORDER_INVALID")
    day_lookup = {}
    ancestry = []
    for month in months:
        if not isinstance(month, dict) or month.get("month") is None:
            raise V103Error("V103_MONTH_RECORD_INVALID")
        report = month.get("original_v65")
        if report is not None:
            if not verify(report) or report.get("contract") != V65:
                raise V103Error("V103_V65_MONTH_SIGNED_PARENT_INVALID")
            ancestry.append(report["fingerprint"])
            for row in report["session_reports"]:
                day = date.fromisoformat(row["session"])
                if day in day_lookup:
                    raise V103Error("V103_DUPLICATE_SOURCE_SESSION")
                day_lookup[day] = row
        else:
            ancestry.append(None)
    censored = False
    first_block = None
    events = []
    reasons = Counter()
    week = Counter()
    month_pnl = Counter()
    closed = 0
    closed_known_pnl = Decimal("0")
    peak = cash
    maximum_flat_drawdown = Decimal("0")
    for day in calendar_sessions:
        key = day.isoformat()
        if day in day_lookup:
            verdict, detail = classify(day_lookup[day], day)
            source_parent = day_lookup[day]["fingerprint"]
        else:
            relevant = next((m for m in months if m["month"] == key[:7]), None)
            if relevant is None:
                raise V103Error("V103_UNREPORTED_MONTH_IN_CALENDAR")
            if day in relevant.get("excluded_early_closes", []):
                verdict, detail = "EARLY_CLOSE_EXCLUDED", "ORIGINAL_1530_TIME_EXIT_NOT_MARKET_OPEN"
            elif day.weekday() not in (0, 2, 4):
                verdict, detail = "POLICY_EXCLUDED", "MWF_ONLY"
            else:
                verdict, detail = "STOCK_SOURCE_CENSORED", relevant.get("status")
            source_parent = None
        reasons[verdict] += 1
        before = str(cash) if not censored else None
        account_step = None
        if verdict in ("STOCK_SOURCE_CENSORED", "OPTION_SOURCE_CENSORED",
                       "UNKNOWN_EXIT_CENSORED") and not censored:
            censored = True
            first_block = {"session": key, "reason": verdict, "detail": detail}
        elif not censored and verdict == "CLOSED_QUOTE_REFERENCE":
            debit = money(detail["debit"])
            profit = money(detail["net_pnl"])
            if debit > cash:
                verdict = "ACCOUNT_CASH_LIMIT_REJECTED"
                reasons["CLOSED_QUOTE_REFERENCE"] -= 1
                reasons[verdict] += 1
                account_step = "0.00"
            else:
                cash += profit
                account_step = str(profit)
                closed += 1
                closed_known_pnl += profit
                weekid = day.isocalendar()
                week[f"{weekid.year}-W{weekid.week:02d}"] += profit
                month_pnl[key[:7]] += profit
                peak = max(peak, cash)
                maximum_flat_drawdown = max(maximum_flat_drawdown, peak-cash)
        elif not censored and verdict in ("POLICY_EXCLUDED", "EARLY_CLOSE_EXCLUDED",
                "VERIFIED_NO_SIGNAL", "SOURCE_VERIFIED_ENTRY_REJECTED"):
            account_step = "0.00"
        events.append(signed({
            "session": key, "disposition": verdict, "reason": detail,
            "original_v65_session_sha": source_parent,
            "cash_before_if_known": before,
            "account_step_quote_pnl_if_known": account_step,
            "cash_after_if_known": str(cash) if not censored else None,
            "earlier_source_blocked_account": censored,
            "broker_fill_verified": False,
        }))
    if not censored and cash - money(initial) != closed_known_pnl:
        raise V103Error("V103_CLOSED_CASH_ACCOUNT_RECONCILIATION_FAILED")
    return signed({
        "contract": CONTRACT, "start": calendar_sessions[0].isoformat() if calendar_sessions else None,
        "end": calendar_sessions[-1].isoformat() if calendar_sessions else None,
        "initial_cash_usd": str(money(initial)),
        "terminal_equity_if_source_complete_usd": str(cash) if not censored else None,
        "first_account_censor": first_block,
        "cash_pnl_if_entire_window_complete_usd": str(closed_known_pnl) if not censored else None,
        "pre_censor_flat_closes": closed,
        "pre_censor_closed_quote_pnl_usd_not_full_window": str(closed_known_pnl),
        "flat_to_flat_pre_censor_drawdown_usd": str(maximum_flat_drawdown),
        "verified_stressed_week_pnl_pre_censor_usd": {k: str(v) for k, v in sorted(week.items())},
        "verified_stressed_month_pnl_pre_censor_usd": {k: str(v) for k, v in sorted(month_pnl.items())},
        "dispositions": dict(sorted(reasons.items())),
        "months_original_v65_shas": ancestry,
        "all_sessions": events,
        "historical_first_publication_qualified": False,
        "not_first_tick_orb": True,
        "no_paid_provider_calls": True,
        "actual_broker_orders": 0, "actual_broker_fills": 0,
        "profitable_live_strategy_proven": False,
    })
