from __future__ import annotations

"""V55 independent completed-minute SPY 0DTE breakout quote-reference experiment.

This is NOT the published first-tick ORB, a PIT publication certification, a
broker execution simulator, or validated alpha. Uses an explicitly versioned
completed-bar close signal and exact original option quote tape, with all
unknown observations censored rather than filled by interpolation.
"""

from bisect import bisect_left
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_HALF_UP
import re
import time as _time
from zoneinfo import ZoneInfo

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

CONTRACT = "atlas-v55-spy-0dte-closed-minute-option-quote-replay-v1"
STRATEGY = "atlas-spy-0dte-completed-minute-close-orb-development-v1"
ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
FEE = Decimal("0.65")
CAP = Decimal("500")
SOURCE_STATES = {"CACHE_HIT", "FETCHED_AND_ARCHIVED"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class V55Error(ValueError):
    pass


def _dec(value):
    try:
        v = Decimal(str(value))
    except (ValueError, InvalidOperation, TypeError) as exc:
        raise V55Error("NONNUMERIC_MARKET_PRICE") from exc
    if not v.is_finite() or v <= 0:
        raise V55Error("NONPOSITIVE_MARKET_PRICE")
    return v


def _at(value):
    if isinstance(value, datetime):
        stamp = value
    else:
        try:
            stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (ValueError, TypeError) as exc:
            raise V55Error("QUOTE_TIMESTAMP_UNPARSEABLE") from exc
    if stamp.utcoffset() is None:
        raise V55Error("QUOTE_TIMESTAMP_TIMEZONE_MISSING")
    return stamp.astimezone(ET)


def _usd(value):
    return value.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)


def _signed(result):
    return {**result, "fingerprint": _fingerprint(result)}


def closed_bar_signal(rows, *, session: date, source_sha256: str, source_unit_id: str):
    """Select the FIRST fully CLOSED bar outside the opening range.

    Do not use the intraminute high to choose entry timing or a strike.
    Source-time publication is assumed >= minute end, NOT independently proved.
    """
    if not HEX64.fullmatch(str(source_sha256)):
        raise V55Error("NATIVE_SOURCE_SHA_MISSING")
    start = datetime.combine(session, time(9, 30), tzinfo=ET)
    timeline = {}
    for row in rows:
        t = _at(row["timestamp_utc"])
        if row.get("symbol") != "SPY" or t.date() != session:
            raise V55Error("NATIVE_BAR_SYMBOL_OR_DATE_MISMATCH")
        if t.second or t.microsecond or t in timeline:
            raise V55Error("NATIVE_BAR_CLOCK_DUPLICATED_OR_UNALIGNED")
        prices = tuple(_dec(row[k]) for k in ("open", "high", "low", "close"))
        op, hi, lo, cl = prices
        if not lo <= min(op, cl) <= max(op, cl) <= hi:
            raise V55Error("NATIVE_BAR_OHLC_INVALID")
        timeline[t] = prices
    result = {
        "contract": CONTRACT, "strategy_version": STRATEGY,
        "session": session.isoformat(), "source_unit_id": source_unit_id,
        "native_canonical_sha256": source_sha256,
        "observed_bars": len(rows), "opening_high": None, "opening_low": None,
        "decision_at_et": None, "selected_contract": None,
        "close_at_decision": None, "signal_status": None,
        "reason_codes": [], "first_publication_independently_proven": False,
        "first_breakout_tick_proven": False,
    }
    if session.weekday() not in (0, 2, 4):
        result["signal_status"] = "WEEKDAY_OUTSIDE_MWF_VERSION"
        result["reason_codes"] = ["PUBLISHED_WEEKDAY_FILTER_RETAINED_FOR_NEW_VARIANT"]
        return _signed(result)
    opening = [timeline.get(start + timedelta(minutes=i)) for i in range(5)]
    if any(row is None for row in opening):
        result["signal_status"] = "MISSING_OPENING_MINUTE"
        result["reason_codes"] = ["OPENING_RANGE_SOURCE_INCOMPLETE"]
        return _signed(result)
    upper = max(row[1] for row in opening)
    lower = min(row[2] for row in opening)
    result["opening_high"], result["opening_low"] = str(upper), str(lower)
    for minute in range(5, 359):
        t = start + timedelta(minutes=minute)
        bar = timeline.get(t)
        if bar is None:
            result["signal_status"] = "MISSING_MINUTE_BEFORE_SIGNAL"
            result["reason_codes"] = ["CANNOT_PROVE_FIRST_COMPLETED_BAR_BREAKOUT"]
            break
        close = bar[3]
        right = "call" if close > upper else "put" if close < lower else None
        if right:
            strike = close.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            result["decision_at_et"] = (t + timedelta(minutes=1, seconds=1)).isoformat()
            result["close_at_decision"] = str(close)
            result["selected_contract"] = {
                "symbol": "SPY", "date_et": session.isoformat(),
                "expiration": session.isoformat(), "strike": str(strike),
                "right": right,
            }
            result["signal_status"] = "COMPLETED_BAR_BREAKOUT_DEVELOPMENT"
            result["reason_codes"] = [
                "FIRST_COMPLETED_CANDLE_CLOSE_OUTSIDE_FIVE_MINUTE_OPENING_RANGE",
                "ONE_SECOND_AFTER_BAR_CLOSE_AVAILABILITY_ASSUMED_NOT_PROVEN",
                "NOT_ORIGINAL_FIRST_TICK_ORB",
            ]
            break
    else:
        result["signal_status"] = "NO_COMPLETED_BAR_CLOSE_BREAKOUT"
        result["reason_codes"] = ["NO_CLOSE_OUTSIDE_OPENING_RANGE_BEFORE_15_30"]
    return _signed(result)


