from __future__ import annotations

"""Bind the causal 09:35 stock spot and define provider-agnostic option candidate demand.

The prior structural CALL identity was selected nearest-ATM against the native stock
open while the intended option-expression decision occurs at 09:35 ET. This gate
corrects that remaining clock mismatch without reading any option provider.

For each option-expressible case it binds the last completed accepted Alpaca SIP raw
1-minute stock bar available at the decision instant. A bar stamped T represents
[T,T+1m), so its close becomes available at T+1m. The latest bar with
T+1m <= decision is therefore causal.

The output does NOT reselect a single historical option contract. Instead it emits
provider-agnostic entry candidate-chain demand by underlying/date/decision clock.
A later option-source adapter may acquire a bounded CALL candidate surface up to
75 calendar DTE, after which the existing option-economics/trade-expression layer
can rank eligible contracts. The exact exit quote is necessarily second-stage:
it depends on which contract is selected.

No option price, option outcome, provider request, PAPER or LIVE authority is created.
"""

from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import math
import re
import statistics
from typing import Any, Sequence
from zoneinfo import ZoneInfo

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.simulation.multiyear_intraday_stock_exit_clock_v1 import (
    CONTRACT as INTRADAY_CLOCK_CONTRACT,
)

CONTRACT = "atlas-multiyear-option-decision-spot-v1"
OUTPUT_REL = "data/options/derived/multiyear_option_decision_spot_v1"
EASTERN = ZoneInfo("America/New_York")
OCC = re.compile(r"^([A-Z0-9.]+)(\d{6})([CP])(\d{8})$")
EXPECTED_CASES = 9974
EXPECTED_CLOCK_READY = 9667
EXPECTED_OLD_EXACT_DEMANDS = 18921
MAX_CANDIDATE_DTE = 75


class OptionDecisionSpotError(ValueError):
    pass


