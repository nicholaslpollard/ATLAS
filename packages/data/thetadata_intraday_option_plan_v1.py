from __future__ import annotations

"""Zero-provider plan for intraday historical option NBBO source qualification.

Consumes only the immutable intraday stock-exit clock report. It does not contact
ThetaData, MarketData.app, OPRA, a broker, or any other provider.

The plan has two purposes:

1. Prove that the requested clocks/contract identities are internally suitable for
   a historical at-time NBBO provider.
2. Build a small, outcome-blind qualification sample plus exact acquisition
   accounting before the operator purchases or authorizes a provider subscription.

The current candidate is ThetaData Options Standard. This plan deliberately does
not treat public entitlement documentation as observed data authority. The oldest
required 2021 sample must be proven by a later provider qualification run.
"""

from collections import Counter, defaultdict
from datetime import date, datetime
import math
from typing import Any, Iterable, Sequence
from zoneinfo import ZoneInfo

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.simulation.multiyear_intraday_stock_exit_clock_v1 import (
    CONTRACT as INTRADAY_CLOCK_CONTRACT,
)

CONTRACT = "atlas-thetadata-intraday-option-source-plan-v1"
OUTPUT_REL = "data/options/manifests/thetadata_intraday_option_source_plan_v1"
EASTERN = ZoneInfo("America/New_York")

# Public documentation observed 2026-10-02. These are planning assumptions only.
# A later read-only qualification must independently prove entitlement and response
# semantics before the full demand set may be acquired.
PROVIDER_CANDIDATE = {
    "provider": "ThetaData",
    "api_generation": "v3",
    "terminal_required": True,
    "target_subscription": "Options Standard",
    "retail_monthly_price_usd_observed": 80,
    "retail_history_marketing_observed": "8 years",
    "subscription_table_first_access_date_observed": "2016-01-01",
    "documented_concurrent_requests_observed": 4,
    "quote_source": "OPRA_NBBO",
    "at_time_endpoint": "/v3/option/at_time/quote",
    "history_quote_endpoint": "/v3/option/history/quote",
    "provider_granularity_observed": "tick level",
    "requested_clock_resolution": "minute boundary",
    "clock_timezone": "America/New_York",
    "at_time_semantics_observed":
        "last NBBO quote reported by OPRA at the specified millisecond of the day",
    "qualification_authority": False,
    "full_acquisition_authority": False,
}

EXPECTED_CASES = 9974
EXPECTED_CLOCK_READY = 9667
EXPECTED_EXACT_DEMANDS = 18921


class ThetaDataIntradayOptionPlanError(ValueError):
    pass


def _time_minutes(text: str) -> int:
    try:
        parsed = datetime.strptime(text, "%H:%M:%S.%f").time()
    except ValueError as exc:
        raise ThetaDataIntradayOptionPlanError(
            f"invalid ET demand time: {text}"
        ) from exc
    if parsed.second != 0 or parsed.microsecond != 0:
        raise ThetaDataIntradayOptionPlanError(
            "intraday option demand is not aligned to a whole minute"
        )
    return parsed.hour * 60 + parsed.minute


def _validate_report(report: dict[str, Any]) -> None:
    _check_signature(report, "intraday_clock_fingerprint")
    demand = report.get("option_quote_demand")
    rows = report.get("rows")
    if (
        report.get("contract") != INTRADAY_CLOCK_CONTRACT
        or report.get("pre2026_call_policy_stock_exit_cases") != EXPECTED_CASES
        or report.get("clock_ready_cases") != EXPECTED_CLOCK_READY
        or not isinstance(demand, dict)
        or demand.get("entry_case_members") != EXPECTED_CLOCK_READY
        or demand.get("exit_case_members") != EXPECTED_CLOCK_READY
        or demand.get("unique_at_time_nbbo_queries") != EXPECTED_EXACT_DEMANDS
        or demand.get("provider_requests_performed") != 0
        or demand.get("selection_uses_option_price_or_future_liquidity") is not False
        or not isinstance(demand.get("demands"), list)
        or len(demand["demands"]) != EXPECTED_EXACT_DEMANDS
        or not isinstance(rows, list)
        or len(rows) != EXPECTED_CASES
        or report.get("provider_requests") != 0
        or report.get("protected_2026_outcomes_read") != 0
        or report.get("historical_account_pnl_authority") is not False
        or report.get("strategy_evidence_authority") is not False
    ):
        raise ThetaDataIntradayOptionPlanError(
            "intraday stock-exit clock report lineage or authority changed"
        )


