from __future__ import annotations

"""V37 offline source-bound SPY pretrade feature bridge, NOT a strategy signal.

Join the original 361 V29-selected pairs and 407 retrospectively observed
20-return variance windows. Preserve missing pricing and PIT provenance.
Crucially, historical source presence does not establish availability at the
10:00 decision or 10:01 order clock; no implied IV is guessed from premium.
"""

from collections import Counter, defaultdict
from dateutil.parser import isoparse
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_spy_physical_spot_exact_demand_v29 import (
    CONTRACT as V29_CONTRACT,
)
from packages.data.options_native_spy_full_period_retrospective_dividend_variance_v1 import (
    CONTRACT as GRID_CONTRACT,
)
from packages.simulation.options_native_spy_quote_account_diagnostic_v34 import (
    QuoteScenarioError, validate_v32_tape,
)
from packages.strategies.options_native_pilot_v1_contract import (
    SPECIFICATION_FINGERPRINT,
)

CONTRACT = "atlas-spy-v37-pretrade-feature-bridge-v1"
PINNED_TAPE_FINGERPRINT = (
    "a0bfbd1ae8db9d3b502ee21780db17a23d37d5284655611167078c5a870c365e"
)
REQUIRED_NEXT_INPUTS = (
    "PIT_20_RETURN_CORPORATE_ACTION_SOURCE_AND_PUBLICATION",
    "PIT_SPY_0959_SOURCE_AVAILABILITY_BY_1001",
    "PIT_AMERICAN_101STEP_CALL_AND_PUT_IV_WITH_RATE_AND_DIVIDENDS",
    "PIT_PRIOR_SESSION_CALL_AND_PUT_OPEN_INTEREST_AND_PUBLICATION",
    "PIT_EXACT_BOTH_LEG_BID_ASK_SIZES_AND_SKEW_BY_1001",
    "PROVEN_STANDARD_OI_OPTION_DELIVERABLE_AND_MULTIPLIER",
    "EVIDENCED_1001_ORDER_EXECUTION_AND_SUBSEQUENT_EXIT_OR_MARK",
)


def _hash_matches(report: dict, key: str = "report_fingerprint") -> bool:
    raw = report.get(key)
    return (isinstance(raw, str) and len(raw) == 64
            and _fingerprint({k: v for k, v in report.items() if k != key}) == raw)


def _positive(raw: Any, label: str) -> Decimal:
    if not isinstance(raw, str) or not raw or raw.strip() != raw:
        raise QuoteScenarioError("V37_INVALID_" + label)
    try:
        val = Decimal(raw)
    except InvalidOperation as exc:
        raise QuoteScenarioError("V37_INVALID_" + label) from exc
    if not val.is_finite() or not Decimal("0") < val < Decimal("1000000"):
        raise QuoteScenarioError("V37_INVALID_" + label)
    return val


