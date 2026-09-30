from __future__ import annotations

"""Deduplicate concrete missing execution proof for observed dated source pairs.

This is a source-work manifest, not a paid query plan or a historical replay.
A provider quote `updated` timestamp does NOT prove first public availability,
and a native daily stock CLOSE has no certified same-clock option timestamp.
"""

from collections import Counter
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_demand_quote_cache_v1 import _write_new
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.data.multiyear_verified_stock_option_source_casebook_v1 import (
    CONTRACT as CASEBOOK_CONTRACT, SOURCE_PAIR,
)
from packages.simulation.multiyear_account_readiness_v1 import (
    CONTRACT as READINESS_CONTRACT,
)

CONTRACT = "atlas-multiyear-historical-option-execution-proof-demand-v1"
OUTPUT_REL = "data/options/derived/multiyear_historical_execution_proof_demand_v1"
REQUIREMENTS = (
    "INDEPENDENT_OPTION_QUOTE_PUBLICATION_OR_RETRIEVAL_AVAILABILITY_CLOCK",
    "INDEPENDENT_UNDERLYING_PRICE_OBSERVATION_AND_AVAILABILITY_CLOCK",
    "VALIDATED_MATCHED_AS_TRADED_UNDERLYING_PRICE_AT_DECISION_EXECUTION_CLOCK",
    "POINT_IN_TIME_OPTION_DELIVERABLE_AND_CONTRACT_MULTIPLIER",
    "CONSERVATIVE_QUOTE_SIDE_LIQUIDITY_AND_EXECUTION_COSTS",
    "EXPLICIT_EXPIRY_EXERCISE_ASSIGNMENT_AND_MISSING_EXIT_POLICY",
)


class HistoricalExecutionRequirementsError(ValueError):
    pass


def _value(value: Any, label: str, *, allow_zero: bool = False) -> str:
    if not isinstance(value, str) or not value:
        raise HistoricalExecutionRequirementsError(f"{label} must be a source decimal")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise HistoricalExecutionRequirementsError(f"{label} malformed") from exc
    if not number.is_finite() or (number < 0 if allow_zero else number <= 0):
        raise HistoricalExecutionRequirementsError(f"{label} invalid")
    return value


def _source_mark(
    option: dict[str, Any], stock: dict[str, Any], *, quote_body_sha: str,
    quote_identity: str, option_symbol: str, ticker: str,
    stage: str,
) -> dict[str, Any]:
    if (
        not isinstance(option, dict) or not isinstance(stock, dict)
        or option.get("two_sided_source") is not True
        or option.get("publication_and_stock_close_clock_unproven") is not True
        or stock.get("status") != "VERIFIED_NATIVE_RAW_EOD_CLOSE"
        or stock.get("actual_close_observation_timestamp_unavailable") is not True
        or option.get("session_et") != stock.get("session_et")
    ):
        raise HistoricalExecutionRequirementsError("source mark was promoted or date-mismatched")
    stamp = datetime.fromisoformat(option["provider_updated_at_utc"])
    session = date.fromisoformat(option["session_et"])
    if stamp.tzinfo is None:
        raise HistoricalExecutionRequirementsError("provider update timestamp naive")
    bid = _value(option["observed_bid_per_share"], "observed bid")
    ask = _value(option["observed_ask_per_share"], "observed ask")
    close = _value(stock["raw_as_traded_close"], "raw stock close")
    if Decimal(ask) < Decimal(bid):
        raise HistoricalExecutionRequirementsError("crossed source quote")
    native_sha = stock.get("native_canonical_sha256")
    native_id = stock.get("native_unit_id")
    if (
        not isinstance(native_sha, str) or len(native_sha) != 64
        or any(ch not in "0123456789abcdef" for ch in native_sha)
        or not isinstance(native_id, str) or not native_id
        or not isinstance(stock.get("request_identity"), str)
        or not stock["request_identity"]
    ):
        raise HistoricalExecutionRequirementsError("original native stock provenance absent")
    identity = _fingerprint({
        "quote_history_body_sha256": quote_body_sha,
        "quote_query_identity": quote_identity,
        "option_symbol": option_symbol,
        "provider_updated_at_utc": stamp.isoformat(),
        "session_et": session.isoformat(),
        "observed_bid": bid, "observed_ask": ask,
    })
    return {
        "stage": stage, "option_observation_identity": identity,
        "session_et": session.isoformat(),
        "option_symbol": option_symbol,
        "physical_quote_body_sha256": quote_body_sha,
        "quote_request_identity": quote_identity,
        "provider_updated_at_utc_not_publication_proof": stamp.isoformat(),
        "source_bid_per_share_not_fill": bid,
        "source_ask_per_share_not_fill": ask,
        "underlying": ticker,
        "native_close_request_identity": stock["request_identity"],
        "native_unit_id": native_id,
        "native_canonical_sha256": native_sha,
        "raw_daily_close_not_synchronized_mark": close,
        "same_session_only_not_common_clock": True,
        "publication_availability_verified": False,
        "stock_option_common_clock_verified": False,
        "historical_trade_execution_authority": False,
    }


