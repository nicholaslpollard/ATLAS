from __future__ import annotations

"""Join accepted 2022 stock decision identity, prior news and CALL source paths.

This produces an evidence/coverage CASEBOOK, not portfolio returns or executable
stock-option comparisons. All 2,643 original structural representatives remain
in the denominator, including missing observed option reference paths.
"""

from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from packages.core.settings import AtlasSettings
from packages.data import marketdata_additive_2022_shards_v1 as shards
from packages.data.marketdata_2022_rank0_later_eod_reference_v1 import (
    AUTHORITY as EOD_AUTHORITY,
    CONTRACT as EOD_CONTRACT,
    DERIVED_REL as EOD_REL,
    EXPECTED_READINESS,
)
from packages.data.marketdata_2022_ranked_eod_readiness_v1 import EXPECTED_PLAN
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CandidateChainCacheError, _fingerprint,
)
from packages.data.marketdata_candidate_expansion_v1 import _exclusive, _read_object
from packages.data.offline_news_context_v1 import (
    OfflineNewsContext, OfflineNewsContextError,
)

CONTRACT = "atlas-integrated-offline-2022-source-casebook-v1"
EXPECTED_EOD_REFERENCE = (
    "15901045e456335638714e1f0259f5dc5ada519a168801f3676eb8582a3e7598"
)
EXPECTED_OPPORTUNITIES = 2643
EASTERN = ZoneInfo("America/New_York")
OUTPUT_REL = "data/research/evidence/integrated_2022_casebook_v1"
AUTHORITY = {
    "provider_requests": 0,
    "provider_fallback": False,
    "protected_outcomes_read": 0,
    "same_clock_stock_option_pnl": False,
    "09_35_executable_option_quote": False,
    "option_deliverables_verified": False,
    "news_sentiment_inferred": False,
    "stock_entry_fill": False,
    "option_entry_fill": False,
    "paper": False,
    "live": False,
    "strategy_promotion": False,
}


class IntegratedCasebookError(ValueError):
    pass


def _accepted_eod_reference(settings: AtlasSettings) -> dict[str, Any]:
    settings.assert_external_storage_binding("options")
    path = settings.resolved_path(f"{EOD_REL}_{EXPECTED_READINESS[:16]}.json")
    if path.is_symlink() or not path.is_file():
        raise IntegratedCasebookError("locally accepted rank-zero EOD artifact missing")
    try:
        report = _read_object(path)
        unsigned = dict(report)
        fp = unsigned.pop("reference_fingerprint", None)
        rows = report["rows"]
        if (
            fp != EXPECTED_EOD_REFERENCE or fp != _fingerprint(unsigned)
            or report.get("contract") != EOD_CONTRACT
            or report.get("status") != "DESCRIPTIVE_LATER_EOD_REFERENCE_ONLY"
            or report.get("original_rank_zero_readiness_fingerprint") != EXPECTED_READINESS
            or report.get("original_2022_quote_plan_fingerprint") != EXPECTED_PLAN
            or report.get("authority") != EOD_AUTHORITY
            or report.get("provider_requests") != 0
            or report.get("original_receipts_modified") != 0
            or report.get("structural_rank_zero_opportunities") != EXPECTED_OPPORTUNITIES
            or report.get("no_later_two_sided_reference") != 5
            or report.get("entry_reference_only_no_subsequent_reference") != 9
            or report.get("entry_and_next_reference_available") != 2629
            or not isinstance(rows, list) or len(rows) != EXPECTED_OPPORTUNITIES
        ):
            raise IntegratedCasebookError("accepted local EOD-reference evidence changed")
        return report
    except IntegratedCasebookError:
        raise
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise IntegratedCasebookError("original EOD-reference file invalid") from exc


