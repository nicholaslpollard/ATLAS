from __future__ import annotations

"""Explain the ten retained exit gaps from their original, hash-bound cache.

This is a source-facts audit. It never resolves a strategy, searches later quotes,
changes an exit/fee policy, settles a position or recomputes account returns.
"""

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any, Callable
from zoneinfo import ZoneInfo

from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.marketdata_candidate_2025_selected_quote_source_v1 import (
    MAX_RAW_BYTES, _classify,
)
from packages.data.multiyear_demand_quote_cache_v1 import CACHE_REL, CONTRACT as CACHE_CONTRACT
from packages.data.multiyear_marketdata_eod_clock_liquidity_probe_v1 import _decode_snapshot_rows
from packages.simulation.multiyear_strategy_aligned_eod_option_replay_v1 import _exit_row_qualified
from packages.simulation.retained_option_account_review_v1 import (
    CONTRACT as REVIEW_CONTRACT, SCENARIO_CONTRACT, _scope,
)

CONTRACT = "atlas-retained-option-exact-exit-source-audit-v1"
OUTPUT_REL = "data/research/retained_option_exit_source_audit_v1"
EASTERN = ZoneInfo("America/New_York")
HASH = re.compile(r"[0-9a-f]{64}")
OCC = re.compile(r"([A-Z0-9.]+)(\d{6})C(\d{8})")
MAX_REPORT_BYTES = 64 * 1024 * 1024
MAX_REVIEW_BYTES = 256 * 1024
MAX_RECEIPT_BYTES = 64 * 1024


class RetainedOptionExitSourceAuditError(ValueError):
    pass


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise RetainedOptionExitSourceAuditError(detail)


@dataclass(frozen=True, slots=True)
class RetainedOptionExitAuditBindingV1:
    review_path: str = "data/research/retained_option_account_review_v1/20261015T035701371767Z_98c60bf4.json"
    review_sha256: str = "1197d49cb469f00bc91cbf617c24b2b2ac0d7738a81f37af3f41323a57ce5966"
    review_fingerprint: str = "c06049ba1ca270f09fcb56d4927530ea78137fee6c0af8ceb23e1645ef51e474"
    scenario_path: str = "data/options/derived/multiyear_continuous_dynamic_exit_v2_option_scenario_03406fdf1def8233.json"
    scenario_sha256: str = "5655894de328597ac604a5aae360d5db1174665e891c6fdc07dd6f5e8fc60f46"
    scenario_fingerprint: str = "03406fdf1def82332b8e01761213ab4cd4eb9e7a8cdb551ea37ad8c9d7bfcf5b"
    replay_fingerprint: str = "b525b49fabd0aead7f6fc5c8edf33e6f7c8d125de9253de6b7d9ecdf4c7516a7"
    scenario_cases: int = 14902
    unresolved_positions: int = 10
    unresolved_contracts: int = 226


DEFAULT_BINDING = RetainedOptionExitAuditBindingV1()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _float(value: str) -> float:
    number = float(value)
    _require(math.isfinite(number), "nonfinite JSON number")
    return number


def _nonfinite(value: str) -> None:
    raise RetainedOptionExitSourceAuditError(f"nonfinite JSON number: {value}")


def _read(path: Path, *, root: Path, limit: int, sha256: str | None = None) -> bytes:
    _require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()),
             f"unsafe linked artifact: {path}")
    _require(path.is_file() and path.stat().st_size <= limit, f"missing or oversized artifact: {path}")
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    _require(len(raw) <= limit, f"artifact exceeded bounded read: {path}")
    _require(sha256 is None or hashlib.sha256(raw).hexdigest() == sha256, f"artifact SHA drifted: {path}")
    return raw


def _object(raw: bytes) -> dict[str, Any]:
    result = json.loads(raw, object_pairs_hook=_pairs, parse_float=_float, parse_constant=_nonfinite)
    _require(isinstance(result, dict), "JSON object required")
    return result


