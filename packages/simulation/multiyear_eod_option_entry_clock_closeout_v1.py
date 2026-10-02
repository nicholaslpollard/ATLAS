from __future__ import annotations

"""Offline closeout for Continuous Exit V2 saturation and EOD option-entry clock drift.

This diagnostic intentionally does not create another exit policy. It consumes only
already accepted immutable local artifacts and answers two bounded questions:

1. Did Continuous Dynamic Exit V2 materially differ from the frozen 3%/5% boundary?
2. How much time/underlying movement elapsed between the stock decision/open context
   and the first accepted historical EOD option entry snapshot?

The result is descriptive research evidence only. It never reselects entries,
contracts, stops, targets or exits and grants no strategy/PAPER/LIVE authority.
"""

from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
import math
import re
import statistics
from typing import Any, Sequence

from packages.core.market_calendar import get_market_calendar
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_native_stock_open_v1 import CONTRACT as NATIVE_CONTRACT
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.simulation.multiyear_continuous_dynamic_exit_v2_option_replay import (
    SCENARIO_CONTRACT as CONTINUOUS_SCENARIO_CONTRACT,
)
from packages.simulation.multiyear_historical_eod_option_account_replay_v1 import (
    SCENARIO_CONTRACT as BASE_SCENARIO_CONTRACT,
)

CONTRACT = "atlas-multiyear-eod-option-entry-clock-closeout-v1"
OUTPUT_REL = "data/options/derived/multiyear_eod_option_entry_clock_closeout_v1"
OCC = re.compile(r"^([A-Z0-9.]+)(\d{6})([CP])(\d{8})$")
STOP_MAX = 0.03
TARGET_MAX = 0.05


class EodOptionEntryClockCloseoutError(ValueError):
    pass


def _aware(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise EodOptionEntryClockCloseoutError(f"{label} must be ISO text")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EodOptionEntryClockCloseoutError(f"{label} invalid ISO timestamp") from exc
    if stamp.tzinfo is None:
        raise EodOptionEntryClockCloseoutError(f"{label} must be timezone-aware")
    return stamp.astimezone(UTC)


def _positive_decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool):
        raise EodOptionEntryClockCloseoutError(f"{label} invalid numeric value")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise EodOptionEntryClockCloseoutError(f"{label} invalid numeric value") from exc
    if not number.is_finite() or number <= 0:
        raise EodOptionEntryClockCloseoutError(f"{label} must be finite and positive")
    return number


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
        raise EodOptionEntryClockCloseoutError("distribution contains non-finite value")

    def quantile(p: float) -> float:
        if len(ordered) == 1:
            return ordered[0]
        position = (len(ordered) - 1) * p
        lo = int(math.floor(position))
        hi = int(math.ceil(position))
        if lo == hi:
            return ordered[lo]
        fraction = position - lo
        return ordered[lo] * (1.0 - fraction) + ordered[hi] * fraction

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


def _moneyness(strike: Decimal, spot: Decimal) -> str:
    if strike == spot:
        return "ATM"
    return "OTM" if strike > spot else "ITM"


def _strike(symbol: object, ticker: str) -> Decimal:
    match = OCC.fullmatch(symbol) if isinstance(symbol, str) else None
    if match is None or match.group(1) != ticker or match.group(3) != "C":
        raise EodOptionEntryClockCloseoutError("CALL OCC identity changed")
    return Decimal(match.group(4)) / Decimal("1000")


