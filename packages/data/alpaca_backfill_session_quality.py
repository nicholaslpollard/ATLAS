from __future__ import annotations

import gzip
import hashlib
import json
from array import array
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import exchange_calendars as xcals
import pandas as pd

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_acquisition import ALPACA_BACKFILL_ACQUISITION_CONTRACT_VERSION
from packages.data.alpaca_backfill_policy import ALPACA_BACKFILL_END, ALPACA_BACKFILL_START
from packages.data.alpaca_backfill_quality import (
    ALPACA_BACKFILL_QUALITY_BASELINE_CONTRACT_VERSION,
    inspect_daily_bar,
    _unit_window,
)


ALPACA_BACKFILL_SESSION_QUALITY_CONTRACT_VERSION = (
    "historical-backfill-quality-session-coverage-v1-trade-lifespan-xnys"
)
CALENDAR_NAME = "XNYS"
TRADE_BACKED = "TRADE_BACKED"
ZERO_ACTIVITY_PLACEHOLDER = "ZERO_ACTIVITY_PLACEHOLDER"
STATUS_TO_BIT = {TRADE_BACKED: 0, ZERO_ACTIVITY_PLACEHOLDER: 1}
BIT_TO_STATUS = {0: TRADE_BACKED, 1: ZERO_ACTIVITY_PLACEHOLDER}
SENTINEL_SYMBOLS = (
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "AAPL",
    "MSFT",
    "AMZN",
    "GOOG",
    "GOOGL",
    "IBM",
    "XOM",
    "JPM",
)


@dataclass(frozen=True, slots=True)
class SymbolSessionAnalysis:
    evaluable_trade_lifespan: bool
    placeholder_only: bool
    trade_backed_nonexchange_only: bool
    first_trade_session: str | None
    last_trade_session: str | None
    expected_xnys_sessions: int
    trade_backed_sessions: int
    placeholder_sessions: int
    missing_sessions: int
    raw_session_coverage_ratio: float | None
    trade_backed_coverage_ratio: float | None
    placeholder_sessions_outside_trade_lifespan: int
    max_consecutive_placeholder_sessions: int
    max_consecutive_missing_sessions: int
    max_consecutive_no_trade_backed_sessions: int
    expected_session_ordinals: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class AlpacaBackfillSessionQualityReport:
    contract_version: str
    parent_quality_contract_version: str
    calendar_name: str
    generated_at_utc: str
    canonical_data_modified: bool
    retained_unit_manifests: int
    retained_raw_bar_pages: int
    raw_payload_hash_failures: int
    identity_safe_raw_rows: int
    parent_identity_safe_raw_rows: int
    trade_backed_raw_rows: int
    parent_trade_backed_raw_rows: int
    zero_activity_placeholder_raw_rows: int
    parent_zero_activity_placeholder_raw_rows: int
    quarantined_response_bar_rows: int
    parent_quarantined_response_bar_rows: int
    observed_symbols: int
    unique_session_keys: int
    duplicate_session_rows: int
    duplicate_session_keys: int
    exact_duplicate_session_keys: int
    conflicting_duplicate_session_keys: int
    status_conflicting_duplicate_session_keys: int
    non_exchange_session_rows: int
    non_exchange_session_keys: int
    evaluable_trade_lifespan_symbols: int
    placeholder_only_symbols: int
    trade_backed_nonexchange_only_symbols: int
    expected_exchange_sessions_within_trade_lifespans: int
    trade_backed_sessions_within_lifespans: int
    placeholder_sessions_within_lifespans: int
    missing_sessions_within_lifespans: int
    placeholder_sessions_outside_trade_lifespans: int
    symbols_with_internal_placeholder_sessions: int
    symbols_with_internal_missing_sessions: int
    max_consecutive_placeholder_sessions: int
    max_consecutive_missing_sessions: int
    max_consecutive_no_trade_backed_sessions: int
    market_sessions_with_zero_raw_coverage: int
    lowest_market_coverage_sessions: list[dict[str, object]]
    sentinel_coverage: dict[str, object]
    raw_row_accounting_exact: bool
    parent_classification_accounting_exact: bool
    unique_session_accounting_exact: bool
    symbol_coverage_path: str
    market_session_coverage_path: str
    duplicate_session_path: str
    non_exchange_session_path: str
    report_path: str