def _read_timestamp(row, day):
    for key in ("timestamp_et", "timestamp", "datetime", "timestamp_utc"):
        if row.get(key) is not None:
            try:
                return _at(row[key])
            except V55Error as exc:
                # ThetaData option history timestamps use the requested ET
                # session clock; a serialized naive 'timestamp' is treated
                # as ET only in this explicitly unverified research variant.
                # Never reinterpret an explicitly UTC column as local ET.
                if str(exc) != "QUOTE_TIMESTAMP_TIMEZONE_MISSING" or key not in ("timestamp", "timestamp_et"):
                    raise
                stamp = datetime.fromisoformat(str(row[key]))
                return stamp.replace(tzinfo=ET)
    if row.get("ms_of_day") is not None:
        raw = row["ms_of_day"]
        try:
            val = Decimal(str(raw))
        except (TypeError, ValueError, InvalidOperation) as exc:
            raise V55Error("BAD_MS_OF_DAY") from exc
        if isinstance(raw, bool) or not val.is_finite() or val != int(val) or not 0 <= val < 86400000:
            raise V55Error("BAD_MS_OF_DAY")
        return datetime.combine(day, time(0, 0), tzinfo=ET) + timedelta(milliseconds=int(val))
    raise V55Error("NO_OBSERVATION_TIMESTAMP")


def _quote(row, *, day, contract):
    stamp = _read_timestamp(row, day)
    if stamp.date() != day:
        raise V55Error("OPTION_QUOTE_OTHER_SESSION")
    for name, expected in (
        ("symbol", "SPY"), ("expiration", day.isoformat()),
        ("right", contract["right"])
    ):
        if row.get(name) is not None and str(row[name]).lower() != str(expected).lower():
            raise V55Error("OPTION_QUOTE_CONTRACT_MISMATCH")
    if row.get("strike") is not None and _dec(row["strike"]) != _dec(contract["strike"]):
        raise V55Error("OPTION_QUOTE_STRIKE_MISMATCH")
    try:
        bid = _dec(row["bid"])
        ask = _dec(row["ask"])
        bid_size = int(row["bid_size"])
        ask_size = int(row["ask_size"])
    except (KeyError, ValueError, TypeError, V55Error) as exc:
        raise V55Error("MISSING_OR_INVALID_BID_ASK_SIZE") from exc
    if (bid_size <= 0 or ask_size <= 0
            or bid_size != float(row["bid_size"])
            or ask_size != float(row["ask_size"])
            or bid > ask):
        raise V55Error("EMPTY_SIZE_OR_CROSSED_QUOTE")
    if (ask - bid) / ((ask + bid) / 2) > Decimal(".15"):
        raise V55Error("QUOTE_SPREAD_ABOVE_15_PERCENT")
    return {
        "timestamp_et": stamp.isoformat(), "bid": str(bid), "ask": str(ask),
        "bid_size": bid_size, "ask_size": ask_size,
    }


