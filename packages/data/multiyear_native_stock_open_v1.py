from __future__ import annotations

"""Bind real accepted 2021–2025 stock cases to original native raw daily OPEN.

No upstream selection replay, full news rescan, provider GET, adjusted-price
strike substitution, or 2026 protected native read. The accepted original
native reader verifies exact plan/checkpoint/Parquet SHA and research raw close.
"""

import math
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from packages.core.settings import AtlasSettings
from packages.data.marketdata_accepted_stock_candidate_export_v1 import (
    CandidateStockExportError, _read_entry_opens,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.marketdata_candidate_expansion_v1 import _exclusive, _read_object
from packages.data.multiyear_stock_news_source_v1 import (
    AUTHORITY as NEWS_JOIN_AUTHORITY,
    CONTRACT as NEWS_JOIN_CONTRACT,
    StockNewsSourceError,
    _verified_census,
    build_stock_news_source,
)

CONTRACT = "atlas-multiyear-verified-native-raw-stock-entry-open-v1"
OUTPUT_REL = "data/research/evidence/multiyear_native_raw_stock_open_v1"
AUTHORITY = {
    "provider_requests": 0, "protected_outcomes_read": 0,
    "native_raw_open_is_not_09_35_fill": True,
    "future_option_liquidity_used_for_selection": False,
    "historical_option_contract_selected": False,
    "option_price_or_pnl": False,
    "portfolio_trade_pnl": False,
    "2026_native_read": False,
    "paper": False, "live": False,
}


class MultiYearRawStockError(ValueError):
    pass


def _verify_news_join(census: dict[str, Any], joined: dict[str, Any]) -> None:
    unsigned = dict(joined)
    fp = unsigned.pop("source_join_fingerprint", None)
    cases = joined.get("rows")
    original = census["cases"]
    if (
        fp != _fingerprint(unsigned)
        or joined.get("contract") != NEWS_JOIN_CONTRACT
        or joined.get("status") != "MULTIYEAR_STOCK_PIT_NEWS_FEATURES_ONLY"
        or joined.get("authority") != NEWS_JOIN_AUTHORITY
        or joined.get("provider_requests") != 0
        or joined.get("protected_outcomes_read") != 0
        or joined.get("original_stock_census_fingerprint") != census["census_fingerprint"]
        or not isinstance(cases, list) or len(cases) != len(original)
        or [x["case_id"] for x in cases] != [x["case_id"] for x in original]
        or any(
            x["ticker"] != y["ticker"]
            or x["signal_session"] != y["signal_session"]
            or x["entry_session"] != y["entry_session"]
            or x["stock_source_status"] != y["source_status"]
            or x["native_raw_entry_open"] is not None
            or x["selected_option_symbol"] is not None
            for x, y in zip(cases, original, strict=True)
        )
    ):
        raise MultiYearRawStockError("original stock/news source mismatch")


def _source_proxy(row: dict[str, Any]) -> SimpleNamespace:
    """Only attributes the original accepted native source reader consumes."""
    open_utc = datetime.fromisoformat(row["original_selected_entry_open_utc"])
    if open_utc.tzinfo is None:
        raise MultiYearRawStockError("original next-session open lost timezone")
    session = date.fromisoformat(row["signal_session"])
    if row["entry_session"] != open_utc.date().isoformat():
        # Every genuine selected source timestamp is a timezone-aware UTC instant;
        # 14:30/13:30 UTC stays the same calendar day for US equities.
        raise MultiYearRawStockError("original raw stock entry session drifted")
    return SimpleNamespace(
        opportunity_id=row["case_id"],
        ticker=row["ticker"], instrument_id=row["instrument_id"],
        signal_session=session, entry_utc=open_utc.astimezone(UTC),
    )


def attach_native_raw_open(
    census: dict[str, Any],
    joined: dict[str, Any],
    *, project_root: Path,
    reader: Callable[..., Any] = _read_entry_opens,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    census = _verified_census(census)
    _verify_news_join(census, joined)
    safe = [
        x for x in census["cases"]
        if date.fromisoformat(x["entry_session"]).year <= 2025
    ]
    held = [
        x for x in census["cases"]
        if date.fromisoformat(x["entry_session"]).year > 2025
    ]
    if not safe:
        raise MultiYearRawStockError("no pre-2026 accepted native-open cases")
    if any(x["source_status"] == "NEEDS_SEPARATE_2026_NATIVE_SOURCE" for x in safe):
        raise MultiYearRawStockError("unsafe late-year original stock source classification")
    if any(
        x["source_status"] != "NEEDS_SEPARATE_2026_NATIVE_SOURCE"
        for x in held
    ):
        raise MultiYearRawStockError("2026 entry not explicitly protected")
    if progress:
        progress({
            "stage": "NATIVE_RAW_OPEN_ACCEPTED_SOURCE_READ",
            "pre_2026_cases": len(safe), "2026_entry_gap_cases": len(held),
            "provider_requests": 0, "protected_outcomes_read": 0,
        })
    proxies = [_source_proxy(row) for row in safe]
    raw, source = reader(
        project_root, proxies,
        progress=lambda stage, detail: progress({
            "stage": stage, **detail, "provider_requests": 0,
        }) if progress is not None else None,
    )
    if (
        not isinstance(raw, dict)
        or set(raw) != {x["case_id"] for x in safe}
        or source.get("protected_master_return_rows_read") != 0
        or not isinstance(source.get("native_raw_source"), dict)
        or not source["native_raw_source"].get("verified_native_raw_unit_count")
        or source["native_raw_source"].get("verified_native_raw_unit_count") !=
        len(source["native_raw_source"].get("verified_native_raw_unit_bindings", []))
    ):
        raise MultiYearRawStockError("accepted source raw OPEN coverage/provenance incomplete")
    rows: list[dict[str, Any]] = []
    years: dict[str, Counter[str]] = {
        str(year): Counter() for year in range(2021, 2027)
    }
    for original, feature in zip(census["cases"], joined["rows"], strict=True):
        case = original["case_id"]
        if case in raw:
            opening = raw[case]
            if (
                isinstance(opening, bool)
                or not isinstance(opening, (float, int))
                or not math.isfinite(opening)
                or opening <= 0
            ):
                raise MultiYearRawStockError("raw as-traded stock opening invalid")
            opening_text = str(opening)
            status = (
                "VERIFIED_NATIVE_RAW_OPEN_NO_MONTHLY_EXPIRY"
                if original["structural_expiration"] is None else
                "VERIFIED_NATIVE_RAW_OPEN_NEEDS_ORIGINAL_PIT_CHAIN"
            )
        else:
            if original["source_status"] != "NEEDS_SEPARATE_2026_NATIVE_SOURCE":
                raise MultiYearRawStockError("unexpected missing accepted raw stock opening")
            opening_text = None
            status = "DEFERRED_ENTRY_2026_NATIVE_SOURCE_NOT_READ"
        year = original["signal_session"][:4]
        years[year][status] += 1
        rows.append({
            "case_id": case,
            "ticker": original["ticker"],
            "instrument_id": original["instrument_id"],
            "policy_id": original["policy_id"],
            "signal_session": original["signal_session"],
            "entry_session": original["entry_session"],
            "original_selected_entry_open_utc":
                original["original_selected_entry_open_utc"],
            "planned_option_decision_at_utc":
                original["planned_option_decision_at_utc"],
            "expiration": original["structural_expiration"],
            "raw_underlying_price": opening_text,
            "underlying_price_basis":
                "RAW_AS_TRADED_NATIVE_1DAY_OPEN" if opening_text is not None else None,
            "raw_open_is_not_09_35_trade_or_fill": True,
            "native_source_status": status,
            "original_stock_source_status": original["source_status"],
            "news_coverage_status": feature["news_coverage_status"],
            "prior_24h_news_articles": feature["prior_24h_news_articles"],
            "prior_7d_news_articles": feature["prior_7d_news_articles"],
            "option_symbol": None,
            "verified_original_native_lineage_only": True,
        })
    if len(rows) != census["daily_long_case_denominator"]:
        raise MultiYearRawStockError("native source changed original denominator")
    for year in range(2021, 2027):
        expected = census["by_year"][str(year)]["accepted_development_daily_long_signals"]
        if sum(years[str(year)].values()) != expected:
            raise MultiYearRawStockError("native source year denominator changed")
    report = {
        "contract": CONTRACT,
        "status": "MULTIYEAR_NATIVE_RAW_OPEN_VERIFIED_SOURCE_ONLY",
        "original_stock_census_fingerprint": census["census_fingerprint"],
        "original_stock_news_fingerprint": joined["source_join_fingerprint"],
        "accepted_native_source": source,
        "case_denominator": len(rows),
        "verified_native_raw_open_cases": len(raw),
        "deferred_2026_entry_cases": len(held),
        "native_units_verified": source["native_raw_source"]["verified_native_raw_unit_count"],
        "by_year": {y: dict(sorted(v.items())) for y, v in years.items()},
        "provider_requests": 0, "protected_outcomes_read": 0,
        "authority": AUTHORITY,
        "rows": rows,
    }
    report["source_fingerprint"] = _fingerprint(report)
    return report


def _target(settings: AtlasSettings, joined: dict[str, Any]) -> Path:
    return settings.resolved_path(
        f"{OUTPUT_REL}_{joined['source_join_fingerprint'][:16]}.json"
    )


def inspect_existing_native_source(
    settings: AtlasSettings, census: dict[str, Any],
    joined: dict[str, Any],
) -> dict[str, Any] | None:
    _verified_census(census)
    _verify_news_join(census, joined)
    path = _target(settings, joined)
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise MultiYearRawStockError("existing native source must be a regular file")
    try:
        report = _read_object(path)
        unsigned = dict(report)
        fp = unsigned.pop("source_fingerprint", None)
        if (
            fp != _fingerprint(unsigned)
            or report.get("contract") != CONTRACT
            or report.get("status") != "MULTIYEAR_NATIVE_RAW_OPEN_VERIFIED_SOURCE_ONLY"
            or report.get("original_stock_census_fingerprint")
            != census["census_fingerprint"]
            or report.get("original_stock_news_fingerprint")
            != joined["source_join_fingerprint"]
            or report.get("case_denominator") != len(census["cases"])
            or report.get("authority") != AUTHORITY
            or report.get("provider_requests") != 0
            or report.get("protected_outcomes_read") != 0
            or [x["case_id"] for x in report["rows"]]
            != [x["case_id"] for x in census["cases"]]
        ):
            raise MultiYearRawStockError("existing native raw source lineage drifted")
        return report
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise MultiYearRawStockError("existing native source unreadable") from exc


def write_native_source(
    settings: AtlasSettings, census: dict[str, Any],
    joined: dict[str, Any], report: dict[str, Any],
) -> tuple[Path, str]:
    _verified_census(census)
    _verify_news_join(census, joined)
    unsigned = dict(report)
    sig = unsigned.pop("source_fingerprint", None)
    if (
        report.get("contract") != CONTRACT
        or sig != _fingerprint(unsigned)
        or report.get("original_stock_census_fingerprint")
        != census["census_fingerprint"]
        or report.get("original_stock_news_fingerprint")
        != joined["source_join_fingerprint"]
        or report.get("authority") != AUTHORITY
        or report.get("provider_requests") != 0
        or report.get("protected_outcomes_read") != 0
        or len(report.get("rows", [])) != len(census["cases"])
    ):
        raise MultiYearRawStockError("invalid original native source write")
    path = _target(settings, joined)
    if path.exists() or path.is_symlink():
        if _read_object(path) != report:
            raise MultiYearRawStockError("existing immutable original native file differs")
        return path, "REUSED_IDENTICAL_ORIGINAL_NATIVE_SOURCE"
    _exclusive(path, report)
    if _read_object(path) != report:
        raise MultiYearRawStockError("new native source readback differs")
    return path, "WRITTEN_NEW_NATIVE_RAW_STOCK_OPEN_SOURCE"


def build_multiyear_native_raw_open_source(
    settings: AtlasSettings, *, duckdb_threads: int = 4,
    news_threads: int = 4,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[dict[str, Any], Path, str]:
    settings.assert_external_storage_binding("research_evidence")
    census, joined, _, action = build_stock_news_source(
        settings, duckdb_threads=duckdb_threads, news_threads=news_threads,
        progress=progress,
    )
    if progress:
        progress({
            "stage": "REUSE_ACCEPTED_STOCK_NEWS",
            "action": action, "cases": census["daily_long_case_denominator"],
            "provider_requests": 0,
        })
    existing = inspect_existing_native_source(settings, census, joined)
    if existing is not None:
        return existing, _target(settings, joined), "REUSED_VERIFIED_NATIVE_SOURCE_NO_RAW_RESCAN"
    report = attach_native_raw_open(
        census, joined, project_root=settings.project_root, progress=progress
    )
    path, action = write_native_source(settings, census, joined, report)
    return report, path, action