def xnys_session_ordinals(start: date, end: date) -> tuple[int, ...]:
    calendar = xcals.get_calendar(CALENDAR_NAME)
    sessions = calendar.sessions_in_range(pd.Timestamp(start), pd.Timestamp(end))
    return tuple(timestamp.date().toordinal() for timestamp in sessions)


def _max_run(values: list[bool]) -> int:
    best = 0
    current = 0
    for value in values:
        if value:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def analyze_symbol_session_status(
    status_by_ordinal: dict[int, str],
    calendar_ordinals: tuple[int, ...],
    calendar_index: dict[int, int],
) -> SymbolSessionAnalysis:
    trade_ordinals = sorted(
        ordinal for ordinal, status in status_by_ordinal.items() if status == TRADE_BACKED
    )
    valid_trade_ordinals = [ordinal for ordinal in trade_ordinals if ordinal in calendar_index]
    placeholder_ordinals = {
        ordinal
        for ordinal, status in status_by_ordinal.items()
        if status == ZERO_ACTIVITY_PLACEHOLDER
    }

    if not valid_trade_ordinals:
        return SymbolSessionAnalysis(
            evaluable_trade_lifespan=False,
            placeholder_only=bool(status_by_ordinal) and not trade_ordinals,
            trade_backed_nonexchange_only=bool(trade_ordinals),
            first_trade_session=None,
            last_trade_session=None,
            expected_xnys_sessions=0,
            trade_backed_sessions=0,
            placeholder_sessions=0,
            missing_sessions=0,
            raw_session_coverage_ratio=None,
            trade_backed_coverage_ratio=None,
            placeholder_sessions_outside_trade_lifespan=len(placeholder_ordinals),
            max_consecutive_placeholder_sessions=0,
            max_consecutive_missing_sessions=0,
            max_consecutive_no_trade_backed_sessions=0,
            expected_session_ordinals=(),
        )

    first_trade = valid_trade_ordinals[0]
    last_trade = valid_trade_ordinals[-1]
    expected = calendar_ordinals[
        calendar_index[first_trade] : calendar_index[last_trade] + 1
    ]

    states = [status_by_ordinal.get(ordinal) for ordinal in expected]
    trade_count = sum(state == TRADE_BACKED for state in states)
    placeholder_count = sum(state == ZERO_ACTIVITY_PLACEHOLDER for state in states)
    missing_count = sum(state is None for state in states)
    expected_count = len(expected)
    placeholder_outside = sum(
        ordinal < first_trade or ordinal > last_trade for ordinal in placeholder_ordinals
    )

    return SymbolSessionAnalysis(
        evaluable_trade_lifespan=True,
        placeholder_only=False,
        trade_backed_nonexchange_only=False,
        first_trade_session=date.fromordinal(first_trade).isoformat(),
        last_trade_session=date.fromordinal(last_trade).isoformat(),
        expected_xnys_sessions=expected_count,
        trade_backed_sessions=trade_count,
        placeholder_sessions=placeholder_count,
        missing_sessions=missing_count,
        raw_session_coverage_ratio=(trade_count + placeholder_count) / expected_count,
        trade_backed_coverage_ratio=trade_count / expected_count,
        placeholder_sessions_outside_trade_lifespan=placeholder_outside,
        max_consecutive_placeholder_sessions=_max_run(
            [state == ZERO_ACTIVITY_PLACEHOLDER for state in states]
        ),
        max_consecutive_missing_sessions=_max_run([state is None for state in states]),
        max_consecutive_no_trade_backed_sessions=_max_run(
            [state != TRADE_BACKED for state in states]
        ),
        expected_session_ordinals=tuple(expected),
    )


def merge_unit_session(
    existing: dict[str, object] | None,
    *,
    status: str,
    signature: str,
) -> dict[str, object]:
    if status not in STATUS_TO_BIT:
        raise ValueError(f"unknown session status: {status}")
    if existing is None:
        return {
            "row_count": 1,
            "signatures": {signature},
            "statuses": {status},
            "exact_duplicate_rows": 0,
            "conflicting_duplicate_rows": 0,
            "merged_status": status,
        }

    signatures = set(existing["signatures"])
    statuses = set(existing["statuses"])
    exact = int(existing["exact_duplicate_rows"])
    conflicting = int(existing["conflicting_duplicate_rows"])
    if signature in signatures:
        exact += 1
    else:
        conflicting += 1
    signatures.add(signature)
    statuses.add(status)
    merged_status = TRADE_BACKED if TRADE_BACKED in statuses else ZERO_ACTIVITY_PLACEHOLDER
    return {
        "row_count": int(existing["row_count"]) + 1,
        "signatures": signatures,
        "statuses": statuses,
        "exact_duplicate_rows": exact,
        "conflicting_duplicate_rows": conflicting,
        "merged_status": merged_status,
    }


