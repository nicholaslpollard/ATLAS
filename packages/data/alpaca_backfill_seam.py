from __future__ import annotations

import gzip
import hashlib
import json
import math
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Iterable

import duckdb
import pandas as pd

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_candidate_canonical import (
    AlpacaBackfillCandidateCanonicalBuilder,
    AlpacaBackfillCandidateCanonicalValidator,
)
from packages.data.alpaca_backfill_storage import AlpacaRawPayloadStore
from packages.data.alpaca_backfill_validated_evidence import sha256_file, stable_source_fingerprint
from packages.providers.alpaca import AlpacaInvalidSymbolError, AlpacaMarketDataClient
from packages.schemas.canonical_market import canonical_stock_daily_schema_matches


ALPACA_BACKFILL_SEAM_PROBE_CONTRACT_VERSION = (
    "historical-backfill-seam-v1-all-boundary-symbols-same-session-provider-probe"
)
ALPACA_BACKFILL_SEAM_TARGET_SESSION = date(2021, 8, 16)
ALPACA_BACKFILL_CANDIDATE_BOUNDARY_SESSION = date(2021, 8, 13)
ALPACA_BACKFILL_SEAM_REQUEST_START = "2021-08-16T00:00:00Z"
ALPACA_BACKFILL_SEAM_REQUEST_END = "2021-08-17T00:00:00Z"
ALPACA_BACKFILL_SEAM_STATUS_COMPLETE = "COMPLETE"
ALPACA_BACKFILL_SEAM_RESPONSE_POLICY = (
    "exact-requested-literal-with-unique-casefold-or-quarantine"
)


SAFE_BAR_COLUMNS = (
    "symbol",
    "session_date",
    "timestamp_utc",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "vwap",
    "transaction_count",
    "batch_index",
    "raw_page_sha256",
)
ANOMALY_COLUMNS = (
    "classification",
    "batch_index",
    "requested_symbol",
    "returned_symbol",
    "returned_is_locked_symbol",
    "casefold_match_count",
    "bar_rows",
    "target_session_bar_rows",
    "raw_page_sha256",
)


