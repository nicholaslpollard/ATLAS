from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from packages.data.intraday_semantics_audit import run_b34_audit, write_b34_report
from packages.strategies.intraday_opening_pack import (
    B34_INTRADAY_PACK_FINGERPRINT,
    B34_INTRADAY_SPECIFICATIONS,
    frozen_pack_manifest,
)


B34_READINESS_CONTRACT = "atlas-b34-intraday-source-readiness-v2-ohlcv-pack-frozen"


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sample_ohlcv_rows(sample: dict[str, object]) -> list[tuple[object, ...]]:
    path = Path(str(sample.get("canonical_path") or ""))
    symbol = str(sample.get("symbol") or "")
    session_date = str(sample.get("session_date") or "")
    if not path.is_file() or not symbol or not session_date:
        return []
    con = duckdb.connect(":memory:")
    try:
        return con.execute(
            """
            SELECT open, high, low, close, volume, vwap, transaction_count
            FROM read_parquet(?, hive_partitioning=false)
            WHERE symbol = ? AND session_date = CAST(? AS DATE)
            ORDER BY timestamp_utc
            """,
            [str(path), symbol, session_date],
        ).fetchall()
    finally:
        con.close()


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def validate_sample_ohlcv(sample: dict[str, object]) -> dict[str, object]:
    expected_rows = int(sample.get("row_count") or 0)
    allow_empty = bool(sample.get("allow_empty"))
    if expected_rows == 0 and allow_empty:
        return {
            "sample_class": str(sample.get("sample_class") or ""),
            "symbol": str(sample.get("symbol") or ""),
            "session_date": str(sample.get("session_date") or ""),
            "row_count": 0,
            "accepted": True,
            "errors": [],
            "note": "accepted source absence; no synthetic OHLCV row created",
        }

    rows = _sample_ohlcv_rows(sample)
    errors: list[str] = []
    if len(rows) != expected_rows:
        errors.append(f"OHLCV row count {len(rows)} != semantic sample row count {expected_rows}")

    for index, (open_, high, low, close, volume, vwap, transaction_count) in enumerate(rows):
        prices = (open_, high, low, close)
        if not all(_finite_number(value) and float(value) > 0 for value in prices):
            errors.append(f"row {index}: OHLC prices must be finite and positive")
            continue
        open_f, high_f, low_f, close_f = map(float, prices)
        if low_f > high_f or high_f < max(open_f, close_f) or low_f > min(open_f, close_f):
            errors.append(f"row {index}: invalid OHLC geometry")
        if not _finite_number(volume) or float(volume) < 0:
            errors.append(f"row {index}: volume must be finite and nonnegative")
        if vwap is not None and (not _finite_number(vwap) or float(vwap) <= 0):
            errors.append(f"row {index}: vwap must be finite and positive when present")
        if transaction_count is not None:
            if isinstance(transaction_count, bool) or not isinstance(transaction_count, int) or transaction_count < 0:
                errors.append(f"row {index}: transaction_count must be a nonnegative integer when present")

    return {
        "sample_class": str(sample.get("sample_class") or ""),
        "symbol": str(sample.get("symbol") or ""),
        "session_date": str(sample.get("session_date") or ""),
        "row_count": len(rows),
        "accepted": not errors,
        "errors": errors,
    }


