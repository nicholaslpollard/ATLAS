from __future__ import annotations

"""Zero-provider ThetaData option-surface enrichment planning.

This stage preserves the accepted 09:35 quote-surface plan and adds two strictly
downstream evidence layers:

1. one historical open-interest surface request per accepted underlying/date;
2. expiration-specific first-order binomial Greeks only after quote + open-interest
   evidence has narrowed the causal candidate set.

No provider request is made here. Unknown historical dividend context blocks Greeks
rather than silently assuming a zero dividend.
"""

from collections import Counter
from datetime import date
import math
from typing import Any, Sequence

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.data.thetadata_candidate_surface_plan_v1 import (
    CONTRACT as SOURCE_PLAN_CONTRACT,
    EXPECTED_MAX_DTE,
    EXPECTED_UNIQUE_SURFACES,
    PROVIDER_CANDIDATE,
)
from packages.portfolio.phase13_policy import (
    PHASE13_OPTION_MAX_DTE,
    PHASE13_OPTION_MAX_SPREAD_TO_MID,
    PHASE13_OPTION_MIN_DTE,
    PHASE13_OPTION_MIN_OPEN_INTEREST,
)

CONTRACT = "atlas-thetadata-candidate-surface-enrichment-plan-v1"
OUTPUT_REL = "data/options/manifests/thetadata_candidate_surface_enrichment_plan_v1"
OPEN_INTEREST_ENDPOINT = "/v3/option/history/open_interest"
BINOMIAL_GREEKS_ENDPOINT = "/v3/option/history/binomial_greeks/first_order"
GREEKS_VERSION = "1"
GREEKS_BINOMIAL_STEPS = 101
GREEKS_RATE_TYPE = "sofr"
DECISION_CLOCK_ET = "09:35:00.000"


class ThetaDataSurfaceEnrichmentPlanError(ValueError):
    pass


def _validate_source_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    _check_signature(plan, "plan_fingerprint")
    request_contract = plan.get("provider_request_contract")
    queries = request_contract.get("full_surface_queries") if isinstance(request_contract, dict) else None
    if (
        plan.get("contract") != SOURCE_PLAN_CONTRACT
        or plan.get("status") != "PLANNED_ZERO_PROVIDER_READS"
        or plan.get("provider_candidate") != PROVIDER_CANDIDATE
        or not isinstance(queries, list)
        or len(queries) != EXPECTED_UNIQUE_SURFACES
        or request_contract.get("expiration") != "*"
        or request_contract.get("strike") != "*"
        or request_contract.get("right") != "call"
        or request_contract.get("max_dte") != EXPECTED_MAX_DTE
        or request_contract.get("strike_range") is not None
        or plan.get("provider_requests") != 0
        or plan.get("historical_fill_authority") is not False
        or plan.get("strategy_evidence_authority") is not False
    ):
        raise ThetaDataSurfaceEnrichmentPlanError(
            "ThetaData quote-surface source plan lineage/authority changed"
        )
    return list(queries)


def _oi_query(source: dict[str, Any]) -> dict[str, Any]:
    params = source["params"]
    if (
        params.get("expiration") != "*"
        or params.get("strike") != "*"
        or params.get("right") != "call"
        or params.get("time_of_day") != DECISION_CLOCK_ET
        or params.get("max_dte") != EXPECTED_MAX_DTE
        or params.get("start_date") != params.get("end_date")
    ):
        raise ThetaDataSurfaceEnrichmentPlanError(
            "quote-surface provider request shape changed"
        )
    payload = {
        "request_type": "THETADATA_HISTORICAL_OPEN_INTEREST_SURFACE",
        "symbol": str(params["symbol"]),
        "date_et": str(params["start_date"]),
        "right": "call",
        "max_dte_calendar_days": EXPECTED_MAX_DTE,
    }
    return {
        "endpoint": OPEN_INTEREST_ENDPOINT,
        "params": {
            "symbol": payload["symbol"],
            "expiration": "*",
            "strike": "*",
            "right": "call",
            "date": payload["date_et"],
            "max_dte": EXPECTED_MAX_DTE,
            "strike_range": None,
            "format": "json",
        },
        "source_quote_query_fingerprint": source["source_query_fingerprint"],
        "query_fingerprint": _fingerprint(payload),
        "member_case_ids": list(source["member_case_ids"]),
        "member_case_count": int(source["member_case_count"]),
    }


