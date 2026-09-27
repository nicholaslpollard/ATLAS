from __future__ import annotations

"""Join accepted 2021–2025 stock signals to PIT-safe 2021–2026 local news.

This is compact per-signal research evidence for future simulator source
selection. It does not load historical returns, select option contracts, call
providers, backdate text or fabricate 2026 development signals.
"""

from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.marketdata_candidate_expansion_v1 import _exclusive, _read_object
from packages.data.multiyear_accepted_stock_census_v1 import (
    AUTHORITY as STOCK_AUTHORITY,
    CONTRACT as STOCK_CONTRACT,
    OUTPUT_REL as STOCK_REL,
    build_development_census,
    write_development_census,
)
from packages.data.offline_multiyear_news_context_v1 import (
    AUTHORITY as NEWS_AUTHORITY, OfflineMultiYearNewsContext,
)

CONTRACT = "atlas-multiyear-stock-pit-news-development-source-v1"
OUTPUT_REL = "data/research/evidence/multiyear_stock_pit_news_source_v1"
AUTHORITY = {
    "provider_requests": 0, "protected_outcomes_read": 0,
    "historical_option_contract_selected": False,
    "historical_stock_trade_pnl": False,
    "historical_option_trade_pnl": False,
    "news_text_or_sentiment_alpha": False,
    "2026_development_replay": False,
    "paper": False, "live": False, "strategy_promotion": False,
}


class StockNewsSourceError(ValueError):
    pass