def _normalized_demand(item: dict[str, Any]) -> dict[str, Any]:
    required = {
        "request_type",
        "option_symbol",
        "symbol",
        "expiration",
        "strike",
        "right",
        "date_et",
        "time_of_day_et",
        "query_fingerprint",
        "roles",
        "member_case_ids",
        "member_case_count",
    }
    if set(item) != required:
        raise ThetaDataIntradayOptionPlanError("option demand schema changed")
    if item["request_type"] != "AT_TIME_NBBO_OPTION_QUOTE":
        raise ThetaDataIntradayOptionPlanError("unexpected option request type")
    if item["right"] != "call":
        raise ThetaDataIntradayOptionPlanError("qualification cohort is no longer CALL-only")
    try:
        day = date.fromisoformat(str(item["date_et"]))
        expiry = date.fromisoformat(str(item["expiration"]))
        strike = float(item["strike"])
    except (TypeError, ValueError) as exc:
        raise ThetaDataIntradayOptionPlanError("option demand identity malformed") from exc
    if day < date(2021, 1, 1) or day > date(2025, 12, 31):
        raise ThetaDataIntradayOptionPlanError("option demand escaped 2021-2025 target")
    if expiry < day or not math.isfinite(strike) or strike <= 0:
        raise ThetaDataIntradayOptionPlanError("option demand expiry/strike invalid")
    minute = _time_minutes(str(item["time_of_day_et"]))
    roles = tuple(sorted(set(str(value) for value in item["roles"])))
    members = tuple(sorted(set(str(value) for value in item["member_case_ids"])))
    if (
        not roles
        or any(role not in {"ENTRY", "EXIT"} for role in roles)
        or not members
        or len(members) != int(item["member_case_count"])
    ):
        raise ThetaDataIntradayOptionPlanError("option demand roles/members malformed")

    payload = {
        "request_type": item["request_type"],
        "option_symbol": str(item["option_symbol"]),
        "symbol": str(item["symbol"]),
        "expiration": expiry.isoformat(),
        "strike": str(item["strike"]),
        "right": "call",
        "date_et": day.isoformat(),
        "time_of_day_et": str(item["time_of_day_et"]),
    }
    if _fingerprint(payload) != item["query_fingerprint"]:
        raise ThetaDataIntradayOptionPlanError("option demand query fingerprint changed")
    return {
        **payload,
        "query_fingerprint": item["query_fingerprint"],
        "roles": list(roles),
        "member_case_ids": list(members),
        "member_case_count": len(members),
        "minute_of_day_et": minute,
    }


def _contract_day_key(item: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        item["symbol"],
        item["expiration"],
        item["strike"],
        item["right"],
        item["date_et"],
    )


def _query_descriptor(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "endpoint": PROVIDER_CANDIDATE["at_time_endpoint"],
        "params": {
            "symbol": item["symbol"],
            "expiration": item["expiration"].replace("-", ""),
            "strike": item["strike"],
            "right": item["right"],
            "start_date": item["date_et"].replace("-", ""),
            "end_date": item["date_et"].replace("-", ""),
            "time_of_day": item["time_of_day_et"],
        },
        "expected_role": list(item["roles"]),
        "source_query_fingerprint": item["query_fingerprint"],
        "member_case_ids": list(item["member_case_ids"]),
    }


def _first(items: Sequence[dict[str, Any]], predicate) -> dict[str, Any] | None:
    for item in items:
        if predicate(item):
            return item
    return None