def _validate_lineage(
    native: dict[str, Any],
    base: dict[str, Any],
    continuous: dict[str, Any],
) -> int:
    for document, field in (
        (native, "source_fingerprint"),
        (base, "scenario_fingerprint"),
        (continuous, "scenario_fingerprint"),
    ):
        _check_signature(document, field)

    denominator = base.get("original_case_denominator")
    if not isinstance(denominator, int) or denominator < 1:
        raise EodOptionEntryClockCloseoutError("base denominator invalid")
    if (
        native.get("contract") != NATIVE_CONTRACT
        or base.get("contract") != BASE_SCENARIO_CONTRACT
        or continuous.get("contract") != CONTINUOUS_SCENARIO_CONTRACT
        or native.get("case_denominator") != denominator
        or continuous.get("original_case_denominator") != denominator
        or len(native.get("rows", [])) != denominator
        or len(base.get("cases", [])) != denominator
        or len(continuous.get("cases", [])) != denominator
        or base.get("native_source_fingerprint") != native.get("source_fingerprint")
        or continuous.get("base_scenario_fingerprint") != base.get("scenario_fingerprint")
        or native.get("provider_requests") != 0
        or native.get("protected_outcomes_read") != 0
        or base.get("provider_requests") != 0
        or base.get("protected_2026_outcomes_read") != 0
        or base.get("historical_account_pnl_authority") is not False
        or continuous.get("provider_requests") != 0
        or continuous.get("protected_2026_outcomes_read") != 0
        or continuous.get("historical_account_pnl_authority") is not False
        or continuous.get("strategy_evidence_authority") is not False
    ):
        raise EodOptionEntryClockCloseoutError(
            "entry-clock closeout source lineage or authority changed"
        )
    return denominator


