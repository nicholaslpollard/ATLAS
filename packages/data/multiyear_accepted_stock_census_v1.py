from __future__ import annotations

"""Six-year visible, outcome-blind selection census from accepted DEVELOPMENT.

This is the bridge from 2022-specific physical data acquisition to a shared
multi-year simulator. Only existing accepted replay selections are read. The
native raw underlying OPEN, option contract and news are NOT invented here.
"""

import math
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Sequence
from zoneinfo import ZoneInfo

from packages.backtesting.recurrent_successor_outcome_replay import (
    SelectedReplayOpportunity,
    load_selected_replay_opportunities,
)
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.marketdata_accepted_stock_candidate_export_v1 import (
    CandidateStockExportError, _monthly_expiration,
)
from packages.data.marketdata_candidate_batch_plan_v1 import TICKER_PATTERN
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.marketdata_candidate_expansion_v1 import _exclusive, _read_object
from packages.strategies.successor_conditioning_contract import (
    DEVELOPMENT_START, DEVELOPMENT_END,
)

CONTRACT = "atlas-multiyear-accepted-stock-signal-census-v1"
YEAR_START = 2021
LAST_SAFE_YEAR = 2025
FINAL_YEAR = 2026
EASTERN = ZoneInfo("America/New_York")
OUTPUT_REL = "data/research/evidence/multiyear_accepted_stock_signal_census_v1"
AUTHORITY = {
    "provider_requests": 0,
    "protected_outcomes_read": 0,
    "provider_fallback": False,
    "option_contract_selected": False,
    "historical_raw_stock_entry_price_verified": False,
    "2026_replay_source_accepted": False,
    "option_pnl": False,
    "paper": False,
    "live": False,
    "strategy_promotion": False,
}


class MultiYearStockSignalError(ValueError):
    pass


def _sha(value: object) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(
        c not in "0123456789abcdef" for c in value
    ):
        raise MultiYearStockSignalError("accepted source fingerprint must be SHA256")
    return value


