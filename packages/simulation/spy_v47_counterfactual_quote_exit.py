from __future__ import annotations

"""V47 exploratory SPY option quote-exit replay, NOT a tradable strategy backtest.

V46 scenarios use hypothetical rates/dividends and non-PIT raw-price returns.
A model LONG is never promoted to a real entry. V47 obtains exact historical
future quote receipts only to test conditional exit-price economics. Source
absence or an unqualified quote is censored, never imputed as a zero exit.
"""

from collections import Counter, defaultdict
from datetime import date, timedelta, datetime
from decimal import Decimal, ROUND_HALF_UP
from statistics import mean, median

from packages.core.market_calendar import get_market_calendar
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_spy_source_admission_v43 import _exact_quote
from packages.strategies.options_native_pilot_v1_contract import MAX_HOLD_SESSIONS
from packages.simulation.spy_v46_provisional_signal import (
    CONTRACT as V46_CONTRACT, EXPECTED_V45_FP, V45_CONTRACT,
)

CONTRACT = "atlas-spy-v47-exploratory-fixed-hold-quote-economics"
EXPECTED_V46_FP = "966a6155d57423cd680a26a84bc5bf85e6d02b1f0f06015037612659ef0cc2f7"
STRATEGY_VERSION = "spy_v47_hypothetical_v46_exits_1_to_5_sessions"
INITIAL_CASH = Decimal("100000.00")
MULTIPLIER = Decimal("100")
PER_LEG_PER_SIDE_FEE = Decimal("0.65")
CAPITAL_FRACTION = Decimal("0.05")
HOLD_DAYS = tuple(range(1, MAX_HOLD_SESSIONS + 1))
ENTRY_STATUS = "TWO_CLOCK_SOURCE_QUALITY_PASSES"
MONEY = Decimal("0.01")


class V47Error(ValueError):
    pass


def _money(value):
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def _check(parent, contract, fingerprint):
    if (not isinstance(parent, dict) or parent.get("contract") != contract
            or parent.get("fingerprint") != fingerprint
            or parent["fingerprint"] != _fingerprint({k:v for k,v in parent.items()
                                                      if k != "fingerprint"})):
        raise V47Error("V47_SOURCE_FINGERPRINT_OR_CONTRACT_DRIFT")


def verified_cases(v46: dict, v45: dict) -> list[dict]:
    _check(v46, V46_CONTRACT, EXPECTED_V46_FP)
    _check(v45, V45_CONTRACT, EXPECTED_V45_FP)
    v46_cases, v45_cases = v46.get("cases"), v45.get("cases")
    if (not isinstance(v46_cases, list) or len(v46_cases) != 361
            or not isinstance(v45_cases, list) or len(v45_cases) != 361
            or v46.get("source_v45_fingerprint") != EXPECTED_V45_FP
            or v46.get("historical_profitability") is not None
            or v46.get("historical_trades_entered") is not None
            or v46.get("rates_and_dividends_are_historical_pit") is not False
            or v46.get("retrospective_raw_return_proxy_is_historical_pit") is not False
            or v46.get("lookahead_pnl_or_future_outcomes_read") is not False
            or v46.get("status_counts", {}).get("ROBUST_HYPOTHETICAL_LONG") != 106
            or v45.get("historically_executed_orders") is not None
            or v45.get("historical_profitability") is not None):
        raise V47Error("V47_SOURCE_AUTHORITY_DRIFT")
    lookup = {r["date_et"]: r for r in v45_cases}
    if len(lookup) != 361 or len({r["date_et"] for r in v46_cases}) != 361:
        raise V47Error("V47_DUPLICATE_DATES")
    selected = []
    for case in v46_cases:
        day = case["date_et"]
        source = lookup.get(day)
        if (source is None or case["cohort_origin"] != source["cohort_origin"]
                or case["source_quality_status"] != source["status"]):
            raise V47Error("V47_SOURCE_COHORT_IDENTITY_DRIFT")
        if case["scenario_screen_status"] != "ROBUST_HYPOTHETICAL_LONG":
            continue
        if (source["status"] != ENTRY_STATUS or source["cohort_origin"]
                not in ("ORIGINAL_V43", "V44_OI_ALTERNATE_VARIANT")
                or len(case.get("scenario_results", [])) != 3
                or {r.get("hypothetical_decision") for r in case["scenario_results"]}
                    != {"HYPOTHETICAL_VARIANCE_EXCEEDS_IV"}):
            raise V47Error("V47_NOT_UNANIMOUS_SCENARIO_ENTRY")
        q = source.get("quote_quality", {}).get("execution_1001", {})
        legs = (q.get("call", {}), q.get("put", {}))
        if (any(leg.get("status") != "QUOTE_MICROSTRUCTURE_PASSES" for leg in legs)
                or q.get("skew_seconds") is None or q["skew_seconds"] > 1):
            raise V47Error("V47_ENTRY_QUOTE_NOT_PREQUALIFIED")
        selected.append(source)
    if len(selected) != 106:
        raise V47Error("V47_FROZEN_106_SCREEN_POPULATION_DRIFT")
    return selected


