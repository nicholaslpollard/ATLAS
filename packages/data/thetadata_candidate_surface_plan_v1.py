from __future__ import annotations

"""Zero-provider plan for ThetaData 09:35 historical option candidate surfaces.

Consumes the immutable multiyear option-decision-spot artifact. It does not contact
ThetaData or any other provider. The plan freezes provider request shapes only after
the stock-side 09:35 decision spot is causally known.

No strike or expiration is preselected. The current ThetaData v3 at-time quote
endpoint supports expiration="*", max_dte, and all strikes at one timestamp, which
matches the provider-agnostic candidate-surface contract emitted by the decision-spot
gate. Contract selection remains downstream of observed causal quote/liquidity,
locally derived Greeks/IV, DTE, event context, and the universal economic gate.
"""

from collections import Counter
from datetime import date, datetime
from typing import Any, Sequence

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.simulation.multiyear_option_decision_spot_v1 import (
    CONTRACT as DECISION_SPOT_CONTRACT,
)

CONTRACT = "atlas-thetadata-candidate-surface-source-plan-v1"
OUTPUT_REL = "data/options/manifests/thetadata_candidate_surface_source_plan_v1"

# Current official retail/docs observations verified 2026-10-02/03.
# These are planning metadata, not provider-entitlement evidence.
PROVIDER_CANDIDATE = {
    "provider": "ThetaData",
    "api_generation": "v3",
    "terminal_required": True,
    "target_subscription": "Options Standard",
    "retail_monthly_price_usd_observed": 80,
    "retail_history_marketing_observed": "10 years",
    "documented_concurrent_requests_observed": 4,
    "quote_source": "OPRA_NBBO",
    "at_time_endpoint": "/v3/option/at_time/quote",
    "at_time_semantics_observed":
        "last NBBO quote reported by OPRA at the specified millisecond of the day",
    "minute_boundary_preferred_with_expiration_wildcard": True,
    "surface_expiration": "*",
    "surface_strike": "*",
    "surface_right": "call",
    "qualification_authority": False,
    "full_acquisition_authority": False,
}

EXPECTED_CLOCK_READY = 9667
EXPECTED_DECISION_READY = 9654
EXPECTED_DECISION_MISSING = 13
EXPECTED_UNIQUE_SURFACES = 9455
EXPECTED_MAX_DTE = 75


class ThetaDataCandidateSurfacePlanError(ValueError):
    pass


def _validate_report(report: dict[str, Any]) -> None:
    _check_signature(report, "decision_spot_fingerprint")
    demand = report.get("candidate_entry_surface_demand")
    rows = report.get("rows")
    if (
        report.get("contract") != DECISION_SPOT_CONTRACT
        or report.get("clock_ready_case_denominator") != EXPECTED_CLOCK_READY
        or report.get("decision_spot_ready_cases") != EXPECTED_DECISION_READY
        or report.get("decision_spot_missing_cases") != EXPECTED_DECISION_MISSING
        or not isinstance(rows, list)
        or len(rows) != EXPECTED_CLOCK_READY
        or not isinstance(demand, dict)
        or demand.get("case_members") != EXPECTED_DECISION_READY
        or demand.get("unique_underlying_date_clock_queries") != EXPECTED_UNIQUE_SURFACES
        or demand.get("right") != "call"
        or demand.get("max_dte_calendar_days") != EXPECTED_MAX_DTE
        or demand.get("single_strike_preselection") is not False
        or demand.get("provider_specific_request_shape_authorized") is not False
        or not isinstance(demand.get("demands"), list)
        or len(demand["demands"]) != EXPECTED_UNIQUE_SURFACES
        or report.get("provider_requests") != 0
        or report.get("option_prices_read") != 0
        or report.get("option_outcomes_read") != 0
        or report.get("historical_fill_authority") is not False
        or report.get("strategy_evidence_authority") is not False
        or report.get("paper_authority") is not False
        or report.get("live_authority") is not False
    ):
        raise ThetaDataCandidateSurfacePlanError(
            "option decision-spot lineage/authority changed"
        )