def build_thetadata_surface_enrichment_plan(
    source_plan: dict[str, Any],
) -> dict[str, Any]:
    quote_queries = _validate_source_plan(source_plan)
    oi_queries = [_oi_query(item) for item in quote_queries]
    if len({item["query_fingerprint"] for item in oi_queries}) != len(oi_queries):
        raise ThetaDataSurfaceEnrichmentPlanError(
            "open-interest surface query identities are not unique"
        )
    years = Counter(str(item["params"]["date"])[:4] for item in oi_queries)

    body = {
        "contract": CONTRACT,
        "status": "PLANNED_ZERO_PROVIDER_READS",
        "source_plan_fingerprint": source_plan["plan_fingerprint"],
        "decision_spot_fingerprint": source_plan["decision_spot_fingerprint"],
        "provider_candidate": PROVIDER_CANDIDATE,
        "open_interest_stage": {
            "endpoint": OPEN_INTEREST_ENDPOINT,
            "request_count": len(oi_queries),
            "requests": oi_queries,
            "by_year": dict(sorted(years.items())),
            "semantics": (
                "OPRA open interest reported around 06:30 ET and representing "
                "previous-trading-day end open interest"
            ),
            "expiration": "*",
            "strike": "*",
            "right": "call",
            "max_dte": EXPECTED_MAX_DTE,
            "strike_range": None,
        },
        "pre_greeks_filter": {
            "dte_calendar_days": [PHASE13_OPTION_MIN_DTE, PHASE13_OPTION_MAX_DTE],
            "minimum_open_interest": PHASE13_OPTION_MIN_OPEN_INTEREST,
            "maximum_spread_to_mid": PHASE13_OPTION_MAX_SPREAD_TO_MID,
            "delta_filter_deferred_until_greeks": True,
            "selection_authority": False,
        },
        "greeks_stage": {
            "endpoint": BINOMIAL_GREEKS_ENDPOINT,
            "request_creation": "DYNAMIC_AFTER_QUOTE_AND_OPEN_INTEREST_JOIN",
            "one_request_per_surviving_underlying_date_expiration": True,
            "expiration": "SPECIFIC_PRE_GREEKS_SURVIVING_EXPIRATION",
            "strike": "*",
            "right": "call",
            "date": "SAME_DECISION_DATE",
            "start_time": DECISION_CLOCK_ET,
            "end_time": DECISION_CLOCK_ET,
            "interval": "1m",
            "annual_dividend": "REQUIRED_PIT_INPUT_NO_SILENT_ZERO_DEFAULT",
            "rate_type": GREEKS_RATE_TYPE,
            "version": GREEKS_VERSION,
            "binomial_steps": GREEKS_BINOMIAL_STEPS,
            "strike_range": None,
            "provider_model": "LEISEN_REIMER_BINOMIAL_TREE_EARLY_EXERCISE",
            "rho_vega_provider_units_require_divide_by_100": True,
            "selection_authority": False,
        },
        "later_stages": {
            "authoritative_delta_filter_after_dividend_aware_greeks": True,
            "volume_context_required_before_full_option_economics": True,
            "exact_exit_quote_only_after_entry_contract_selection": True,
        },
        "provider_requests": 0,
        "provider_writes": 0,
        "option_outcomes_read": 0,
        "single_contract_selected": False,
        "historical_fill_authority": False,
        "historical_account_pnl_authority": False,
        "strategy_evidence_authority": False,
        "paper_authority": False,
        "live_authority": False,
    }
    body["enrichment_plan_fingerprint"] = _fingerprint(body)
    return body


def _identity(row: dict[str, Any]) -> tuple[str, float, str]:
    try:
        expiration = date.fromisoformat(str(row["expiration"])[:10]).isoformat()
        strike = float(row["strike"])
        right = str(row["right"]).lower()
    except (KeyError, TypeError, ValueError) as exc:
        raise ThetaDataSurfaceEnrichmentPlanError(
            "option surface row identity malformed"
        ) from exc
    if not math.isfinite(strike) or strike <= 0 or right != "call":
        raise ThetaDataSurfaceEnrichmentPlanError(
            "option surface row identity invalid"
        )
    return expiration, strike, right