def exit_sessions(entry_day: str, *, calendar=None):
    calendar = calendar or get_market_calendar()
    d = date.fromisoformat(entry_day)
    sessions = calendar.sessions_in_range(d, d + timedelta(days=20))
    following = [s.isoformat() for s in sessions if s > d]
    if len(following) < MAX_HOLD_SESSIONS or not calendar.is_session(d):
        raise V47Error("V47_XNYS_FIVE_NEXT_SESSIONS_UNAVAILABLE")
    return dict(zip(HOLD_DAYS, following[:MAX_HOLD_SESSIONS]))


def build_plan(selected: list[dict], *, calendar=None):
    """Only source-eligible V46 exploratory LONG dates; no future outcomes read."""
    by_day = {}
    for row in selected:
        day = row["date_et"]
        expiry = row["expiration"]
        strike = str(row["strike"])
        future = exit_sessions(day, calendar=calendar)
        if any(date.fromisoformat(exit_day) >= date.fromisoformat(expiry)
               for exit_day in future.values()):
            raise V47Error("V47_HOLD_AT_OR_AFTER_EXPIRY")
        by_day[day] = {
            "entry_date_et": day, "cohort_origin": row["cohort_origin"],
            "expiration": expiry, "strike": strike,
            "entry": row["quote_quality"]["execution_1001"],
            "exit_dates": future,
        }
    if len(by_day) != len(selected):
        raise V47Error("V47_DUPLICATE_ENTRY_DATES")
    return by_day


def exit_demands(plan: dict):
    for day, pair in sorted(plan.items()):
        for hold, exit_day in pair["exit_dates"].items():
            for right in ("call", "put"):
                yield {
                    "candidate_id": f"SPY.V47.{day}.{pair['expiration']}.{pair['strike']}",
                    "purpose": f"s{hold}_{right}_1001",
                    "method": "option_at_time_quote",
                    "kwargs": {
                        "symbol": "SPY",
                        "expiration": pair["expiration"],
                        "strike": pair["strike"],
                        "right": right,
                        "date_et": exit_day,
                        "time_of_day_et": "10:01:00.000",
                    },
                }


def _pair_quote_exit(demands_and_sources: dict, hold: int):
    q = {}
    for right in ("call", "put"):
        item = demands_and_sources.get(f"s{hold}_{right}_1001")
        if item is None:
            return {"status": "CENSORED_SOURCE_MISSING"}
        requirement, source = item
        observed = _exact_quote(source, requirement)
        q[right] = observed
        if observed["status"] != "QUOTE_MICROSTRUCTURE_PASSES":
            return {"status": "CENSORED_EXIT_QUOTE_UNQUALIFIED",
                    "leg": right, "detail": observed}
    try:
        left, right = datetime.fromisoformat(q["call"]["timestamp_et"]), datetime.fromisoformat(q["put"]["timestamp_et"])
    except (KeyError, ValueError, TypeError) as exc:
        raise V47Error("V47_EXIT_TIMESTAMP_NOT_AWARE") from exc
    skew = abs((left-right).total_seconds())
    if skew > 1:
        return {"status": "CENSORED_EXIT_LEG_SKEW", "skew_seconds": skew}
    return {"status": "PAIRED_EXIT_QUOTE_QUALIFIED", "call": q["call"],
            "put": q["put"], "skew_seconds": skew}


def _quote_pnl(entry, exitq, *, stressed=False):
    """One-pair quote reference, not a fill; stress adds a full spread per leg/side."""
    entry_ask = sum((Decimal(str(entry[right]["ask"])) for right in ("call", "put")), Decimal(0))
    exit_bid = sum((Decimal(str(exitq[right]["bid"])) for right in ("call", "put")), Decimal(0))
    entry_spread = sum((Decimal(str(entry[right]["ask"]))-Decimal(str(entry[right]["bid"]))
                        for right in ("call", "put")), Decimal(0))
    exit_spread = sum((Decimal(str(exitq[right]["ask"]))-Decimal(str(exitq[right]["bid"]))
                       for right in ("call", "put")), Decimal(0))
    entry_cost = _money((entry_ask + (entry_spread if stressed else 0))*MULTIPLIER
                        + 2*PER_LEG_PER_SIDE_FEE)
    exit_credit = _money((exit_bid - (exit_spread if stressed else 0))*MULTIPLIER
                         - 2*PER_LEG_PER_SIDE_FEE)
    if exit_credit < 0:
        return {"status": "STRESS_SELL_BID_BELOW_COSTS_NO_EXECUTABLE_PRICE"}
    return {
        "status": "PAIR_QUOTE_REFERENCE_NET",
        "entry_debit_plus_fees": str(entry_cost),
        "exit_credit_less_fees": str(exit_credit),
        "net_dollars_one_pair": str(exit_credit - entry_cost),
        "net_percent_of_debit": float((exit_credit-entry_cost)/entry_cost*100),
        "fee_per_leg_per_side": str(PER_LEG_PER_SIDE_FEE),
        "price_source_is_broker_fill": False,
    }


