from __future__ import annotations

"""V48 OFFLINE audit of user-executed V47 option quote economics.

Produces no strategy signals, parameter choices, provider calls, or execution
claims. Historical quote returns are conditional on V46's hypothetical,
non-PIT selections. This is immutable DEVELOPMENT evidence only.
"""

from collections import Counter, defaultdict
from decimal import Decimal
from statistics import mean, median
from typing import Any

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v47_counterfactual_quote_exit import (
    CONTRACT as V47_CONTRACT,
)

CONTRACT = "atlas-spy-v48-v47-frozen-negative-evidence-audit"
PINNED_V47_FINGERPRINT = "9eea1abc12eca482d967cad172a9a2851b7c8cfc0879a7f97104d4bed01e855d"
ORIGINAL = "ORIGINAL_V43"
ALTERNATE = "V44_OI_ALTERNATE_VARIANT"
EXPECTED_CASES = {ORIGINAL: 48, ALTERNATE: 58}
HOLDS = tuple(str(n) for n in range(1, 6))
STUDIES = ("primary", "stress")


class AuditError(ValueError):
    pass


def verify(report: dict) -> list[dict]:
    if not isinstance(report, dict):
        raise AuditError("V48_REQUIRED_V47_JSON_OBJECT")
    fp = report.get("fingerprint")
    if (report.get("contract") != V47_CONTRACT
            or fp != PINNED_V47_FINGERPRINT
            or fp != _fingerprint({k: v for k, v in report.items() if k != "fingerprint"})):
        raise AuditError("V48_V47_IMMUTABLE_REPORT_DRIFT")
    counts = report.get("source_request_counts", {})
    if (report.get("hypothetical_long_candidates") != 106
            or report.get("historical_strategy_trades_executed") is not None
            or report.get("historical_strategy_profitability") is not None
            or report.get("fixed_hold_does_not_match_frozen_dynamic_exit") is not True
            or report.get("hypothetical_rate_dividend_and_raw_return_inputs_not_pit") is not True
            or report.get("quote_snapshots_are_not_actual_fills") is not True
            or report.get("account_terminal_equity_on_unresolved_exit") is not None
            or counts.get("source_uses_requested") != 1060
            or counts.get("source_uses_resolved") != 1058
            or counts.get("source_uses_failed_or_unresolved") != 2):
        raise AuditError("V48_REPORT_AUTHORITY_OR_SOURCE_COVERAGE_DRIFT")
    cases = report.get("cases")
    if (not isinstance(cases, list) or len(cases) != 106
            or Counter(x.get("cohort_origin") for x in cases) != EXPECTED_CASES
            or len({x.get("entry_date_et") for x in cases}) != 106
            or [x["entry_date_et"] for x in cases] != sorted(x["entry_date_et"] for x in cases)):
        raise AuditError("V48_V47_CASE_COHORT_DRIFT")
    for case in cases:
        if set(case.get("holds", {})) != set(HOLDS):
            raise AuditError("V48_HOLD_COVERAGE_DRIFT")
        for h in HOLDS:
            v = case["holds"][h]
            if ((v.get("status") == "PAIRED_EXIT_QUOTE_QUALIFIED")
                    != (v.get("primary") is not None)):
                raise AuditError("V48_EXIT_STATUS_RECONCILIATION_FAILURE")
    return cases


def _round(x: float | None) -> float | None:
    return round(x, 5) if x is not None else None


def _stats(values: list[float]) -> dict[str, Any]:
    ordered = sorted(values)
    return {
        "sample": len(ordered),
        "positive": sum(v > 0 for v in ordered),
        "negative": sum(v < 0 for v in ordered),
        "zero": sum(v == 0 for v in ordered),
        "mean_pct": _round(mean(ordered)) if ordered else None,
        "median_pct": _round(median(ordered)) if ordered else None,
        "minimum_pct": _round(ordered[0]) if ordered else None,
        "maximum_pct": _round(ordered[-1]) if ordered else None,
        "mean_without_single_largest_winner_pct": (
            _round(mean(ordered[:-1])) if len(ordered) >= 2 else None
        ),
        "mean_without_five_largest_winners_pct": (
            _round(mean(ordered[:-5])) if len(ordered) >= 6 else None
        ),
    }


def _metrics(cases: list[dict], hold: str, study: str) -> dict:
    vals = [
        float(c["holds"][hold][study]["net_percent_of_debit"])
        for c in cases
        if c["holds"][hold][study] is not None
        and c["holds"][hold][study].get("status") == "PAIR_QUOTE_REFERENCE_NET"
    ]
    return {
        "all_eligible_hypothetical_dates": len(cases),
        "quoted_dates": len(vals),
        "censored_dates": len(cases) - len(vals),
        "conditional_quote_reference_returns_pct": _stats(vals),
    }


