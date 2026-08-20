from __future__ import annotations

import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_acquisition import ALPACA_BACKFILL_ACQUISITION_CONTRACT_VERSION
from packages.data.alpaca_backfill_identity_asset_risk import (
    ALPACA_BACKFILL_IDENTITY_ASSET_RISK_CONTRACT_VERSION,
)
from packages.data.alpaca_backfill_policy import ALPACA_BACKFILL_END, ALPACA_BACKFILL_START


ALPACA_BACKFILL_QUALITY_BASELINE_CONTRACT_VERSION = (
    "historical-backfill-quality-v1-retained-raw-bar-baseline"
)


@dataclass(frozen=True, slots=True)
class BarInspection:
    timestamp_text: str | None
    session_date: date | None
    time_utc: str | None
    missing_required: bool
    invalid_timestamp: bool
    out_of_unit_range: bool
    invalid_ohlc_numeric: bool
    nonpositive_ohlc: bool
    invalid_ohlc_geometry: bool
    invalid_volume: bool
    missing_trade_count: bool
    invalid_trade_count: bool
    missing_vwap: bool
    invalid_vwap: bool
    weekend_session: bool

    @property
    def definite_invalid(self) -> bool:
        return bool(
            self.missing_required
            or self.invalid_timestamp
            or self.out_of_unit_range
            or self.invalid_ohlc_numeric
            or self.nonpositive_ohlc
            or self.invalid_ohlc_geometry
            or self.invalid_volume
            or self.invalid_trade_count
            or self.invalid_vwap
        )


@dataclass(frozen=True, slots=True)
class AlpacaBackfillQualityBaselineReport:
    contract_version: str
    acquisition_contract_version: str
    identity_asset_risk_contract_version: str
    generated_at_utc: str
    canonical_data_modified: bool
    retained_unit_manifests: int
    retained_raw_bar_pages: int
    raw_payload_hash_failures: int
    identity_safe_bar_rows: int
    gate3_reported_identity_safe_bar_rows: int
    quarantined_response_bar_rows: int
    gate3_reported_quarantined_response_bar_rows: int
    observed_symbols: int
    symbol_summary_reconciliation_failures: int
    definite_invalid_rows: int
    missing_required_rows: int
    invalid_timestamp_rows: int
    out_of_unit_range_rows: int
    invalid_ohlc_numeric_rows: int
    nonpositive_ohlc_rows: int
    invalid_ohlc_geometry_rows: int
    invalid_volume_rows: int
    missing_trade_count_rows: int
    invalid_trade_count_rows: int
    missing_vwap_rows: int
    invalid_vwap_rows: int
    weekend_session_rows: int
    year_row_counts: dict[str, int]
    utc_time_counts: dict[str, int]
    bar_key_pattern_counts: dict[str, int]
    row_accounting_exact: bool
    quarantine_accounting_exact: bool
    symbol_summary_reconciliation_exact: bool
    symbol_summary_path: str
    report_path: str


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def inspect_daily_bar(record: object, *, unit_start: date, unit_end: date) -> BarInspection:
    """Classify definite raw daily-bar quality defects without provider assumptions."""

    if not isinstance(record, dict):
        return BarInspection(
            timestamp_text=None,
            session_date=None,
            time_utc=None,
            missing_required=True,
            invalid_timestamp=True,
            out_of_unit_range=False,
            invalid_ohlc_numeric=True,
            nonpositive_ohlc=False,
            invalid_ohlc_geometry=False,
            invalid_volume=True,
            missing_trade_count=True,
            invalid_trade_count=False,
            missing_vwap=True,
            invalid_vwap=False,
            weekend_session=False,
        )

    required = ("t", "o", "h", "l", "c", "v")
    missing_required = any(key not in record or record.get(key) is None for key in required)

    timestamp_text = _text(record.get("t"))
    parsed: datetime | None = None
    if timestamp_text is not None:
        try:
            parsed = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            parsed = parsed.astimezone(UTC)
        except ValueError:
            parsed = None
    invalid_timestamp = parsed is None
    session_date = parsed.date() if parsed is not None else None
    time_utc = parsed.time().replace(tzinfo=None).isoformat() if parsed is not None else None
    out_of_unit_range = bool(
        session_date is not None and not (unit_start <= session_date <= unit_end)
    )
    weekend_session = bool(session_date is not None and session_date.weekday() >= 5)

    o = _finite_number(record.get("o"))
    h = _finite_number(record.get("h"))
    l = _finite_number(record.get("l"))
    c = _finite_number(record.get("c"))
    invalid_ohlc_numeric = any(value is None for value in (o, h, l, c))
    nonpositive_ohlc = False
    invalid_ohlc_geometry = False
    if not invalid_ohlc_numeric:
        assert o is not None and h is not None and l is not None and c is not None
        nonpositive_ohlc = min(o, h, l, c) <= 0.0
        invalid_ohlc_geometry = bool(h < max(o, l, c) or l > min(o, h, c))

    volume = _finite_number(record.get("v"))
    invalid_volume = volume is None or volume < 0.0

    missing_trade_count = record.get("n") is None
    trade_count = _finite_number(record.get("n")) if not missing_trade_count else None
    invalid_trade_count = bool(not missing_trade_count and (trade_count is None or trade_count < 0.0))

    missing_vwap = record.get("vw") is None
    vwap = _finite_number(record.get("vw")) if not missing_vwap else None
    invalid_vwap = bool(not missing_vwap and (vwap is None or vwap <= 0.0))

    return BarInspection(
        timestamp_text=timestamp_text,
        session_date=session_date,
        time_utc=time_utc,
        missing_required=missing_required,
        invalid_timestamp=invalid_timestamp,
        out_of_unit_range=out_of_unit_range,
        invalid_ohlc_numeric=invalid_ohlc_numeric,
        nonpositive_ohlc=nonpositive_ohlc,
        invalid_ohlc_geometry=invalid_ohlc_geometry,
        invalid_volume=invalid_volume,
        missing_trade_count=missing_trade_count,
        invalid_trade_count=invalid_trade_count,
        missing_vwap=missing_vwap,
        invalid_vwap=invalid_vwap,
        weekend_session=weekend_session,
    )