def run_b34_source_readiness(project_root: Path) -> dict[str, object]:
    semantic = run_b34_audit(project_root)
    samples = [dict(sample) for sample in semantic.get("sample_classes", [])]
    ohlcv = [validate_sample_ohlcv(sample) for sample in samples]

    segment_totals = {"premarket": 0, "regular": 0, "after_hours": 0}
    for sample in samples:
        counts = sample.get("segment_counts") or {}
        if isinstance(counts, dict):
            for segment in segment_totals:
                segment_totals[segment] += int(counts.get(segment) or 0)

    classes = {str(sample.get("sample_class") or ""): sample for sample in samples}
    required_classes = {
        "liquid_symbol_day",
        "sparse_or_no_trade_symbol_day",
        "split_day",
        "other_corporate_action_day",
        "dst_session_boundary_day",
    }
    class_coverage_ok = required_classes.issubset(classes) and all(
        bool(classes[name].get("accepted")) for name in required_classes
    )
    integrity_ok = all(bool(item.get("accepted")) for item in semantic.get("unit_integrity", []))
    ohlcv_ok = all(bool(item.get("accepted")) for item in ohlcv)
    extended_hours_ready = segment_totals["premarket"] > 0 and segment_totals["regular"] > 0
    protected_ok = int((semantic.get("protected_interval") or {}).get("overlapping_canonical_partitions_opened") or 0) == 0

    source_ready = all(
        (
            bool(semantic.get("accepted")),
            class_coverage_ok,
            integrity_ok,
            ohlcv_ok,
            extended_hours_ready,
            protected_ok,
        )
    )

    report: dict[str, Any] = {
        **semantic,
        "contract": B34_READINESS_CONTRACT,
        "semantic_audit_contract": semantic.get("contract"),
        "semantic_audit_evidence_sha256": semantic.get("evidence_sha256"),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_readiness_accepted": source_ready,
        "ohlcv_validation": ohlcv,
        "extended_hours_coverage": {
            "sample_segment_totals": segment_totals,
            "premarket_and_regular_represented": extended_hours_ready,
            "after_hours_represented": segment_totals["after_hours"] > 0,
            "interpretation": (
                "Observed SIP bars demonstrate representable premarket, regular, and when present "
                "after-hours trade aggregates. Missing minute stamps remain source absence and are not filled."
            ),
        },
        "auction_halt_missing_bar_policy": {
            "opening_auction": (
                "B34 does not infer a separate auction print from aggregate bars; any eligible opening trades "
                "reported inside the 09:30 bar remain part of that provider aggregate."
            ),
            "halts_and_no_trade_minutes": (
                "An absent aggregate is not classified as a halt or a zero-volume minute. It is preserved as "
                "absence. Strategy aggregates use observed trades only and never fabricate a bar."
            ),
        },
        "split_adjustment_policy": {
            "canonical_minute_adjustment": "raw",
            "fabricate_adjusted_minute_bars": False,
            "cross_split_price_or_volume_lookback": "ineligible_fail_closed",
        },
        "information_clock": {
            "bar_timestamp": "left edge/start of one-minute interval",
            "bar_available": "timestamp + 1 minute",
            "premarket_window_et": "04:00 inclusive through 09:30 exclusive",
            "premarket_latest_eligible_stamp_et": "09:29",
            "premarket_state_available_et": "09:30",
            "opening_range_window_et": "09:30 inclusive through 09:45 exclusive",
            "opening_range_latest_eligible_stamp_et": "09:44",
            "opening_range_state_available_et": "09:45",
        },
        "opening_premarket_pack": {
            "frozen": True,
            "contract": frozen_pack_manifest()["contract"],
            "fingerprint": B34_INTRADAY_PACK_FINGERPRINT,
            "strategy_ids": [spec.strategy_id for spec in B34_INTRADAY_SPECIFICATIONS],
            "authority": "RESEARCH",
            "outcome_access_permitted": False,
            "governed_performance_accessed": False,
        },
        "b34_package_ready_for_repository_acceptance": source_ready,
        "broad_minute_materialization_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "provider_calls": 0,
        "broker_reads": 0,
        "broker_writes": 0,
    }
    report["evidence_sha256"] = hashlib.sha256(
        _stable_json({k: v for k, v in report.items() if k != "generated_at_utc"}).encode("utf-8")
    ).hexdigest()
    report["status"] = "ACCEPTED" if source_ready else "REJECTED"
    report["accepted"] = source_ready
    return report


def write_b34_source_readiness(project_root: Path, report: dict[str, object]) -> Path:
    return write_b34_report(project_root, report)