def replay_source(signal, source, *, starting_cash="25000", lag_seconds=1,
                  max_adverse_pct="1", progress=None):
    """Research quote-reference replay: trade assumptions are explicitly labeled.

    Every supplied quote observation generates a review or a rejection event.
    Refuses missing intervals >60s or absent/invalid last liquidation quote.
    """
    if lag_seconds not in (1, 3) or str(max_adverse_pct) not in ("0.5", "1", "2"):
        raise V55Error("UNREGISTERED_LATENCY_OR_DRIFT_POLICY")
    if signal.get("fingerprint") != _fingerprint({k:v for k,v in signal.items() if k!="fingerprint"}):
        raise V55Error("SIGNAL_FINGERPRINT_CHANGED")
    cash = _usd(_dec(starting_cash))
    events = [{"type": "OPPORTUNITY", "signal": signal}]
    report = {
        "contract": CONTRACT, "strategy_version": STRATEGY,
        "session": signal["session"], "starting_cash": str(cash),
        "source_status": source.get("status") if isinstance(source, dict) else "SOURCE_NOT_REQUESTED",
        "source_query_id": source.get("query_id") if isinstance(source, dict) else None,
        "source_sha256": source.get("source_sha256") if isinstance(source, dict) else None,
        "signal": signal, "events": events, "status": None,
        "entry_debit": None, "exit_credit": None, "trade_net_pnl": None,
        "terminal_equity_if_resolved": None, "censor_reason": None,
        "actual_fills": 0, "publication_verified": False, "valid_historical_alpha": False,
        "assumed_1s_bar_close_publication_lag": True,
        "quote_reference_not_broker_execution": True,
        "naive_provider_history_timestamp_interpreted_as_ET_if_present": True,
        "policy": {"max_premium_usd": "500", "take_profit_option_pct": "100",
                   "stop_option_pct": "-50", "time_exit_et": "15:30",
                   "lag_seconds": lag_seconds, "max_adverse_pct": str(max_adverse_pct)}
    }
    def finish(status, reason=None):
        report["status"] = status
        report["censor_reason"] = reason
        if status in ("NO_SIGNAL", "NO_ENTRY"):
            report["terminal_equity_if_resolved"] = str(cash)
        events.append({"type": "CLOSEOUT", "status": status, "reason": reason,
                       "terminal_equity": report["terminal_equity_if_resolved"]})
        return _signed(report)
    if signal["selected_contract"] is None:
        return finish("NO_SIGNAL", signal["signal_status"])
    if not isinstance(source, dict) or source.get("status") not in SOURCE_STATES:
        return finish("NO_ENTRY", "OPTION_SOURCE_MISSING_OR_UNQUALIFIED")
    if not HEX64.fullmatch(str(source.get("source_sha256"))) or not source.get("query_id"):
        return finish("NO_ENTRY", "OPTION_SOURCE_SHA_OR_QUERY_MISSING")
    q = source.get("exact_requirement", {})
    required = q.get("kwargs", {})
    contract = signal["selected_contract"]
    if (q.get("method") != "option_history_exact_quote_tape"
            or any(str(required.get(k)) != str(v) for k,v in contract.items())
            or required.get("interval") not in ("1s", "tick")):
        return finish("NO_ENTRY", "OPTION_SOURCE_EXACT_IDENTITY_INVALID")
    day = date.fromisoformat(signal["session"])
    rows = source["source_rows"]
    if not rows:
        return finish("NO_ENTRY", "OPTION_SOURCE_EMPTY")
    # Inspect source observation CLOCKS only up front. Future prices must not
    # be used to reject or select an earlier entry.
    if progress:
        progress(f"STAGE_START parse_quote_observation_clocks rows={len(rows)}")
    stamps = []
    milestone = 10
    phase_started = _time.monotonic()
    for i,row in enumerate(rows):
        try:
            stamps.append(_read_timestamp(row, day))
        except (V55Error, KeyError, TypeError) as exc:
            events.append({"type": "SOURCE_CLOCK_REJECTION", "row": i, "reason": str(exc)})
            return finish("NO_ENTRY", "SOURCE_OBSERVATION_CLOCK_UNQUALIFIED")
        while progress and milestone <= 100 and 100*(i+1) >= milestone*len(rows):
            elapsed = max(_time.monotonic()-phase_started,.001)
            rate = (i+1)/elapsed
            eta = (len(rows)-i-1)/rate
            progress(f"PROGRESS_{milestone}PCT phase=parse_quote_observation_clocks"
                     f" completed={i+1}/{len(rows)} percent={100*(i+1)/len(rows):.1f}"
                     f" last_row={i} elapsed={elapsed:.1f}s"
                     f" throughput_rows_s={rate:.1f} eta_rough_s={eta:.1f}")
            milestone += 10
    if stamps != sorted(stamps) or len(set(stamps)) != len(stamps):
        return finish("NO_ENTRY", "AMBIGUOUS_OR_OUT_OF_ORDER_QUOTE_TAPE")
    if progress:
        progress(f"STAGE_PASS parse_quote_observation_clocks rows={len(rows)}")
    decision = _at(signal["decision_at_et"])
    idx = bisect_left(stamps, decision)
    if idx >= len(rows):
        return finish("NO_ENTRY", "NO_QUOTE_AFTER_BAR_CLOSE_DECISION")
    try:
        order = _quote(rows[idx], day=day, contract=contract)
    except (V55Error, KeyError, TypeError) as exc:
        events.append({"type": "ENTRY_QUOTE_REJECTION", "row": idx, "reason": str(exc)})
        return finish("NO_ENTRY", "FIRST_ORDER_QUOTE_NOT_ELIGIBLE")
    order_at = stamps[idx]
    if (order_at - decision).total_seconds() > 30:
        return finish("NO_ENTRY", "NO_FRESH_QUOTE_FOR_DECISION")
    action_target = order_at + timedelta(seconds=lag_seconds)
    action_idx = bisect_left(stamps, action_target)
    if action_idx >= len(rows) or (stamps[action_idx] - action_target).total_seconds() > 1:
        return finish("NO_ENTRY", "NO_OBSERVED_ACTION_QUOTE_WITHIN_ONE_SECOND")
    try:
        action = _quote(rows[action_idx], day=day, contract=contract)
    except (V55Error, KeyError, TypeError) as exc:
        events.append({"type": "ACTION_QUOTE_REJECTION", "row": action_idx, "reason": str(exc)})
        return finish("NO_ENTRY", "ACTION_QUOTE_NOT_ELIGIBLE")
    change = (_dec(action["ask"]) / _dec(order["ask"]) - 1) * 100
    events.append({"type": "ORDER_ACTION_QUOTE_REFERENCE",
                   "decision_at_et": decision.isoformat(),
                   "order": order, "action": action,
                   "adverse_ask_change_pct": str(max(Decimal(0), change)),
                   "first_publication_verified": False})
    if change > _dec(max_adverse_pct):
        return finish("NO_ENTRY", "ACTION_ASK_PRICE_CHANGE_OVER_LIMIT")
    ask = _dec(action["ask"])
    qty = int((CAP / (ask * 100)).to_integral_value(rounding=ROUND_FLOOR))
    debit = _usd(qty * (ask * 100 + FEE))
    if not qty or debit > cash or qty > action["ask_size"]:
        return finish("NO_ENTRY", "PREMIUM_CAP_CASH_OR_ASK_SIZE_INSUFFICIENT")
    cash -= debit
    report["entry_debit"] = str(debit)
    events.append({"type": "MODELED_ENTRY_QUOTE_REFERENCE",
                   "at_et": action["timestamp_et"], "ask": str(ask),
                   "qty": qty, "debit_plus_entry_fees": str(debit),
                   "cash_after": str(cash), "broker_fill_verified": False})
    last_time = stamps[action_idx]
    last_eligible = action
    if progress:
        progress(f"STAGE_START replay_exit_quote_path rows_remaining={len(rows)-action_idx-1}")
    deadline = datetime.combine(day, time(15,30),tzinfo=ET)
    total_reviews = len(rows) - action_idx - 1
    review_milestone = 10
    review_started = _time.monotonic()
    for i in range(action_idx + 1, len(rows)):
        now = stamps[i]
        if now > deadline:
            break
        if progress:
            completed = i - action_idx
            while review_milestone <= 100 and 100*completed >= review_milestone*max(1,total_reviews):
                elapsed = max(_time.monotonic()-review_started,.001)
                rate = completed/elapsed
                eta = max(0,total_reviews-completed)/rate if rate else 0
                progress(f"PROGRESS_{review_milestone}PCT phase=replay_exit_quote_path"
                         f" completed={completed}/{total_reviews}"
                         f" percent={100*completed/max(1,total_reviews):.1f}"
                         f" elapsed={elapsed:.1f}s throughput_rows_s={rate:.1f}"
                         f" eta_rough_s={eta:.1f} last_row={i}")
                review_milestone += 10
        gap = (now - last_time).total_seconds()
        try:
            current = _quote(rows[i], day=day, contract=contract)
        except (V55Error, KeyError, TypeError) as exc:
            events.append({"type": "EXIT_SOURCE_REJECTION", "row": i,
                           "at_et": now.isoformat(), "reason": str(exc)})
            return finish("UNRESOLVED_POSITION", "UNQUALIFIED_EXIT_QUOTE_PATH")
        bid = _dec(current["bid"])
        reason = ("TAKE_PROFIT_100" if bid >= ask*2 else
                  "STOP_LOSS_50" if bid <= ask/2 else "HOLD")
        ev = {"type": "EXIT_REVIEW", "row": i, "quote": current,
              "observed_gap_seconds": gap, "reason": reason}
        events.append(ev)
        if gap > 60:
            return finish("UNRESOLVED_POSITION", "QUOTE_PATH_GAP_OVER_60_SECONDS")
        if qty > current["bid_size"] and reason != "HOLD":
            return finish("UNRESOLVED_POSITION", "EXIT_BID_SIZE_INSUFFICIENT")
        last_time = now
        last_eligible = current
        if reason != "HOLD":
            if progress:
                progress(f"STAGE_PASS replay_exit_quote_path exit_trigger={reason}"
                         f" reviewed={i-action_idx}/{total_reviews}")
            credit = _usd(qty * (bid*100-FEE))
            report["exit_credit"] = str(credit)
            report["trade_net_pnl"] = str(_usd(credit-debit))
            report["terminal_equity_if_resolved"] = str(_usd(cash+credit))
            events.append({"type": "MODELED_EXIT_QUOTE_REFERENCE",
                           "at_et": now.isoformat(), "exit_reason": reason,
                           "bid": str(bid), "credit_less_exit_fees": str(credit),
                           "account_after": report["terminal_equity_if_resolved"],
                           "broker_fill_verified": False})
            return finish("CLOSED_QUOTE_REFERENCE")
    if progress:
        progress(f"STAGE_PASS replay_exit_quote_path completed_through={last_time.isoformat()}")
    if (deadline-last_time).total_seconds() > 30 or last_time > deadline:
        return finish("UNRESOLVED_POSITION", "NO_FRESH_15_30_QUOTE_FOR_LIQUIDATION")
    bid = _dec(last_eligible["bid"])
    if qty > last_eligible["bid_size"]:
        return finish("UNRESOLVED_POSITION", "TIME_EXIT_BID_SIZE_INSUFFICIENT")
    credit = _usd(qty * (bid*100-FEE))
    report["exit_credit"] = str(credit)
    report["trade_net_pnl"] = str(_usd(credit-debit))
    report["terminal_equity_if_resolved"] = str(_usd(cash+credit))
    events.append({"type": "MODELED_EXIT_QUOTE_REFERENCE",
                   "at_et": deadline.isoformat(), "quote_observed_at": last_time.isoformat(),
                   "exit_reason": "TIME_15_30", "credit_less_exit_fees": str(credit),
                   "broker_fill_verified": False})
    return finish("CLOSED_QUOTE_REFERENCE")