def _normalize_surface(item: dict[str, Any]) -> dict[str, Any]:
    required = {
        "request_type",
        "symbol",
        "date_et",
        "time_of_day_et",
        "right",
        "max_dte_calendar_days",
        "expiration_policy",
        "strike_policy",
        "query_fingerprint",
        "member_case_ids",
        "member_case_count",
    }
    if set(item) != required:
        raise ThetaDataCandidateSurfacePlanError("candidate-surface schema changed")
    if (
        item["request_type"] != "OPTION_CALL_CANDIDATE_SURFACE_AT_DECISION_CLOCK"
        or item["right"] != "call"
        or int(item["max_dte_calendar_days"]) != EXPECTED_MAX_DTE
        or item["expiration_policy"] != "ALL_EXPIRATIONS_WITHIN_PROVIDER_MAX_DTE"
        or item["strike_policy"] != "CANDIDATE_SURFACE_NOT_PRESELECTED_STRIKE"
    ):
        raise ThetaDataCandidateSurfacePlanError(
            "candidate-surface scientific request shape changed"
        )
    try:
        day = date.fromisoformat(str(item["date_et"]))
        clock = datetime.strptime(
            str(item["time_of_day_et"]), "%H:%M:%S.%f"
        ).time()
    except ValueError as exc:
        raise ThetaDataCandidateSurfacePlanError(
            "candidate-surface date/clock malformed"
        ) from exc
    if not date(2021, 1, 1) <= day <= date(2025, 12, 31):
        raise ThetaDataCandidateSurfacePlanError(
            "candidate-surface escaped 2021-2025 target"
        )
    if (clock.hour, clock.minute, clock.second, clock.microsecond) != (9, 35, 0, 0):
        raise ThetaDataCandidateSurfacePlanError(
            "candidate-surface decision clock is no longer 09:35 ET"
        )
    members = sorted(set(str(value) for value in item["member_case_ids"]))
    if not members or len(members) != int(item["member_case_count"]):
        raise ThetaDataCandidateSurfacePlanError(
            "candidate-surface member identities malformed"
        )
    payload = {
        "request_type": item["request_type"],
        "symbol": str(item["symbol"]),
        "date_et": day.isoformat(),
        "time_of_day_et": str(item["time_of_day_et"]),
        "right": "call",
        "max_dte_calendar_days": EXPECTED_MAX_DTE,
        "expiration_policy": item["expiration_policy"],
        "strike_policy": item["strike_policy"],
    }
    if _fingerprint(payload) != item["query_fingerprint"]:
        raise ThetaDataCandidateSurfacePlanError(
            "candidate-surface query fingerprint changed"
        )
    return {
        **payload,
        "query_fingerprint": item["query_fingerprint"],
        "member_case_ids": members,
        "member_case_count": len(members),
    }


def _provider_query(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "endpoint": PROVIDER_CANDIDATE["at_time_endpoint"],
        "params": {
            "symbol": item["symbol"],
            "expiration": "*",
            "strike": "*",
            "right": "call",
            "start_date": item["date_et"].replace("-", ""),
            "end_date": item["date_et"].replace("-", ""),
            "time_of_day": item["time_of_day_et"],
            "max_dte": EXPECTED_MAX_DTE,
            "strike_range": None,
            "format": "json",
        },
        "source_query_fingerprint": item["query_fingerprint"],
        "member_case_ids": item["member_case_ids"],
        "member_case_count": item["member_case_count"],
    }