def bridge_pretrade_inputs(v32: dict, v29: dict, variance_grid: dict) -> dict:
    """Pure no-provider cross-check: selected identities are never re-picked."""
    if (v32.get("fingerprint") != PINNED_TAPE_FINGERPRINT
            or not isinstance(v29, dict)
            or v29.get("contract") != V29_CONTRACT
            or v29.get("pilot_specification_fingerprint") != SPECIFICATION_FINGERPRINT
            or v29.get("original_entry_clocks") != 411
            or v29.get("provisional_entry_pairs") != 361
            or v29.get("abstained_weekly_clocks") != 50
            or v29.get("entry_physical_spot_historical_availability_qualified") is not False
            or v29.get("source_quote_selection_used_future_prices") is not False
            or v29.get("historical_options_fill_authority") is not False
            or v29.get("protected_2026_outcomes_read") != 0
            or v29.get("fingerprint") != v32.get("source_plan_fingerprint")
            or not _hash_matches(v29, "fingerprint")):
        raise QuoteScenarioError("V37_ORIGINAL_PAIR_PLAN_SCOPE_OR_FINGERPRINT_DRIFT")
    grouped = validate_v32_tape(v32, PINNED_TAPE_FINGERPRINT)
    if (not isinstance(variance_grid, dict)
            or variance_grid.get("contract") != GRID_CONTRACT
            or variance_grid.get("specification_fingerprint") != SPECIFICATION_FINGERPRINT
            or variance_grid.get("status") !=
                "FULL_PERIOD_RETROSPECTIVE_SENSITIVITY_ONLY_NO_PIT_FEATURES"
            or variance_grid.get("fixed_weekly_decision_count") != 411
            or variance_grid.get("physically_price_complete_decisions") != 407
            or variance_grid.get("historical_economic_feature_accepted") is not False
            or variance_grid.get("historical_backtest_authorized") is not False
            or variance_grid.get("pilot_input_acceptance") is not False
            or variance_grid.get("historical_performance_evidence") is not False
            or variance_grid.get("reads", {}).get("provider_requests") != 0
            or variance_grid.get("reads", {}).get("outcomes") != 0
            or not _hash_matches(variance_grid)):
        raise QuoteScenarioError("V37_RETROSPECTIVE_VARIANCE_AUTHORITY_DRIFT")
    candidates = v29.get("cases")
    prior = variance_grid.get("weekly_retrospective_sensitivity")
    if (not isinstance(candidates, list) or len(candidates) != 411
            or not isinstance(prior, list) or len(prior) != 411):
        raise QuoteScenarioError("V37_FROZEN_CLOCK_COVERAGE_MISSING")
    cases = {x["date_et"]: x for x in candidates}
    volatility = {x["decision_date"]: x for x in prior}
    if (len(cases) != 411 or len(volatility) != 411
            or set(cases) != set(volatility)):
        raise QuoteScenarioError("V37_DUPLICATE_OR_MISSING_CLOCK")
    raw_uses = grouped[1]
    entry_rows = {x["entry_date_et"]: x for x in raw_uses}
    if len(entry_rows) != 361:
        raise QuoteScenarioError("V37_ORIGINAL_ENTRY_IDENTITY_COUNT_DRIFT")
    feature_rows = []
    counts = Counter()
    by_year = defaultdict(Counter)
    for day in sorted(cases):
        pair, prior_row = cases[day], volatility[day]
        year = day[:4]
        date.fromisoformat(day)
        if pair.get("status") != "PHYSICAL_SPOT_PROVISIONAL_PAIR_ONLY":
            if day in entry_rows:
                raise QuoteScenarioError("V37_ABSTAIN_CLOCK_BECAME_SELECTED")
            counts["original_entry_abstention"] += 1
            by_year[year]["original_entry_abstention"] += 1
            continue
        observation = entry_rows.get(day)
        if (observation is None
                or pair.get("entry_original_query_id") != observation["entry_source_query_id"]
                or pair.get("selected_expiration") != observation["expiration"]
                or Decimal(pair.get("selected_strike")) != Decimal(observation["strike"])
                or pair.get("selection_used_future_prices") is not False):
            raise QuoteScenarioError("V37_FUTURE_PAIR_IDENTITY_OR_ENTRY_DRIFT")
        spot = _positive(pair.get("raw_0959_spot"), "SPY_SPOT")
        ask = _positive(observation["original_100share_two_leg_entry_ask"], "ASK")
        expiry = date.fromisoformat(pair["selected_expiration"])
        if not 30 <= (expiry - date.fromisoformat(day)).days <= 45:
            raise QuoteScenarioError("V37_EXPIRY_OUTSIDE_ORIGINAL_PILOT_DTE")
        row = {
            "original_entry_date_et": day,
            "original_entry_source_query_id": observation["entry_source_query_id"],
            "original_quote_tape_fingerprint": v32["fingerprint"],
            "frozen_expiration_et": expiry.isoformat(),
            "frozen_strike": observation["strike"],
            "source_spy_0959_spot": str(spot),
            "source_spy_0959_availability_at_1001_qualified": False,
            "source_original_two_leg_1000_ask_usd": str(ask),
            "source_original_quote_is_order_fill": False,
            "conditional_retrospective_dividend_volatility": None,
            "conditional_unadjusted_raw_volatility": None,
            "forecast_source_historical_pit_qualified": False,
            "american_call_iv": None,
            "american_put_iv": None,
            "implied_pair_variance": None,
            "frozen_pilot_entry_signal": None,
            "historical_source_qualified_1001_order_fill": False,
            "requires": list(REQUIRED_NEXT_INPUTS),
            "status": "HISTORICAL_PRETRADE_FEATURES_INCOMPLETE",
        }
        if prior_row.get("status") == "RETROSPECTIVE_VARIANCE_SENSITIVITY_ONLY":
            raw = _positive(prior_row["annualized_raw_price_volatility"], "RAW_VOL")
            conditioned = _positive(
                prior_row["annualized_retrospective_dividend_conditioned_volatility"], "RETRO_VOL"
            )
            if raw > 10 or conditioned > 10:
                raise QuoteScenarioError("V37_VOLATILITY_MAGNITUDE")
            row["conditional_unadjusted_raw_volatility"] = str(raw)
            row["conditional_retrospective_dividend_volatility"] = str(conditioned)
            counts["selected_retrospective_20return_window"] += 1
            by_year[year]["selected_retrospective_20return_window"] += 1
        elif prior_row.get("status") == "RAW_PRICE_GAP_NO_VARIANCE_DIAGNOSTIC":
            counts["selected_missing_raw_window"] += 1
            by_year[year]["selected_missing_raw_window"] += 1
        else:
            raise QuoteScenarioError("V37_INVALID_RETROSPECTIVE_GRID_CASE")
        feature_rows.append(row)
        by_year[year]["selected_pair"] += 1
    if (len(feature_rows) != 361 or counts["original_entry_abstention"] != 50
            or counts["selected_retrospective_20return_window"]
                + counts["selected_missing_raw_window"] != 361):
        raise QuoteScenarioError("V37_ORIGINAL_ENTRY_DENOMINATOR_DRIFT")
    report = {
        "contract": CONTRACT,
        "status": "SOURCE_BOUND_HISTORICAL_PRETRADE_FEATURE_GAP_PACKET_NOT_SIGNAL",
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "source_v32_quote_tape_fingerprint": v32["fingerprint"],
        "source_v29_spot_selection_fingerprint": v29["fingerprint"],
        "source_411week_volatility_grid_fingerprint": variance_grid["report_fingerprint"],
        "original_weekly_decision_clocks": 411,
        "source_selected_pairs": 361,
        "original_abstentions": 50,
        "selected_retrospective_window_present": counts["selected_retrospective_20return_window"],
        "selected_retrospective_window_missing": counts["selected_missing_raw_window"],
        "qualified_real_historical_volatility_signals": 0,
        "source_iv_values_supplied": 0,
        "trading_pnl_computed": False,
        "hypothetical_cash_scenarios_run": 0,
        "source_quotes_fills": False,
        "retrospective_dividend_source_used_for_historical_decisions": False,
        "historical_publication_clocks_qualified": False,
        "source_reads_original_only_no_new_provider": True,
        "requested_next_source_features": list(REQUIRED_NEXT_INPUTS),
        "by_decision_year": {y: dict(sorted(n.items())) for y, n in sorted(by_year.items())},
        "entries": feature_rows,
        "provider_requests": 0,
        "broker_requests": 0,
        "protected_2026_outcomes_read": 0,
        "future_close_prices_used_to_select_entry": False,
    }
    report["fingerprint"] = _fingerprint(report)
    return report