def _unit_window(year: int) -> tuple[date, date]:
    return max(ALPACA_BACKFILL_START, date(year, 1, 1)), min(ALPACA_BACKFILL_END, date(year, 12, 31))


class AlpacaBackfillQualityBaselineBuilder:
    """Gate 5-A retained-raw quality scan; no provider fetch and no canonical writes."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        root = settings.resolved_path(settings.data.paths.derived) / "historical_backfill" / "alpaca"
        self.acquisition_root = root / "acquisition"
        self.identity_root = root / "identity"
        self.quality_root = root / "quality"
        self.acquisition_report_path = self.acquisition_root / "acquisition_report.json"
        self.observed_summary_path = self.acquisition_root / "observed_symbols.parquet"
        self.anomaly_path = self.acquisition_root / "response_symbol_anomalies.parquet"
        self.unit_manifest_root = self.acquisition_root / "units"
        self.asset_risk_report_path = self.identity_root / "identity_asset_risk_report.json"
        self.symbol_summary_path = self.quality_root / "bar_quality_by_symbol.parquet"
        self.report_path = self.quality_root / "quality_baseline_report.json"

    @staticmethod
    def _write_parquet(path: Path, rows: list[dict[str, object]], order_by: str) -> None:
        frame = pd.DataFrame(rows)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = unique_temp_path(path)
        con = duckdb.connect(":memory:")
        try:
            con.register("quality_df", frame)
            con.execute(
                f"COPY (SELECT * FROM quality_df ORDER BY {order_by}) TO ? "
                "(FORMAT PARQUET, COMPRESSION ZSTD)",
                [str(temp)],
            )
        finally:
            con.close()
        replace_with_retry(temp, path)

    def _load_parent_reports(self) -> tuple[dict[str, Any], dict[str, Any]]:
        if not self.acquisition_report_path.is_file():
            raise RuntimeError("Gate 5-A requires the accepted Gate 3 acquisition report")
        if not self.asset_risk_report_path.is_file():
            raise RuntimeError("Gate 5-A requires the accepted Gate 4-D asset-risk report")
        acquisition = json.loads(self.acquisition_report_path.read_text(encoding="utf-8"))
        gate4 = json.loads(self.asset_risk_report_path.read_text(encoding="utf-8"))
        if acquisition.get("contract_version") != ALPACA_BACKFILL_ACQUISITION_CONTRACT_VERSION:
            raise RuntimeError("Gate 5-A acquisition contract mismatch")
        if acquisition.get("complete") is not True or int(acquisition.get("missing_units", -1)) != 0:
            raise RuntimeError("Gate 5-A requires complete Gate 3 acquisition")
        if acquisition.get("canonical_data_modified") is not False:
            raise RuntimeError("Gate 5-A Gate 3 report does not preserve canonical safety")
        if gate4.get("contract_version") != ALPACA_BACKFILL_IDENTITY_ASSET_RISK_CONTRACT_VERSION:
            raise RuntimeError("Gate 5-A Gate 4-D contract mismatch")
        if gate4.get("canonical_data_modified") is not False:
            raise RuntimeError("Gate 5-A Gate 4 report does not preserve canonical safety")
        return acquisition, gate4

    def _load_observed(self) -> dict[str, dict[str, object]]:
        con = duckdb.connect(":memory:")
        try:
            cursor = con.execute(
                "SELECT symbol, bar_rows, first_timestamp, last_timestamp "
                "FROM read_parquet(?) WHERE observed=TRUE ORDER BY symbol",
                [str(self.observed_summary_path)],
            )
            columns = [item[0] for item in cursor.description]
            rows = cursor.fetchall()
        finally:
            con.close()
        return {str(row[0]): dict(zip(columns, row)) for row in rows}

    def _load_anomaly_keys(self) -> tuple[dict[tuple[int, int, str], int], int]:
        if not self.anomaly_path.is_file():
            raise RuntimeError("Gate 5-A requires the Gate 3 response-symbol anomaly artifact")
        con = duckdb.connect(":memory:")
        try:
            schema = {row[0] for row in con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(self.anomaly_path)]).fetchall()}
            required = {"year", "batch_index", "returned_symbol", "bar_rows"}
            if not required.issubset(schema):
                raise RuntimeError(f"Gate 5-A anomaly artifact lacks unit identity columns: {sorted(required - schema)}")
            rows = con.execute(
                "SELECT year, batch_index, returned_symbol, sum(bar_rows) "
                "FROM read_parquet(?) WHERE returned_symbol IS NOT NULL "
                "GROUP BY 1,2,3 ORDER BY 1,2,3",
                [str(self.anomaly_path)],
            ).fetchall()
        finally:
            con.close()
        mapping = {(int(year), int(batch), str(symbol)): int(count) for year, batch, symbol, count in rows}
        return mapping, sum(mapping.values())

    def run(self) -> AlpacaBackfillQualityBaselineReport:
        acquisition, gate4 = self._load_parent_reports()
        observed = self._load_observed()
        anomaly_keys, anomaly_expected_rows = self._load_anomaly_keys()

        symbol_stats: dict[str, dict[str, object]] = {
            symbol: {
                "symbol": symbol,
                "bar_rows": 0,
                "first_timestamp": None,
                "last_timestamp": None,
                "definite_invalid_rows": 0,
                "weekend_session_rows": 0,
                "missing_trade_count_rows": 0,
                "missing_vwap_rows": 0,
            }
            for symbol in observed
        }
        issue_counts: Counter[str] = Counter()
        year_counts: Counter[int] = Counter()
        utc_time_counts: Counter[str] = Counter()
        key_patterns: Counter[str] = Counter()
        quarantined_seen: Counter[tuple[int, int, str]] = Counter()

        raw_pages = 0
        hash_failures = 0
        identity_safe_rows = 0
        manifests = sorted(self.unit_manifest_root.glob("*/*.json"))
        expected_manifests = int(acquisition.get("planned_units", -1))
        if len(manifests) != expected_manifests:
            raise RuntimeError(
                f"Gate 5-A unit manifest count mismatch: {len(manifests)} != {expected_manifests}"
            )

        for manifest_path in manifests:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("contract_version") != ALPACA_BACKFILL_ACQUISITION_CONTRACT_VERSION:
                raise RuntimeError(f"Gate 5-A incompatible unit manifest: {manifest_path}")
            if manifest.get("status") != "COMPLETE" or manifest.get("canonical_data_modified") is not False:
                raise RuntimeError(f"Gate 5-A incomplete/unsafe unit manifest: {manifest_path}")

            year = int(manifest_path.parent.name)
            stem = manifest_path.stem
            try:
                batch_index = int(stem.split("_")[-1])
            except ValueError as exc:
                raise RuntimeError(f"Gate 5-A cannot resolve batch index: {manifest_path}") from exc
            unit_start, unit_end = _unit_window(year)

            for page_record in manifest.get("raw_pages") or []:
                payload_path = Path(str(page_record.get("payload_path") or ""))
                expected_sha = str(page_record.get("sha256") or "")
                if not payload_path.is_file():
                    raise RuntimeError(f"Gate 5-A missing retained raw bar page: {payload_path}")
                raw_bytes = gzip.decompress(payload_path.read_bytes())
                actual_sha = hashlib.sha256(raw_bytes).hexdigest()
                if actual_sha != expected_sha:
                    hash_failures += 1
                    continue
                raw_pages += 1
                payload = json.loads(raw_bytes)
                bars = payload.get("bars") if isinstance(payload, dict) else None
                if not isinstance(bars, dict):
                    raise RuntimeError(f"Gate 5-A unexpected bar payload shape: {payload_path}")

                for raw_symbol, values in bars.items():
                    symbol = _text(raw_symbol)
                    if symbol is None or not isinstance(values, list):
                        raise RuntimeError(f"Gate 5-A invalid returned symbol/bar list: {payload_path}")
                    anomaly_key = (year, batch_index, symbol)
                    if anomaly_key in anomaly_keys:
                        quarantined_seen[anomaly_key] += len(values)
                        continue
                    if symbol not in observed:
                        raise RuntimeError(
                            f"Gate 5-A non-quarantined returned symbol is not Gate 3 observed: {symbol!r} "
                            f"year={year} batch={batch_index}"
                        )

                    for record in values:
                        identity_safe_rows += 1
                        year_counts[year] += 1
                        if isinstance(record, dict):
                            key_patterns[",".join(sorted(str(key) for key in record))] += 1
                        else:
                            key_patterns["<non-dict>"] += 1
                        inspected = inspect_daily_bar(record, unit_start=unit_start, unit_end=unit_end)
                        stats = symbol_stats[symbol]
                        stats["bar_rows"] = int(stats["bar_rows"]) + 1
                        if inspected.timestamp_text is not None and not inspected.invalid_timestamp:
                            current_first = stats["first_timestamp"]
                            current_last = stats["last_timestamp"]
                            if current_first is None or inspected.timestamp_text < str(current_first):
                                stats["first_timestamp"] = inspected.timestamp_text
                            if current_last is None or inspected.timestamp_text > str(current_last):
                                stats["last_timestamp"] = inspected.timestamp_text
                        if inspected.time_utc is not None:
                            utc_time_counts[inspected.time_utc] += 1
                        if inspected.definite_invalid:
                            stats["definite_invalid_rows"] = int(stats["definite_invalid_rows"]) + 1
                            issue_counts["definite_invalid_rows"] += 1
                        if inspected.weekend_session:
                            stats["weekend_session_rows"] = int(stats["weekend_session_rows"]) + 1
                            issue_counts["weekend_session_rows"] += 1
                        if inspected.missing_trade_count:
                            stats["missing_trade_count_rows"] = int(stats["missing_trade_count_rows"]) + 1
                            issue_counts["missing_trade_count_rows"] += 1
                        if inspected.missing_vwap:
                            stats["missing_vwap_rows"] = int(stats["missing_vwap_rows"]) + 1
                            issue_counts["missing_vwap_rows"] += 1
                        for name in (
                            "missing_required",
                            "invalid_timestamp",
                            "out_of_unit_range",
                            "invalid_ohlc_numeric",
                            "nonpositive_ohlc",
                            "invalid_ohlc_geometry",
                            "invalid_volume",
                            "invalid_trade_count",
                            "invalid_vwap",
                        ):
                            if bool(getattr(inspected, name)):
                                issue_counts[f"{name}_rows"] += 1

        if hash_failures:
            raise RuntimeError(f"Gate 5-A retained raw bar hash failures: {hash_failures}")

        quarantine_mismatches = {
            key: (anomaly_keys.get(key, 0), quarantined_seen.get(key, 0))
            for key in set(anomaly_keys) | set(quarantined_seen)
            if anomaly_keys.get(key, 0) != quarantined_seen.get(key, 0)
        }
        if quarantine_mismatches:
            sample = list(sorted(quarantine_mismatches.items()))[:10]
            raise RuntimeError(f"Gate 5-A quarantine row mismatch: {sample}")

        reconciliation_failures = 0
        output_rows: list[dict[str, object]] = []
        for symbol in sorted(observed):
            expected = observed[symbol]
            actual = symbol_stats[symbol]
            reconciled = bool(
                int(actual["bar_rows"]) == int(expected["bar_rows"])
                and _text(actual["first_timestamp"]) == _text(expected["first_timestamp"])
                and _text(actual["last_timestamp"]) == _text(expected["last_timestamp"])
            )
            if not reconciled:
                reconciliation_failures += 1
            output_rows.append(
                {
                    **actual,
                    "gate3_bar_rows": int(expected["bar_rows"]),
                    "gate3_first_timestamp": _text(expected["first_timestamp"]),
                    "gate3_last_timestamp": _text(expected["last_timestamp"]),
                    "gate3_summary_reconciled": reconciled,
                }
            )

        row_accounting_exact = identity_safe_rows == int(acquisition.get("bar_rows", -1))
        quarantine_rows = sum(quarantined_seen.values())
        quarantine_accounting_exact = bool(
            quarantine_rows == anomaly_expected_rows
            == int(acquisition.get("response_symbol_anomaly_bar_rows", -1))
        )
        symbol_summary_exact = reconciliation_failures == 0 and len(output_rows) == int(acquisition.get("observed_symbols", -1))
        if not row_accounting_exact or not quarantine_accounting_exact or not symbol_summary_exact:
            raise RuntimeError(
                "Gate 5-A baseline accounting invariant failed: "
                f"rows={row_accounting_exact} quarantine={quarantine_accounting_exact} "
                f"symbols={symbol_summary_exact}"
            )

        self._write_parquet(self.symbol_summary_path, output_rows, "symbol")
        report = AlpacaBackfillQualityBaselineReport(
            contract_version=ALPACA_BACKFILL_QUALITY_BASELINE_CONTRACT_VERSION,
            acquisition_contract_version=ALPACA_BACKFILL_ACQUISITION_CONTRACT_VERSION,
            identity_asset_risk_contract_version=ALPACA_BACKFILL_IDENTITY_ASSET_RISK_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            canonical_data_modified=False,
            retained_unit_manifests=len(manifests),
            retained_raw_bar_pages=raw_pages,
            raw_payload_hash_failures=hash_failures,
            identity_safe_bar_rows=identity_safe_rows,
            gate3_reported_identity_safe_bar_rows=int(acquisition.get("bar_rows", -1)),
            quarantined_response_bar_rows=quarantine_rows,
            gate3_reported_quarantined_response_bar_rows=int(acquisition.get("response_symbol_anomaly_bar_rows", -1)),
            observed_symbols=len(output_rows),
            symbol_summary_reconciliation_failures=reconciliation_failures,
            definite_invalid_rows=int(issue_counts["definite_invalid_rows"]),
            missing_required_rows=int(issue_counts["missing_required_rows"]),
            invalid_timestamp_rows=int(issue_counts["invalid_timestamp_rows"]),
            out_of_unit_range_rows=int(issue_counts["out_of_unit_range_rows"]),
            invalid_ohlc_numeric_rows=int(issue_counts["invalid_ohlc_numeric_rows"]),
            nonpositive_ohlc_rows=int(issue_counts["nonpositive_ohlc_rows"]),
            invalid_ohlc_geometry_rows=int(issue_counts["invalid_ohlc_geometry_rows"]),
            invalid_volume_rows=int(issue_counts["invalid_volume_rows"]),
            missing_trade_count_rows=int(issue_counts["missing_trade_count_rows"]),
            invalid_trade_count_rows=int(issue_counts["invalid_trade_count_rows"]),
            missing_vwap_rows=int(issue_counts["missing_vwap_rows"]),
            invalid_vwap_rows=int(issue_counts["invalid_vwap_rows"]),
            weekend_session_rows=int(issue_counts["weekend_session_rows"]),
            year_row_counts={str(year): int(count) for year, count in sorted(year_counts.items())},
            utc_time_counts={key: int(value) for key, value in sorted(utc_time_counts.items())},
            bar_key_pattern_counts={key: int(value) for key, value in key_patterns.most_common()},
            row_accounting_exact=row_accounting_exact,
            quarantine_accounting_exact=quarantine_accounting_exact,
            symbol_summary_reconciliation_exact=symbol_summary_exact,
            symbol_summary_path=str(self.symbol_summary_path),
            report_path=str(self.report_path),
        )
        atomic_write_text(self.report_path, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
