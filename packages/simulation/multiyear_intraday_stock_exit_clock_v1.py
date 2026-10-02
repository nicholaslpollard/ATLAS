from __future__ import annotations

"""Resolve the stock-side exit clock to accepted one-minute source evidence.

This is a source/clock diagnostic, not a new strategy or option-performance model.

The existing Continuous Dynamic Exit V2 scenario supplies:
- the accepted selected stock cases;
- the frozen per-case STOP/TARGET fractions;
- the daily-session STOP/TARGET/TIME result;
- the already-selected structural CALL symbol.

The accepted Alpaca SIP raw 1-minute lake supplies only the timing/order evidence
inside the daily exit session. No provider GET is permitted here.

For STOP/TARGET cases, the first minute bar touching either boundary determines the
minute-path disposition. If both boundaries are touched in the same one-minute bar,
STOP is chosen adverse-first because sub-minute ordering is not observed. A minute
bar stamped at T is only actionable at T+1 minute because ATLAS minute timestamps are
left-edge interval starts. TIME exits use the official exchange close.

This package deliberately permits the minute path to disagree with the older daily
OHLC adverse-first disposition. Such disagreement is evidence that daily bars were
insufficient to establish event ordering; it is recorded, never silently rewritten.

The report emits generic at-time CALL NBBO quote demands for future source
qualification. It performs zero option-provider requests and grants no historical
fill, strategy, PAPER, or LIVE authority.
"""

from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import math
import re
import statistics
from typing import Any, Iterable, Sequence
from zoneinfo import ZoneInfo

from packages.backtesting.b35_development_source import (
    B35_DEVELOPMENT_SOURCE_CONTRACT,
)
from packages.core.market_calendar import MarketCalendar, get_market_calendar
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_native_stock_open_v1 import CONTRACT as NATIVE_CONTRACT
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.simulation.multiyear_continuous_dynamic_exit_v2_option_replay import (
    SCENARIO_CONTRACT as CONTINUOUS_SCENARIO_CONTRACT,
)
from packages.simulation.multiyear_historical_eod_option_account_replay_v1 import (
    SCENARIO_CONTRACT as BASE_SCENARIO_CONTRACT,
)

CONTRACT = "atlas-multiyear-intraday-stock-exit-clock-v1"
OUTPUT_REL = "data/options/derived/multiyear_intraday_stock_exit_clock_v1"
EASTERN = ZoneInfo("America/New_York")
OCC = re.compile(r"^([A-Z0-9.]+)(\d{6})([CP])(\d{8})$")
EXPECTED_ORIGINAL_DENOMINATOR = 14902
EXPECTED_PRE2026_CALL_POLICY_EXIT_CASES = 9974


class IntradayStockExitClockError(ValueError):
    pass


def _aware(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise IntradayStockExitClockError(f"{label} must be ISO text")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IntradayStockExitClockError(f"{label} invalid ISO timestamp") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise IntradayStockExitClockError(f"{label} must be timezone-aware")
    return stamp.astimezone(UTC)


def _positive_decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool):
        raise IntradayStockExitClockError(f"{label} invalid numeric value")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise IntradayStockExitClockError(f"{label} invalid numeric value") from exc
    if not number.is_finite() or number <= 0:
        raise IntradayStockExitClockError(f"{label} must be finite and positive")
    return number


def _fraction(value: object, label: str) -> Decimal:
    number = _positive_decimal(value, label)
    if number >= 1:
        raise IntradayStockExitClockError(f"{label} must be less than one")
    return number


def _occ_parts(symbol: object, ticker: str) -> dict[str, str]:
    match = OCC.fullmatch(symbol) if isinstance(symbol, str) else None
    if match is None or match.group(1) != ticker or match.group(3) != "C":
        raise IntradayStockExitClockError("selected CALL OCC identity changed")
    compact = match.group(2)
    expiry = date(
        2000 + int(compact[:2]), int(compact[2:4]), int(compact[4:6])
    )
    strike = Decimal(match.group(4)) / Decimal("1000")
    if strike <= 0:
        raise IntradayStockExitClockError("selected CALL strike is not positive")
    return {
        "symbol": ticker,
        "expiration": expiry.isoformat(),
        "strike": str(strike),
        "right": "call",
        "option_symbol": symbol,
    }