def _clean_symbol(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    symbol = value.strip()
    if not symbol or "," in symbol or any(ch.isspace() for ch in symbol):
        return None
    return symbol


def _chunks(values: list[str], size: int) -> Iterable[tuple[str, ...]]:
    for index in range(0, len(values), size):
        yield tuple(values[index : index + size])


def classify_seam_response_symbol(
    returned_symbol: str,
    requested_symbols: tuple[str, ...],
    locked_symbols: set[str],
) -> tuple[str | None, str | None, int]:
    """Apply Gate-3-equivalent exact-case response safety to one seam symbol.

    A response is identity-safe only when the returned literal was submitted exactly
    and no second submitted literal shares its case-folded form. Any provider case
    folding or unexpected literal is quarantined rather than remapped.
    """

    casefold_matches = [
        symbol for symbol in requested_symbols if symbol.casefold() == returned_symbol.casefold()
    ]
    if returned_symbol in requested_symbols and casefold_matches == [returned_symbol]:
        return None, returned_symbol, 1
    requested_symbol: str | None = None
    if len(casefold_matches) > 1:
        classification = "AMBIGUOUS_CASE_FOLD_RESPONSE"
    elif len(casefold_matches) == 1:
        requested_symbol = casefold_matches[0]
        classification = (
            "CASE_FOLD_IDENTITY_COLLISION"
            if returned_symbol in locked_symbols
            else "CASE_FOLD_RESPONSE"
        )
    else:
        classification = "UNREQUESTED_RESPONSE_SYMBOL"
    return classification, requested_symbol, len(casefold_matches)


def seam_source_fingerprint(
    *,
    candidate_fingerprint: str,
    candidate_boundary_sha256: str,
    massive_boundary_sha256: str,
    symbols: list[str],
    symbol_batch_size: int,
    feed: str,
    adjustment: str,
    asof: str,
    timeframe: str,
) -> str:
    return stable_source_fingerprint(
        {
            "contract_version": ALPACA_BACKFILL_SEAM_PROBE_CONTRACT_VERSION,
            "candidate_fingerprint": candidate_fingerprint,
            "candidate_boundary_session": ALPACA_BACKFILL_CANDIDATE_BOUNDARY_SESSION.isoformat(),
            "candidate_boundary_sha256": candidate_boundary_sha256,
            "massive_boundary_session": ALPACA_BACKFILL_SEAM_TARGET_SESSION.isoformat(),
            "massive_boundary_sha256": massive_boundary_sha256,
            "request_start": ALPACA_BACKFILL_SEAM_REQUEST_START,
            "request_end": ALPACA_BACKFILL_SEAM_REQUEST_END,
            "symbols": symbols,
            "symbol_batch_size": symbol_batch_size,
            "feed": feed,
            "adjustment": adjustment,
            "asof": asof,
            "timeframe": timeframe,
            "response_policy": ALPACA_BACKFILL_SEAM_RESPONSE_POLICY,
        }
    )


def _unit_id(source_fingerprint: str, batch_index: int, symbols: tuple[str, ...]) -> str:
    return stable_source_fingerprint(
        {
            "contract_version": ALPACA_BACKFILL_SEAM_PROBE_CONTRACT_VERSION,
            "source_fingerprint": source_fingerprint,
            "batch_index": batch_index,
            "symbols": list(symbols),
        }
    )


def _relative_difference(left: float, right: float) -> float:
    return abs(left - right) / max(abs(left), abs(right), 1e-12)


def _session_date(value: object) -> str:
    return str(value)[:10]


def _write_parquet(path: Path, rows: list[dict[str, object]], columns: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows, columns=list(columns))
    temp = unique_temp_path(path)
    con = duckdb.connect(":memory:")
    try:
        con.register("frame", frame)
        con.execute(
            "COPY (SELECT * FROM frame) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
            [str(temp)],
        )
    finally:
        con.close()
    replace_with_retry(temp, path)


def _quantile(values: list[float], q: float) -> float | None:
    finite = sorted(value for value in values if math.isfinite(value))
    if not finite:
        return None
    if len(finite) == 1:
        return finite[0]
    position = (len(finite) - 1) * q
    lo = int(math.floor(position))
    hi = int(math.ceil(position))
    if lo == hi:
        return finite[lo]
    weight = position - lo
    return finite[lo] * (1.0 - weight) + finite[hi] * weight


class AlpacaBackfillSeamProbe:
    """Gate 7-A cached same-session Alpaca-vs-Massive seam evidence.

    The 2016-2021 candidate remains unchanged. This probe acquires only the first
    Massive production session (2021-08-16) for the union of Friday candidate and
    Monday Massive symbols, stores exact raw responses, quarantines response-symbol
    ambiguity with Gate-3-equivalent semantics, and compares safe Alpaca rows to the
    already-canonical Massive rows. Production canonical data is read-only.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.client = AlpacaMarketDataClient(settings)
        self.raw_store = AlpacaRawPayloadStore(settings)
        self.candidate_builder = AlpacaBackfillCandidateCanonicalBuilder(settings)
        self.candidate_validator = AlpacaBackfillCandidateCanonicalValidator(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "historical_backfill" / "alpaca" / "seam" / "v1"
        self.unit_root = self.root / "units"
        self.safe_bars_path = self.root / "alpaca_2021-08-16_safe_bars.parquet"
        self.anomalies_path = self.root / "response_symbol_anomalies.parquet"
        self.provider_comparison_path = self.root / "same_session_provider_comparison.parquet"
        self.boundary_status_path = self.root / "boundary_symbol_status.parquet"
        self.report_path = self.root / "seam_probe_report.json"
        canonical_root = settings.resolved_path(settings.data.paths.canonical)
        self.massive_boundary_path = (
            canonical_root
            / "stocks"
            / "1d"
            / "year=2021"
            / "date=2021-08-16"
            / "part-000.parquet"
        )
        self.candidate_boundary_path = (
            self.candidate_builder.bar_root
            / "year=2021"
            / "date=2021-08-13"
            / "part-000.parquet"
        )

    @staticmethod
    def _schema_exact(path: Path) -> bool:
        if not path.is_file():
            return False
        con = duckdb.connect(":memory:")
        try:
            description = con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]).fetchall()
        finally:
            con.close()
        return canonical_stock_daily_schema_matches(description)

    @staticmethod
    def _symbols(path: Path) -> list[str]:
        con = duckdb.connect(":memory:")
        try:
            rows = con.execute(
                "SELECT DISTINCT symbol FROM read_parquet(?) ORDER BY symbol",
                [str(path)],
            ).fetchall()
        finally:
            con.close()
        return [symbol for (value,) in rows if (symbol := _clean_symbol(value)) is not None]

    def _load_parents(self) -> dict[str, object]:
        candidate_validation = self.candidate_validator.run()
        if candidate_validation.get("pass") is not True:
            raise RuntimeError("Gate 7-A requires accepted/passing Gate 6 candidate history")
        if not self.candidate_builder.report_path.is_file():
            raise RuntimeError("Gate 7-A requires the Gate 6 candidate manifest")
        candidate_report = json.loads(
            self.candidate_builder.report_path.read_text(encoding="utf-8")
        )
        for path, label in (
            (self.candidate_boundary_path, "candidate 2021-08-13"),
            (self.massive_boundary_path, "Massive 2021-08-16"),
        ):
            if not path.is_file():
                raise RuntimeError(f"Gate 7-A missing {label} canonical file: {path}")
            if not self._schema_exact(path):
                raise RuntimeError(f"Gate 7-A {label} file does not match canonical daily schema")

        candidate_symbols = self._symbols(self.candidate_boundary_path)
        massive_symbols = self._symbols(self.massive_boundary_path)
        union_symbols = sorted(set(candidate_symbols).union(massive_symbols))
        cfg = self.settings.alpaca.market_data
        fingerprint = seam_source_fingerprint(
            candidate_fingerprint=str(candidate_report["source_fingerprint"]),
            candidate_boundary_sha256=sha256_file(self.candidate_boundary_path),
            massive_boundary_sha256=sha256_file(self.massive_boundary_path),
            symbols=union_symbols,
            symbol_batch_size=int(cfg.symbol_batch_size),
            feed=str(cfg.feed),
            adjustment=str(cfg.adjustment),
            asof=str(cfg.asof),
            timeframe=str(cfg.timeframe),
        )
        return {
            "candidate_report": candidate_report,
            "candidate_symbols": candidate_symbols,
            "massive_symbols": massive_symbols,
            "union_symbols": union_symbols,
            "source_fingerprint": fingerprint,
            "candidate_boundary_sha256": sha256_file(self.candidate_boundary_path),
            "massive_boundary_sha256": sha256_file(self.massive_boundary_path),
        }

    def _manifest_path(self, batch_index: int) -> Path:
        return self.unit_root / f"batch_{batch_index:04d}.json"

    @staticmethod
    def _raw_record_valid(record: dict[str, object]) -> bool:
        payload_path = Path(str(record.get("payload_path") or ""))
        metadata_path = Path(str(record.get("metadata_path") or ""))
        expected_sha = str(record.get("sha256") or "")
        if not payload_path.is_file() or not metadata_path.is_file() or not expected_sha:
            return False
        try:
            raw = gzip.decompress(payload_path.read_bytes())
        except (OSError, EOFError):
            return False
        return hashlib.sha256(raw).hexdigest() == expected_sha

    def _load_completed_unit(
        self,
        *,
        batch_index: int,
        symbols: tuple[str, ...],
        source_fingerprint: str,
    ) -> dict[str, Any] | None:
        path = self._manifest_path(batch_index)
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        expected_id = _unit_id(source_fingerprint, batch_index, symbols)
        locked = (
            payload.get("contract_version") == ALPACA_BACKFILL_SEAM_PROBE_CONTRACT_VERSION
            and payload.get("source_fingerprint") == source_fingerprint
            and payload.get("unit_id") == expected_id
            and payload.get("status") == ALPACA_BACKFILL_SEAM_STATUS_COMPLETE
            and payload.get("symbols") == list(symbols)
            and payload.get("request_start") == ALPACA_BACKFILL_SEAM_REQUEST_START
            and payload.get("request_end") == ALPACA_BACKFILL_SEAM_REQUEST_END
            and payload.get("feed") == self.settings.alpaca.market_data.feed
            and payload.get("adjustment") == self.settings.alpaca.market_data.adjustment
            and payload.get("asof") == self.settings.alpaca.market_data.asof
            and payload.get("timeframe") == self.settings.alpaca.market_data.timeframe
        )
        if not locked:
            return None
        records = list(payload.get("raw_pages") or []) + list(payload.get("provider_rejections") or [])
        if not all(self._raw_record_valid(record) for record in records if isinstance(record, dict)):
            return None
        return payload

    def _acquire_unit(
        self,
        *,
        batch_index: int,
        symbols: tuple[str, ...],
        source_fingerprint: str,
    ) -> dict[str, Any]:
        request_symbols = list(symbols)
        raw_pages: list[dict[str, object]] = []
        rejections: dict[str, dict[str, object]] = {}
        page_count = 0
        while request_symbols:
            try:
                for page_index, page in enumerate(
                    self.client.historical_bar_pages(
                        symbols=request_symbols,
                        start=ALPACA_BACKFILL_SEAM_REQUEST_START,
                        end=ALPACA_BACKFILL_SEAM_REQUEST_END,
                    )
                ):
                    page_count += 1
                    raw = self.raw_store.persist(
                        page,
                        category="seam_validation_bars",
                        partition=f"2021-08-16_batch_{batch_index:04d}_page_{page_index:04d}",
                    )
                    raw_pages.append(
                        {
                            "page_index": page_index,
                            "sha256": raw.sha256,
                            "payload_path": raw.payload_path,
                            "metadata_path": raw.metadata_path,
                            "page_token_used": raw.page_token_used,
                            "next_page_token": raw.next_page_token,
                        }
                    )
                break
            except AlpacaInvalidSymbolError as exc:
                if page_count or raw_pages:
                    raise RuntimeError(
                        "Gate 7-A provider rejected a symbol after successful pagination; "
                        "refusing partial-unit retry"
                    ) from exc
                invalid = exc.symbol
                if invalid not in request_symbols:
                    raise RuntimeError(
                        f"Gate 7-A provider rejected symbol outside submitted batch: {invalid}"
                    ) from exc
                raw = self.raw_store.persist(
                    exc.page,
                    category="seam_validation_rejections",
                    partition=f"2021-08-16_batch_{batch_index:04d}_reject_{len(rejections):04d}",
                )
                rejections[invalid] = {
                    "symbol": invalid,
                    "http_status": exc.page.http_status,
                    "provider_message": exc.provider_message,
                    "sha256": raw.sha256,
                    "payload_path": raw.payload_path,
                    "metadata_path": raw.metadata_path,
                }
                request_symbols = [symbol for symbol in request_symbols if symbol != invalid]

        manifest = {
            "contract_version": ALPACA_BACKFILL_SEAM_PROBE_CONTRACT_VERSION,
            "source_fingerprint": source_fingerprint,
            "unit_id": _unit_id(source_fingerprint, batch_index, symbols),
            "status": ALPACA_BACKFILL_SEAM_STATUS_COMPLETE,
            "canonical_data_modified": False,
            "batch_index": batch_index,
            "symbols": list(symbols),
            "symbol_count": len(symbols),
            "request_start": ALPACA_BACKFILL_SEAM_REQUEST_START,
            "request_end": ALPACA_BACKFILL_SEAM_REQUEST_END,
            "feed": self.settings.alpaca.market_data.feed,
            "adjustment": self.settings.alpaca.market_data.adjustment,
            "asof": self.settings.alpaca.market_data.asof,
            "timeframe": self.settings.alpaca.market_data.timeframe,
            "raw_pages": raw_pages,
            "provider_rejections": [rejections[key] for key in sorted(rejections)],
            "completed_at_utc": datetime.now(UTC).isoformat(),
        }
        atomic_write_text(
            self._manifest_path(batch_index),
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        )
        return manifest

    def _materialize_probe_rows(
        self,
        *,
        units: list[tuple[int, tuple[str, ...], dict[str, Any]]],
        locked_symbols: set[str],
    ) -> dict[str, int]:
        safe_rows: list[dict[str, object]] = []
        anomalies: list[dict[str, object]] = []
        raw_hash_failures = 0
        target = ALPACA_BACKFILL_SEAM_TARGET_SESSION.isoformat()

        for batch_index, requested_symbols, manifest in units:
            for record in manifest.get("raw_pages") or []:
                if not isinstance(record, dict):
                    continue
                if not self._raw_record_valid(record):
                    raw_hash_failures += 1
                    continue
                payload_path = Path(str(record["payload_path"]))
                raw = gzip.decompress(payload_path.read_bytes())
                payload = json.loads(raw.decode("utf-8"))
                bars = payload.get("bars") if isinstance(payload, dict) else None
                if not isinstance(bars, dict):
                    continue
                for raw_symbol, values in bars.items():
                    returned_symbol = _clean_symbol(raw_symbol)
                    if returned_symbol is None or not isinstance(values, list):
                        continue
                    classification, requested_symbol, match_count = classify_seam_response_symbol(
                        returned_symbol,
                        requested_symbols,
                        locked_symbols,
                    )
                    target_values = [
                        item
                        for item in values
                        if isinstance(item, dict) and _session_date(item.get("t")) == target
                    ]
                    if classification is not None:
                        anomalies.append(
                            {
                                "classification": classification,
                                "batch_index": batch_index,
                                "requested_symbol": requested_symbol,
                                "returned_symbol": returned_symbol,
                                "returned_is_locked_symbol": returned_symbol in locked_symbols,
                                "casefold_match_count": match_count,
                                "bar_rows": len(values),
                                "target_session_bar_rows": len(target_values),
                                "raw_page_sha256": str(record.get("sha256") or ""),
                            }
                        )
                        continue
                    for item in target_values:
                        safe_rows.append(
                            {
                                "symbol": returned_symbol,
                                "session_date": target,
                                "timestamp_utc": item.get("t"),
                                "open": item.get("o"),
                                "high": item.get("h"),
                                "low": item.get("l"),
                                "close": item.get("c"),
                                "volume": item.get("v"),
                                "vwap": item.get("vw"),
                                "transaction_count": item.get("n"),
                                "batch_index": batch_index,
                                "raw_page_sha256": str(record.get("sha256") or ""),
                            }
                        )

        _write_parquet(self.safe_bars_path, safe_rows, SAFE_BAR_COLUMNS)
        _write_parquet(self.anomalies_path, anomalies, ANOMALY_COLUMNS)
        return {
            "safe_rows": len(safe_rows),
            "anomaly_records": len(anomalies),
            "anomaly_target_rows": sum(int(row["target_session_bar_rows"]) for row in anomalies),
            "raw_hash_failures": raw_hash_failures,
        }

    def _comparison(self, parents: dict[str, object]) -> dict[str, object]:
        con = duckdb.connect(":memory:")
        try:
            con.execute("CREATE VIEW a AS SELECT * FROM read_parquet(?)", [str(self.safe_bars_path)])
            con.execute("CREATE VIEW m AS SELECT * FROM read_parquet(?)", [str(self.massive_boundary_path)])
            con.execute("CREATE VIEW f AS SELECT * FROM read_parquet(?)", [str(self.candidate_boundary_path)])
            duplicate_alpaca = int(
                con.execute(
                    "SELECT coalesce(sum(n-1),0) FROM (SELECT symbol,count(*) n FROM a GROUP BY symbol HAVING count(*)>1)"
                ).fetchone()[0]
            )
            duplicate_massive = int(
                con.execute(
                    "SELECT coalesce(sum(n-1),0) FROM (SELECT symbol,count(*) n FROM m GROUP BY symbol HAVING count(*)>1)"
                ).fetchone()[0]
            )
            comparison_rows = con.execute(
                """
                SELECT
                    a.symbol,
                    a.open AS alpaca_open, m.open AS massive_open,
                    a.high AS alpaca_high, m.high AS massive_high,
                    a.low AS alpaca_low, m.low AS massive_low,
                    a.close AS alpaca_close, m.close AS massive_close,
                    a.volume AS alpaca_volume, m.volume AS massive_volume
                FROM a JOIN m USING (symbol)
                ORDER BY a.symbol
                """
            ).fetchall()
        finally:
            con.close()

        comparison: list[dict[str, object]] = []
        ohlc_diffs: list[float] = []
        close_diffs: list[float] = []
        volume_diffs: list[float] = []
        exact_ohlc = 0
        exact_close = 0
        for row in comparison_rows:
            symbol = str(row[0])
            a_o, m_o, a_h, m_h, a_l, m_l, a_c, m_c, a_v, m_v = map(float, row[1:])
            field_diffs = [
                _relative_difference(a_o, m_o),
                _relative_difference(a_h, m_h),
                _relative_difference(a_l, m_l),
                _relative_difference(a_c, m_c),
            ]
            close_diff = field_diffs[-1]
            volume_diff = _relative_difference(a_v, m_v)
            ohlc_diffs.extend(field_diffs)
            close_diffs.append(close_diff)
            volume_diffs.append(volume_diff)
            row_exact_ohlc = a_o == m_o and a_h == m_h and a_l == m_l and a_c == m_c
            row_exact_close = a_c == m_c
            exact_ohlc += int(row_exact_ohlc)
            exact_close += int(row_exact_close)
            comparison.append(
                {
                    "symbol": symbol,
                    "alpaca_open": a_o,
                    "massive_open": m_o,
                    "alpaca_high": a_h,
                    "massive_high": m_h,
                    "alpaca_low": a_l,
                    "massive_low": m_l,
                    "alpaca_close": a_c,
                    "massive_close": m_c,
                    "alpaca_volume": a_v,
                    "massive_volume": m_v,
                    "max_ohlc_relative_diff": max(field_diffs),
                    "close_relative_diff": close_diff,
                    "volume_relative_diff": volume_diff,
                    "exact_ohlc": row_exact_ohlc,
                    "exact_close": row_exact_close,
                }
            )

        comparison_columns = tuple(comparison[0].keys()) if comparison else (
            "symbol",
            "alpaca_open",
            "massive_open",
            "alpaca_high",
            "massive_high",
            "alpaca_low",
            "massive_low",
            "alpaca_close",
            "massive_close",
            "alpaca_volume",
            "massive_volume",
            "max_ohlc_relative_diff",
            "close_relative_diff",
            "volume_relative_diff",
            "exact_ohlc",
            "exact_close",
        )
        _write_parquet(self.provider_comparison_path, comparison, comparison_columns)

        con = duckdb.connect(":memory:")
        try:
            candidate_only = int(
                con.execute(
                    "SELECT count(*) FROM read_parquet(?) f LEFT JOIN read_parquet(?) m USING(symbol) WHERE m.symbol IS NULL",
                    [str(self.candidate_boundary_path), str(self.massive_boundary_path)],
                ).fetchone()[0]
            )
            massive_only = int(
                con.execute(
                    "SELECT count(*) FROM read_parquet(?) m LEFT JOIN read_parquet(?) f USING(symbol) WHERE f.symbol IS NULL",
                    [str(self.massive_boundary_path), str(self.candidate_boundary_path)],
                ).fetchone()[0]
            )
            exact_boundary = int(
                con.execute(
                    "SELECT count(*) FROM read_parquet(?) f JOIN read_parquet(?) m USING(symbol)",
                    [str(self.candidate_boundary_path), str(self.massive_boundary_path)],
                ).fetchone()[0]
            )
            boundary_rows = con.execute(
                """
                SELECT
                    coalesce(f.symbol,m.symbol) symbol,
                    f.symbol IS NOT NULL AS candidate_friday_present,
                    m.symbol IS NOT NULL AS massive_monday_present,
                    f.close AS candidate_friday_close,
                    m.open AS massive_monday_open,
                    m.close AS massive_monday_close
                FROM read_parquet(?) f FULL OUTER JOIN read_parquet(?) m USING(symbol)
                ORDER BY symbol
                """,
                [str(self.candidate_boundary_path), str(self.massive_boundary_path)],
            ).fetchall()
        finally:
            con.close()

        status_rows: list[dict[str, object]] = []
        boundary_gap_open: list[float] = []
        boundary_gap_close: list[float] = []
        for symbol, friday_present, monday_present, friday_close, monday_open, monday_close in boundary_rows:
            gap_open: float | None = None
            gap_close: float | None = None
            if friday_close is not None and monday_open is not None:
                gap_open = _relative_difference(float(friday_close), float(monday_open))
                boundary_gap_open.append(gap_open)
            if friday_close is not None and monday_close is not None:
                gap_close = _relative_difference(float(friday_close), float(monday_close))
                boundary_gap_close.append(gap_close)
            status_rows.append(
                {
                    "symbol": str(symbol),
                    "candidate_friday_present": bool(friday_present),
                    "massive_monday_present": bool(monday_present),
                    "candidate_friday_close": friday_close,
                    "massive_monday_open": monday_open,
                    "massive_monday_close": monday_close,
                    "friday_close_to_monday_open_relative_move": gap_open,
                    "friday_close_to_monday_close_relative_move": gap_close,
                }
            )
        status_columns = tuple(status_rows[0].keys()) if status_rows else (
            "symbol",
            "candidate_friday_present",
            "massive_monday_present",
            "candidate_friday_close",
            "massive_monday_open",
            "massive_monday_close",
            "friday_close_to_monday_open_relative_move",
            "friday_close_to_monday_close_relative_move",
        )
        _write_parquet(self.boundary_status_path, status_rows, status_columns)

        safe_symbols = {str(row["symbol"]) for row in comparison}
        all_alpaca_safe = set(self._symbols(self.safe_bars_path))
        massive_symbols = set(parents["massive_symbols"])
        return {
            "duplicate_alpaca_target_rows": duplicate_alpaca,
            "duplicate_massive_target_rows": duplicate_massive,
            "alpaca_safe_target_symbols": len(all_alpaca_safe),
            "massive_target_symbols": len(massive_symbols),
            "matched_exact_symbols": len(safe_symbols),
            "alpaca_safe_only_symbols": len(all_alpaca_safe - massive_symbols),
            "massive_only_vs_safe_alpaca_symbols": len(massive_symbols - all_alpaca_safe),
            "exact_ohlc_symbols": exact_ohlc,
            "exact_close_symbols": exact_close,
            "close_within_1bp_fraction": (
                sum(value <= 0.0001 for value in close_diffs) / len(close_diffs)
                if close_diffs
                else None
            ),
            "ohlc_relative_diff_median": _quantile(ohlc_diffs, 0.5),
            "ohlc_relative_diff_p95": _quantile(ohlc_diffs, 0.95),
            "ohlc_relative_diff_max": max(ohlc_diffs) if ohlc_diffs else None,
            "close_relative_diff_p95": _quantile(close_diffs, 0.95),
            "volume_relative_diff_median": _quantile(volume_diffs, 0.5),
            "volume_relative_diff_p95": _quantile(volume_diffs, 0.95),
            "candidate_friday_symbols": len(parents["candidate_symbols"]),
            "candidate_friday_massive_monday_exact_symbols": exact_boundary,
            "candidate_friday_only_symbols": candidate_only,
            "massive_monday_only_symbols": massive_only,
            "boundary_open_move_p95": _quantile(boundary_gap_open, 0.95),
            "boundary_open_move_max": max(boundary_gap_open) if boundary_gap_open else None,
            "boundary_close_move_p95": _quantile(boundary_gap_close, 0.95),
            "boundary_close_move_max": max(boundary_gap_close) if boundary_gap_close else None,
        }

    def run(self) -> dict[str, object]:
        parents = self._load_parents()
        symbols = list(parents["union_symbols"])
        batch_size = int(self.settings.alpaca.market_data.symbol_batch_size)
        batches = list(_chunks(symbols, batch_size))
        units: list[tuple[int, tuple[str, ...], dict[str, Any]]] = []
        executed = 0
        skipped = 0
        for batch_index, batch in enumerate(batches):
            existing = self._load_completed_unit(
                batch_index=batch_index,
                symbols=batch,
                source_fingerprint=str(parents["source_fingerprint"]),
            )
            if existing is None:
                existing = self._acquire_unit(
                    batch_index=batch_index,
                    symbols=batch,
                    source_fingerprint=str(parents["source_fingerprint"]),
                )
                executed += 1
            else:
                skipped += 1
            units.append((batch_index, batch, existing))

        row_stats = self._materialize_probe_rows(
            units=units,
            locked_symbols=set(symbols),
        )
        comparison = self._comparison(parents)
        rejection_count = sum(
            len(manifest.get("provider_rejections") or []) for _index, _batch, manifest in units
        )
        report = {
            "contract_version": ALPACA_BACKFILL_SEAM_PROBE_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "canonical_data_modified": False,
            "source_fingerprint": parents["source_fingerprint"],
            "candidate_source_fingerprint": parents["candidate_report"]["source_fingerprint"],
            "candidate_boundary_session": ALPACA_BACKFILL_CANDIDATE_BOUNDARY_SESSION.isoformat(),
            "massive_boundary_session": ALPACA_BACKFILL_SEAM_TARGET_SESSION.isoformat(),
            "request_start": ALPACA_BACKFILL_SEAM_REQUEST_START,
            "request_end": ALPACA_BACKFILL_SEAM_REQUEST_END,
            "feed": self.settings.alpaca.market_data.feed,
            "adjustment": self.settings.alpaca.market_data.adjustment,
            "asof": self.settings.alpaca.market_data.asof,
            "timeframe": self.settings.alpaca.market_data.timeframe,
            "response_symbol_policy": ALPACA_BACKFILL_SEAM_RESPONSE_POLICY,
            "candidate_boundary_sha256": parents["candidate_boundary_sha256"],
            "massive_boundary_sha256": parents["massive_boundary_sha256"],
            "candidate_boundary_schema_exact": self._schema_exact(self.candidate_boundary_path),
            "massive_boundary_schema_exact": self._schema_exact(self.massive_boundary_path),
            "candidate_boundary_symbols": len(parents["candidate_symbols"]),
            "massive_boundary_symbols": len(parents["massive_symbols"]),
            "union_symbols": len(symbols),
            "planned_units": len(batches),
            "completed_units": len(units),
            "executed_units_this_run": executed,
            "skipped_units_this_run": skipped,
            "provider_rejected_symbols": rejection_count,
            **row_stats,
            **comparison,
            "safe_bars_path": str(self.safe_bars_path),
            "response_symbol_anomalies_path": str(self.anomalies_path),
            "provider_comparison_path": str(self.provider_comparison_path),
            "boundary_status_path": str(self.boundary_status_path),
            "report_path": str(self.report_path),
        }
        checks = {
            "gate6_parent_pass": True,
            "candidate_boundary_schema_exact": report["candidate_boundary_schema_exact"] is True,
            "massive_boundary_schema_exact": report["massive_boundary_schema_exact"] is True,
            "all_probe_units_complete": report["completed_units"] == report["planned_units"],
            "raw_payload_hashes_clean": report["raw_hash_failures"] == 0,
            "safe_alpaca_target_duplicates_zero": report["duplicate_alpaca_target_rows"] == 0,
            "massive_target_duplicates_zero": report["duplicate_massive_target_rows"] == 0,
            "same_session_provider_overlap_present": report["matched_exact_symbols"] > 0,
            "canonical_data_untouched": report["canonical_data_modified"] is False,
        }
        report["structural_checks"] = checks
        report["structural_pass"] = all(checks.values())
        atomic_write_text(
            self.report_path,
            json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        )
        return report