def build_eod_option_entry_clock_closeout(
    native: dict[str, Any],
    base: dict[str, Any],
    continuous: dict[str, Any],
) -> dict[str, Any]:
    denominator = _validate_lineage(native, base, continuous)
    native_by_id = {row["case_id"]: row for row in native["rows"]}
    base_by_id = {row["case_id"]: row for row in base["cases"]}
    continuous_by_id = {row["case_id"]: row for row in continuous["cases"]}
    if (
        len(native_by_id) != denominator
        or len(base_by_id) != denominator
        or len(continuous_by_id) != denominator
        or set(native_by_id) != set(base_by_id)
        or set(native_by_id) != set(continuous_by_id)
    ):
        raise EodOptionEntryClockCloseoutError("full case denominator changed")

    entry_ready_ids: list[str] = []
    decision_days: list[date] = []
    entry_days: list[date] = []
    for case_id, base_row in base_by_id.items():
        call = base_row.get("call")
        if not isinstance(call, dict) or call.get("status") != "ENTRY_READY_MODELED_STANDARD_EOD":
            continue
        entry = call.get("entry")
        if not isinstance(entry, dict):
            raise EodOptionEntryClockCloseoutError("entry-ready CALL lost entry")
        decision = _aware(base_row["decision_at_utc"], "stock decision")
        entry_at = _aware(entry["at_utc"], "option entry")
        if entry_at <= decision:
            raise EodOptionEntryClockCloseoutError("option entry is not after stock decision")
        entry_ready_ids.append(case_id)
        decision_days.append(decision.date())
        entry_days.append(date.fromisoformat(entry["session_et"]))

    if not entry_ready_ids:
        raise EodOptionEntryClockCloseoutError("no causal EOD CALL entries available")

    start = min(decision_days)
    end = max(entry_days)
    sessions = get_market_calendar().sessions_in_range(start, end)
    session_index = {session: index for index, session in enumerate(sessions)}

    rows: list[dict[str, Any]] = []
    lag_sessions: list[float] = []
    lag_hours: list[float] = []
    moves: list[float] = []
    absolute_moves: list[float] = []
    moneyness_changes = 0
    threshold_counts = Counter()
    status_counts = Counter()
    initial_moneyness = Counter()
    entry_moneyness = Counter()
    by_year_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)

    stop_values: list[float] = []
    target_values: list[float] = []
    stop_at_max = 0
    target_at_max = 0
    continuous_cases = 0

    for case_id, continuous_row in continuous_by_id.items():
        policy = continuous_row.get("continuous_exit_policy")
        if isinstance(policy, dict):
            stop = float(policy["stop_fraction"])
            target = float(policy["target_fraction"])
            if not math.isfinite(stop) or not math.isfinite(target):
                raise EodOptionEntryClockCloseoutError("continuous policy non-finite")
            stop_values.append(stop)
            target_values.append(target)
            continuous_cases += 1
            stop_at_max += math.isclose(stop, STOP_MAX, rel_tol=0.0, abs_tol=1e-12)
            target_at_max += math.isclose(target, TARGET_MAX, rel_tol=0.0, abs_tol=1e-12)

    for case_id in entry_ready_ids:
        native_row = native_by_id[case_id]
        base_row = base_by_id[case_id]
        continuous_row = continuous_by_id[case_id]
        call = base_row["call"]
        entry = call["entry"]

        if (
            native_row.get("ticker") != base_row.get("ticker")
            or base_row.get("ticker") != continuous_row.get("ticker")
            or native_row.get("signal_session") != base_row.get("signal_session")
            or base_row.get("signal_session") != continuous_row.get("signal_session")
        ):
            raise EodOptionEntryClockCloseoutError("case identity changed")

        raw_open = _positive_decimal(
            native_row.get("raw_underlying_price"), "native raw stock open"
        )
        entry_underlying = _positive_decimal(
            entry.get("underlying_price_same_snapshot"),
            "option-entry same-snapshot underlying",
        )
        strike = _strike(call.get("option_symbol"), base_row["ticker"])
        decision = _aware(base_row["decision_at_utc"], "stock decision")
        entry_at = _aware(entry["at_utc"], "option entry")
        decision_day = decision.date()
        entry_day = date.fromisoformat(entry["session_et"])
        if decision_day not in session_index or entry_day not in session_index:
            raise EodOptionEntryClockCloseoutError("decision/entry session missing from XNYS")
        session_lag = session_index[entry_day] - session_index[decision_day]
        if session_lag < 0:
            raise EodOptionEntryClockCloseoutError("negative option-entry session lag")

        move = float(entry_underlying / raw_open - Decimal("1"))
        abs_move = abs(move)
        hours = (entry_at - decision).total_seconds() / 3600.0
        initial_class = _moneyness(strike, raw_open)
        entry_class = _moneyness(strike, entry_underlying)
        changed = initial_class != entry_class

        lag_sessions.append(float(session_lag))
        lag_hours.append(hours)
        moves.append(move)
        absolute_moves.append(abs_move)
        initial_moneyness[initial_class] += 1
        entry_moneyness[entry_class] += 1
        moneyness_changes += changed
        status = str(continuous_row.get("strategy_aligned_status"))
        status_counts[status] += 1
        for threshold in (0.01, 0.02, 0.03, 0.05):
            if abs_move >= threshold:
                threshold_counts[f"ABS_MOVE_GTE_{int(threshold * 100)}PCT"] += 1
        if move > 0:
            threshold_counts["UNDERLYING_UP_BEFORE_OPTION_ENTRY"] += 1
        elif move < 0:
            threshold_counts["UNDERLYING_DOWN_BEFORE_OPTION_ENTRY"] += 1
        else:
            threshold_counts["UNDERLYING_UNCHANGED_BEFORE_OPTION_ENTRY"] += 1

        row = {
            "case_id": case_id,
            "year": base_row["year"],
            "ticker": base_row["ticker"],
            "policy_id": base_row["policy_id"],
            "signal_session": base_row["signal_session"],
            "stock_decision_at_utc": decision.isoformat(),
            "option_entry_at_utc": entry_at.isoformat(),
            "option_entry_session_et": entry_day.isoformat(),
            "xnys_session_lag": session_lag,
            "elapsed_hours": hours,
            "raw_stock_open": str(raw_open),
            "option_entry_underlying_same_snapshot": str(entry_underlying),
            "underlying_move_before_option_entry": move,
            "absolute_underlying_move_before_option_entry": abs_move,
            "option_symbol": call["option_symbol"],
            "strike": str(strike),
            "moneyness_at_raw_open": initial_class,
            "moneyness_at_option_entry": entry_class,
            "moneyness_changed": changed,
            "continuous_status": status,
            "stock_exit_not_after_option_entry":
                status == "STOCK_EXIT_NOT_AFTER_OPTION_EOD_ENTRY",
        }
        rows.append(row)
        by_year_rows[str(base_row["year"])].append(row)

    def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
        if not items:
            return {
                "causal_eod_call_entries": 0,
                "stock_exit_not_after_option_entry": 0,
                "stock_exit_not_after_option_entry_fraction": None,
                "source_ready_strategy_aligned_round_trips": 0,
                "session_lag": _distribution([]),
                "elapsed_hours": _distribution([]),
                "underlying_move_before_option_entry": _distribution([]),
                "absolute_underlying_move_before_option_entry": _distribution([]),
                "absolute_move_threshold_counts": {},
                "moneyness_at_raw_open": {},
                "moneyness_at_option_entry": {},
                "moneyness_changed": 0,
                "moneyness_changed_fraction": None,
            }
        count = len(items)
        early = sum(item["stock_exit_not_after_option_entry"] for item in items)
        ready = sum(
            item["continuous_status"] == "STRATEGY_ALIGNED_EOD_ROUND_TRIP_SOURCE_READY"
            for item in items
        )
        threshold_summary = {}
        for threshold in (0.01, 0.02, 0.03, 0.05):
            key = f"ABS_MOVE_GTE_{int(threshold * 100)}PCT"
            n = sum(
                item["absolute_underlying_move_before_option_entry"] >= threshold
                for item in items
            )
            threshold_summary[key] = {"count": n, "fraction": n / count}
        initial = Counter(item["moneyness_at_raw_open"] for item in items)
        later = Counter(item["moneyness_at_option_entry"] for item in items)
        changed_n = sum(item["moneyness_changed"] for item in items)
        return {
            "causal_eod_call_entries": count,
            "stock_exit_not_after_option_entry": early,
            "stock_exit_not_after_option_entry_fraction": early / count,
            "source_ready_strategy_aligned_round_trips": ready,
            "session_lag": _distribution([item["xnys_session_lag"] for item in items]),
            "elapsed_hours": _distribution([item["elapsed_hours"] for item in items]),
            "underlying_move_before_option_entry": _distribution(
                [item["underlying_move_before_option_entry"] for item in items]
            ),
            "absolute_underlying_move_before_option_entry": _distribution(
                [item["absolute_underlying_move_before_option_entry"] for item in items]
            ),
            "absolute_move_threshold_counts": threshold_summary,
            "moneyness_at_raw_open": dict(sorted(initial.items())),
            "moneyness_at_option_entry": dict(sorted(later.items())),
            "moneyness_changed": changed_n,
            "moneyness_changed_fraction": changed_n / count,
        }

    overall = summarize(rows)
    report = {
        "contract": CONTRACT,
        "status": "COMPLETE_EOD_OPTION_ENTRY_CLOCK_AND_CONTINUOUS_V2_CLOSEOUT",
        "native_source_fingerprint": native["source_fingerprint"],
        "base_scenario_fingerprint": base["scenario_fingerprint"],
        "continuous_scenario_fingerprint": continuous["scenario_fingerprint"],
        "original_case_denominator": denominator,
        "continuous_v2": {
            "continuous_policy_cases": continuous_cases,
            "stop_distribution": _distribution(stop_values),
            "target_distribution": _distribution(target_values),
            "stop_at_3pct_count": stop_at_max,
            "stop_at_3pct_fraction": stop_at_max / continuous_cases,
            "target_at_5pct_count": target_at_max,
            "target_at_5pct_fraction": target_at_max / continuous_cases,
            "all_targets_at_upper_boundary": target_at_max == continuous_cases,
            "v2_is_exit_parameterizer_not_new_entry_selector": True,
        },
        "entry_clock_translation": overall,
        "entry_clock_status_counts": dict(sorted(status_counts.items())),
        "directional_pre_entry_counts": {
            key: int(threshold_counts[key])
            for key in (
                "UNDERLYING_UP_BEFORE_OPTION_ENTRY",
                "UNDERLYING_DOWN_BEFORE_OPTION_ENTRY",
                "UNDERLYING_UNCHANGED_BEFORE_OPTION_ENTRY",
            )
        },
        "by_year": {
            year: summarize(by_year_rows.get(year, []))
            for year in ("2021", "2022", "2023", "2024", "2025", "2026")
        },
        "provider_requests": 0,
        "protected_2026_outcomes_read": 0,
        "historical_fills_verified": 0,
        "historical_account_pnl_authority": False,
        "strategy_evidence_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "rows": sorted(
            rows,
            key=lambda item: (
                item["option_entry_at_utc"],
                item["case_id"],
            ),
        ),
    }
    report["closeout_fingerprint"] = _fingerprint(report)
    return report