def _account_scenario(cases: list[dict], hold: int, cost_key: str):
    """Chronological one-slot *hypothetical* account; never discard missing exits."""
    cash, next_available, events, skipped = INITIAL_CASH, None, [], Counter()
    unresolved = None
    for c in cases:
        day = c["entry_date_et"]
        if unresolved is not None:
            skipped["UNRESOLVED_POSITION_BLOCKS_LATER_ENTRIES"] += 1
            continue
        if next_available is not None and day <= next_available:
            skipped["OPEN_PAIR_SLOT_UNAVAILABLE"] += 1
            continue
        item = c["holds"][str(hold)]
        entry = c["entry_quote"]
        entry_cost = _quote_pnl(entry, item["exit_quote"], stressed=(cost_key=="stress")) if item["status"] == "PAIRED_EXIT_QUOTE_QUALIFIED" else None
        # On a censored exit, the entry debit is still measured from entry quotes;
        # the later missing exit cannot retroactively cancel that purchase.
        ask = sum((Decimal(str(entry[r]["ask"])) for r in ("call", "put")), Decimal(0))
        spread = sum((Decimal(str(entry[r]["ask"]))-Decimal(str(entry[r]["bid"])) for r in ("call", "put")), Decimal(0))
        debit = _money((ask+(spread if cost_key=="stress" else 0))*MULTIPLIER+2*PER_LEG_PER_SIDE_FEE)
        if debit > cash*CAPITAL_FRACTION:
            skipped["FIVE_PERCENT_DEBIT_CAP"] += 1
            continue
        exit_date = item["exit_date_et"]
        cash -= debit
        event = {"entry_date_et": day, "target_exit_date_et": exit_date,
                 "origin": c["cohort_origin"], "entry_debit_plus_fees": str(debit)}
        if item["status"] != "PAIRED_EXIT_QUOTE_QUALIFIED":
            unresolved = {**event, "exit_status": item["status"],
                          "cash_excludes_unmarked_open_pair": str(cash)}
            events.append({**event, "status": "UNRESOLVED_PRICE"})
            continue
        if entry_cost is None or entry_cost.get("status") != "PAIR_QUOTE_REFERENCE_NET":
            unresolved = {**event, "exit_status": entry_cost["status"] if entry_cost else "MISSING",
                          "cash_excludes_unmarked_open_pair": str(cash)}
            events.append({**event, "status": "UNRESOLVED_STRESS_PRICE"})
            continue
        credit = Decimal(entry_cost["exit_credit_less_fees"])
        cash += credit
        next_available = exit_date
        events.append({**event, "status": "CLOSED_QUOTE_REFERENCE_ONLY",
                       "exit_credit_less_fees": str(credit),
                       "net_dollars": str(credit-debit)})
    return {
        "hold_sessions": hold, "cost_scenario": cost_key, "initial_cash": str(INITIAL_CASH),
        "ending_cash_if_fully_resolved": str(cash) if unresolved is None else None,
        "unresolved_position": unresolved, "closed_quote_reference_pairs":
            sum(e["status"]=="CLOSED_QUOTE_REFERENCE_ONLY" for e in events),
        "entry_events_including_unresolved": len(events), "skipped_counts": dict(skipped),
        "events": events,
        "historical_execution_or_true_strategy_pnl": False,
    }