def _recorded_account(report: dict) -> dict:
    all_accounts = report.get("chronological_one_slot_quote_reference_accounts", [])
    selected = [
        a for a in all_accounts
        if a.get("research_variant") == "ORIGINAL_V43_ONLY"
        and a.get("hold_sessions") == 1
        and a.get("cost_scenario") in STUDIES
    ]
    if len(selected) != 2:
        raise AuditError("V48_ORIGINAL_ONE_DAY_ACCOUNT_MISSING")
    output = {}
    for account in selected:
        key = account["cost_scenario"]
        if (account.get("unresolved_position") is not None
                or account.get("closed_quote_reference_pairs") != 48
                or account.get("entry_events_including_unresolved") != 48
                or account.get("ending_cash_if_fully_resolved") is None
                or account.get("skipped_counts")):
            raise AuditError("V48_ONE_DAY_ACCOUNT_INCOMPLETE")
        events = account["events"]
        if len(events) != 48 or any(e.get("status") != "CLOSED_QUOTE_REFERENCE_ONLY" for e in events):
            raise AuditError("V48_ACCOUNT_EVENT_CENSOR_DRIFT")
        pnl = sum((Decimal(e["net_dollars"]) for e in events), Decimal(0))
        start = Decimal(account["initial_cash"])
        ending = Decimal(account["ending_cash_if_fully_resolved"])
        if start != Decimal("100000.00") or start+pnl != ending:
            raise AuditError("V48_ACCOUNT_DOLLAR_RECONCILIATION_DRIFT")
        by_week = defaultdict(lambda: Decimal(0))
        by_month = defaultdict(lambda: Decimal(0))
        by_year = defaultdict(lambda: Decimal(0))
        from datetime import date
        for e in events:
            exit_day = date.fromisoformat(e["target_exit_date_et"])
            amount = Decimal(e["net_dollars"])
            iso = exit_day.isocalendar()
            by_week[f"{iso.year}-W{iso.week:02}"] += amount
            by_month[exit_day.strftime("%Y-%m")] += amount
            by_year[exit_day.strftime("%Y")] += amount
        def window(buckets):
            return {
                "active_windows": len(buckets),
                "positive": sum(amount > 0 for amount in buckets.values()),
                "negative": sum(amount < 0 for amount in buckets.values()),
                "zero": sum(amount == 0 for amount in buckets.values()),
                "realized_pnl_by_window_dollars": {k: str(v.quantize(Decimal("0.01")))
                                                    for k, v in sorted(buckets.items())},
            }
        output[key] = {
            "initial_cash": str(start),
            "ending_cash_quote_reference_only": str(ending),
            "net_dollars": str(pnl.quantize(Decimal("0.01"))),
            "closed_pairs": len(events),
            "positive_pairs": sum(Decimal(e["net_dollars"]) > 0 for e in events),
            "weeks_with_recorded_closures": window(by_week),
            "months_with_recorded_closures": window(by_month),
            "years_with_recorded_closures": window(by_year),
            "no_trading_sessions_not_valued_at_daily_granularity": True,
        }
    return output


def audit(report: dict) -> dict:
    cases = verify(report)
    all_holds = {
        h: {study: _metrics(cases, h, study) for study in STUDIES} for h in HOLDS
    }
    origins = {
        origin: {
            h: {study: _metrics([x for x in cases if x["cohort_origin"] == origin],
                                h, study) for study in STUDIES}
            for h in HOLDS
        } for origin in EXPECTED_CASES
    }
    year_origin = {
        year: {
            origin: {
                "hypothetical_entry_dates": sum(
                    x["entry_date_et"].startswith(year) and x["cohort_origin"] == origin
                    for x in cases),
                "day_1_primary": _metrics(
                    [x for x in cases if x["entry_date_et"].startswith(year)
                     and x["cohort_origin"] == origin], "1", "primary"),
                "day_5_primary": _metrics(
                    [x for x in cases if x["entry_date_et"].startswith(year)
                     and x["cohort_origin"] == origin], "5", "primary"),
            } for origin in EXPECTED_CASES
        } for year in sorted({x["entry_date_et"][:4] for x in cases})
    }
    censored = Counter(
        c["holds"][h]["status"] for c in cases for h in HOLDS
        if c["holds"][h]["status"] != "PAIRED_EXIT_QUOTE_QUALIFIED"
    )
    observed = sum(all_holds[h]["primary"]["quoted_dates"] for h in HOLDS)
    if observed != 510 or sum(censored.values()) != 20:
        raise AuditError("V48_QUOTE_CENSOR_COUNTS_DRIFT")
    fifth = all_holds["5"]["primary"]["conditional_quote_reference_returns_pct"]
    fifth_stress = all_holds["5"]["stress"]["conditional_quote_reference_returns_pct"]
    if not (fifth["mean_pct"] > 0
            and fifth["median_pct"] < 0
            and fifth["mean_without_single_largest_winner_pct"] < 0
            and fifth_stress["mean_pct"] < 0):
        raise AuditError("V48_FROZEN_FIFTH_DAY_OUTLIER_VERDICT_DRIFT")
    out = {
        "contract": CONTRACT,
        "source_v47_fingerprint": report["fingerprint"],
        "status": "DEVELOPMENT_NEGATIVE_EXPLORATORY_QUOTE_EVIDENCE_NO_PROMOTION",
        "candidate_eligibility": "V46_HYPOTHETICAL_NOT_PIT",
        "qualified_observed_pairs": observed,
        "censored_pair_observations": sum(censored.values()),
        "source_missing_requests": 2,
        "censor_reason_counts": dict(sorted(censored.items())),
        "all_five_holds_by_cost_scenario": all_holds,
        "separate_strategy_origins": origins,
        "year_and_origin_diagnostics": year_origin,
        "fully_resolved_original_one_day_cash_reference": _recorded_account(report),
        "five_day_positive_mean_depends_on_one_outlier": True,
        "all_five_hold_medians_negative": all(
            all_holds[h]["primary"]["conditional_quote_reference_returns_pct"]["median_pct"] < 0
            for h in HOLDS
        ),
        "independent_validation_or_actual_order_fills": False,
        "profitable_trading_strategy_demonstrated": False,
        "no_future_outcomes_used_to_reselect_or_optimize_trades": True,
        "provider_requests": 0,
        "broker_requests": 0,
    }
    out["fingerprint"] = _fingerprint(out)
    return out