def _aware(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise OptionDecisionSpotError(f"{label} must be ISO text")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OptionDecisionSpotError(f"{label} invalid ISO timestamp") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise OptionDecisionSpotError(f"{label} must be timezone-aware")
    return stamp.astimezone(UTC)


def _positive(value: object, label: str) -> Decimal:
    if isinstance(value, bool):
        raise OptionDecisionSpotError(f"{label} invalid numeric value")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise OptionDecisionSpotError(f"{label} invalid numeric value") from exc
    if not number.is_finite() or number <= 0:
        raise OptionDecisionSpotError(f"{label} must be finite and positive")
    return number


def _distribution(values: Sequence[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0, "min": None, "p25": None, "median": None,
            "mean": None, "p75": None, "p90": None, "max": None,
        }
    ordered = sorted(float(value) for value in values)
    if any(not math.isfinite(value) for value in ordered):
        raise OptionDecisionSpotError("distribution contains non-finite value")

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


def _occ(symbol: object, ticker: str) -> tuple[str, Decimal]:
    match = OCC.fullmatch(symbol) if isinstance(symbol, str) else None
    if match is None or match.group(1) != ticker or match.group(3) != "C":
        raise OptionDecisionSpotError("baseline structural CALL identity changed")
    compact = match.group(2)
    expiry = date(
        2000 + int(compact[:2]), int(compact[2:4]), int(compact[4:6])
    )
    strike = Decimal(match.group(4)) / Decimal("1000")
    if strike <= 0:
        raise OptionDecisionSpotError("baseline structural strike invalid")
    return expiry.isoformat(), strike


def _moneyness(strike: Decimal, spot: Decimal) -> str:
    if strike == spot:
        return "ATM"
    return "OTM" if strike > spot else "ITM"


def validate_intraday_clock(report: dict[str, Any]) -> None:
    _check_signature(report, "intraday_clock_fingerprint")
    demand = report.get("option_quote_demand")
    rows = report.get("rows")
    if (
        report.get("contract") != INTRADAY_CLOCK_CONTRACT
        or report.get("pre2026_call_policy_stock_exit_cases") != EXPECTED_CASES
        or report.get("clock_ready_cases") != EXPECTED_CLOCK_READY
        or not isinstance(rows, list)
        or len(rows) != EXPECTED_CASES
        or not isinstance(demand, dict)
        or demand.get("entry_case_members") != EXPECTED_CLOCK_READY
        or demand.get("exit_case_members") != EXPECTED_CLOCK_READY
        or demand.get("unique_at_time_nbbo_queries") != EXPECTED_OLD_EXACT_DEMANDS
        or demand.get("provider_requests_performed") != 0
        or report.get("provider_requests") != 0
        or report.get("protected_2026_outcomes_read") != 0
        or report.get("historical_account_pnl_authority") is not False
        or report.get("strategy_evidence_authority") is not False
    ):
        raise OptionDecisionSpotError(
            "intraday stock-exit clock lineage/authority changed"
        )


def select_decision_spot_cases(report: dict[str, Any]) -> list[dict[str, Any]]:
    validate_intraday_clock(report)
    selected: list[dict[str, Any]] = []
    for row in report["rows"]:
        if not row.get("option_expression_clock_ready"):
            continue
        decision = _aware(row["decision_at_utc"], "option decision")
        local = decision.astimezone(EASTERN)
        if (local.hour, local.minute, local.second, local.microsecond) != (9, 35, 0, 0):
            raise OptionDecisionSpotError("option decision is no longer 09:35 ET")
        if row["entry_session"] != local.date().isoformat():
            raise OptionDecisionSpotError("entry session/09:35 decision date changed")
        expiry, strike = _occ(row["option_symbol"], row["ticker"])
        raw_open = _positive(row["raw_stock_open"], "native raw stock open")
        exit_at = _aware(row["causal_exit_action_at_utc"], "causal stock exit")
        if exit_at <= decision:
            raise OptionDecisionSpotError(
                "clock-ready case no longer exits after option decision"
            )
        selected.append({
            "case_id": row["case_id"],
            "year": str(row["year"]),
            "ticker": row["ticker"],
            "policy_id": row["policy_id"],
            "economic_family_id": row.get("economic_family_id"),
            "signal_session": row["signal_session"],
            "entry_session": row["entry_session"],
            "decision_at_utc": decision.isoformat(),
            "raw_stock_open": str(raw_open),
            "baseline_option_symbol": row["option_symbol"],
            "baseline_expiration": expiry,
            "baseline_strike": str(strike),
            "causal_stock_exit_action_at_utc": exit_at.isoformat(),
            "minute_exit_disposition": row["minute_exit_disposition"],
        })
    if len(selected) != EXPECTED_CLOCK_READY:
        raise OptionDecisionSpotError(
            f"decision-spot denominator changed: {len(selected)} != {EXPECTED_CLOCK_READY}"
        )
    return selected


def minute_source_requirements(
    cases: Sequence[dict[str, Any]],
) -> dict[tuple[int, int], dict[str, set[str]]]:
    result: dict[tuple[int, int], dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for case in cases:
        session = date.fromisoformat(case["entry_session"])
        result[(session.year, session.month)][case["ticker"]].add(
            session.isoformat()
        )
    return {
        key: {symbol: set(days) for symbol, days in values.items()}
        for key, values in result.items()
    }


def resolve_decision_spot(
    case: dict[str, Any],
    bars: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    decision = _aware(case["decision_at_utc"], "option decision")
    entry_session = date.fromisoformat(case["entry_session"])
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    previous: datetime | None = None
    for bar in sorted(bars, key=lambda value: value["timestamp_utc"]):
        stamp = bar["timestamp_utc"]
        if not isinstance(stamp, datetime) or stamp.tzinfo is None:
            raise OptionDecisionSpotError("minute timestamp lost timezone")
        stamp = stamp.astimezone(UTC)
        if previous is not None and stamp <= previous:
            raise OptionDecisionSpotError("minute rows are not strictly increasing")
        previous = stamp
        if stamp.astimezone(EASTERN).date() != entry_session:
            raise OptionDecisionSpotError("entry minute row local date changed")
        available_at = stamp + timedelta(minutes=1)
        if available_at <= decision:
            candidates.append((available_at, bar))
    if not candidates:
        return {
            **case,
            "status": "NO_COMPLETED_REGULAR_MINUTE_AVAILABLE_AT_0935",
            "decision_spot": None,
            "source_bar_timestamp_utc": None,
            "source_available_at_utc": None,
            "source_staleness_seconds": None,
            "raw_open_to_decision_move": None,
            "baseline_moneyness_at_decision": None,
            "baseline_strike_distance_fraction": None,
        }

    available_at, bar = candidates[-1]
    spot = _positive(bar["close"], "decision stock spot")
    raw_open = _positive(case["raw_stock_open"], "native raw stock open")
    strike = _positive(case["baseline_strike"], "baseline strike")
    move = float(spot / raw_open - Decimal("1"))
    distance = float(abs(strike - spot) / spot)
    staleness = (decision - available_at).total_seconds()
    if staleness < 0:
        raise OptionDecisionSpotError("decision stock spot is future information")
    return {
        **case,
        "status": "CAUSAL_0935_DECISION_SPOT_READY",
        "decision_spot": str(spot),
        "source_bar_timestamp_utc": bar["timestamp_utc"].astimezone(UTC).isoformat(),
        "source_available_at_utc": available_at.isoformat(),
        "source_staleness_seconds": staleness,
        "raw_open_to_decision_move": move,
        "baseline_moneyness_at_decision": _moneyness(strike, spot),
        "baseline_strike_distance_fraction": distance,
    }


def _candidate_key(row: dict[str, Any]) -> tuple[str, str, str]:
    decision = _aware(row["decision_at_utc"], "decision")
    local = decision.astimezone(EASTERN)
    return row["ticker"], local.date().isoformat(), local.strftime("%H:%M:%S.%f")[:-3]


def build_decision_spot_report(
    *,
    intraday_clock: dict[str, Any],
    source_metadata: dict[str, Any],
    resolved_rows: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    validate_intraday_clock(intraday_clock)
    rows = sorted(
        (dict(row) for row in resolved_rows),
        key=lambda row: (row["decision_at_utc"], row["case_id"]),
    )
    if len(rows) != EXPECTED_CLOCK_READY:
        raise OptionDecisionSpotError("resolved decision-spot denominator changed")
    if len({row["case_id"] for row in rows}) != len(rows):
        raise OptionDecisionSpotError("duplicate decision-spot case")

    ready = [row for row in rows if row["status"] == "CAUSAL_0935_DECISION_SPOT_READY"]
    missing = len(rows) - len(ready)
    moves = [float(row["raw_open_to_decision_move"]) for row in ready]
    abs_moves = [abs(value) for value in moves]
    distances = [float(row["baseline_strike_distance_fraction"]) for row in ready]
    staleness = [float(row["source_staleness_seconds"]) for row in ready]
    money = Counter(row["baseline_moneyness_at_decision"] for row in ready)

    thresholds: dict[str, dict[str, float | int]] = {}
    for threshold in (0.005, 0.01, 0.02, 0.03, 0.05):
        count = sum(value >= threshold for value in abs_moves)
        thresholds[f"ABS_MOVE_GTE_{threshold:g}"] = {
            "count": count,
            "fraction": count / len(ready) if ready else 0.0,
        }

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in ready:
        groups[_candidate_key(row)].append(row)
    demands: list[dict[str, Any]] = []
    for (ticker, day, clock), members in sorted(groups.items()):
        payload = {
            "request_type": "OPTION_CALL_CANDIDATE_SURFACE_AT_DECISION_CLOCK",
            "symbol": ticker,
            "date_et": day,
            "time_of_day_et": clock,
            "right": "call",
            "max_dte_calendar_days": MAX_CANDIDATE_DTE,
            "expiration_policy": "ALL_EXPIRATIONS_WITHIN_PROVIDER_MAX_DTE",
            "strike_policy": "CANDIDATE_SURFACE_NOT_PRESELECTED_STRIKE",
        }
        demands.append({
            **payload,
            "query_fingerprint": _fingerprint(payload),
            "member_case_ids": sorted(row["case_id"] for row in members),
            "member_case_count": len(members),
        })

    by_year: dict[str, dict[str, Any]] = {}
    for year in range(2021, 2026):
        year_rows = [row for row in rows if row["year"] == str(year)]
        year_ready = [
            row for row in year_rows
            if row["status"] == "CAUSAL_0935_DECISION_SPOT_READY"
        ]
        by_year[str(year)] = {
            "cases": len(year_rows),
            "decision_spot_ready": len(year_ready),
            "missing_decision_spot": len(year_rows) - len(year_ready),
            "absolute_open_to_0935_move": _distribution([
                abs(float(row["raw_open_to_decision_move"])) for row in year_ready
            ]),
            "baseline_moneyness_at_0935": dict(sorted(Counter(
                row["baseline_moneyness_at_decision"] for row in year_ready
            ).items())),
        }

    report = {
        "contract": CONTRACT,
        "status": "COMPLETE_CAUSAL_0935_STOCK_SPOT_AND_OPTION_CANDIDATE_DEMAND",
        "intraday_clock_fingerprint": intraday_clock["intraday_clock_fingerprint"],
        "clock_ready_case_denominator": EXPECTED_CLOCK_READY,
        "decision_spot_ready_cases": len(ready),
        "decision_spot_missing_cases": missing,
        "decision_spot_ready_fraction": len(ready) / len(rows),
        "decision_clock_et": "09:35:00.000",
        "stock_spot_basis":
            "LAST_COMPLETED_ACCEPTED_ALPACA_SIP_RAW_1M_CLOSE_AVAILABLE_AT_DECISION",
        "source_metadata": dict(source_metadata),
        "raw_open_to_0935_move": _distribution(moves),
        "absolute_raw_open_to_0935_move": _distribution(abs_moves),
        "absolute_move_thresholds": thresholds,
        "source_staleness_seconds": _distribution(staleness),
        "baseline_structural_call_at_0935": {
            "moneyness": dict(sorted(money.items())),
            "strike_distance_fraction": _distribution(distances),
            "baseline_symbol_is_final_contract_selection": False,
            "interpretation":
                "retained only as diagnostic; final option contract is selected from causal candidate evidence",
        },
        "candidate_entry_surface_demand": {
            "case_members": len(ready),
            "unique_underlying_date_clock_queries": len(demands),
            "right": "call",
            "max_dte_calendar_days": MAX_CANDIDATE_DTE,
            "single_strike_preselection": False,
            "provider_specific_request_shape_authorized": False,
            "demands": demands,
        },
        "exit_source_stage": {
            "status": "DEFERRED_UNTIL_ENTRY_CONTRACT_SELECTION",
            "exact_exit_clock_already_bound_per_case": True,
            "selected_contract_required_before_exit_quote_query": True,
        },
        "by_year": by_year,
        "provider_requests": 0,
        "option_prices_read": 0,
        "option_outcomes_read": 0,
        "historical_fill_authority": False,
        "historical_account_pnl_authority": False,
        "strategy_evidence_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "rows": rows,
    }
    report["decision_spot_fingerprint"] = _fingerprint(report)
    return report