def report(v46: dict, v45: dict, plan: dict, sources: dict, acquisition: dict) -> dict:
    selected = verified_cases(v46, v45)
    if set(plan) != {c["date_et"] for c in selected}:
        raise V47Error("V47_PLAN_CHANGED")
    expected = len(selected)*len(HOLD_DAYS)*2
    if acquisition.get("source_uses_requested") != expected:
        raise V47Error("V47_EXIT_DEMAND_COUNT_DRIFT")
    results, stats, by_origin = [], defaultdict(list), defaultdict(Counter)
    for day, p in sorted(plan.items()):
        case = {
            "entry_date_et": day, "cohort_origin": p["cohort_origin"],
            "expiration": p["expiration"], "strike": p["strike"],
            "entry_quote": p["entry"], "holds": {},
        }
        for hold, exit_day in p["exit_dates"].items():
            exitq = _pair_quote_exit(sources.get(day, {}), hold)
            h = {"exit_date_et": exit_day, "status": exitq["status"],
                 "exit_quote": exitq if exitq["status"] == "PAIRED_EXIT_QUOTE_QUALIFIED" else None,
                 "reason": exitq if exitq["status"] != "PAIRED_EXIT_QUOTE_QUALIFIED" else None,
                 "primary": None, "stress": None}
            if h["exit_quote"] is not None:
                h["primary"] = _quote_pnl(p["entry"], exitq)
                h["stress"] = _quote_pnl(p["entry"], exitq, stressed=True)
            case["holds"][str(hold)] = h
            stats[hold].append({"date": day, "origin": p["cohort_origin"], **h})
            by_origin[p["cohort_origin"]][f"s{hold}_{h['status']}"] += 1
        results.append(case)
    metrics = {}
    for hold, rows in stats.items():
        observed = [r for r in rows if r["status"]=="PAIRED_EXIT_QUOTE_QUALIFIED"]
        primary = [r["primary"] for r in observed if r["primary"]["status"] == "PAIR_QUOTE_REFERENCE_NET"]
        stress = [r["stress"] for r in observed if r["stress"]["status"] == "PAIR_QUOTE_REFERENCE_NET"]
        metrics[str(hold)] = {
            "source_qualified_pairs": len(observed), "censored_pairs": len(rows)-len(observed),
            "requested_pairs": len(rows),
            "primary_quote_reference_net_percent": {
                "n": len(primary),
                "mean": mean(float(r["net_percent_of_debit"]) for r in primary) if primary else None,
                "median": median(float(r["net_percent_of_debit"]) for r in primary) if primary else None,
                "positive": sum(float(r["net_percent_of_debit"]) > 0 for r in primary),
            },
            "stress_quote_reference_net_percent": {
                "n": len(stress),
                "mean": mean(float(r["net_percent_of_debit"]) for r in stress) if stress else None,
                "median": median(float(r["net_percent_of_debit"]) for r in stress) if stress else None,
                "positive": sum(float(r["net_percent_of_debit"]) > 0 for r in stress),
            },
            "by_year": {year: {
                "qualified": sum(r["status"]=="PAIRED_EXIT_QUOTE_QUALIFIED" for r in rows if r["date"].startswith(year)),
                "censored": sum(r["status"]!="PAIRED_EXIT_QUOTE_QUALIFIED" for r in rows if r["date"].startswith(year)),
            } for year in sorted({r["date"][:4] for r in rows})},
        }
    # Preserve original and alternate strategy variants as independent cash
    # studies; the explicitly labeled union is a NEW exploratory hybrid, never
    # evidence for the unchanged frozen-original strategy.
    account_cohorts = (
        ("ORIGINAL_V43_ONLY", [c for c in results if c["cohort_origin"] == "ORIGINAL_V43"]),
        ("V44_ALTERNATE_ONLY", [c for c in results if c["cohort_origin"] == "V44_OI_ALTERNATE_VARIANT"]),
        ("EXPLORATORY_COMBINED_NEW_VARIANT", results),
    )
    accounts = [
        {"research_variant": label, **_account_scenario(cohort, hold, key)}
        for label, cohort in account_cohorts
        for hold in HOLD_DAYS for key in ("primary", "stress")
    ]
    out = {
        "contract": CONTRACT, "status": "EXPLORATORY_EXIT_QUOTE_ECONOMICS_NOT_STRATEGY_PNL",
        "source_v46_fingerprint": v46["fingerprint"],
        "source_v45_fingerprint": v45["fingerprint"],
        "source_request_counts": acquisition, "hypothetical_long_candidates": len(results),
        "exit_hold_sessions": list(HOLD_DAYS), "historical_quote_metrics_by_hold": metrics,
        "source_qualified_count_by_origin": {k:dict(v) for k,v in sorted(by_origin.items())},
        "chronological_one_slot_quote_reference_accounts": accounts,
        "account_replay_variants_separately_labeled": [name for name, _ in account_cohorts],
        "cases": results,
        "hypothetical_rate_dividend_and_raw_return_inputs_not_pit": True,
        "fixed_hold_does_not_match_frozen_dynamic_exit": True,
        "quote_snapshots_are_not_actual_fills": True,
        "missing_exit_not_zero_proceeds": True,
        "account_terminal_equity_on_unresolved_exit": None,
        "historical_strategy_trades_executed": None, "historical_strategy_profitability": None,
        "used_protected_2026_outcomes": False,
    }
    out["fingerprint"] = _fingerprint(out)
    return out