def _record_signature(record: object) -> str:
    return hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
            "utf-8"
        )
    ).hexdigest()


def _write_parquet(
    path: Path,
    rows: list[dict[str, object]],
    columns: list[str],
    order_by: str,
) -> None:
    frame = pd.DataFrame(rows, columns=columns)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = unique_temp_path(path)
    con = duckdb.connect(":memory:")
    try:
        con.register("artifact_df", frame)
        con.execute(
            f"COPY (SELECT * FROM artifact_df ORDER BY {order_by}) TO ? "
            "(FORMAT PARQUET, COMPRESSION ZSTD)",
            [str(temp)],
        )
    finally:
        con.close()
    replace_with_retry(temp, path)


class AlpacaBackfillSessionQualityBuilder:
    """Gate 5-B duplicate and exchange-session coverage audit from retained raw evidence."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        root = settings.resolved_path(settings.data.paths.derived) / "historical_backfill" / "alpaca"
        self.acquisition_root = root / "acquisition"
        self.quality_root = root / "quality"
        self.unit_manifest_root = self.acquisition_root / "units"
        self.anomaly_path = self.acquisition_root / "response_symbol_anomalies.parquet"
        self.parent_report_path = self.quality_root / "quality_baseline_report.json"
        self.parent_symbol_path = self.quality_root / "bar_quality_by_symbol.parquet"
        self.symbol_coverage_path = self.quality_root / "session_coverage_by_symbol.parquet"
        self.market_session_coverage_path = self.quality_root / "market_session_coverage.parquet"
        self.duplicate_session_path = self.quality_root / "duplicate_session_keys.parquet"
        self.non_exchange_session_path = self.quality_root / "non_exchange_session_keys.parquet"
        self.report_path = self.quality_root / "session_coverage_report.json"

    def _load_parent(self) -> tuple[dict[str, Any], set[str]]:
        if not self.parent_report_path.is_file() or not self.parent_symbol_path.is_file():
            raise RuntimeError("Gate 5-B requires the completed Gate 5-A quality baseline")
        report = json.loads(self.parent_report_path.read_text(encoding="utf-8"))
        if report.get("contract_version") != ALPACA_BACKFILL_QUALITY_BASELINE_CONTRACT_VERSION:
            raise RuntimeError("Gate 5-B parent quality contract mismatch")
        required_true = (
            "row_accounting_exact",
            "quarantine_accounting_exact",
            "symbol_summary_reconciliation_exact",
            "trade_backed_accounting_exact",
        )
        if report.get("canonical_data_modified") is not False:
            raise RuntimeError("Gate 5-B parent quality baseline modified canonical data")
        if int(report.get("definite_invalid_rows", -1)) != 0:
            raise RuntimeError("Gate 5-B requires zero definite Gate 5-A bar defects")
        if not all(report.get(name) is True for name in required_true):
            raise RuntimeError("Gate 5-B requires all Gate 5-A accounting invariants")
        if (
            int(report.get("trade_backed_usable_rows", -1))
            + int(report.get("zero_activity_placeholder_rows", -1))
            != int(report.get("identity_safe_bar_rows", -1))
        ):
            raise RuntimeError("Gate 5-B parent trade/placeholder accounting mismatch")

        con = duckdb.connect(":memory:")
        try:
            rows = con.execute(
                "SELECT symbol FROM read_parquet(?) ORDER BY symbol",
                [str(self.parent_symbol_path)],
            ).fetchall()
        finally:
            con.close()
        symbols = {str(symbol) for (symbol,) in rows}
        if len(symbols) != int(report.get("observed_symbols", -1)):
            raise RuntimeError("Gate 5-B parent symbol artifact count mismatch")
        return report, symbols

    def _load_anomaly_keys(self) -> tuple[dict[tuple[int, int, str], int], int]:
        con = duckdb.connect(":memory:")
        try:
            rows = con.execute(
                "SELECT year, batch_index, returned_symbol, sum(bar_rows) "
                "FROM read_parquet(?) WHERE returned_symbol IS NOT NULL "
                "GROUP BY 1,2,3 ORDER BY 1,2,3",
                [str(self.anomaly_path)],
            ).fetchall()
        finally:
            con.close()
        mapping = {
            (int(year), int(batch), str(symbol)): int(count)
            for year, batch, symbol, count in rows
        }
        return mapping, sum(mapping.values())

    def run(self) -> AlpacaBackfillSessionQualityReport:
        parent, observed_symbols = self._load_parent()
        anomaly_keys, expected_quarantine_rows = self._load_anomaly_keys()
        calendar_ordinals = xnys_session_ordinals(ALPACA_BACKFILL_START, ALPACA_BACKFILL_END)
        calendar_index = {ordinal: index for index, ordinal in enumerate(calendar_ordinals)}
        calendar_set = set(calendar_ordinals)

        encoded_by_symbol = {symbol: array("I") for symbol in observed_symbols}
        duplicate_rows: list[dict[str, object]] = []
        nonexchange_rows: list[dict[str, object]] = []
        quarantine_seen: Counter[tuple[int, int, str]] = Counter()
        raw_pages = 0
        hash_failures = 0
        raw_rows = 0
        raw_trade_rows = 0
        raw_placeholder_rows = 0
        raw_nonexchange_rows = 0

        manifests = sorted(self.unit_manifest_root.glob("*/*.json"))
        if len(manifests) != int(parent.get("retained_unit_manifests", -1)):
            raise RuntimeError("Gate 5-B retained unit manifest count differs from Gate 5-A")

        for manifest_path in manifests:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("contract_version") != ALPACA_BACKFILL_ACQUISITION_CONTRACT_VERSION:
                raise RuntimeError(f"Gate 5-B incompatible unit manifest: {manifest_path}")
            if manifest.get("status") != "COMPLETE" or manifest.get("canonical_data_modified") is not False:
                raise RuntimeError(f"Gate 5-B incomplete/unsafe unit manifest: {manifest_path}")
            year = int(manifest_path.parent.name)
            batch_index = int(manifest_path.stem.split("_")[-1])
            unit_start, unit_end = _unit_window(year)
            unit_sessions: dict[tuple[str, int], dict[str, object]] = {}

            for page_record in manifest.get("raw_pages") or []:
                payload_path = Path(str(page_record.get("payload_path") or ""))
                expected_sha = str(page_record.get("sha256") or "")
                if not payload_path.is_file():
                    raise RuntimeError(f"Gate 5-B missing raw page: {payload_path}")
                raw_bytes = gzip.decompress(payload_path.read_bytes())
                if hashlib.sha256(raw_bytes).hexdigest() != expected_sha:
                    hash_failures += 1
                    continue
                raw_pages += 1
                payload = json.loads(raw_bytes)
                bars = payload.get("bars") if isinstance(payload, dict) else None
                if not isinstance(bars, dict):
                    raise RuntimeError(f"Gate 5-B invalid retained bar payload: {payload_path}")

                for raw_symbol, values in bars.items():
                    symbol = str(raw_symbol)
                    if not isinstance(values, list):
                        raise RuntimeError(f"Gate 5-B invalid bar list: {payload_path}")
                    anomaly_key = (year, batch_index, symbol)
                    if anomaly_key in anomaly_keys:
                        quarantine_seen[anomaly_key] += len(values)
                        continue
                    if symbol not in observed_symbols:
                        raise RuntimeError(
                            f"Gate 5-B non-quarantined symbol not in Gate 5-A: {symbol!r}"
                        )

                    for record in values:
                        inspected = inspect_daily_bar(
                            record, unit_start=unit_start, unit_end=unit_end
                        )
                        if inspected.definite_invalid or inspected.session_date is None:
                            raise RuntimeError(
                                "Gate 5-B encountered a row inconsistent with clean Gate 5-A: "
                                f"{symbol!r} {inspected.timestamp_text!r}"
                            )
                        status = (
                            ZERO_ACTIVITY_PLACEHOLDER
                            if inspected.zero_activity_placeholder
                            else TRADE_BACKED
                        )
                        ordinal = inspected.session_date.toordinal()
                        raw_rows += 1
                        if status == TRADE_BACKED:
                            raw_trade_rows += 1
                        else:
                            raw_placeholder_rows += 1
                        if ordinal not in calendar_set:
                            raw_nonexchange_rows += 1
                        key = (symbol, ordinal)
                        unit_sessions[key] = merge_unit_session(
                            unit_sessions.get(key),
                            status=status,
                            signature=_record_signature(record),
                        )

            for (symbol, ordinal), item in sorted(unit_sessions.items()):
                row_count = int(item["row_count"])
                statuses = set(item["statuses"])
                signatures = set(item["signatures"])
                merged_status = str(item["merged_status"])
                if row_count > 1:
                    duplicate_rows.append(
                        {
                            "symbol": symbol,
                            "session_date": date.fromordinal(ordinal).isoformat(),
                            "year": year,
                            "batch_index": batch_index,
                            "row_count": row_count,
                            "duplicate_rows": row_count - 1,
                            "signature_count": len(signatures),
                            "status_count": len(statuses),
                            "exact_duplicate_rows": int(item["exact_duplicate_rows"]),
                            "conflicting_duplicate_rows": int(item["conflicting_duplicate_rows"]),
                            "status_conflict": len(statuses) > 1,
                            "merged_status": merged_status,
                        }
                    )
                if ordinal not in calendar_set:
                    nonexchange_rows.append(
                        {
                            "symbol": symbol,
                            "session_date": date.fromordinal(ordinal).isoformat(),
                            "year": year,
                            "batch_index": batch_index,
                            "row_count": row_count,
                            "merged_status": merged_status,
                        }
                    )
                bit = STATUS_TO_BIT[merged_status]
                encoded_by_symbol[symbol].append((ordinal << 1) | bit)

        if hash_failures:
            raise RuntimeError(f"Gate 5-B raw payload hash failures: {hash_failures}")
        quarantine_mismatch = {
            key: (anomaly_keys.get(key, 0), quarantine_seen.get(key, 0))
            for key in set(anomaly_keys) | set(quarantine_seen)
            if anomaly_keys.get(key, 0) != quarantine_seen.get(key, 0)
        }
        if quarantine_mismatch:
            raise RuntimeError(
                f"Gate 5-B quarantine mismatch: {list(sorted(quarantine_mismatch.items()))[:10]}"
            )

        symbol_rows: list[dict[str, object]] = []
        market_counts: dict[int, Counter[str]] = {
            ordinal: Counter() for ordinal in calendar_ordinals
        }
        unique_session_keys = 0
        evaluable = 0
        placeholder_only = 0
        nonexchange_only = 0
        expected_sessions = 0
        trade_sessions = 0
        placeholder_sessions = 0
        missing_sessions = 0
        placeholder_outside = 0
        symbols_with_placeholders = 0
        symbols_with_missing = 0
        max_placeholder_run = 0
        max_missing_run = 0
        max_no_trade_run = 0
        symbol_output_map: dict[str, dict[str, object]] = {}

        for symbol in sorted(encoded_by_symbol):
            status_by_ordinal: dict[int, str] = {}
            for encoded in encoded_by_symbol[symbol]:
                ordinal = int(encoded) >> 1
                status = BIT_TO_STATUS[int(encoded) & 1]
                if ordinal in status_by_ordinal:
                    raise RuntimeError(
                        f"Gate 5-B cross-unit duplicate session key: {symbol!r} "
                        f"{date.fromordinal(ordinal)}"
                    )
                status_by_ordinal[ordinal] = status
            unique_session_keys += len(status_by_ordinal)
            analysis = analyze_symbol_session_status(
                status_by_ordinal, calendar_ordinals, calendar_index
            )
            if analysis.evaluable_trade_lifespan:
                evaluable += 1
            if analysis.placeholder_only:
                placeholder_only += 1
            if analysis.trade_backed_nonexchange_only:
                nonexchange_only += 1
            expected_sessions += analysis.expected_xnys_sessions
            trade_sessions += analysis.trade_backed_sessions
            placeholder_sessions += analysis.placeholder_sessions
            missing_sessions += analysis.missing_sessions
            placeholder_outside += analysis.placeholder_sessions_outside_trade_lifespan
            symbols_with_placeholders += analysis.placeholder_sessions > 0
            symbols_with_missing += analysis.missing_sessions > 0
            max_placeholder_run = max(
                max_placeholder_run, analysis.max_consecutive_placeholder_sessions
            )
            max_missing_run = max(max_missing_run, analysis.max_consecutive_missing_sessions)
            max_no_trade_run = max(
                max_no_trade_run, analysis.max_consecutive_no_trade_backed_sessions
            )

            for ordinal in analysis.expected_session_ordinals:
                counts = market_counts[ordinal]
                counts["active"] += 1
                state = status_by_ordinal.get(ordinal)
                if state == TRADE_BACKED:
                    counts["trade"] += 1
                elif state == ZERO_ACTIVITY_PLACEHOLDER:
                    counts["placeholder"] += 1
                else:
                    counts["missing"] += 1

            output = {
                "symbol": symbol,
                "unique_session_keys": len(status_by_ordinal),
                **{
                    key: value
                    for key, value in asdict(analysis).items()
                    if key != "expected_session_ordinals"
                },
            }
            symbol_rows.append(output)
            symbol_output_map[symbol] = output

        duplicate_session_rows = sum(int(row["duplicate_rows"]) for row in duplicate_rows)
        exact_duplicate_keys = sum(int(row["signature_count"]) == 1 for row in duplicate_rows)
        conflicting_duplicate_keys = sum(
            int(row["signature_count"]) > 1 for row in duplicate_rows
        )
        status_conflicting_keys = sum(bool(row["status_conflict"]) for row in duplicate_rows)

        market_rows: list[dict[str, object]] = []
        zero_raw_market_sessions = 0
        for ordinal in calendar_ordinals:
            counts = market_counts[ordinal]
            active = int(counts["active"])
            trade = int(counts["trade"])
            placeholder = int(counts["placeholder"])
            missing = int(counts["missing"])
            raw_covered = trade + placeholder
            if active > 0 and raw_covered == 0:
                zero_raw_market_sessions += 1
            market_rows.append(
                {
                    "session_date": date.fromordinal(ordinal).isoformat(),
                    "active_lifespan_symbols": active,
                    "trade_backed_symbols": trade,
                    "zero_activity_placeholder_symbols": placeholder,
                    "absent_symbols": missing,
                    "raw_coverage_ratio": (raw_covered / active) if active else None,
                    "trade_backed_ratio": (trade / active) if active else None,
                }
            )

        lowest_market = sorted(
            (
                row
                for row in market_rows
                if int(row["active_lifespan_symbols"]) >= 100
                and row["raw_coverage_ratio"] is not None
            ),
            key=lambda row: (
                float(row["raw_coverage_ratio"]),
                float(row["trade_backed_ratio"]),
                str(row["session_date"]),
            ),
        )[:20]
        lowest_market_report = [
            {
                "session_date": row["session_date"],
                "active_lifespan_symbols": row["active_lifespan_symbols"],
                "trade_backed_symbols": row["trade_backed_symbols"],
                "zero_activity_placeholder_symbols": row[
                    "zero_activity_placeholder_symbols"
                ],
                "absent_symbols": row["absent_symbols"],
                "raw_coverage_ratio": row["raw_coverage_ratio"],
                "trade_backed_ratio": row["trade_backed_ratio"],
            }
            for row in lowest_market
        ]
        sentinel_coverage = {
            symbol: symbol_output_map[symbol]
            for symbol in SENTINEL_SYMBOLS
            if symbol in symbol_output_map
        }

        raw_accounting = raw_rows == int(parent.get("identity_safe_bar_rows", -1))
        parent_classification = bool(
            raw_trade_rows == int(parent.get("trade_backed_usable_rows", -1))
            and raw_placeholder_rows
            == int(parent.get("zero_activity_placeholder_rows", -1))
            and sum(quarantine_seen.values())
            == expected_quarantine_rows
            == int(parent.get("quarantined_response_bar_rows", -1))
        )
        unique_accounting = unique_session_keys + duplicate_session_rows == raw_rows
        if not raw_accounting or not parent_classification or not unique_accounting:
            raise RuntimeError(
                "Gate 5-B accounting invariant failed: "
                f"raw={raw_accounting} classification={parent_classification} "
                f"unique={unique_accounting}"
            )
        if raw_pages != int(parent.get("retained_raw_bar_pages", -1)):
            raise RuntimeError("Gate 5-B raw page count differs from Gate 5-A")

        _write_parquet(
            self.symbol_coverage_path,
            symbol_rows,
            list(symbol_rows[0].keys()),
            "symbol",
        )
        _write_parquet(
            self.market_session_coverage_path,
            market_rows,
            list(market_rows[0].keys()),
            "session_date",
        )
        duplicate_columns = [
            "symbol",
            "session_date",
            "year",
            "batch_index",
            "row_count",
            "duplicate_rows",
            "signature_count",
            "status_count",
            "exact_duplicate_rows",
            "conflicting_duplicate_rows",
            "status_conflict",
            "merged_status",
        ]
        _write_parquet(
            self.duplicate_session_path,
            duplicate_rows,
            duplicate_columns,
            "session_date, symbol, year, batch_index",
        )
        nonexchange_columns = [
            "symbol",
            "session_date",
            "year",
            "batch_index",
            "row_count",
            "merged_status",
        ]
        _write_parquet(
            self.non_exchange_session_path,
            nonexchange_rows,
            nonexchange_columns,
            "session_date, symbol, year, batch_index",
        )

        report = AlpacaBackfillSessionQualityReport(
            contract_version=ALPACA_BACKFILL_SESSION_QUALITY_CONTRACT_VERSION,
            parent_quality_contract_version=ALPACA_BACKFILL_QUALITY_BASELINE_CONTRACT_VERSION,
            calendar_name=CALENDAR_NAME,
            generated_at_utc=datetime.now(UTC).isoformat(),
            canonical_data_modified=False,
            retained_unit_manifests=len(manifests),
            retained_raw_bar_pages=raw_pages,
            raw_payload_hash_failures=hash_failures,
            identity_safe_raw_rows=raw_rows,
            parent_identity_safe_raw_rows=int(parent.get("identity_safe_bar_rows", -1)),
            trade_backed_raw_rows=raw_trade_rows,
            parent_trade_backed_raw_rows=int(parent.get("trade_backed_usable_rows", -1)),
            zero_activity_placeholder_raw_rows=raw_placeholder_rows,
            parent_zero_activity_placeholder_raw_rows=int(
                parent.get("zero_activity_placeholder_rows", -1)
            ),
            quarantined_response_bar_rows=sum(quarantine_seen.values()),
            parent_quarantined_response_bar_rows=int(
                parent.get("quarantined_response_bar_rows", -1)
            ),
            observed_symbols=len(observed_symbols),
            unique_session_keys=unique_session_keys,
            duplicate_session_rows=duplicate_session_rows,
            duplicate_session_keys=len(duplicate_rows),
            exact_duplicate_session_keys=exact_duplicate_keys,
            conflicting_duplicate_session_keys=conflicting_duplicate_keys,
            status_conflicting_duplicate_session_keys=status_conflicting_keys,
            non_exchange_session_rows=raw_nonexchange_rows,
            non_exchange_session_keys=len(nonexchange_rows),
            evaluable_trade_lifespan_symbols=evaluable,
            placeholder_only_symbols=placeholder_only,
            trade_backed_nonexchange_only_symbols=nonexchange_only,
            expected_exchange_sessions_within_trade_lifespans=expected_sessions,
            trade_backed_sessions_within_lifespans=trade_sessions,
            placeholder_sessions_within_lifespans=placeholder_sessions,
            missing_sessions_within_lifespans=missing_sessions,
            placeholder_sessions_outside_trade_lifespans=placeholder_outside,
            symbols_with_internal_placeholder_sessions=symbols_with_placeholders,
            symbols_with_internal_missing_sessions=symbols_with_missing,
            max_consecutive_placeholder_sessions=max_placeholder_run,
            max_consecutive_missing_sessions=max_missing_run,
            max_consecutive_no_trade_backed_sessions=max_no_trade_run,
            market_sessions_with_zero_raw_coverage=zero_raw_market_sessions,
            lowest_market_coverage_sessions=lowest_market_report,
            sentinel_coverage=sentinel_coverage,
            raw_row_accounting_exact=raw_accounting,
            parent_classification_accounting_exact=parent_classification,
            unique_session_accounting_exact=unique_accounting,
            symbol_coverage_path=str(self.symbol_coverage_path),
            market_session_coverage_path=str(self.market_session_coverage_path),
            duplicate_session_path=str(self.duplicate_session_path),
            non_exchange_session_path=str(self.non_exchange_session_path),
            report_path=str(self.report_path),
        )
        atomic_write_text(
            self.report_path,
            json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
        )
        return report