def _signature(value: dict[str, Any], field: str, expected: str | None = None) -> None:
    unsigned = dict(value)
    claimed = unsigned.pop(field, None)
    _require(isinstance(claimed, str) and HASH.fullmatch(claimed) is not None
             and claimed == _fingerprint(unsigned) and (expected is None or claimed == expected),
             f"{field} drifted")


def _stamp(value: str) -> datetime:
    stamp = datetime.fromisoformat(value)
    _require(stamp.tzinfo is not None and stamp.utcoffset() is not None, "aware source clock required")
    return stamp.astimezone(UTC)


def _relative(value: str, prefix: str) -> None:
    path = PurePosixPath(value)
    _require(not path.is_absolute() and ".." not in path.parts and value.startswith(prefix + "/"),
             "artifact binding must use its explicit relative directory")


def _source(settings: AtlasSettings, work: dict[str, Any]) -> tuple[list[dict[str, Any]] | None, dict[str, Any]]:
    source = work["recorded_entry_source_binding"]
    rid, body_sha = source["physical_quote_request_identity"], source["physical_quote_body_sha256"]
    _require(isinstance(rid, str) and HASH.fullmatch(rid) is not None
             and isinstance(body_sha, str) and HASH.fullmatch(body_sha) is not None, "invalid exact source binding")
    root = settings.resolved_path(CACHE_REL)
    stem = root / rid[:2] / rid
    paths = [stem.with_suffix(suffix) for suffix in (".json", ".receipt.json", ".attempt.json")]
    for path in paths:
        _require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()),
                 f"unsafe source cache path: {path}")
    missing = [suffix for suffix, path in zip(("body", "receipt", "attempt"), paths) if not path.exists()]
    evidence = {"request_identity": rid, "body_sha256": body_sha, "missing_cache_members": missing}
    if missing:
        return None, evidence
    receipt_raw = _read(paths[1], root=root, limit=MAX_RECEIPT_BYTES)
    intent_raw = _read(paths[2], root=root, limit=MAX_RECEIPT_BYTES)
    receipt, intent = _object(receipt_raw), _object(intent_raw)
    _signature(receipt, "receipt_fingerprint")
    _signature(intent, "intent_fingerprint")
    query = receipt["query"]
    _require(isinstance(query, dict) and set(query) == {"option_symbol", "from_inclusive", "to_exclusive"}
             and intent["query"] == query and query["option_symbol"] == work["option_symbol"],
             "physical source query differs from unresolved contract")
    _require(_fingerprint({"contract": CACHE_CONTRACT, "query": query}) == rid
             and receipt["request_identity"] == intent["request_identity"] == rid
             and receipt["contract"] == intent["contract"] == CACHE_CONTRACT
             and intent["automatic_retry_permitted"] is False, "physical request/attempt identity drifted")
    start, end = date.fromisoformat(query["from_inclusive"]), date.fromisoformat(query["to_exclusive"])
    expiry = date.fromisoformat(work["expiration"])
    entry_day = _stamp(work["entry_at_utc"]).astimezone(EASTERN).date()
    exit_day = _stamp(work["recorded_failed_exit_at_utc"]).astimezone(EASTERN).date()
    _require(date(2021, 1, 1) <= start <= entry_day < exit_day < end <= expiry + timedelta(days=1)
             and end <= date(2026, 1, 1), "physical source window crosses bound entry/exit/expiry scope")
    raw = _read(paths[0], root=root, limit=MAX_RAW_BYTES, sha256=body_sha)
    _object(raw)  # Reject duplicate/nonfinite JSON before the legacy pure decoder.
    ticket = {**query, "request_identity": rid}
    classification, safe = _classify(ticket, receipt["http_status"], raw)
    rate = receipt.get("rate_limit", {})
    _require(isinstance(rate, dict), "physical receipt rate-limit metadata malformed")
    _require(receipt["status"] == "COMPLETE_SOURCE_ONLY"
             and classification == receipt["classification"] == "EOD_SOURCE_ROWS_NO_FILL_AUTHORITY"
             and receipt["body_sha256"] == body_sha and type(receipt["body_bytes"]) is int
             and receipt["body_bytes"] == len(raw) and receipt["safe_summary"] == safe
             and receipt.get("source_only_not_fill_or_trade_pnl") is True
             and receipt.get("subscription_data_retention_required") is True
             and all(type(rate.get(k)) is int and rate[k] >= 0 for k in ("consumed", "remaining")),
             "physical receipt/body classification or provenance drifted")
    evidence.update({"query": query, "body_bytes": len(raw),
        "receipt_fingerprint": receipt["receipt_fingerprint"], "intent_fingerprint": intent["intent_fingerprint"],
        "receipt_file_sha256": hashlib.sha256(receipt_raw).hexdigest(),
        "intent_file_sha256": hashlib.sha256(intent_raw).hexdigest()})
    return _decode_snapshot_rows(raw, ticket, safe["observed_rows"]), evidence