def freeze_development_census(
    opportunities: Sequence[SelectedReplayOpportunity],
    source: dict[str, object],
    *, expiry_rule: Callable[[date], date] = _monthly_expiration,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Project signal identity ONLY; never serialize outcome/return fields.

    All 2021–2025 candidate daily LONG cases remain in the source denominator
    even when option eligibility/expiry cannot yet be established.
    """
    if (
        not isinstance(source, dict)
        or not isinstance(source.get("selected_opportunity_count"), int)
        or source["selected_opportunity_count"] != len(opportunities)
        or not opportunities
    ):
        raise MultiYearStockSignalError("accepted source selection count changed")
    source_fp = _sha(source.get("source_integrity_fingerprint"))
    analysis_fp = _sha(source.get("conditioning_analysis_fingerprint"))
    calendar = get_market_calendar()
    seen: set[str] = set()
    cases: list[dict[str, Any]] = []
    dispositions: Counter[str] = Counter()
    selected_timeframe_counts: Counter[str] = Counter()
    for index, item in enumerate(opportunities, 1):
        selected_timeframe_counts[item.native_timeframe] += 1
        if item.native_timeframe != "1d" or item.direction != "LONG":
            continue
        if not YEAR_START <= item.signal_session.year <= LAST_SAFE_YEAR:
            continue
        if item.opportunity_id in seen:
            raise MultiYearStockSignalError("duplicate accepted selected opportunity")
        seen.add(item.opportunity_id)
        if (
            item.source_analysis_fingerprint != analysis_fp
            or not isinstance(item.ticker, str)
            or TICKER_PATTERN.fullmatch(item.ticker) is None
            or not isinstance(item.instrument_id, str) or not item.instrument_id
            or not item.policy_id
            or item.entry_utc.tzinfo is None
            or item.decision_utc.tzinfo is None
        ):
            raise MultiYearStockSignalError("selected source identity/lineage invalid")
        signal_open, signal_close = calendar.regular_open_close(item.signal_session)
        entry_session = item.entry_utc.astimezone(EASTERN).date()
        entry_open, _ = calendar.regular_open_close(entry_session)
        if (
            item.decision_utc.astimezone(UTC) != signal_close
            or item.entry_utc.astimezone(UTC) != entry_open
            or entry_session <= item.signal_session
        ):
            raise MultiYearStockSignalError("accepted daily decision/entry clock differs")
        # 2025-12-31 signal may lead to a 2026 entry. That future source is not
        # silently smuggled through the pre-2026 DEVELOPMENT native path.
        disposition = (
            "NEEDS_SEPARATE_2026_NATIVE_SOURCE"
            if entry_session.year > LAST_SAFE_YEAR
            else "ELIGIBLE_NEEDS_VERIFIED_NATIVE_RAW_OPEN_AND_PIT_CHAIN"
        )
        expiration: str | None = None
        try:
            expiry = expiry_rule(item.signal_session)
        except CandidateStockExportError as exc:
            if str(exc) != "no bounded exchange monthly expiry is available":
                raise
            disposition = "NO_MONTHLY_EXPIRATION_IN_FROZEN_28_TO_60_DAY_WINDOW"
        else:
            if not 28 <= (expiry - item.signal_session).days <= 60:
                raise MultiYearStockSignalError("frozen structural expiry window altered")
            expiration = expiry.isoformat()
        # Expiry may fall outside 2025 although the signal+entry don't.
        # Exact option-chain snapshot is on previous signal session.
        dispositions[disposition] += 1
        cases.append({
            "case_id": item.opportunity_id,
            "ticker": item.ticker,
            "instrument_id": item.instrument_id,
            "policy_id": item.policy_id,
            "economic_family_id": item.economic_family_id,
            "fold_id": item.fold_id,
            "native_timeframe": "1d",
            "direction": "LONG",
            "signal_session": item.signal_session.isoformat(),
            "signal_available_at_utc": signal_close.isoformat(),
            "entry_session": entry_session.isoformat(),
            "original_selected_entry_open_utc": entry_open.isoformat(),
            "planned_option_decision_at_utc":
                (entry_open + timedelta(minutes=5)).isoformat(),
            "structural_expiration": expiration,
            "source_status": disposition,
            "source_selection_analysis_fingerprint": analysis_fp,
            "source_selection_integrity_fingerprint": source_fp,
            "native_raw_entry_open": None,
            "selected_option_symbol": None,
            "option_chain_source_request_identity": None,
            "prior_news_article_count": None,
            "no_outcome_or_return_fields_projected": True,
        })
        if progress and (len(cases) % 1000 == 0):
            progress({"stage": "DEVELOPMENT_SIGNAL_CENSUS",
                      "accepted_cases": len(cases), "source_items_scanned": index,
                      "provider_requests": 0})
    if not cases:
        raise MultiYearStockSignalError("no accepted daily LONG signals 2021..2025")
    cases.sort(key=lambda row: (row["signal_session"], row["ticker"], row["case_id"]))
    year_census: dict[str, dict[str, Any]] = {}
    for year in range(YEAR_START, FINAL_YEAR + 1):
        group = [row for row in cases if int(row["signal_session"][:4]) == year]
        year_census[str(year)] = {
            "accepted_development_daily_long_signals": len(group),
            "source_statuses": dict(sorted(Counter(
                row["source_status"] for row in group
            ).items())),
            "option_contract_selected": 0,
            "verified_raw_entry_open_prices": 0,
            "source_authority": (
                "NEEDS_SEPARATE_PROSPECTIVE_OR_ACCEPTED_2026_SOURCE"
                if year == 2026 else
                "ACCEPTED_DEVELOPMENT_SELECTED_SIGNAL_METADATA_ONLY"
            ),
        }
    if year_census["2026"]["accepted_development_daily_long_signals"] != 0:
        raise MultiYearStockSignalError("2026 protected data leaked into development")
    output = {
        "contract": CONTRACT,
        "status": "SIX_YEAR_VISIBLE_ACCEPTED_SIGNAL_CENSUS_SOURCE_ONLY",
        "selection_utc_source_start": "2021-01-01",
        "selection_utc_source_end": "2025-12-31",
        "2026_status": "NO_ACCEPTED_UNPROTECTED_2026_REPLAY_SELECTION_IN_THIS_SOURCE",
        "accepted_development_start": DEVELOPMENT_START,
        "accepted_development_end": DEVELOPMENT_END,
        "original_source_integrity_fingerprint": source_fp,
        "conditioning_analysis_fingerprint": analysis_fp,
        "original_selected_source_count": source["selected_opportunity_count"],
        "original_timeframe_counts": dict(sorted(selected_timeframe_counts.items())),
        "daily_long_case_denominator": len(cases),
        "source_statuses": dict(sorted(dispositions.items())),
        "by_year": year_census,
        "provider_requests": 0,
        "protected_outcomes_read": 0,
        "authority": AUTHORITY,
        "cases": cases,
    }
    output["census_fingerprint"] = _fingerprint(output)
    return output


def build_development_census(
    settings: AtlasSettings, *, duckdb_threads: int = 4,
    loader: Callable[..., Any] = load_selected_replay_opportunities,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if type(duckdb_threads) is not int or not 1 <= duckdb_threads <= 8:
        raise MultiYearStockSignalError("bounded local DuckDB threads must be 1..8")
    settings.assert_external_storage_binding("research_evidence")
    if progress:
        progress({"stage": "ACCEPTED_2021_TO_2025_SELECTION_ONCE",
                  "duckdb_threads": duckdb_threads, "provider_requests": 0})
    selected, source = loader(
        settings.project_root,
        start_session=date(2021, 1, 1),
        end_session=date(2025, 12, 31),
        duckdb_threads=duckdb_threads,
    )
    if progress:
        progress({"stage": "ACCEPTED_DEVELOPMENT_SOURCE_LOADED",
                  "original_selected_items": len(selected), "provider_requests": 0})
    return freeze_development_census(selected, source, progress=progress)


def write_development_census(
    settings: AtlasSettings, result: dict[str, Any],
) -> tuple[Path, str]:
    if (
        result.get("contract") != CONTRACT
        or result.get("authority") != AUTHORITY
        or result.get("provider_requests") != 0
        or result.get("protected_outcomes_read") != 0
        or result.get("by_year", {}).get("2026", {}).get(
            "accepted_development_daily_long_signals"
        ) != 0
        or result.get("census_fingerprint") != _fingerprint({
            k: v for k, v in result.items() if k != "census_fingerprint"
        })
    ):
        raise MultiYearStockSignalError("invalid development census/authority")
    output = settings.resolved_path(
        f"{OUTPUT_REL}_{result['original_source_integrity_fingerprint'][:16]}.json"
    )
    if output.exists() or output.is_symlink():
        if _read_object(output) != result:
            raise MultiYearStockSignalError(
                "existing immutable multi-year signal source differs"
            )
        return output, "REUSED_IDENTICAL_ACCEPTED_SIGNAL_CENSUS"
    _exclusive(output, result)
    if _read_object(output) != result:
        raise MultiYearStockSignalError("new signal census readback differs")
    return output, "WRITTEN_NEW_ACCEPTED_SIGNAL_CENSUS"
