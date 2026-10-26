from __future__ import annotations

"""V16 integrated SPY options-native PILOT acquisition/exit/readiness census.

Single offline sweep of the frozen 411 historical 10:00 weekly CALL+PUT
entry-request identities, already acquired V12 source evidence, immutable
V14 indices and V15 in-memory diagnostic pair geometry. Independently
plans five post-entry 10:00 XNYS exit-review source dates per entry,
deduplicates original query fingerprints and never mistakes uncollected
future exit quotes for completed outcomes.

This is an acquisition and simulator-readiness plan, NOT a simulator or
backtest. The frozen pilot requires PIT spot, 21 prior closes, OI,
American-model rates/dividends/Greeks, timestamp availability, true fill
events/fees, exercise and exit evidence that cannot be inferred from
a diagnostic quote or a synthetic test. No protected returns read.
"""

from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.hybrid_options_at_time_one_call_v1 import (
    PINNED_MANIFEST_FINGERPRINT, _load_full_manifest,
)
from packages.data.hybrid_options_at_time_source_gate_v1 import validate_exact_request
from packages.data.hybrid_options_derived_dte_index_v1 import ELIGIBLE_STATES
from packages.data.hybrid_options_unattended_campaign_v1 import _inspect_attempt
from packages.data.hybrid_options_source_linked_research_reader_v1 import (
    HybridSourceLinkedReaderError,
    read_selected_original_observations, summarize_selected_chain,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.strategies.options_native_pilot_v1_contract import (
    DATA_FINGERPRINT, MAX_DTE, MAX_HOLD_SESSIONS,
    MIN_DTE, SPECIFICATION_FINGERPRINT,
)

CONTRACT = "atlas-options-native-accelerated-entry-exit-readiness-v16"
EXPECTED_ENTRIES = 411
EXPECTED_ALL_AT_TIME = 9866
SPY_ORIGIN = "FROZEN_SPY_WEEKLY_OPTIONS_NATIVE"
ENDPOINT = "/v3/option/at_time/quote"
SPY_2025_PRIOR_SAVED = "2025-06-09"

BLOCKERS = (
    "ENTRY_SOURCE_CHAIN_COMPLETENESS_UNPROVEN",
    "OPTION_QUOTE_HISTORICAL_AVAILABILITY_CLOCK_UNPROVEN",
    "PIT_SPY_SPOT_AND_PRIOR_20_ECONOMIC_RETURNS_NOT_BOUND",
    "PIT_SPLIT_DIVIDEND_RATE_CURVE_NOT_BOUND",
    "PRIOR_STATE_OPTION_OPEN_INTEREST_NOT_BOUND",
    "AMERICAN_MODEL_IV_GREEKS_NOT_BOUND",
    "CONTRACT_DELIVERABLE_MULTIPLIER_NOT_VERIFIED",
    "OPTIONS_HOURS_AND_EXECUTION_FEES_NOT_QUALIFIED",
    "EXACT_EXIT_REVIEW_SOURCES_AND_FILLED_ORDER_EVENTS_MISSING",
    "COMPLETE_ACCOUNT_REPLAY_NOT_AUTHORIZED",
)


class NativePilotAcceleratedReadinessError(ValueError):
    pass


def _exit_review_sessions(entry: date) -> tuple[date, ...]:
    calendar = get_market_calendar("XNYS")
    future = calendar.sessions_in_range(entry, entry + timedelta(days=18))
    sessions = tuple(
        item.date() if isinstance(item, datetime) else item
        for item in future
    )
    days = tuple(day for day in sessions if day > entry)
    if len(days) < MAX_HOLD_SESSIONS:
        raise NativePilotAcceleratedReadinessError(
            "INSUFFICIENT_POST_ENTRY_XNYS_SESSIONS"
        )
    return days[:MAX_HOLD_SESSIONS]


def _exit_at_time_query(day: date) -> dict[str, Any]:
    stamp = day.strftime("%Y%m%d")
    params = {
        "symbol": "SPY", "expiration": "*", "strike": "*",
        "right": "both", "start_date": stamp, "end_date": stamp,
        "time_of_day": "10:00:00.000", "max_dte": MAX_DTE,
        "strike_range": 2, "format": "json",
    }
    return {
        "endpoint": ENDPOINT, "params": params,
        "query_id": _fingerprint({
            "provider": "thetadata", "endpoint": ENDPOINT, "params": params,
        }),
        "session_et": day.isoformat(),
        "source_role": "POST_ENTRY_MARK_REVIEW_NOT_FILL",
        "provider_requests": 0,
        "source_complete": False,
        "simulator_ready": False,
    }


def review_native_pilot_acquisition_readiness(
    settings: AtlasSettings, manifest: Path, candidate_plan: Path,
    *, with_quote_geometry: bool = True,
) -> dict[str, Any]:
    settings.assert_external_storage_binding("options")
    frozen = _load_full_manifest(settings, manifest, candidate_plan)
    if (frozen["manifest_fingerprint"] != PINNED_MANIFEST_FINGERPRINT
            or frozen["source_request_count"] != EXPECTED_ALL_AT_TIME):
        raise NativePilotAcceleratedReadinessError("FROZEN_PLAN_IDENTITY_CHANGED")
    spy = [row for row in frozen["requests"] if row["origin"] == SPY_ORIGIN]
    if (len(spy) != EXPECTED_ENTRIES
            or len({r["query_id"] for r in spy}) != EXPECTED_ENTRIES):
        raise NativePilotAcceleratedReadinessError("SPY_ENTRY_INVENTORY_NOT_411")
    # V9 assigns globally unique priorities across BOTH frozen branches,
    # with qualification anchors and dates interleaved. SPY-only priority
    # numbers therefore have legitimate gaps and cannot equal 1..411.
    # The pinned full-manifest loader already verifies original ordering;
    # retain a defensive unique/bounded check without renumbering rows.
    spy.sort(key=lambda r: r["priority"])
    priorities = [row["priority"] for row in spy]
    if (any(type(p) is not int or not 1 <= p <= EXPECTED_ALL_AT_TIME
            for p in priorities)
            or len(set(priorities)) != EXPECTED_ENTRIES):
        raise NativePilotAcceleratedReadinessError(
            "SPY_GLOBAL_PRIORITIES_NOT_UNIQUE_OR_BOUNDED"
        )
    known_source_ids = {row["query_id"] for row in spy}
    source_states = Counter()
    quote_stats = Counter()
    exit_requests: dict[str, dict[str, Any]] = {}
    exit_demand_uses = 0
    entry_coverage = []
    for row in spy:
        sdk = validate_exact_request(row)
        state = _inspect_attempt(settings, row["query_id"])
        if (sdk["symbol"] != "SPY"
                or sdk["time_of_day_et"] != "10:00:00.000"
                or sdk["right"] != "both"
                or sdk["max_dte"] != MAX_DTE
                or sdk["strike_range"] != 2):
            raise NativePilotAcceleratedReadinessError("ENTRY_SCOPE_DRIFT")
        day = date.fromisoformat(row["date_et"])
        is_prior = row["date_et"] == SPY_2025_PRIOR_SAVED
        if is_prior and state != "UNATTEMPTED":
            raise NativePilotAcceleratedReadinessError(
                "LEGACY_SPY_SOURCE_DID_NOT_REMAIN_SEPARATE"
            )
        source_states["external_saved" if is_prior else state] += 1
        if state in ELIGIBLE_STATES:
            if with_quote_geometry:
                try:
                    source = read_selected_original_observations(settings, row)
                    # Frozen SPY pilot: 30–45 calendar DTE, <=30s quote ages;
                    # *also* requires <=1s pair skew, OI, PIT spot, etc.
                    geometry = summarize_selected_chain(
                        source, dte_min=MIN_DTE, dte_max=MAX_DTE,
                        max_quote_age_seconds=30,
                        max_spread_to_mid=0.15,
                    )
                except HybridSourceLinkedReaderError as exc:
                    # Fixed local V15 error codes plus the exact frozen
                    # source identity; preserve fail-closed source validation.
                    raise NativePilotAcceleratedReadinessError(
                        "SPY_SOURCE_LINKED_RESEARCH_FAILED"
                        f" date={row['date_et']}"
                        f" query_id={row['query_id']}"
                        f" code={exc}"
                    ) from exc
                quote_stats["research_window_rows"] += geometry[
                    "research_window_observed_rows"
                ]
                quote_stats["observed_pairs"] += geometry[
                    "observed_call_put_strike_pairs"
                ]
                quote_stats["fresh_spread_pairs_only"] += geometry[
                    "observed_pairs_passing_freshness_spread_only"
                ]
                quote_stats["non_displayed_rows"] += geometry.get(
                    "research_window_non_displayed_rows", 0
                )
                quote_stats["stale_rows"] += geometry["research_window_stale_rows"]
                quote_stats["wide_rows"] += geometry[
                    "research_window_wide_spread_rows"
                ]
                quote_stats["indexed_entry_clocks"] += 1
        elif state.startswith("RAW_ARCHIVED"):
            raise NativePilotAcceleratedReadinessError(
                "ARCHIVED_NONQUALIFIED_ENTRY_SOURCE"
            )
        for review in _exit_review_sessions(day):
            item = _exit_at_time_query(review)
            qid = item["query_id"]
            exit_requests[qid] = item
            exit_demand_uses += 1
        entry_coverage.append({
            "date_et": row["date_et"],
            "query_id": row["query_id"],
            "state": ("ORIGINAL_2025_SPY_EVIDENCE_SEPARATE"
                      if is_prior else state),
            "source_role": "WEEKLY_ENTRY_DECISION_ONLY",
            "source_is_execution_admissible": False,
        })
    if exit_demand_uses != EXPECTED_ENTRIES * MAX_HOLD_SESSIONS:
        raise NativePilotAcceleratedReadinessError(
            "EXIT_REVIEW_SESSION_INVENTORY_CHANGED"
        )
    exit_reusable = sum(qid in known_source_ids for qid in exit_requests)
    missing_ext = sorted(
        (item for qid, item in exit_requests.items()
         if qid not in known_source_ids),
        key=lambda item: (item["session_et"], item["query_id"]),
    )
    stats = dict(sorted(source_states.items()))
    count = sum(source_states.values())
    if count != EXPECTED_ENTRIES:
        raise NativePilotAcceleratedReadinessError("ENTRY_COVERAGE_RECONCILIATION")
    reported = {
        "contract": CONTRACT,
        "status": "FROZEN_NATIVE_SPY_PILOT_ACQUISITION_AND_SIMULATOR_GAPS",
        "frozen_specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "frozen_data_contract_fingerprint": DATA_FINGERPRINT,
        "frozen_manifest_fingerprint": PINNED_MANIFEST_FINGERPRINT,
        "entry_required": EXPECTED_ENTRIES,
        "entry_states": stats,
        "entry_covered_v12_sources": (
            stats.get("RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC", 0)
            + stats.get("RAW_ARCHIVED_SCOPE_DIAGNOSTIC", 0)
        ),
        "separately_saved_2025_spy_diagnostic": stats.get("external_saved", 0),
        "entry_outstanding_unattempted": stats.get("UNATTEMPTED", 0),
        "entry_source_states": entry_coverage,
        "pilot_native_min_dte": MIN_DTE,
        "pilot_native_max_dte": MAX_DTE,
        "pilot_native_max_quote_age_seconds": 30,
        "pilot_native_max_call_put_observation_skew_seconds": 1,
        "pilot_quote_diagnostics": dict(sorted(quote_stats.items())),
        "exit_review_uses": exit_demand_uses,
        "distinct_exit_review_queries": len(exit_requests),
        "exit_queries_reusing_frozen_entry_scope": exit_reusable,
        "additional_distinct_exit_review_queries": len(missing_ext),
        "additional_exit_source_request_ids": [
            item["query_id"] for item in missing_ext
        ],
        "remaining_simulator_blockers": list(BLOCKERS),
        "provider_quote_max_dte_semantics_proven": False,
        "entry_execution_ready": False,
        "exit_execution_ready": False,
        "strategy_promotion_authorized": False,
        "simulator_ready": False,
        "provider_requests": 0,
        "broker_requests": 0,
        "protected_outcomes_read": 0,
        "simulations_run": 0,
        "files_written": 0,
    }
    reported["fingerprint"] = _fingerprint(reported)
    return reported