def _qualification_anchors(
    surfaces: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Select deterministic outcome-blind surface anchors across every target year."""
    ordered = sorted(
        surfaces,
        key=lambda item: (
            item["date_et"],
            item["symbol"],
            item["query_fingerprint"],
        ),
    )
    chosen: list[tuple[str, dict[str, Any]]] = []
    for year in range(2021, 2026):
        year_rows = [item for item in ordered if item["date_et"].startswith(str(year))]
        if not year_rows:
            raise ThetaDataCandidateSurfacePlanError(
                f"no candidate surfaces for qualification year {year}"
            )
        positions = (
            ("FIRST", year_rows[0]),
            ("MIDDLE", year_rows[len(year_rows) // 2]),
            ("LAST", year_rows[-1]),
        )
        for label, item in positions:
            chosen.append((f"YEAR_{year}_{label}", item))

    by_fp: dict[str, dict[str, Any]] = {}
    for reason, item in chosen:
        record = by_fp.get(item["query_fingerprint"])
        if record is None:
            record = {
                "qualification_reasons": [reason],
                "date_et": item["date_et"],
                "time_of_day_et": item["time_of_day_et"],
                "symbol": item["symbol"],
                "decision_spot_query_fingerprint": item["query_fingerprint"],
                "query": _provider_query(item),
            }
            by_fp[item["query_fingerprint"]] = record
        else:
            record["qualification_reasons"].append(reason)

    anchors = sorted(
        by_fp.values(),
        key=lambda item: (
            item["date_et"],
            item["symbol"],
            item["decision_spot_query_fingerprint"],
        ),
    )
    for index, item in enumerate(anchors, start=1):
        item["anchor_index"] = index
        item["qualification_reasons"] = sorted(set(item["qualification_reasons"]))
    return anchors


def build_thetadata_candidate_surface_source_plan(
    report: dict[str, Any],
) -> dict[str, Any]:
    _validate_report(report)
    demand = report["candidate_entry_surface_demand"]
    surfaces = [_normalize_surface(item) for item in demand["demands"]]
    if len({item["query_fingerprint"] for item in surfaces}) != len(surfaces):
        raise ThetaDataCandidateSurfacePlanError(
            "candidate-surface query identities are not unique"
        )

    years = Counter(item["date_et"][:4] for item in surfaces)
    symbols = {item["symbol"] for item in surfaces}
    grouped_cases = sum(int(item["member_case_count"]) for item in surfaces)
    anchors = _qualification_anchors(surfaces)

    body = {
        "contract": CONTRACT,
        "status": "PLANNED_ZERO_PROVIDER_READS",
        "decision_spot_fingerprint": report["decision_spot_fingerprint"],
        "provider_candidate": PROVIDER_CANDIDATE,
        "target_scope": {
            "clock_ready_case_denominator": EXPECTED_CLOCK_READY,
            "decision_spot_ready_cases": EXPECTED_DECISION_READY,
            "decision_spot_missing_cases": EXPECTED_DECISION_MISSING,
            "candidate_surface_case_members": grouped_cases,
            "unique_surface_requests": len(surfaces),
            "unique_underlyings": len(symbols),
            "date_min": min(item["date_et"] for item in surfaces),
            "date_max": max(item["date_et"] for item in surfaces),
            "by_year": dict(sorted(years.items())),
            "decision_clock_et": "09:35:00.000",
            "right": "call",
            "max_dte_calendar_days": EXPECTED_MAX_DTE,
        },
        "provider_request_contract": {
            "requests_if_fully_acquired": len(surfaces),
            "one_request_per_underlying_date_decision_clock": True,
            "expiration": "*",
            "strike": "*",
            "right": "call",
            "max_dte": EXPECTED_MAX_DTE,
            "strike_range": None,
            "why_no_strike_range": (
                "do not exclude a contract before observed causal quote/liquidity and "
                "local option-economics inputs can evaluate it"
            ),
            "minute_boundary_clock": True,
            "full_surface_queries": [_provider_query(item) for item in surfaces],
        },
        "qualification": {
            "outcome_blind": True,
            "selection_fields": [
                "year",
                "chronological_position",
                "underlying_identity",
                "decision_clock",
            ],
            "anchor_query_count": len(anchors),
            "anchors": anchors,
            "required_checks_after_provider_read": [
                "oldest 2021 surface is entitled and retrievable",
                "response rows retain requested underlying and CALL right",
                "response timestamps never exceed the 09:35 ET request clock",
                "returned expirations are nonexpired and within max_dte",
                "returned strikes are finite and positive with no duplicate contract identity",
                "bid/ask prices and displayed sizes have stable units/types",
                "positive two-sided rows never have bid above ask",
                "explicit NO_DATA remains distinct from transport/permission failure",
                "repeat request produces identical normalized historical surface",
                "raw response bytes and exact request parameters are SHA/receipt bound",
            ],
            "full_acquisition_authorized": False,
        },
        "downstream_contract_selection": {
            "single_contract_selected_here": False,
            "phase13_eligible_dte_window_days": [14, 45],
            "phase13_abs_delta_window": [0.35, 0.65],
            "phase13_min_open_interest": 100,
            "phase13_max_spread_to_mid": 0.15,
            "historical_iv_greeks_source":
                "LOCAL_MODEL_DERIVED_FROM_OBSERVED_QUOTE_WITH_PIT_RATE_DIVIDEND_INPUTS",
            "open_interest_source_required_separately": True,
            "exact_exit_quote_deferred_until_entry_contract_selected": True,
        },
        "provider_requests": 0,
        "provider_writes": 0,
        "option_prices_read": 0,
        "option_outcomes_read": 0,
        "historical_fill_authority": False,
        "historical_account_pnl_authority": False,
        "strategy_evidence_authority": False,
        "paper_authority": False,
        "live_authority": False,
    }
    body["plan_fingerprint"] = _fingerprint(body)
    return body