def _distribution(values: Sequence[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "min": None,
            "p25": None,
            "median": None,
            "mean": None,
            "p75": None,
            "p90": None,
            "max": None,
        }
    ordered = sorted(float(value) for value in values)
    if any(not math.isfinite(value) for value in ordered):
        raise IntradayStockExitClockError("distribution contains non-finite value")

    def quantile(p: float) -> float:
        if len(ordered) == 1:
            return ordered[0]
        position = (len(ordered) - 1) * p
        lo = int(math.floor(position))
        hi = int(math.ceil(position))
        if lo == hi:
            return ordered[lo]
        weight = position - lo
        return ordered[lo] * (1.0 - weight) + ordered[hi] * weight

    return {
        "count": len(ordered),
        "min": ordered[0],
        "p25": quantile(0.25),
        "median": quantile(0.50),
        "mean": statistics.fmean(ordered),
        "p75": quantile(0.75),
        "p90": quantile(0.90),
        "max": ordered[-1],
    }


def _validate_lineage(
    native: dict[str, Any],
    base: dict[str, Any],
    continuous: dict[str, Any],
) -> None:
    for document, field in (
        (native, "source_fingerprint"),
        (base, "scenario_fingerprint"),
        (continuous, "scenario_fingerprint"),
    ):
        _check_signature(document, field)
    if (
        native.get("contract") != NATIVE_CONTRACT
        or base.get("contract") != BASE_SCENARIO_CONTRACT
        or continuous.get("contract") != CONTINUOUS_SCENARIO_CONTRACT
        or native.get("case_denominator") != EXPECTED_ORIGINAL_DENOMINATOR
        or base.get("original_case_denominator") != EXPECTED_ORIGINAL_DENOMINATOR
        or continuous.get("original_case_denominator") != EXPECTED_ORIGINAL_DENOMINATOR
        or len(native.get("rows", [])) != EXPECTED_ORIGINAL_DENOMINATOR
        or len(base.get("cases", [])) != EXPECTED_ORIGINAL_DENOMINATOR
        or len(continuous.get("cases", [])) != EXPECTED_ORIGINAL_DENOMINATOR
        or base.get("native_source_fingerprint") != native.get("source_fingerprint")
        or continuous.get("base_scenario_fingerprint") != base.get("scenario_fingerprint")
        or native.get("provider_requests") != 0
        or native.get("protected_outcomes_read") != 0
        or base.get("provider_requests") != 0
        or base.get("protected_2026_outcomes_read") != 0
        or continuous.get("provider_requests") != 0
        or continuous.get("protected_2026_outcomes_read") != 0
        or continuous.get("historical_account_pnl_authority") is not False
        or continuous.get("strategy_evidence_authority") is not False
    ):
        raise IntradayStockExitClockError("intraday exit-clock source lineage changed")


def select_intraday_exit_clock_cases(
    native: dict[str, Any],
    base: dict[str, Any],
    continuous: dict[str, Any],
) -> list[dict[str, Any]]:
    """Select every pre-2026 case that already has policy, stock exit and CALL identity.

    This selection does not inspect option prices, future option liquidity, paired
    option P&L or account admission.
    """

    _validate_lineage(native, base, continuous)
    native_by = {row["case_id"]: row for row in native["rows"]}
    base_by = {row["case_id"]: row for row in base["cases"]}
    cont_by = {row["case_id"]: row for row in continuous["cases"]}
    if (
        len(native_by) != EXPECTED_ORIGINAL_DENOMINATOR
        or set(native_by) != set(base_by)
        or set(native_by) != set(cont_by)
    ):
        raise IntradayStockExitClockError("full case mapping changed")

    selected: list[dict[str, Any]] = []
    for case_id in sorted(cont_by):
        row = cont_by[case_id]
        policy = row.get("continuous_exit_policy")
        stock_exit = row.get("stock_exit")
        call = row.get("call")
        if (
            not isinstance(policy, dict)
            or not isinstance(stock_exit, dict)
            or not isinstance(call, dict)
            or int(row["year"]) > 2025
        ):
            continue
        native_row = native_by[case_id]
        base_row = base_by[case_id]
        if (
            row.get("ticker") != native_row.get("ticker")
            or row.get("ticker") != base_row.get("ticker")
            or row.get("signal_session") != native_row.get("signal_session")
            or row.get("signal_session") != base_row.get("signal_session")
            or row.get("decision_at_utc") != base_row.get("decision_at_utc")
        ):
            raise IntradayStockExitClockError("selected case identity changed")
        raw_open = _positive_decimal(
            native_row.get("raw_underlying_price"), "native raw stock open"
        )
        decision = _aware(row["decision_at_utc"], "option decision")
        entry_session = date.fromisoformat(native_row["entry_session"])
        if decision.astimezone(EASTERN).date() != entry_session:
            raise IntradayStockExitClockError("option decision/entry session changed")
        exit_session = date.fromisoformat(stock_exit["session_et"])
        if exit_session < entry_session or exit_session.year > 2025:
            raise IntradayStockExitClockError("pre-2026 stock exit session changed")
        disposition = stock_exit.get("disposition")
        if disposition not in {"STOP", "TARGET", "TIME"}:
            raise IntradayStockExitClockError("stock exit disposition changed")
        occ = _occ_parts(call.get("option_symbol"), row["ticker"])
        selected.append(
            {
                "case_id": case_id,
                "year": str(row["year"]),
                "ticker": row["ticker"],
                "policy_id": row["policy_id"],
                "economic_family_id": row.get("economic_family_id"),
                "signal_session": row["signal_session"],
                "entry_session": entry_session.isoformat(),
                "decision_at_utc": decision.isoformat(),
                "raw_stock_open": str(raw_open),
                "stop_fraction": str(_fraction(policy["stop_fraction"], "stop fraction")),
                "target_fraction": str(
                    _fraction(policy["target_fraction"], "target fraction")
                ),
                "daily_exit_disposition": disposition,
                "daily_exit_session": exit_session.isoformat(),
                "daily_exit_session_offset": stock_exit.get("session_offset"),
                "daily_gap_through_stop": bool(stock_exit.get("gap_through_stop")),
                "daily_gap_through_target": bool(stock_exit.get("gap_through_target")),
                "daily_same_session_collision": bool(
                    stock_exit.get("same_session_collision")
                ),
                **occ,
            }
        )
    if len(selected) != EXPECTED_PRE2026_CALL_POLICY_EXIT_CASES:
        raise IntradayStockExitClockError(
            "pre-2026 CALL/policy/stock-exit denominator changed: "
            f"{len(selected)} != {EXPECTED_PRE2026_CALL_POLICY_EXIT_CASES}"
        )
    return selected


def minute_source_requirements(
    cases: Iterable[dict[str, Any]],
) -> dict[tuple[int, int], dict[str, set[str]]]:
    """Return only STOP/TARGET exit-session symbol/date requirements.

    TIME exits are resolved from the official exchange close and do not require a
    minute file merely to rediscover that close.
    """

    result: dict[tuple[int, int], dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for case in cases:
        if case["daily_exit_disposition"] == "TIME":
            continue
        session = date.fromisoformat(case["daily_exit_session"])
        result[(session.year, session.month)][case["ticker"]].add(session.isoformat())
    return {
        key: {symbol: set(days) for symbol, days in values.items()}
        for key, values in result.items()
    }


def _bar_decimal(bar: dict[str, Any], name: str) -> Decimal:
    return _positive_decimal(bar.get(name), f"minute {name}")


def _bar_timestamp(bar: dict[str, Any]) -> datetime:
    value = bar.get("timestamp_utc")
    if isinstance(value, datetime):
        stamp = value
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise IntradayStockExitClockError("minute timestamp must be aware")
        return stamp.astimezone(UTC)
    return _aware(value, "minute timestamp")


def _quote_descriptor(
    *,
    case: dict[str, Any],
    at_utc: datetime,
    role: str,
) -> dict[str, Any]:
    local = at_utc.astimezone(EASTERN)
    payload = {
        "request_type": "AT_TIME_NBBO_OPTION_QUOTE",
        "option_symbol": case["option_symbol"],
        "symbol": case["symbol"],
        "expiration": case["expiration"],
        "strike": case["strike"],
        "right": case["right"],
        "date_et": local.date().isoformat(),
        "time_of_day_et": local.strftime("%H:%M:%S.000"),
    }
    return {
        **payload,
        "role": role,
        "query_fingerprint": _fingerprint(payload),
    }


def resolve_intraday_exit_case(
    case: dict[str, Any],
    bars: Sequence[dict[str, Any]],
    *,
    calendar: MarketCalendar | None = None,
) -> dict[str, Any]:
    calendar = calendar or get_market_calendar()
    decision = _aware(case["decision_at_utc"], "option decision")
    exit_session = date.fromisoformat(case["daily_exit_session"])
    open_utc, close_utc = calendar.regular_open_close(exit_session)
    entry_price = _positive_decimal(case["raw_stock_open"], "raw stock open")
    stop_price = entry_price * (Decimal("1") - _fraction(case["stop_fraction"], "stop"))
    target_price = entry_price * (
        Decimal("1") + _fraction(case["target_fraction"], "target")
    )
    daily_disposition = case["daily_exit_disposition"]

    event_stamp: datetime | None = None
    action_at: datetime | None = None
    minute_disposition: str | None = None
    collision = False
    gap_through = False
    trigger_bar: dict[str, str] | None = None

    if daily_disposition == "TIME":
        minute_disposition = "TIME"
        event_stamp = close_utc
        action_at = close_utc
    else:
        previous: datetime | None = None
        for bar in sorted(bars, key=_bar_timestamp):
            stamp = _bar_timestamp(bar)
            if stamp < open_utc or stamp >= close_utc:
                raise IntradayStockExitClockError("non-regular minute supplied")
            if stamp.astimezone(EASTERN).date() != exit_session:
                raise IntradayStockExitClockError("minute row session/date mismatch")
            if previous is not None and stamp <= previous:
                raise IntradayStockExitClockError("minute rows are not strictly increasing")
            previous = stamp
            open_px = _bar_decimal(bar, "open")
            high = _bar_decimal(bar, "high")
            low = _bar_decimal(bar, "low")
            close = _bar_decimal(bar, "close")
            if low > high or high < max(open_px, close) or low > min(open_px, close):
                raise IntradayStockExitClockError("invalid minute OHLC geometry")

            if open_px <= stop_price:
                minute_disposition = "STOP"
                gap_through = True
            elif open_px >= target_price:
                minute_disposition = "TARGET"
                gap_through = True
            else:
                stop_hit = low <= stop_price
                target_hit = high >= target_price
                if stop_hit and target_hit:
                    minute_disposition = "STOP"
                    collision = True
                elif stop_hit:
                    minute_disposition = "STOP"
                elif target_hit:
                    minute_disposition = "TARGET"
            if minute_disposition is not None:
                event_stamp = stamp
                action_at = min(stamp + timedelta(minutes=1), close_utc)
                trigger_bar = {
                    "timestamp_utc": stamp.isoformat(),
                    "open": str(open_px),
                    "high": str(high),
                    "low": str(low),
                    "close": str(close),
                }
                break

    if minute_disposition is None or action_at is None or event_stamp is None:
        status = "MINUTE_TRIGGER_NOT_FOUND_ON_DAILY_EXIT_SESSION"
        expression_ready = False
    else:
        expression_ready = action_at > decision
        if not expression_ready:
            status = "STOCK_EXIT_AT_OR_BEFORE_OPTION_DECISION"
        elif minute_disposition != daily_disposition:
            status = "MINUTE_PATH_REORDERS_DAILY_EXIT"
        else:
            status = "INTRADAY_EXIT_CLOCK_READY"

    entry_quote = (
        _quote_descriptor(case=case, at_utc=decision, role="ENTRY")
        if expression_ready
        else None
    )
    exit_quote = (
        _quote_descriptor(case=case, at_utc=action_at, role="EXIT")
        if expression_ready and action_at is not None
        else None
    )
    elapsed_minutes = (
        (action_at - decision).total_seconds() / 60.0
        if action_at is not None
        else None
    )
    return {
        "case_id": case["case_id"],
        "year": case["year"],
        "ticker": case["ticker"],
        "policy_id": case["policy_id"],
        "economic_family_id": case.get("economic_family_id"),
        "signal_session": case["signal_session"],
        "entry_session": case["entry_session"],
        "decision_at_utc": decision.isoformat(),
        "raw_stock_open": case["raw_stock_open"],
        "stop_fraction": case["stop_fraction"],
        "target_fraction": case["target_fraction"],
        "stop_price": str(stop_price),
        "target_price": str(target_price),
        "option_symbol": case["option_symbol"],
        "daily_exit_disposition": daily_disposition,
        "daily_exit_session": case["daily_exit_session"],
        "daily_exit_session_offset": case["daily_exit_session_offset"],
        "minute_exit_disposition": minute_disposition,
        "minute_event_stamp_utc": (
            event_stamp.isoformat() if event_stamp is not None else None
        ),
        "causal_exit_action_at_utc": (
            action_at.isoformat() if action_at is not None else None
        ),
        "minutes_after_option_decision": elapsed_minutes,
        "daily_vs_minute_disposition_changed": (
            minute_disposition is not None and minute_disposition != daily_disposition
        ),
        "minute_same_bar_collision_adverse_first": collision,
        "minute_gap_through_boundary": gap_through,
        "trigger_bar": trigger_bar,
        "option_expression_clock_ready": expression_ready,
        "status": status,
        "entry_quote_demand": entry_quote,
        "exit_quote_demand": exit_quote,
    }


def _deduplicate_quote_demands(
    rows: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        for field in ("entry_quote_demand", "exit_quote_demand"):
            item = row.get(field)
            if not isinstance(item, dict):
                continue
            fp = item["query_fingerprint"]
            base = {k: v for k, v in item.items() if k not in {"role"}}
            existing = grouped.get(fp)
            if existing is None:
                grouped[fp] = {
                    **base,
                    "roles": [item["role"]],
                    "member_case_ids": [row["case_id"]],
                }
            else:
                existing["roles"].append(item["role"])
                existing["member_case_ids"].append(row["case_id"])
    for value in grouped.values():
        value["roles"] = sorted(set(value["roles"]))
        value["member_case_ids"] = sorted(set(value["member_case_ids"]))
        value["member_case_count"] = len(value["member_case_ids"])
    return sorted(
        grouped.values(),
        key=lambda item: (
            item["date_et"],
            item["time_of_day_et"],
            item["option_symbol"],
            item["query_fingerprint"],
        ),
    )


def build_intraday_exit_clock_report(
    *,
    native: dict[str, Any],
    base: dict[str, Any],
    continuous: dict[str, Any],
    source_metadata: dict[str, Any],
    resolved_rows: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    _validate_lineage(native, base, continuous)
    rows = sorted(
        (dict(row) for row in resolved_rows),
        key=lambda row: (row["decision_at_utc"], row["case_id"]),
    )
    if len(rows) != EXPECTED_PRE2026_CALL_POLICY_EXIT_CASES:
        raise IntradayStockExitClockError("resolved intraday case denominator changed")
    if len({row["case_id"] for row in rows}) != len(rows):
        raise IntradayStockExitClockError("duplicate resolved intraday case")

    statuses = Counter(row["status"] for row in rows)
    daily_dispositions = Counter(row["daily_exit_disposition"] for row in rows)
    minute_dispositions = Counter(
        str(row["minute_exit_disposition"])
        for row in rows
        if row["minute_exit_disposition"] is not None
    )
    changed = sum(row["daily_vs_minute_disposition_changed"] for row in rows)
    clock_ready = sum(row["option_expression_clock_ready"] for row in rows)
    before_decision = statuses["STOCK_EXIT_AT_OR_BEFORE_OPTION_DECISION"]
    elapsed = [
        float(row["minutes_after_option_decision"])
        for row in rows
        if row["option_expression_clock_ready"]
        and row["minutes_after_option_decision"] is not None
    ]

    by_year: dict[str, dict[str, Any]] = {}
    by_policy: dict[str, dict[str, Any]] = {}
    for label, getter, target in (
        ("year", lambda row: row["year"], by_year),
        ("policy", lambda row: row["policy_id"], by_policy),
    ):
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            groups[str(getter(row))].append(row)
        for key, group in sorted(groups.items()):
            target[key] = {
                "cases": len(group),
                "clock_ready": sum(
                    row["option_expression_clock_ready"] for row in group
                ),
                "exit_at_or_before_0935": sum(
                    row["status"] == "STOCK_EXIT_AT_OR_BEFORE_OPTION_DECISION"
                    for row in group
                ),
                "daily_vs_minute_disposition_changed": sum(
                    row["daily_vs_minute_disposition_changed"] for row in group
                ),
                "daily_dispositions": dict(
                    sorted(Counter(row["daily_exit_disposition"] for row in group).items())
                ),
                "minute_dispositions": dict(
                    sorted(
                        Counter(
                            str(row["minute_exit_disposition"])
                            for row in group
                            if row["minute_exit_disposition"] is not None
                        ).items()
                    )
                ),
                "statuses": dict(sorted(Counter(row["status"] for row in group).items())),
            }

    demands = _deduplicate_quote_demands(rows)
    entry_members = sum(
        row["entry_quote_demand"] is not None for row in rows
    )
    exit_members = sum(row["exit_quote_demand"] is not None for row in rows)
    report = {
        "contract": CONTRACT,
        "status": "COMPLETE_INTRADAY_STOCK_EXIT_CLOCK_AND_OPTION_QUOTE_DEMAND_PLAN",
        "native_source_fingerprint": native["source_fingerprint"],
        "base_scenario_fingerprint": base["scenario_fingerprint"],
        "continuous_scenario_fingerprint": continuous["scenario_fingerprint"],
        "source_metadata": dict(source_metadata),
        "original_case_denominator": EXPECTED_ORIGINAL_DENOMINATOR,
        "pre2026_call_policy_stock_exit_cases": len(rows),
        "clock_ready_cases": clock_ready,
        "clock_ready_fraction": clock_ready / len(rows),
        "stock_exit_at_or_before_option_decision": before_decision,
        "stock_exit_at_or_before_option_decision_fraction": before_decision / len(rows),
        "daily_vs_minute_disposition_changed": changed,
        "daily_vs_minute_disposition_changed_fraction": changed / len(rows),
        "daily_dispositions": dict(sorted(daily_dispositions.items())),
        "minute_dispositions": dict(sorted(minute_dispositions.items())),
        "statuses": dict(sorted(statuses.items())),
        "minutes_after_option_decision": _distribution(elapsed),
        "by_year": by_year,
        "by_policy": by_policy,
        "option_quote_demand": {
            "entry_case_members": entry_members,
            "exit_case_members": exit_members,
            "unique_at_time_nbbo_queries": len(demands),
            "selection_uses_option_price_or_future_liquidity": False,
            "query_roles": ["ENTRY", "EXIT"],
            "provider_requests_performed": 0,
            "demands": demands,
        },
        "provider_requests": 0,
        "protected_2026_outcomes_read": 0,
        "historical_fills_verified": 0,
        "historical_account_pnl_authority": False,
        "strategy_evidence_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "rows": rows,
    }
    report["intraday_clock_fingerprint"] = _fingerprint(report)
    return report
