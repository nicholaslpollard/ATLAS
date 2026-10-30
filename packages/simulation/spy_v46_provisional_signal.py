from __future__ import annotations

"""V46 exploratory option-variance economics; never a PIT signal or backtest.

Compare independently archived 09:59 quotes with a *retrospectively constructed*
prior-return volatility proxy under explicit hypothetical rate/dividend settings.
No candidate can be promoted to a historical entry from this report.
"""

from collections import Counter, defaultdict
from datetime import date, datetime, time
from math import isfinite
from zoneinfo import ZoneInfo

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.american_option_iv_lr_v41 import american_lr_implied_volatility

CONTRACT = "atlas-spy-provisional-variance-economics-v46"
V45_CONTRACT = "atlas-spy-unified-two-clock-original-plus-alternate-v45"
V37_CONTRACT = "atlas-spy-v37-pretrade-feature-bridge-v1"
EXPECTED_V45_FP = "450da4ee779aad96b6656e1d7a03435bf3521875c72ebca6f69b845a7205bd5e"
SCENARIOS = (("LOW_RATE_ZERO_YIELD", 0.01, 0.0),
             ("MID_RATE_MODERATE_YIELD", 0.04, 0.015),
             ("HIGH_RATE_HIGH_YIELD", 0.08, 0.03))
ANOMALY_DATES = frozenset(("2018-04-02", "2021-06-21"))


class ProvisionalScreenError(ValueError):
    pass


def _positive_number(value, label):
    if isinstance(value, bool):
        raise ProvisionalScreenError(f"V46_INVALID_{label}")
    try:
        v = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ProvisionalScreenError(f"V46_INVALID_{label}") from exc
    if not isfinite(v) or not 0 < v < 1e6:
        raise ProvisionalScreenError(f"V46_INVALID_{label}")
    return v


def _verified(report, contract, fingerprint=None):
    if (not isinstance(report, dict) or report.get("contract") != contract
            or not isinstance(report.get("fingerprint"), str)
            or report["fingerprint"] != _fingerprint({k: v for k, v in report.items() if k != "fingerprint"})
            or (fingerprint is not None and report["fingerprint"] != fingerprint)):
        raise ProvisionalScreenError("V46_PARENT_SOURCE_INTEGRITY_FAILED")


def _validate(v45, v37):
    _verified(v45, V45_CONTRACT, EXPECTED_V45_FP)
    _verified(v37, V37_CONTRACT)
    if (v45.get("total_original_weekly_clocks") != 411
            or v45.get("original_selected_weekly_clocks") != 361
            or v45.get("original_abstentions_unchanged") != 50
            or v45.get("cohort_origin_counts") != {
                "NO_SOURCE_QUALITY_ELIGIBLE_PAIR": 22,
                "ORIGINAL_V43": 178,
                "V44_OI_ALTERNATE_VARIANT": 161,
            }
            or v45.get("cohort_status_counts") != {
                "SOURCE_QUALITY_NOT_ELIGIBLE": 22,
                "TWO_CLOCK_SOURCE_QUALITY_PASSES": 323,
                "TWO_CLOCK_SOURCE_QUALITY_UNQUALIFIED": 16,
            }
            or v45.get("historically_executed_orders") is not None
            or v45.get("historical_profitability") is not None
            or v45.get("american_iv_computed") is not False
            or v37.get("source_selected_pairs") != 361
            or v37.get("original_abstentions") != 50
            or v37.get("trading_pnl_computed") is not False
            or v37.get("qualified_real_historical_volatility_signals") != 0
            or v37.get("historical_publication_clocks_qualified") is not False):
        raise ProvisionalScreenError("V46_PARENT_AUTHORITIES_CHANGED")
    cases = v45.get("cases")
    entries = v37.get("entries")
    if not isinstance(cases, list) or not isinstance(entries, list) or len(cases) != 361 or len(entries) != 361:
        raise ProvisionalScreenError("V46_MISSING_361_POPULATION")
    by_day = {row["original_entry_date_et"]: row for row in entries}
    if (len(by_day) != 361 or len({c["date_et"] for c in cases}) != 361
            or set(by_day) != {c["date_et"] for c in cases}):
        raise ProvisionalScreenError("V46_DIFFERENT_DATE_POPULATION")
    anomalies = {row["date_et"] for row in v45.get("suspicious_equal_call_put_quotes", [])}
    if anomalies != ANOMALY_DATES:
        raise ProvisionalScreenError("V46_SOURCE_ANOMALY_SET_CHANGED")
    return cases, by_day


def _model_maturity_years(day, expiry):
    """*Assumed* 16:00 ET expiry; not independently verified OCC exercise time."""
    zone = ZoneInfo("America/New_York")
    start = datetime.combine(date.fromisoformat(day), time(10, 0), tzinfo=zone)
    end = datetime.combine(date.fromisoformat(expiry), time(16, 0), tzinfo=zone)
    maturity_seconds = (end.timestamp() - start.timestamp())
    if not 30 * 86400 <= maturity_seconds <= 46 * 86400:
        raise ProvisionalScreenError("V46_INVALID_ASSUMED_MATURITY")
    return maturity_seconds / (365.0 * 86400)