def build_execution_proof_demand(
    casebook: dict[str, Any], readiness: dict[str, Any], *,
    expected_cases: int = 14902,
) -> dict[str, Any]:
    for doc, key in ((casebook, "casebook_fingerprint"), (readiness, "readiness_fingerprint")):
        _check_signature(doc, key)
    total = 2 * expected_cases
    if (
        casebook.get("contract") != CASEBOOK_CONTRACT
        or readiness.get("contract") != READINESS_CONTRACT
        or readiness.get("source_casebook_fingerprint") != casebook["casebook_fingerprint"]
        or any(doc.get("original_case_denominator") != expected_cases
               or doc.get("original_right_memberships") != total
               or doc.get("provider_requests") != 0
               for doc in (casebook, readiness))
        or readiness.get("actual_executable_option_trades") != 0
        or readiness.get("historical_account_pnl_authority") is not False
        or casebook.get("account_pnl_authority") is not False
    ):
        raise HistoricalExecutionRequirementsError("signed source lineage, population or authority changed")
    rows = casebook.get("rows")
    blockers = readiness.get("rows")
    if not isinstance(rows, list) or not isinstance(blockers, list):
        raise HistoricalExecutionRequirementsError("source or readiness rows missing")
    indexed = {row["case_right_id"]: row for row in blockers}
    if (len(rows) != total or len(blockers) != total
            or len(indexed) != total or set(indexed) != {row["case_right_id"] for row in rows}):
        raise HistoricalExecutionRequirementsError("case-right source/readiness denominator changed")
    work_rows: list[dict[str, Any]] = []
    distinct_option: dict[str, dict[str, Any]] = {}
    distinct_native = set()
    yearly: dict[str, Counter[str]] = {str(y): Counter() for y in range(2021, 2027)}
    for row in sorted(rows, key=lambda x: x["case_right_id"]):
        key = row["case_right_id"]
        ready = indexed[key]
        if (row["original_case_id"] != ready["original_case_id"]
                or row["right"] != ready["right"]
                or row["year"] != ready["year"]
                or row["option_symbol"] != ready["option_symbol"]
                or row["ticker"] != ready["ticker"]
                or ready.get("historical_trade_admitted") is not False):
            raise HistoricalExecutionRequirementsError("source/readiness right identity drift")
        if row["source_join_status"] != SOURCE_PAIR:
            yearly[row["year"]][ready["replay_blocker"]] += 1
            continue
        if ready["replay_blocker"] != "SOURCE_DATES_PAIRED_BUT_CLOCK_DELIVERABLE_AND_FILL_UNPROVEN":
            raise HistoricalExecutionRequirementsError("qualified source pair was promoted")
        sha = row.get("quote_source_body_sha256") or row.get(
            "original_quote_body_sha256"
        )
        query = row.get("quote_source_request_identity") or row.get(
            "quote_request_identity"
        )
        clipped = row.get("quote_source_is_clipped_recovery") is True
        if (
            not isinstance(sha, str) or len(sha) != 64
            or any(ch not in "0123456789abcdef" for ch in sha)
            or not isinstance(query, str) or not query
            or not isinstance(row.get("option_symbol"), str)
            or (clipped and (
                row.get("original_quote_body_sha256") is not None
                or not isinstance(row.get("quote_source_from_inclusive"), str)
                or not isinstance(row.get("quote_source_to_exclusive"), str)
            ))
        ):
            raise HistoricalExecutionRequirementsError("physical quote provenance missing")
        entry = _source_mark(
            row["first_later_option_source"], row["entry_session_native_source"],
            quote_body_sha=sha, quote_identity=query,
            option_symbol=row["option_symbol"], ticker=row["ticker"],
            stage="ENTRY_SOURCE_NOT_EXECUTION",
        )
        later = _source_mark(
            row["next_later_option_source"], row["next_session_native_source"],
            quote_body_sha=sha, quote_identity=query,
            option_symbol=row["option_symbol"], ticker=row["ticker"],
            stage="LATER_SOURCE_NOT_EXIT_EXECUTION",
        )
        if clipped:
            for mark in (entry, later):
                mark["source_is_clipped_recovery"] = True
                mark["source_from_inclusive"] = row["quote_source_from_inclusive"]
                mark["source_to_exclusive"] = row["quote_source_to_exclusive"]
                mark["missing_original_prefix_is_not_reconstructed"] = True
        if entry["session_et"] >= later["session_et"]:
            raise HistoricalExecutionRequirementsError("future source chronology changed")
        for mark in (entry, later):
            option_key = mark["option_observation_identity"]
            original = dict(mark)
            original.pop("stage")
            if option_key in distinct_option and distinct_option[option_key] != original:
                raise HistoricalExecutionRequirementsError("same quote identity changed observed value")
            distinct_option[option_key] = original
            distinct_native.add(mark["native_close_request_identity"])
        yearly[row["year"]]["DATED_PAIR_PENDING_INDEPENDENT_EXECUTION_PROOF"] += 1
        work_rows.append({
            "case_right_id": key,
            "original_case_id": row["original_case_id"],
            "year": row["year"], "right": row["right"],
            "ticker": row["ticker"], "option_symbol": row["option_symbol"],
            "entry_source": entry, "later_source": later,
            "required_independent_proofs": list(REQUIREMENTS),
            "historical_entry_admitted": False,
            "historical_exit_admitted": False,
            "historical_trade_or_account_pnl_authority": False,
        })
    if (len(work_rows) != casebook.get("dated_option_and_stock_source_rights")
            or sum(sum(year.values()) for year in yearly.values()) != total):
        raise HistoricalExecutionRequirementsError("paired-source coverage changed")
    report = {
        "contract": CONTRACT,
        "status": "CLOCK_AND_DELIVERABLE_PROOF_DEMAND_SOURCE_ONLY",
        "casebook_fingerprint": casebook["casebook_fingerprint"],
        "readiness_fingerprint": readiness["readiness_fingerprint"],
        "original_case_denominator": expected_cases,
        "original_right_memberships": total,
        "dated_pair_work_items": len(work_rows),
        "dated_pair_source_marks": len(work_rows) * 2,
        "distinct_option_observations": len(distinct_option),
        "distinct_original_native_close_queries": len(distinct_native),
        "required_independent_proofs": list(REQUIREMENTS),
        "by_year": {
            year: dict(sorted(yearly[year].items())) for year in yearly
        },
        "rows": work_rows,
        "provider_requests": 0,
        "historical_option_trades": 0,
        "historical_account_pnl": None,
        "historical_account_pnl_authority": False,
        "protected_2026_outcomes_read": 0,
    }
    report["proof_demand_fingerprint"] = _fingerprint(report)
    return report


def persist_execution_proof_demand(
    settings: AtlasSettings, report: dict[str, Any],
) -> tuple[Path, str]:
    settings.assert_external_storage_binding("options")
    _check_signature(report, "proof_demand_fingerprint")
    path = settings.resolved_path(
        f"{OUTPUT_REL}_{report['proof_demand_fingerprint'][:16]}.json"
    )
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or _read_object(path) != report:
            raise HistoricalExecutionRequirementsError("previous immutable proof demand differs")
        return path, "REUSED_IDENTICAL_EXECUTION_PROOF_DEMAND"
    _write_new(path, report)
    return path, "WRITTEN_IMMUTABLE_EXECUTION_PROOF_DEMAND"