def build_binomial_greeks_demand(
    *,
    symbol: str,
    date_et: str,
    quote_rows: Sequence[dict[str, Any]],
    open_interest_rows: Sequence[dict[str, Any]],
    annual_dividend: float | None,
) -> dict[str, Any]:
    """Build only the expiration requests that survive quote/OI causal screening."""

    day = date.fromisoformat(date_et)
    if annual_dividend is not None and (
        not math.isfinite(float(annual_dividend)) or annual_dividend < 0
    ):
        raise ThetaDataSurfaceEnrichmentPlanError(
            "historical annual dividend must be finite and nonnegative"
        )

    oi_by_contract: dict[tuple[str, float, str], int] = {}
    for row in open_interest_rows:
        key = _identity(row)
        if str(row.get("symbol")) != symbol:
            raise ThetaDataSurfaceEnrichmentPlanError(
                "open-interest row underlying changed"
            )
        try:
            oi = int(row["open_interest"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ThetaDataSurfaceEnrichmentPlanError(
                "open-interest row value malformed"
            ) from exc
        if oi < 0:
            raise ThetaDataSurfaceEnrichmentPlanError(
                "open-interest row value negative"
            )
        oi_by_contract[key] = oi

    survivor_expirations: set[str] = set()
    evaluated = 0
    for row in quote_rows:
        key = _identity(row)
        if str(row.get("symbol")) != symbol:
            raise ThetaDataSurfaceEnrichmentPlanError(
                "quote row underlying changed"
            )
        expiration, _, _ = key
        dte = (date.fromisoformat(expiration) - day).days
        if not PHASE13_OPTION_MIN_DTE <= dte <= PHASE13_OPTION_MAX_DTE:
            continue
        try:
            bid = float(row["bid"])
            ask = float(row["ask"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ThetaDataSurfaceEnrichmentPlanError(
                "quote row bid/ask malformed"
            ) from exc
        if (
            not math.isfinite(bid)
            or not math.isfinite(ask)
            or bid < 0
            or ask < bid
        ):
            raise ThetaDataSurfaceEnrichmentPlanError(
                "quote row bid/ask invalid"
            )
        mid = (bid + ask) / 2.0
        if mid <= 0:
            continue
        evaluated += 1
        spread_to_mid = (ask - bid) / mid
        if (
            spread_to_mid <= PHASE13_OPTION_MAX_SPREAD_TO_MID
            and oi_by_contract.get(key, 0) >= PHASE13_OPTION_MIN_OPEN_INTEREST
        ):
            survivor_expirations.add(expiration)

    if annual_dividend is None:
        status = (
            "BLOCKED_HISTORICAL_DIVIDEND_CONTEXT_REQUIRED"
            if survivor_expirations
            else "NO_PRE_GREEKS_SURVIVORS"
        )
        queries: list[dict[str, Any]] = []
    else:
        status = (
            "GREEKS_DEMAND_READY"
            if survivor_expirations
            else "NO_PRE_GREEKS_SURVIVORS"
        )
        queries = []
        for expiration in sorted(survivor_expirations):
            payload = {
                "request_type": "THETADATA_BINOMIAL_FIRST_ORDER_GREEKS_AT_DECISION_MINUTE",
                "symbol": symbol,
                "expiration": expiration,
                "date_et": date_et,
                "time_of_day_et": DECISION_CLOCK_ET,
                "annual_dividend": float(annual_dividend),
                "rate_type": GREEKS_RATE_TYPE,
                "version": GREEKS_VERSION,
                "binomial_steps": GREEKS_BINOMIAL_STEPS,
            }
            queries.append({
                "endpoint": BINOMIAL_GREEKS_ENDPOINT,
                "params": {
                    "symbol": symbol,
                    "expiration": expiration.replace("-", ""),
                    "strike": "*",
                    "right": "call",
                    "date": date_et.replace("-", ""),
                    "start_time": DECISION_CLOCK_ET,
                    "end_time": DECISION_CLOCK_ET,
                    "interval": "1m",
                    "annual_dividend": float(annual_dividend),
                    "rate_type": GREEKS_RATE_TYPE,
                    "version": GREEKS_VERSION,
                    "binomial_steps": GREEKS_BINOMIAL_STEPS,
                    "strike_range": None,
                    "format": "json",
                },
                "query_fingerprint": _fingerprint(payload),
            })

    body = {
        "contract": CONTRACT,
        "status": status,
        "symbol": symbol,
        "date_et": date_et,
        "quote_rows": len(quote_rows),
        "open_interest_rows": len(open_interest_rows),
        "phase13_dte_spread_oi_rows_evaluated": evaluated,
        "surviving_expirations": sorted(survivor_expirations),
        "annual_dividend": annual_dividend,
        "greeks_requests": queries,
        "provider_requests": 0,
        "single_contract_selected": False,
        "historical_fill_authority": False,
        "strategy_evidence_authority": False,
    }
    body["demand_fingerprint"] = _fingerprint(body)
    return body