def _qualification_anchors(
    demands: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Choose source/clock anchors without option price or outcome information."""

    ordered = sorted(
        demands,
        key=lambda item: (
            item["date_et"],
            item["minute_of_day_et"],
            item["option_symbol"],
            item["query_fingerprint"],
        ),
    )
    chosen: list[tuple[str, dict[str, Any]]] = []

    for year in range(2021, 2026):
        year_rows = [item for item in ordered if item["date_et"].startswith(str(year))]
        if not year_rows:
            raise ThetaDataIntradayOptionPlanError(
                f"no exact option demands for qualification year {year}"
            )
        for role in ("ENTRY", "EXIT"):
            role_rows = [item for item in year_rows if role in item["roles"]]
            if not role_rows:
                raise ThetaDataIntradayOptionPlanError(
                    f"year {year} lacks {role} qualification clocks"
                )
            picks = (
                ("FIRST", role_rows[0]),
                ("MIDDLE", role_rows[len(role_rows) // 2]),
                ("LAST", role_rows[-1]),
            )
            for position, item in picks:
                chosen.append((f"YEAR_{year}_{role}_{position}", item))

    earliest_exit = min(
        (item for item in ordered if "EXIT" in item["roles"]),
        key=lambda item: (item["minute_of_day_et"], item["date_et"], item["option_symbol"]),
    )
    latest_exit = max(
        (item for item in ordered if "EXIT" in item["roles"]),
        key=lambda item: (item["minute_of_day_et"], item["date_et"], item["option_symbol"]),
    )
    chosen.append(("EARLIEST_EXIT_CLOCK", earliest_exit))
    chosen.append(("LATEST_EXIT_CLOCK", latest_exit))

    early_close = _first(
        ordered,
        lambda x: "EXIT" in x["roles"] and x["time_of_day_et"] == "13:00:00.000",
    )
    if early_close is not None:
        chosen.append(("EARLY_CLOSE_1300_ET", early_close))

    # Deduplicate physical query while retaining all qualification reasons.
    by_fp: dict[str, dict[str, Any]] = {}
    for reason, item in chosen:
        record = by_fp.get(item["query_fingerprint"])
        if record is None:
            record = {
                "qualification_reasons": [reason],
                "query": _query_descriptor(item),
                "date_et": item["date_et"],
                "time_of_day_et": item["time_of_day_et"],
                "option_symbol": item["option_symbol"],
            }
            by_fp[item["query_fingerprint"]] = record
        else:
            record["qualification_reasons"].append(reason)
    anchors = sorted(
        by_fp.values(),
        key=lambda item: (
            item["date_et"],
            item["time_of_day_et"],
            item["option_symbol"],
        ),
    )
    for index, item in enumerate(anchors, start=1):
        item["anchor_index"] = index
        item["qualification_reasons"] = sorted(set(item["qualification_reasons"]))
    return anchors


def build_thetadata_intraday_option_source_plan(
    report: dict[str, Any],
) -> dict[str, Any]:
    _validate_report(report)
    raw_demands = report["option_quote_demand"]["demands"]
    demands = [_normalized_demand(item) for item in raw_demands]
    if len({item["query_fingerprint"] for item in demands}) != len(demands):
        raise ThetaDataIntradayOptionPlanError("exact option demand is not unique")

    years = Counter(item["date_et"][:4] for item in demands)
    roles = Counter()
    times = Counter()
    contract_days: dict[
        tuple[str, str, str, str, str],
        list[dict[str, Any]],
    ] = defaultdict(list)
    for item in demands:
        for role in item["roles"]:
            roles[role] += 1
        times[item["time_of_day_et"]] += 1
        contract_days[_contract_day_key(item)].append(item)

    group_sizes = [len(group) for group in contract_days.values()]
    span_minutes: list[int] = []
    history_row_upper_bound = 0
    for group in contract_days.values():
        minute_values = sorted(int(item["minute_of_day_et"]) for item in group)
        span = minute_values[-1] - minute_values[0]
        span_minutes.append(span)
        history_row_upper_bound += span + 1

    minute_aligned = all(
        str(item["time_of_day_et"]).endswith(":00.000") for item in demands
    )
    target_coverage_after_2016 = all(
        date.fromisoformat(item["date_et"]) >= date(2016, 1, 1)
        for item in demands
    )
    anchors = _qualification_anchors(demands)

    report_body = {
        "contract": CONTRACT,
        "status": "PLANNED_ZERO_PROVIDER_READS",
        "intraday_clock_fingerprint": report["intraday_clock_fingerprint"],
        "provider_candidate": PROVIDER_CANDIDATE,
        "target_scope": {
            "case_members": report["clock_ready_cases"],
            "exact_at_time_nbbo_queries": len(demands),
            "date_min": min(item["date_et"] for item in demands),
            "date_max": max(item["date_et"] for item in demands),
            "by_year": dict(sorted(years.items())),
            "role_memberships": dict(sorted(roles.items())),
            "unique_clock_times_et": len(times),
            "minute_boundary_aligned": minute_aligned,
            "all_demands_on_or_after_documented_standard_first_access": (
                target_coverage_after_2016
            ),
        },
        "request_shape_analysis": {
            "exact_at_time_request_count": len(demands),
            "unique_contract_day_groups": len(contract_days),
            "contract_day_group_size": {
                "min": min(group_sizes),
                "max": max(group_sizes),
                "mean": sum(group_sizes) / len(group_sizes),
                "groups_with_multiple_exact_clocks": sum(
                    value > 1 for value in group_sizes
                ),
            },
            "contract_day_min_to_max_clock_span_minutes": {
                "min": min(span_minutes),
                "max": max(span_minutes),
                "mean": sum(span_minutes) / len(span_minutes),
            },
            "one_minute_history_min_to_max_row_upper_bound": history_row_upper_bound,
            "note": (
                "No acquisition batching is authorized here. At-time requests minimize "
                "returned data; one-minute history can reduce request count for dense "
                "same-contract/day clocks but may return many unused rows. Choose only "
                "after observed provider latency/response size qualification."
            ),
        },
        "qualification": {
            "outcome_blind": True,
            "selection_fields": [
                "year",
                "ENTRY_or_EXIT_role",
                "clock_time",
                "contract_identity",
            ],
            "anchor_query_count": len(anchors),
            "anchors": anchors,
            "required_checks_after_provider_read": [
                "entitlement includes oldest 2021 anchor",
                "HTTP/terminal success and deterministic schema",
                "requested contract identity exactly matches response",
                "response timestamp is not after requested ET clock",
                "bid/ask sizes and prices have stable units/types",
                "bid <= ask when both are positive",
                "minute-boundary at-time semantics match documented last OPRA NBBO",
                "repeat request yields identical historical row or explainable provider revision",
                "no silent nearest-contract substitution",
                "empty/no-quote response is explicit and distinct from transport failure",
                "raw response bytes and request parameters are SHA/receipt bound",
            ],
            "full_acquisition_authorized": False,
        },
        "provider_requests": 0,
        "provider_writes": 0,
        "historical_fill_authority": False,
        "historical_account_pnl_authority": False,
        "strategy_evidence_authority": False,
        "paper_authority": False,
        "live_authority": False,
    }
    report_body["plan_fingerprint"] = _fingerprint(report_body)
    return report_body