def _accepted_stock_source(
    settings: AtlasSettings,
    reference_rows: list[dict[str, Any]],
    *, shard_reader: Callable[..., Any] = shards._read_bound,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[tuple[int, str], dict[str, Any]]:
    """Verify original source bindings only; do NOT rerun candidate selection."""
    indices = sorted({row["shard_index"] for row in reference_rows})
    if indices != list(range(71)):
        raise IntegratedCasebookError("complete accepted additive shard census changed")
    sources: dict[tuple[int, str], dict[str, Any]] = {}
    for n, i in enumerate(indices, 1):
        _, source_path, binding = shard_reader(settings, i, shards.FROZEN_PRIOR_PLAN)
        source = _read_object(source_path)
        if (
            source.get("year") != 2022 or source.get("shard_index") != i
            or source.get("protected_master_return_rows_read") != 0
            or source.get("authority", {}).get("provider_reads") is not False
            or source.get("contract") != shards.CONTRACT
            or source.get("original_prior_plan_fingerprint") != shards.FROZEN_PRIOR_PLAN
            or len(source.get("rows", [])) != binding["selected_opportunities"]
        ):
            raise IntegratedCasebookError("original accepted stock shard changed")
        for row in source["rows"]:
            key = (i, row["opportunity_id"])
            if key in sources:
                raise IntegratedCasebookError("duplicate stock source identity")
            sources[key] = row
        if progress and (n % 10 == 0 or n == len(indices)):
            progress({"stage": "STOCK_SOURCE_BINDINGS", "shards": n,
                      "total_shards": len(indices), "provider_requests": 0})
    return sources


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise IntegratedCasebookError("source decision timestamp is not timezone-aware")
    return parsed.astimezone(UTC)


def _positive(value: object) -> bool:
    try:
        number = Decimal(str(value))
        return number.is_finite() and number > 0
    except (InvalidOperation, ValueError, TypeError):
        return False


def assemble_casebook(
    reference: dict[str, Any],
    source_by_key: dict[tuple[int, str], dict[str, Any]],
    news: OfflineNewsContext,
    *, progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Pure join; deliberately NO modeled trade P&L or downstream authority."""
    rows = reference["rows"]
    seen: set[tuple[int, str]] = set()
    disposition: Counter[str] = Counter()
    news24, news7 = 0, 0
    out: list[dict[str, Any]] = []
    for n, row in enumerate(rows, 1):
        key = (row["shard_index"], row["opportunity_id"])
        if key in seen:
            raise IntegratedCasebookError("original representative duplicated")
        seen.add(key)
        source = source_by_key.get(key)
        if source is None:
            raise IntegratedCasebookError("original accepted stock source missing")
        decision = _timestamp(source["decision_at_utc"])
        local = decision.astimezone(EASTERN)
        if (
            source["ticker"] != row["ticker"]
            or source["opportunity_id"] != row["opportunity_id"]
            or source["signal_session"] != row["source_signal_session"]
            or source["expiration"] != row["expiration"]
            or source["side"] != "call"
            or source["price_origin"] != "ACCEPTED_NATIVE_RAW_1DAY_ENTRY_OPEN"
            or source["underlying_price_basis"] != "RAW_AS_TRADED"
            or not _positive(source["raw_underlying_price"])
            or local.date().isoformat() != row["stock_decision_session_et"]
            or (local.hour, local.minute, local.second) != (9, 35, 0)
            or not date.fromisoformat(row["source_signal_session"])
            < local.date() < date.fromisoformat(row["expiration"])
            or row["structural_rank"] != 0
            or row["selection_never_uses_later_liquidity"] is not True
        ):
            raise IntegratedCasebookError("stock/news/option decision identity drifted")
        status = row["reference_status"]
        if status not in {
            "NO_LATER_TWO_SIDED_REFERENCE",
            "ENTRY_REFERENCE_ONLY_NO_SUBSEQUENT_REFERENCE",
            "ENTRY_AND_NEXT_REFERENCE_AVAILABLE",
        }:
            raise IntegratedCasebookError("unknown original option-source disposition")
        entry_day = row["first_later_two_sided_session"]
        next_day = row["subsequent_two_sided_session"]
        if status == "NO_LATER_TWO_SIDED_REFERENCE":
            if entry_day is not None or next_day is not None:
                raise IntegratedCasebookError("missing quote has fabricated dates")
        elif status == "ENTRY_REFERENCE_ONLY_NO_SUBSEQUENT_REFERENCE":
            if entry_day is None or next_day is not None:
                raise IntegratedCasebookError("entry-only quote chronology differs")
        elif entry_day is None or next_day is None:
            raise IntegratedCasebookError("complete option pair lacks source dates")
        if entry_day is not None:
            if not local.date() < date.fromisoformat(entry_day) <= date.fromisoformat(row["expiration"]):
                raise IntegratedCasebookError("option EOD reference used decision-day/future expiry")
            if not _positive(row["first_later_eod_ask_reference_per_share"]):
                raise IntegratedCasebookError("option entry reference is not positive")
        if next_day is not None:
            if not date.fromisoformat(entry_day) < date.fromisoformat(next_day) <= date.fromisoformat(row["expiration"]):
                raise IntegratedCasebookError("option next EOD reference not strictly later")
            if not _positive(row["subsequent_eod_bid_reference_per_share"]):
                raise IntegratedCasebookError("option subsequent bid is not positive")
        context = news.prior_counts(source["ticker"], decision_utc=decision)
        news24 += context["unique_articles_available_prior_24h"] > 0
        news7 += context["unique_articles_available_prior_7d"] > 0
        disposition[status] += 1
        out.append({
            "shard_index": key[0], "opportunity_id": key[1],
            "ticker": source["ticker"], "option_symbol": row["option_symbol"],
            "stock_signal_session": source["signal_session"],
            "original_decision_at_utc": decision.isoformat(),
            "original_decision_session_et": local.date().isoformat(),
            "original_stock_raw_open_reference_per_share": source["raw_underlying_price"],
            "stock_raw_open_is_not_a_0935_or_later_eod_fill": True,
            "structural_option_rank": 0,
            "selected_option_expiration": row["expiration"],
            "option_reference_status": status,
            "first_later_option_eod_session": entry_day,
            "first_later_option_ask_reference_per_share": row["first_later_eod_ask_reference_per_share"],
            "next_later_option_eod_session": next_day,
            "next_later_option_bid_reference_per_share": row["subsequent_eod_bid_reference_per_share"],
            "option_ask_to_next_bid_reference_fraction_not_pnl": row["hypothetical_ask_to_next_bid_reference_fraction"],
            "prior_24h_news_article_count": context["unique_articles_available_prior_24h"],
            "prior_7d_news_article_count": context["unique_articles_available_prior_7d"],
            "news_time_basis": context["news_time_basis"],
            "stock_option_common_clock_comparison_ready": False,
            "missing_for_comparator": [
                "STOCK_MARKS_ON_SAME_LATER_ENTRY_AND_EXIT_SESSIONS",
                "MATCHED_OBSERVATION_TIMESTAMPS_AND_FILL_ASSUMPTIONS",
                "OPTION_DELIVERABLE_AND_CONTRACT_MULTIPLIER",
            ],
        })
        if progress and (n % 500 == 0 or n == len(rows)):
            progress({"stage": "CASEBOOK_JOIN", "opportunities": n,
                      "total_opportunities": len(rows), "provider_requests": 0})
    if (
        len(rows) != EXPECTED_OPPORTUNITIES or len(out) != EXPECTED_OPPORTUNITIES
        or dict(disposition) != {
            "NO_LATER_TWO_SIDED_REFERENCE": 5,
            "ENTRY_REFERENCE_ONLY_NO_SUBSEQUENT_REFERENCE": 9,
            "ENTRY_AND_NEXT_REFERENCE_AVAILABLE": 2629,
        }
    ):
        raise IntegratedCasebookError("full original rank-zero denominator changed")
    output = {
        "contract": CONTRACT,
        "status": "JOINED_COVERAGE_ONLY_NO_COMMON_CLOCK_TRADE_PNL",
        "original_eod_reference_fingerprint": reference["reference_fingerprint"],
        "original_rank_zero_readiness_fingerprint": EXPECTED_READINESS,
        "original_2022_quote_plan_fingerprint": EXPECTED_PLAN,
        "original_stock_source_scope": "ACCEPTED_NATIVE_RAW_2022_ADDITIVE_DEVELOPMENT",
        "news_source": news.lineage,
        "news_2022_normalized_articles_scanned": news.scanned_articles,
        "full_structural_denominator": len(out),
        "distinct_tickers": len({row["ticker"] for row in out}),
        "prior_24h_news_opportunities": news24,
        "prior_7d_news_opportunities": news7,
        "option_reference_dispositions": dict(sorted(disposition.items())),
        "provider_requests": 0,
        "protected_outcomes_read": 0,
        "authority": AUTHORITY,
        "rows": out,
    }
    output["casebook_fingerprint"] = _fingerprint(output)
    return output


def build_casebook(
    settings: AtlasSettings, *,
    progress: Callable[[dict[str, Any]], None] | None = None,
    news_threads: int = 4,
) -> dict[str, Any]:
    settings.assert_external_storage_binding("research_evidence")
    reference = _accepted_eod_reference(settings)
    sources = _accepted_stock_source(settings, reference["rows"], progress=progress)
    tickers = {row["ticker"] for row in reference["rows"]}
    if progress:
        progress({"stage": "NEWS_2022_NORMALIZED_METADATA", "month_partitions": 12,
                  "ticker_universe": len(tickers), "provider_requests": 0})
    news = OfflineNewsContext.from_accepted_2022(
        settings, tickers, threads=news_threads, progress=progress,
    )
    return assemble_casebook(reference, sources, news, progress=progress)


def write_casebook(settings: AtlasSettings, payload: dict[str, Any]) -> tuple[Path, str]:
    if (
        payload.get("contract") != CONTRACT or payload.get("authority") != AUTHORITY
        or payload.get("original_eod_reference_fingerprint") != EXPECTED_EOD_REFERENCE
        or payload.get("full_structural_denominator") != EXPECTED_OPPORTUNITIES
        or payload.get("provider_requests") != 0
        or payload.get("protected_outcomes_read") != 0
        or payload.get("casebook_fingerprint") != _fingerprint({
            k: v for k, v in payload.items() if k != "casebook_fingerprint"
        })
    ):
        raise IntegratedCasebookError("casebook payload/lineage cannot be written")
    path = settings.resolved_path(f"{OUTPUT_REL}_{EXPECTED_EOD_REFERENCE[:16]}.json")
    if path.exists() or path.is_symlink():
        if _read_object(path) != payload:
            raise IntegratedCasebookError("existing immutable casebook differs; no overwrite")
        return path, "REUSED_IDENTICAL_CASEBOOK"
    _exclusive(path, payload)
    if _read_object(path) != payload:
        raise IntegratedCasebookError("new casebook readback differs")
    return path, "WRITTEN_NEW_CASEBOOK"
