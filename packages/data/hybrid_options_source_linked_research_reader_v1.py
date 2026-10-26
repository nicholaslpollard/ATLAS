from __future__ import annotations

"""V15 immutable-lineage historical at-time quote observation reader.

Bridges V14 source-linked positional references to bounded *in-memory*
original quote observations, not to strategy simulator inputs, option fills,
synthetic quotes, certified complete chains, or broker execution. Every
read independently checks the original V9 query, V12 receipts, full original
SDK-normalized gzip source and immutable V14 index bytes/fingerprint.
Only originally observed rows at or before the frozen decision clock and
within its requested calendar DTE can be materialized, preserving their
original fields. V15 does not write, contact providers or examine outcomes.
"""

from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from packages.core.settings import AtlasSettings
from packages.data.hybrid_options_at_time_one_call_v1 import (
    PINNED_MANIFEST_FINGERPRINT, _load_full_manifest,
)
from packages.data.hybrid_options_at_time_source_gate_v1 import (
    validate_exact_request,
)
from packages.data.hybrid_options_derived_dte_index_v1 import (
    ELIGIBLE_STATES, OUTPUT_REL, _expected_index, _index_path,
    _match_existing,
)
from packages.data.hybrid_options_saved_scope_quality_v1 import _original_rows
from packages.data.hybrid_options_unattended_campaign_v1 import (
    ROOT_REL as V12_ROOT, _inspect_attempt, _read_receipt,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.thetadata_candidate_surface_qualification_v1 import (
    _finite_number,
)

CONTRACT = "atlas-hybrid-source-linked-at-time-causal-research-reader-v15"
TZ = ZoneInfo("America/New_York")
MAX_SELECTED_QUOTES = 50_000
RESEARCH_DTE_MIN = 14
RESEARCH_DTE_MAX = 45
RESEARCH_MAX_QUOTE_AGE_SECONDS = 60
RESEARCH_MAX_SPREAD_TO_MID = 0.15


class HybridSourceLinkedReaderError(ValueError):
    pass


def read_selected_original_observations(
    settings: AtlasSettings, row: dict[str, Any],
) -> dict[str, Any]:
    """Read one source, fail closed on its immutable source or index drift.

    Returns source-original quote dictionaries *in memory* only, with
    explicit diagnostic/non-admission metadata. No result is persisted.
    """
    settings.assert_external_storage_binding("options")
    sdk = validate_exact_request(row)
    qid = row["query_id"]
    state = _inspect_attempt(settings, qid)
    if state not in ELIGIBLE_STATES:
        raise HybridSourceLinkedReaderError(
            "V12_ORIGINAL_DIAGNOSTIC_SOURCE_NOT_ELIGIBLE"
        )
    receipt = _read_receipt(
        settings.resolved_path(V12_ROOT) / "attempts"
        / qid[:2] / (qid + ".terminal.json"),
        qid, "terminal",
    )
    if receipt is None or not isinstance(receipt.get("archive"), dict):
        raise HybridSourceLinkedReaderError("SOURCE_TERMINAL_RECEIPT_MISSING")
    original = _original_rows(settings, qid, receipt["archive"])
    expected = _expected_index(row, receipt, original)
    if not _match_existing(settings, expected):
        raise HybridSourceLinkedReaderError("V14_IMMUTABLE_INDEX_NOT_PRESENT")
    positions = expected["original_row_indices"]
    if (not isinstance(positions, list)
            or len(positions) > MAX_SELECTED_QUOTES
            or len(positions) != len(set(positions))
            or any(type(p) is not int or p < 0 or p >= len(original)
                   for p in positions)
            or positions != sorted(positions)):
        raise HybridSourceLinkedReaderError("V14_POSITIONAL_INDEX_INVALID")

    selected = tuple(dict(original[p]) for p in positions)
    if len(selected) != expected["locally_selected_rows"]:
        raise HybridSourceLinkedReaderError("IN_MEMORY_SELECTION_COUNT_DRIFT")
    return {
        "contract": CONTRACT,
        "status": "CAUSAL_SOURCE_ORIGINAL_OBSERVATIONS_NOT_EXECUTABLE",
        "query_id": qid,
        "origin": row["origin"],
        "symbol": sdk["symbol"],
        "session_et": sdk["date_et"],
        "decision_clock_et": sdk["time_of_day_et"],
        "requested_right": sdk["right"],
        "requested_max_dte": sdk["max_dte"],
        "original_response_sha256": expected["original_v12_archive_sha256"],
        "original_receipt_fingerprint": expected["original_v12_terminal_fingerprint"],
        "original_index_fingerprint": expected["index_fingerprint"],
        "original_source_row_count": len(original),
        "source_row_positions": tuple(positions),
        "selected_quotes": selected,
        "local_selection_is_provider_scoped": False,
        "original_complete_chain_proven": False,
        "source_is_execution_admissible": False,
        "simulator_ready": False,
        "provider_requests": 0,
    }


def summarize_selected_chain(
    selection: dict[str, Any],
    *,
    dte_min: int = RESEARCH_DTE_MIN,
    dte_max: int = RESEARCH_DTE_MAX,
    max_quote_age_seconds: int = RESEARCH_MAX_QUOTE_AGE_SECONDS,
    max_spread_to_mid: float = RESEARCH_MAX_SPREAD_TO_MID,
) -> dict[str, Any]:
    """Research-only coverage and liquidity diagnostics; never fill prices."""
    if (selection.get("contract") != CONTRACT
            or selection.get("status") !=
                "CAUSAL_SOURCE_ORIGINAL_OBSERVATIONS_NOT_EXECUTABLE"
            or selection.get("source_is_execution_admissible") is not False
            or selection.get("simulator_ready") is not False
            or selection.get("local_selection_is_provider_scoped") is not False):
        raise HybridSourceLinkedReaderError("SOURCE_ONLY_AUTHORITY_BOUNDARY")

    if (type(dte_min) is not int or type(dte_max) is not int
            or not 0 <= dte_min <= dte_max <= selection["requested_max_dte"]
            or type(max_quote_age_seconds) is not int
            or max_quote_age_seconds < 0
            or not isinstance(max_spread_to_mid, (float, int))
            or isinstance(max_spread_to_mid, bool)
            or not 0 < max_spread_to_mid <= 1):
        raise HybridSourceLinkedReaderError("RESEARCH_WINDOW_PARAMETERS_INVALID")
    clock = datetime.combine(
        date.fromisoformat(selection["session_et"]),
        datetime.strptime(selection["decision_clock_et"], "%H:%M:%S.%f").time(),
        TZ,
    )
    eligible = []
    by_expiry_right = Counter()
    strikes_by_expiry: dict[str, dict[float, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    qualified_by_pair: dict[tuple[str, float], set[str]] = defaultdict(set)
    observed_by_pair: dict[tuple[str, float], set[str]] = defaultdict(set)
    stale = 0
    wide = 0
    non_displayed = 0
    for q in selection["selected_quotes"]:
        exp = date.fromisoformat(str(q["expiration"])[:10])
        dte = (exp - clock.date()).days
        if not 0 <= dte <= selection["requested_max_dte"]:
            raise HybridSourceLinkedReaderError("RECONSTRUCTED_QUOTE_ESCAPES_SCOPE")
        ts = datetime.fromisoformat(q["timestamp"].replace("Z", "+00:00"))
        if ts.tzinfo is None or ts.utcoffset() is None:
            raise HybridSourceLinkedReaderError("QUOTE_TIMESTAMP_NAIVE")
        age = (clock - ts.astimezone(TZ)).total_seconds()
        if age < 0 or ts.astimezone(TZ).date() != clock.date():
            raise HybridSourceLinkedReaderError("QUOTE_ESCAPES_CAUSAL_CLOCK")
        if not dte_min <= dte <= dte_max:
            continue
        right = str(q["right"]).lower()
        strike = _finite_number(q["strike"], "strike")
        if right not in {"call", "put"} or strike <= 0:
            raise HybridSourceLinkedReaderError("QUOTE_KEY_INVALID")
        key = (exp.isoformat(), strike)
        pair_rights = observed_by_pair[key]
        if right in pair_rights:
            raise HybridSourceLinkedReaderError("DUPLICATE_WINDOW_CONTRACT")
        pair_rights.add(right)
        strikes_by_expiry[exp.isoformat()][strike].add(right)
        by_expiry_right[(exp.isoformat(), right)] += 1
        bid = _finite_number(q["bid"], "bid")
        ask = _finite_number(q["ask"], "ask")
        size_bid = q["bid_size"]
        size_ask = q["ask_size"]
        if not isinstance(size_bid, int) or not isinstance(size_ask, int):
            raise HybridSourceLinkedReaderError("SOURCE_DISPLAY_SIZE_NOT_INTEGER")
        # V10/V13 permit zero-sided historical observations in the original
        # source (nonnegative prices/sizes). They are real SOURCE evidence,
        # but cannot qualify as displayed, executable two-sided quotes.
        # Preserve them in observed pair geometry and count the disqualification
        # separately. A crossed *positive* market remains a structural failure.
        if bid > 0 and ask > 0 and ask < bid:
            raise HybridSourceLinkedReaderError("CROSSED_TWO_SIDED_QUOTE")
        if bid <= 0 or ask <= 0 or size_bid <= 0 or size_ask <= 0:
            non_displayed += 1
            eligible.append((exp.isoformat(), strike, right))
            continue
        mid = (bid + ask) / 2
        spread = (ask - bid) / mid
        fresh = age <= max_quote_age_seconds
        tight = spread <= max_spread_to_mid
        if not fresh:
            stale += 1
        if not tight:
            wide += 1
        if fresh and tight:
            qualified_by_pair[key].add(right)
        eligible.append((exp.isoformat(), strike, right))
    observed_pairs = sum(1 for rights in observed_by_pair.values()
                         if rights == {"call", "put"})
    quality_pairs = sum(1 for rights in qualified_by_pair.values()
                        if rights == {"call", "put"})
    by_expiry = []
    for expiry in sorted(strikes_by_expiry):
        rights = by_expiry_right[(expiry, "call")], by_expiry_right[(expiry, "put")]
        pairs = sum(
            1 for both in strikes_by_expiry[expiry].values()
            if both == {"call", "put"}
        )
        by_expiry.append({
            "expiration": expiry,
            "observed_calls": rights[0],
            "observed_puts": rights[1],
            "observed_strike_keys": len(strikes_by_expiry[expiry]),
            "observed_call_put_pairs": pairs,
        })
    report = {
        "contract": CONTRACT,
        "status": "SOURCE_LINKED_OBSERVED_CHAIN_DIAGNOSTIC_ONLY",
        "query_id": selection["query_id"],
        "original_source_sha256": selection["original_response_sha256"],
        "original_index_fingerprint": selection["original_index_fingerprint"],
        "session_et": selection["session_et"],
        "symbol": selection["symbol"],
        "decision_clock_et": selection["decision_clock_et"],
        "research_window_dte": [dte_min, dte_max],
        "quote_age_limit_seconds": max_quote_age_seconds,
        "spread_to_mid_threshold": float(max_spread_to_mid),
        "v14_in_range_source_rows": len(selection["selected_quotes"]),
        "research_window_observed_rows": len(eligible),
        "research_window_stale_rows": stale,
        "research_window_wide_spread_rows": wide,
        "research_window_non_displayed_rows": non_displayed,
        "observed_expirations": len(by_expiry),
        "observed_call_put_strike_pairs": observed_pairs,
        "observed_pairs_passing_freshness_spread_only": quality_pairs,
        "per_expiration": by_expiry,
        "strike_universe_completeness_proven": False,
        "point_in_time_underlying_spot_bound": False,
        "historical_open_interest_bound": False,
        "dividend_publication_causality_bound": False,
        "trade_fills_simulated": False,
        "execution_admissible": False,
        "simulator_ready": False,
        "provider_requests": 0,
        "broker_requests": 0,
        "protected_outcomes_read": 0,
        "simulations_run": 0,
    }
    report["fingerprint"] = _fingerprint(report)
    return report


def audit_frozen_indexed_chains(
    settings: AtlasSettings, manifest: Path, candidate_plan: Path,
) -> dict[str, Any]:
    settings.assert_external_storage_binding("options")
    frozen = _load_full_manifest(settings, manifest, candidate_plan)
    if (frozen["manifest_fingerprint"] != PINNED_MANIFEST_FINGERPRINT
            or frozen["source_request_count"] != 9866):
        raise HybridSourceLinkedReaderError("FROZEN_MANIFEST_DRIFT")
    reports = []
    totals = Counter()
    for row in frozen["requests"]:
        state = _inspect_attempt(settings, row["query_id"])
        if state not in ELIGIBLE_STATES:
            if state.startswith("RAW_ARCHIVED"):
                raise HybridSourceLinkedReaderError("INVALID_ARCHIVE_NOT_CHAIN_READABLE")
            continue
        selected = read_selected_original_observations(settings, row)
        detail = summarize_selected_chain(selected)
        reports.append(detail)
        totals["original_source_rows"] += selected["original_source_row_count"]
        totals["v14_selected_rows"] += detail["v14_in_range_source_rows"]
        totals["research_window_rows"] += detail["research_window_observed_rows"]
        totals["research_window_non_displayed_rows"] += detail[
            "research_window_non_displayed_rows"
        ]
        totals["research_window_stale_rows"] += detail["research_window_stale_rows"]
        totals["research_window_wide_spread_rows"] += detail[
            "research_window_wide_spread_rows"
        ]
        totals["observed_pairs"] += detail["observed_call_put_strike_pairs"]
        totals["qualified_pairs"] += detail[
            "observed_pairs_passing_freshness_spread_only"
        ]
    report = {
        "contract": CONTRACT,
        "status": "READ_ONLY_INDEX_LINKED_CAUSAL_CHAIN_CENSUS",
        "frozen_manifest_fingerprint": PINNED_MANIFEST_FINGERPRINT,
        "sources_inspected": len(reports),
        "original_rows": totals["original_source_rows"],
        "v14_selected_rows": totals["v14_selected_rows"],
        "research_14_45_dte_observed_rows": totals["research_window_rows"],
        "research_14_45_dte_non_displayed_rows": totals[
            "research_window_non_displayed_rows"
        ],
        "research_14_45_dte_stale_rows": totals["research_window_stale_rows"],
        "research_14_45_dte_wide_spread_rows": totals[
            "research_window_wide_spread_rows"
        ],
        "observed_call_put_strike_pairs": totals["observed_pairs"],
        "pairs_passing_freshness_and_spread_only": totals["qualified_pairs"],
        "per_source": reports,
        "source_provider_chain_completeness_proven": False,
        "strategy_outcomes_observed": False,
        "simulator_ready": False,
        "provider_requests": 0,
        "broker_requests": 0,
        "protected_outcomes_read": 0,
        "simulations_run": 0,
        "files_written": 0,
    }
    report["fingerprint"] = _fingerprint(report)
    return report