def _verified_census(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StockNewsSourceError("accepted signal census must be an object")
    unsigned = dict(value)
    signature = unsigned.pop("census_fingerprint", None)
    cases = value.get("cases")
    if (
        signature != _fingerprint(unsigned)
        or value.get("contract") != STOCK_CONTRACT
        or value.get("status") != "SIX_YEAR_VISIBLE_ACCEPTED_SIGNAL_CENSUS_SOURCE_ONLY"
        or value.get("authority") != STOCK_AUTHORITY
        or value.get("provider_requests") != 0
        or value.get("protected_outcomes_read") != 0
        or not isinstance(cases, list)
        or len(cases) != value.get("daily_long_case_denominator")
        or value.get("by_year", {}).get("2026", {}).get(
            "accepted_development_daily_long_signals"
        ) != 0
    ):
        raise StockNewsSourceError("accepted source census lineage/authority changed")
    if len({x["case_id"] for x in cases}) != len(cases):
        raise StockNewsSourceError("duplicate selected stock signal in source census")
    if any(
        x["no_outcome_or_return_fields_projected"] is not True
        or x["native_raw_entry_open"] is not None
        or x["selected_option_symbol"] is not None
        or x["source_selection_integrity_fingerprint"]
        != value["original_source_integrity_fingerprint"]
        or x["source_selection_analysis_fingerprint"]
        != value["conditioning_analysis_fingerprint"]
        or not 2021 <= int(x["signal_session"][:4]) <= 2025
        for x in cases
    ):
        raise StockNewsSourceError("source cases contain unaccepted future/outcome evidence")
    return value


def join_stock_pit_news(
    census: dict[str, Any], news: OfflineMultiYearNewsContext,
    *, progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    census = _verified_census(census)
    rows: list[dict[str, Any]] = []
    by_year: dict[str, Counter[str]] = {
        str(year): Counter() for year in range(2021, 2027)
    }
    news_positive24 = news_positive7 = missing = 0
    for idx, row in enumerate(census["cases"], 1):
        decision = datetime.fromisoformat(row["planned_option_decision_at_utc"])
        if decision.tzinfo is None:
            raise StockNewsSourceError("original decision requires timezone")
        context = news.prior_counts(row["ticker"], decision_utc=decision)
        status = context["coverage_status"]
        if status not in {
            "VERIFIED_SOURCE_COVERAGE_AT_DECISION",
            "NEWS_SOURCE_NOT_ACQUIRED_THROUGH_DECISION",
        }:
            raise StockNewsSourceError("unknown original PIT-news source status")
        if (
            (decision.astimezone(UTC).date() <= news.coverage_end)
            != (status == "VERIFIED_SOURCE_COVERAGE_AT_DECISION")
        ):
            raise StockNewsSourceError("news coverage status disagrees with accepted cutoff")
        d24 = context["unique_articles_available_prior_24h"]
        d7 = context["unique_articles_available_prior_7d"]
        if status == "VERIFIED_SOURCE_COVERAGE_AT_DECISION":
            if (
                type(d24) is not int or type(d7) is not int
                or not 0 <= d24 <= d7
            ):
                raise StockNewsSourceError("news count/coverage identity invalid")
            news_positive24 += d24 > 0
            news_positive7 += d7 > 0
        else:
            if d24 is not None or d7 is not None:
                raise StockNewsSourceError("missing news period became false zero")
            missing += 1
        year = row["signal_session"][:4]
        by_year[year][status] += 1
        # Original source case IDs preserve denominator across no-news and
        # structurally ineligible stock/option source statuses.
        rows.append({
            "case_id": row["case_id"], "ticker": row["ticker"],
            "signal_session": row["signal_session"],
            "entry_session": row["entry_session"],
            "planned_option_decision_at_utc": decision.astimezone(UTC).isoformat(),
            "stock_source_status": row["source_status"],
            "source_selected_stock_integrity_fingerprint":
                row["source_selection_integrity_fingerprint"],
            "native_raw_entry_open": None,
            "selected_option_symbol": None,
            "news_coverage_status": status,
            "prior_24h_news_articles": d24,
            "prior_7d_news_articles": d7,
            "news_timestamp_policy": (
                "MAX_PROVIDER_CREATED_UPDATED_CONSERVATIVE"
                if status == "VERIFIED_SOURCE_COVERAGE_AT_DECISION" else
                "NO_ACQUIRED_NEWS_THROUGH_DECISION"
            ),
            "no_future_news_or_option_liquidity_selection": True,
        })
        if progress and (idx % 1000 == 0 or idx == len(census["cases"])):
            progress({"stage": "SIX_YEAR_STOCK_PIT_NEWS_JOIN",
                      "cases_processed": idx, "cases_total": len(census["cases"]),
                      "provider_requests": 0})
    year_coverage = {}
    for year in range(2021, 2027):
        expected = census["by_year"][str(year)]["accepted_development_daily_long_signals"]
        row_total = sum(by_year[str(year)].values())
        if expected != row_total:
            raise StockNewsSourceError("source cases changed for year " + str(year))
        year_coverage[str(year)] = {
            "original_stock_signal_denominator": expected,
            "news_statuses": dict(sorted(by_year[str(year)].items())),
            "stock_source_authority": census["by_year"][str(year)]["source_authority"],
        }
    if not rows or year_coverage["2026"]["original_stock_signal_denominator"] != 0:
        raise StockNewsSourceError("accepted multi-year source denominator drifted")
    report = {
        "contract": CONTRACT,
        "status": "MULTIYEAR_STOCK_PIT_NEWS_FEATURES_ONLY",
        "original_stock_census_fingerprint": census["census_fingerprint"],
        "original_stock_source_integrity_fingerprint":
            census["original_source_integrity_fingerprint"],
        "accepted_news_source": news.lineage,
        "news_source_cutoff": news.coverage_end.isoformat(),
        "news_articles_scanned": news.scanned_articles,
        "news_duplicate_relevant_article_rows": news.duplicate_article_rows,
        "original_stock_signal_denominator": len(rows),
        "news_positive_24h_signals": news_positive24,
        "news_positive_7d_signals": news_positive7,
        "missing_news_source_signals": missing,
        "six_year_coverage": year_coverage,
        "provider_requests": 0,
        "protected_outcomes_read": 0,
        "authority": AUTHORITY,
        "rows": rows,
    }
    report["source_join_fingerprint"] = _fingerprint(report)
    return report


def _output(settings: AtlasSettings, census: dict[str, Any]) -> Path:
    return settings.resolved_path(
        f"{OUTPUT_REL}_{census['census_fingerprint'][:16]}.json"
    )


def inspect_existing_join(
    settings: AtlasSettings, census: dict[str, Any],
) -> dict[str, Any] | None:
    """Prefer one accepted derived feature file over repeating 70 month scans."""
    census = _verified_census(census)
    path = _output(settings, census)
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise StockNewsSourceError("derived feature source target is not a regular file")
    try:
        result = _read_object(path)
        unsigned = dict(result)
        sig = unsigned.pop("source_join_fingerprint", None)
        if (
            result.get("contract") != CONTRACT
            or result.get("status") != "MULTIYEAR_STOCK_PIT_NEWS_FEATURES_ONLY"
            or sig != _fingerprint(unsigned)
            or result.get("original_stock_census_fingerprint")
            != census["census_fingerprint"]
            or result.get("authority") != AUTHORITY
            or result.get("provider_requests") != 0
            or result.get("protected_outcomes_read") != 0
            or len(result.get("rows", [])) != census["daily_long_case_denominator"]
        ):
            raise StockNewsSourceError("existing source join identity/content changed")
        return result
    except (ValueError, TypeError, KeyError, OSError) as exc:
        raise StockNewsSourceError("existing source join cannot be trusted") from exc


def write_stock_news_source(
    settings: AtlasSettings, census: dict[str, Any], report: dict[str, Any],
) -> tuple[Path, str]:
    census = _verified_census(census)
    unsigned = dict(report)
    signature = unsigned.pop("source_join_fingerprint", None)
    if (
        report.get("contract") != CONTRACT
        or report.get("original_stock_census_fingerprint") != census["census_fingerprint"]
        or report.get("authority") != AUTHORITY
        or report.get("provider_requests") != 0
        or report.get("protected_outcomes_read") != 0
        or signature != _fingerprint(unsigned)
    ):
        raise StockNewsSourceError("source join cannot be persisted")
    path = _output(settings, census)
    if path.exists() or path.is_symlink():
        if _read_object(path) != report:
            raise StockNewsSourceError("existing immutable stock-news source differs")
        return path, "REUSED_IDENTICAL_STOCK_NEWS_FEATURES"
    _exclusive(path, report)
    if _read_object(path) != report:
        raise StockNewsSourceError("new stock-news source readback differs")
    return path, "WRITTEN_NEW_STOCK_NEWS_FEATURES"


def build_stock_news_source(
    settings: AtlasSettings, *, duckdb_threads: int = 4,
    news_threads: int = 4,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], Path, str]:
    settings.assert_external_storage_binding("research_evidence")
    settings.assert_external_storage_binding("news")
    prefix = settings.resolved_path(STOCK_REL)
    sources = sorted(prefix.parent.glob(prefix.name + "_*.json"))
    if len(sources) > 1:
        raise StockNewsSourceError(
            "multiple accepted stock source generations; select one explicitly"
        )
    if sources:
        if sources[0].is_symlink() or not sources[0].is_file():
            raise StockNewsSourceError("accepted stock census path is not a file")
        census = _verified_census(_read_object(sources[0]))
        source_path = sources[0]
        census_action = "REUSED_EXISTING_VERIFIED_STOCK_CENSUS"
    else:
        census = build_development_census(
            settings, duckdb_threads=duckdb_threads, progress=progress,
        )
        source_path, census_action = write_development_census(settings, census)
    if progress:
        progress({"stage": "ACCEPTED_STOCK_CENSUS_READY",
                  "status": census_action,
                  "cases": census["daily_long_case_denominator"],
                  "source_path": str(source_path), "provider_requests": 0})
    reused = inspect_existing_join(settings, census)
    if reused is not None:
        return census, reused, _output(settings, census), "REUSED_VERIFIED_FEATURE_SOURCE_NO_NEWS_RESCAN"
    tickers = {r["ticker"] for r in census["cases"]}
    news = OfflineMultiYearNewsContext.from_accepted_history(
        settings, tickers, threads=news_threads, progress=progress,
    )
    report = join_stock_pit_news(census, news, progress=progress)
    path, action = write_stock_news_source(settings, census, report)
    return census, report, path, action