def evaluate(v45: dict, v37: dict, *, progress=None) -> dict:
    """Return assumption-only candidate signals; never trade/execution/P&L."""
    cases, features = _validate(v45, v37)
    results = []
    by_origin = defaultdict(Counter)
    by_year = defaultdict(Counter)
    aggregate = Counter()
    for index, case in enumerate(cases, start=1):
        day = case["date_et"]
        feat = features[day]
        row = {"date_et": day, "cohort_origin": case["cohort_origin"],
               "source_quality_status": case["status"],
               "scenario_screen_status": None, "scenario_results": [],
               "hypothetical_entry_orders": None, "historical_trade_pnl": None}
        if case["status"] != "TWO_CLOCK_SOURCE_QUALITY_PASSES":
            row["scenario_screen_status"] = "SOURCE_QUALITY_REJECTED"
        elif day in ANOMALY_DATES:
            row["scenario_screen_status"] = "IDENTICAL_CROSS_RIGHT_QUOTES_REVIEW"
        elif (feat.get("conditional_unadjusted_raw_volatility") is None
              or feat.get("forecast_source_historical_pit_qualified") is not False):
            row["scenario_screen_status"] = "RAW_PREVIOUS_20_RETURN_PROXY_UNAVAILABLE"
        else:
            raw_vol = _positive_number(feat["conditional_unadjusted_raw_volatility"], "RAW_PRIOR_VOL")
            if raw_vol > 10:
                raise ProvisionalScreenError("V46_RAW_VOL_OUT_OF_BOUNDS")
            spot = _positive_number(case["spot_0959"], "SPOT")
            strike = _positive_number(case["strike"], "STRIKE")
            expiry = case["expiration"]
            if (case["cohort_origin"] == "ORIGINAL_V43" and
                    (date.fromisoformat(expiry) != date.fromisoformat(feat["frozen_expiration_et"])
                     or abs(strike - _positive_number(feat["frozen_strike"], "FROZEN_STRIKE")) > 1e-8)):
                raise ProvisionalScreenError("V46_ORIGINAL_FROZEN_IDENTITY_CHANGED")
            years = _model_maturity_years(day, expiry)
            pre = case["quote_quality"]["pretrade_0959"]
            quote = {}
            for right in ("call", "put"):
                q = pre[right]
                if q.get("status") != "PRETRADE_QUOTE_0959_PASSES":
                    raise ProvisionalScreenError("V46_0959_QUOTE_NOT_QUALITY_PASSED")
                quote[right] = (_positive_number(q["bid"], "BID"),
                                _positive_number(q["ask"], "ASK"))
                if quote[right][0] > quote[right][1]:
                    raise ProvisionalScreenError("V46_CROSSED_QUOTE")
            for label, rate, dividend in SCENARIOS:
                ivs = {}
                for right in ("call", "put"):
                    bid, ask = quote[right]
                    ivs[right] = american_lr_implied_volatility(
                        right, bid=bid, ask=ask, spot=spot, strike=strike,
                        years=years, rate=rate, dividend_yield=dividend,
                    )
                if any(v is None for v in ivs.values()):
                    decision = "MODEL_IV_UNSOLVABLE"
                else:
                    decision = ("HYPOTHETICAL_VARIANCE_EXCEEDS_IV" if
                                raw_vol**2 > (ivs["call"]**2 + ivs["put"]**2)/2
                                else "HYPOTHETICAL_VARIANCE_NOT_ABOVE_IV")
                row["scenario_results"].append({
                    "scenario": label, "assumed_rate": rate,
                    "assumed_continuous_dividend_yield": dividend,
                    "assumed_expiry_1600_et": True,
                    "raw_prior_annual_volatility_not_pit": raw_vol,
                    "model_call_iv": ivs["call"], "model_put_iv": ivs["put"],
                    "hypothetical_decision": decision,
                })
            decisions = {r["hypothetical_decision"] for r in row["scenario_results"]}
            row["scenario_screen_status"] = (
                "ROBUST_HYPOTHETICAL_LONG" if decisions == {"HYPOTHETICAL_VARIANCE_EXCEEDS_IV"}
                else "ROBUST_HYPOTHETICAL_ABSTAIN" if decisions == {"HYPOTHETICAL_VARIANCE_NOT_ABOVE_IV"}
                else "SCENARIO_DEPENDENT_OR_UNSOLVABLE"
            )
        aggregate[row["scenario_screen_status"]] += 1
        by_origin[row["cohort_origin"]][row["scenario_screen_status"]] += 1
        by_year[day[:4]][row["scenario_screen_status"]] += 1
        results.append(row)
        if progress:
            progress(index, len(cases), day, row["scenario_screen_status"])
    report = {
        "contract": CONTRACT, "status": "HYPOTHETICAL_VARIANCE_SCREEN_NOT_PIT_AND_NOT_SIMULATION",
        "source_v45_fingerprint": v45["fingerprint"],
        "source_v37_fingerprint": v37["fingerprint"],
        "scenario_assumptions": [dict(name=name, risk_free_rate=rate,
                                       continuous_dividend_yield=dividend)
                                 for name, rate, dividend in SCENARIOS],
        "source_cases": len(cases),
        "status_counts": dict(sorted(aggregate.items())),
        "by_origin": {k:dict(sorted(v.items())) for k,v in sorted(by_origin.items())},
        "by_year": {k:dict(sorted(v.items())) for k,v in sorted(by_year.items())},
        "cases": results,
        "retrospective_raw_return_proxy_is_historical_pit": False,
        "rates_and_dividends_are_historical_pit": False,
        "discrete_dividend_early_exercise_model_verified": False,
        "occ_standard_deliverables_verified": False,
        "historical_trades_entered": None, "historical_profitability": None,
        "lookahead_pnl_or_future_outcomes_read": False,
        "purpose": "screen strategy economics before independent PIT qualification and exit acquisition",
    }
    report["fingerprint"] = _fingerprint(report)
    return report
