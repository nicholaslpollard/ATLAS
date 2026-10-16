from __future__ import annotations

"""One fixed prior-window raw SPY source packet; never a forecast or backtest.

Reuse native acceptance/plan/checkpoint checks from the existing SPY reader.
Raw closes are intentionally not converted to economic returns: this packet
exposes the action and publication-clock work required before that is valid.
"""

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
import math
from typing import Any, Callable

import pandas as pd

from packages.backtesting.successor_spy_benchmark_source import (
    NativeSpyDailyReadLimits, _bounded_native_file, _daily_fallback_rows, _sha256_file,
)
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.strategies.options_native_pilot_v1_contract import (
    AUTHORITY, LOOKBACK_RETURNS, SPECIFICATION_FINGERPRINT,
)

CONTRACT = "atlas-options-native-pilot-raw-spy-input-packet-v1"
FEATURE_CUTOFF = datetime(2020, 1, 6, 15, tzinfo=UTC)
READ_LIMITS = NativeSpyDailyReadLimits()


class PilotInputPacketError(ValueError):
    pass


def requested_prior_sessions():
    calendar = get_market_calendar("XNYS")
    sessions = calendar.sessions_in_range(
        (FEATURE_CUTOFF - timedelta(days=75)).date(), FEATURE_CUTOFF.date(),
    )
    prior = tuple(day for day in sessions if calendar.regular_open_close(day)[1] < FEATURE_CUTOFF)
    return prior[-(LOOKBACK_RETURNS + 1):]


def build_options_native_pilot_input_packet(
    settings: AtlasSettings, *, progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    requested = requested_prior_sessions()
    if len(requested) != 21 or {day.year for day in requested} != {2019, 2020}:
        raise PilotInputPacketError("fixed prior-window scope drifted")
    frame, lineage = _daily_fallback_rows(
        settings, requested_sessions=requested, read_limits=READ_LIMITS, progress=progress,
    )
    if set(frame.columns) != {"session_date", "close"}:
        raise PilotInputPacketError("native close projection schema drifted")
    frame = frame.copy()
    frame["session_date"] = pd.to_datetime(frame["session_date"], errors="raise").dt.date
    if frame.duplicated(["session_date"]).any() or not set(frame["session_date"]).issubset(set(requested)):
        raise PilotInputPacketError("duplicate or out-of-window source row")
    bindings = lineage.get("unit_bindings")
    if (not isinstance(bindings, list) or len(bindings) != 2
            or {row["year"] for row in bindings} != {2019, 2020}
            or lineage.get("protected_or_future_daily_partition_opened") is not False):
        raise PilotInputPacketError("native unit scope is not the two frozen years")
    by_year = {row["year"]: row for row in bindings}
    values = {}
    for row in frame.itertuples(index=False):
        value = float(row.close)
        if not math.isfinite(value) or value <= 0:
            raise PilotInputPacketError("invalid raw source close")
        values[row.session_date] = repr(value)
    calendar = get_market_calendar("XNYS")
    rows = []
    for day in requested:
        rows.append({
            "symbol": "SPY", "session_date": day.isoformat(),
            "raw_close_float64_text": values.get(day),
            "state": "RAW_DAILY_CLOSE_PRESENT" if day in values else "MISSING_REQUESTED_RAW_CLOSE",
            "calendar_regular_close_utc": calendar.regular_open_close(day)[1].isoformat(),
            "calendar_boundary_is_publication_proof": False,
            "observed_at_utc": None, "historical_available_at_utc": None,
            "economic_return_qualified": False,
            "native_unit_id": by_year[day.year]["unit_id"],
            "canonical_sha256": by_year[day.year]["canonical_sha256"],
        })
    layout = V2Layout.beneath((settings.project_root / "data").resolve())
    metadata = []
    for path in (layout.manifests / "research_daily.json", layout.validation / "native_acceptance.json",
                 layout.manifests / "native_acquisition_plan.json"):
        _bounded_native_file(path, layout, READ_LIMITS.metadata_bytes)
        metadata.append({"locator": path.relative_to(settings.project_root.resolve()).as_posix(),
                         "bytes": path.stat().st_size, "sha256": _sha256_file(path)})
    missing = [day.isoformat() for day in requested if day not in values]
    gaps = [
        "PIT_SPLIT_AND_DIVIDEND_TREATMENT_REQUIRED_FOR_ECONOMIC_RETURNS",
        "HISTORICAL_AVAILABILITY_CLOCKS_OR_QUALIFIED_BOUNDED_MODEL_REQUIRED",
        "CAUSAL_1000_SPOT_NOT_READ",
        "EXACT_PAIR_QUOTE_OI_DELIVERABLE_IV_RATE_DIVIDEND_INPUTS_NOT_READ",
        "BROKER_COST_AND_EXECUTION_SETTLEMENT_QUALIFICATION_OPEN",
    ]
    if missing:
        gaps.insert(0, "INCOMPLETE_RAW_PRIOR_CLOSE_WINDOW")
    result = {
        "contract": CONTRACT, "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "status": "PARTIAL_RAW_INPUT_PACKET_WITH_GAPS" if missing else "COMPLETE_RAW_INPUT_PACKET_WITH_QUALIFICATION_GAPS",
        "feature_cutoff_utc": FEATURE_CUTOFF.isoformat(),
        "anchor_reason": "FIRST_FROZEN_WEEKLY_2020_ENTRY; source-only prior-window anchor, not performance selection",
        "source_semantics": "ALPACA_SIP_V2_NATIVE_RAW_REGULAR_DAILY_CLOSE_FLOAT64; NO_ADJUSTED_PRICE_SUBSTITUTION",
        "requested_closes": len(requested), "present_closes": len(values),
        "missing_sessions": missing, "prior_close_rows": rows,
        "lineage": lineage, "metadata_file_bindings": metadata,
        "read_limits_bytes": asdict(READ_LIMITS),
        "scan_scope": {"selected_symbol": "SPY", "native_daily_units": len(bindings),
                       "selected_sessions_predicate_applied_in_sql": True,
                       "full_file_hashes_checked": True, "minute_units": 0, "option_histories": 0,
                       "forecast_or_outcome_labels_computed": 0},
        "economic_log_returns": None, "forecast_total_variance": None,
        "historical_availability_qualified": False, "pilot_input_acceptance": False,
        "qualification_gaps": gaps,
        "authority": dict(AUTHORITY) | {"raw_source_scans": len(bindings)},
    }
    result["report_fingerprint"] = _fingerprint(result)
    return result