def _facts(work: dict[str, Any], case: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    at = _stamp(work["recorded_failed_exit_at_utc"])
    day = at.astimezone(EASTERN).date()
    _, close = get_market_calendar().regular_open_close(day)
    _require(at == close, "retained failed-exit clock differs from original stock-session close")
    exact = [row for row in rows if row["session_et"] == day.isoformat()]
    _require(len(exact) == 1, "retained exact-exit quote missing or duplicated in pinned source")
    row, stored = exact[0], case["strategy_exit_option_mark"]
    _require(isinstance(stored, dict), "retained failed-exit source projection missing")
    for field in ("session_et", "updated_at_utc", "two_sided", "positive_bid_size", "positive_reported_volume"):
        _require(type(stored.get(field)) is type(row[field]) and stored[field] == row[field],
                 f"retained exact-exit source projection drifted: {field}")
    _require(stored["bid_per_share"] == row["bid"], "retained exit bid projection drifted")
    observed = _stamp(row["updated_at_utc"])
    failures = []
    for okay, reason in (
        (row["updated_is_1600_et"], "LEGACY_REQUIRES_1600_ET"),
        (row["two_sided"], "NOT_POSITIVE_UNCROSSED_TWO_SIDED"),
        (row["positive_bid_size"], "BID_SIZE_NOT_POSITIVE"),
        (row["positive_reported_volume"], "REPORTED_VOLUME_NOT_POSITIVE"),
        (row["underlying_price_same_snapshot"] is not None, "SAME_SNAPSHOT_UNDERLYING_MISSING"),
    ):
        if not okay:
            failures.append(reason)
    legacy_pass = _exit_row_qualified(row)
    _require(legacy_pass == (not failures), "legacy predicate decomposition changed")
    size = row["bid_size_contracts"]
    return {"status": "VERIFIED_ORIGINAL_EXACT_EXIT_SOURCE_FACTS",
        "expected_stock_session_close_utc": close.isoformat(),
        "early_close_stock_session": close.astimezone(EASTERN).hour != 16,
        "snapshot_clock_relation": "AT_RECORDED_EXIT" if observed == at else
            "AFTER_RECORDED_EXIT" if observed > at else "BEFORE_RECORDED_EXIT",
        "snapshot_at_calendar_close": observed == close,
        "calendar_close_rejected_by_legacy_1600_rule": observed == close and not row["updated_is_1600_et"],
        "legacy_failure_reasons": failures, "retained_rejection_reproduced": not legacy_pass,
        "reported_bid_size_covers_position": size >= work["contracts"] if size is not None else None,
        "quote_snapshot_not_fill": row}


def audit_retained_option_exit_sources(
    settings: AtlasSettings, *, binding: RetainedOptionExitAuditBindingV1 = DEFAULT_BINDING,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Read a pinned review/scenario and at most ten named physical cache triplets."""
    _relative(binding.review_path, "data/research/retained_option_account_review_v1")
    _relative(binding.scenario_path, "data/options/derived")
    _require(type(binding.unresolved_positions) is int and 1 <= binding.unresolved_positions <= 10
             and type(binding.scenario_cases) is int and 1 <= binding.scenario_cases <= 20000
             and type(binding.unresolved_contracts) is int and 1 <= binding.unresolved_contracts <= 100000,
             "audit population binding invalid")
    for key, value in asdict(binding).items():
        if key.endswith(("fingerprint", "sha256")):
            _require(isinstance(value, str) and HASH.fullmatch(value) is not None, f"invalid {key}")
    review = _object(_read(settings.resolved_path(binding.review_path),
        root=settings.resolved_path("data/research/retained_option_account_review_v1"),
        limit=MAX_REVIEW_BYTES, sha256=binding.review_sha256))
    _signature(review, "report_fingerprint", binding.review_fingerprint)
    _require(review["contract"] == REVIEW_CONTRACT
             and review["status"] == "COMPLETE_RETAINED_LEDGER_REVIEW_UNRESOLVED_EVIDENCE_DEMAND"
             and review["original_cases"] == binding.scenario_cases
             and review["source_scenario_fingerprint"] == binding.scenario_fingerprint
             and review["source_scenario_file_sha256"] == binding.scenario_sha256
             and review["source_replay_fingerprint"] == binding.replay_fingerprint,
             "retained review lineage drifted")
    for key in ("provider_requests", "broker_requests", "raw_source_files_read", "simulations_run"):
        _require(type(review[key]) is int and review[key] == 0, f"review scope drifted: {key}")
    for key in ("original_artifacts_modified", "source_reaccepted", "strategy_promotion",
                "historical_account_return_authority", "paper", "live"):
        _require(review[key] is False, f"review authority drifted: {key}")
    _require(review["equity"] is review["total_return"] is review["terminal_valuation_clock"] is None,
             "unknown retained valuation changed")
    scenario = _object(_read(settings.resolved_path(binding.scenario_path),
        root=settings.resolved_path("data/options/derived"), limit=MAX_REPORT_BYTES,
        sha256=binding.scenario_sha256))
    _signature(scenario, "scenario_fingerprint", binding.scenario_fingerprint)
    _scope(scenario, scenario=True)
    _require(scenario["contract"] == SCENARIO_CONTRACT
             and scenario["original_case_denominator"] == binding.scenario_cases
             and len(scenario["cases"]) == binding.scenario_cases, "retained scenario population changed")
    cases = {row["case_id"]: row for row in scenario["cases"]}
    _require(len(cases) == binding.scenario_cases, "duplicate retained scenario case")
    work_items = review["unresolved_positions"]
    _require(isinstance(work_items, list) and len(work_items) == review["unresolved"] == binding.unresolved_positions
             and len({row["case_id"] for row in work_items}) == len(work_items)
             and sum(row["contracts"] for row in work_items) == binding.unresolved_contracts,
             "unresolved review population changed")
    output, sources = [], {}
    for index, work in enumerate(sorted(work_items, key=lambda row: row["case_id"]), 1):
        cid = work["case_id"]
        _require(cid in cases and type(work["contracts"]) is int and 1 <= work["contracts"] <= 10000,
                 "unresolved case/quantity invalid")
        case, symbol = cases[cid], work["option_symbol"]
        occ = OCC.fullmatch(symbol)
        _require(occ is not None and occ.group(1) == work["ticker"]
                 and datetime.strptime(occ.group(2), "%y%m%d").date().isoformat() == work["expiration"],
                 "unresolved contract identity drifted")
        _require(case["ticker"] == work["ticker"] and case["economic_family_id"] == work["economic_family_id"]
                 and case["call"]["option_symbol"] == symbol
                 and case["call"]["entry"]["at_utc"] == work["entry_at_utc"]
                 and case["stock_exit"] == work["recorded_stock_exit"]
                 and case["strategy_aligned_status"] == work["source_gap_reason"]
                    == "STRATEGY_EXIT_SESSION_OPTION_LIQUIDITY_GAP",
                 "unresolved scenario/review membership drifted")
        source = work["recorded_entry_source_binding"]
        _require(all(case["call"]["entry"][key] == source[key] for key in (
            "physical_quote_request_identity", "physical_quote_body_sha256")), "entry source binding drifted")
        rid = source["physical_quote_request_identity"]
        if rid not in sources:
            sources[rid] = _source(settings, work)
        rows, evidence = sources[rid]
        _require(evidence["body_sha256"] == source["physical_quote_body_sha256"], "shared source body binding drifted")
        facts = ({"status": "CACHE_EVIDENCE_MISSING", "legacy_failure_reasons": None,
                  "retained_rejection_reproduced": None, "reported_bid_size_covers_position": None}
                 if rows is None else _facts(work, case, rows))
        output.append({"case_id": cid, "ticker": work["ticker"], "option_symbol": symbol,
            "contracts": work["contracts"], "recorded_failed_exit_at_utc": work["recorded_failed_exit_at_utc"],
            "recorded_source_gap_reason": work["source_gap_reason"], "source_evidence": evidence, **facts})
        if progress:
            progress(f"exact source {index}/{len(work_items)}: {symbol}: {facts['status']}")
    verified = [row for row in output if row["status"] == "VERIFIED_ORIGINAL_EXACT_EXIT_SOURCE_FACTS"]
    missing = len(output) - len(verified)
    report = {"contract": CONTRACT,
        "status": "COMPLETE_EXACT_EXIT_SOURCE_AUDIT_WITH_CACHE_GAPS" if missing else "COMPLETE_EXACT_EXIT_SOURCE_AUDIT",
        "binding_fingerprint": _fingerprint(asdict(binding)),
        "source_review_fingerprint": binding.review_fingerprint, "source_review_file_sha256": binding.review_sha256,
        "source_scenario_fingerprint": binding.scenario_fingerprint, "source_scenario_file_sha256": binding.scenario_sha256,
        "positions": output, "position_count": len(output), "contract_count": binding.unresolved_contracts,
        "verified_position_sources": len(verified), "missing_position_sources": missing,
        "legacy_failure_counts_nonexclusive": dict(sorted(Counter(
            reason for row in verified for reason in row["legacy_failure_reasons"]).items())),
        "snapshot_clock_relations": dict(sorted(Counter(row["snapshot_clock_relation"] for row in verified).items())),
        "calendar_close_rejected_by_legacy_1600_rule": sum(row["calendar_close_rejected_by_legacy_1600_rule"] for row in verified),
        "reported_bid_size_below_position": sum(row["reported_bid_size_covers_position"] is False for row in verified),
        "reported_bid_size_unknown": sum(row["reported_bid_size_covers_position"] is None for row in verified),
        "retained_classification_disagreements": sum(row["retained_rejection_reproduced"] is False for row in verified),
        "raw_option_files_read": sum(rows is not None for rows, _ in sources.values()),
        "raw_option_bytes_read": sum(evidence.get("body_bytes", 0) for _, evidence in sources.values()),
        "raw_stock_files_read": 0, "protected_2026_outcomes_read": 0,
        "provider_requests": 0, "broker_requests": 0, "simulations_run": 0,
        "later_quote_search_performed": False, "source_reaccepted": False, "historical_fill_authority": False,
        "option_trading_hours_qualified": False, "source_publication_availability_verified": False,
        "exit_policy_changed": False, "fee_policy_changed": False, "settlement_inferred": False,
        "capital_released": False, "original_artifacts_modified": False, "strategy_promotion": False,
        "equity": None, "total_return": None, "terminal_valuation_clock": None, "paper": False, "live": False}
    report["report_fingerprint"] = _fingerprint(report)
    return report
