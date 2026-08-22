from __future__ import annotations

import gzip
import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_acquisition import ALPACA_BACKFILL_ACQUISITION_CONTRACT_VERSION
from packages.data.alpaca_backfill_policy import ALPACA_BACKFILL_END, ALPACA_BACKFILL_START
from packages.data.alpaca_backfill_quality import (
    ALPACA_BACKFILL_QUALITY_BASELINE_CONTRACT_VERSION,
    ZERO_ACTIVITY_PLACEHOLDER_CLASS,
    inspect_daily_bar,
    _unit_window,
)
from packages.data.alpaca_backfill_session_quality import (
    ALPACA_BACKFILL_SESSION_QUALITY_CONTRACT_VERSION,
    TRADE_BACKED,
)


ALPACA_BACKFILL_VALIDATED_EVIDENCE_CONTRACT_VERSION = (
    "historical-backfill-validated-evidence-v1-provenance-locked-parquet"
)
CACHE_VERSION_DIR = "v1"
CACHE_ROLE = "DERIVED_VALIDATED_EVIDENCE_NOT_CANONICAL"
EVIDENCE_COLUMNS = [
    "source_year",
    "source_batch_index",
    "source_page_index",
    "source_page_sha256",
    "source_record_index",
    "provider_symbol",
    "timestamp_utc",
    "session_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "trade_count",
    "vwap",
    "bar_class",
]
EVIDENCE_TABLE_SCHEMA = """
CREATE TABLE evidence_year (
    source_year INTEGER NOT NULL,
    source_batch_index INTEGER NOT NULL,
    source_page_index INTEGER NOT NULL,
    source_page_sha256 VARCHAR NOT NULL,
    source_record_index INTEGER NOT NULL,
    provider_symbol VARCHAR NOT NULL,
    timestamp_utc VARCHAR NOT NULL,
    session_date DATE NOT NULL,
    open DOUBLE NOT NULL,
    high DOUBLE NOT NULL,
    low DOUBLE NOT NULL,
    close DOUBLE NOT NULL,
    volume DOUBLE NOT NULL,
    trade_count DOUBLE NOT NULL,
    vwap DOUBLE NOT NULL,
    bar_class VARCHAR NOT NULL
)
"""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _finite(value: object) -> float:
    if value is None or isinstance(value, bool):
        raise RuntimeError("validated evidence encountered missing/non-numeric field")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("validated evidence encountered non-numeric field") from exc
    if not math.isfinite(number):
        raise RuntimeError("validated evidence encountered non-finite field")
    return number


def stable_source_fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def selected_parent_semantics(
    quality: dict[str, Any],
    session: dict[str, Any],
) -> dict[str, object]:
    return {
        "quality": {
            "contract_version": quality.get("contract_version"),
            "identity_safe_bar_rows": int(quality.get("identity_safe_bar_rows", -1)),
            "trade_backed_usable_rows": int(quality.get("trade_backed_usable_rows", -1)),
            "zero_activity_placeholder_rows": int(
                quality.get("zero_activity_placeholder_rows", -1)
            ),
            "quarantined_response_bar_rows": int(
                quality.get("quarantined_response_bar_rows", -1)
            ),
            "observed_symbols": int(quality.get("observed_symbols", -1)),
            "definite_invalid_rows": int(quality.get("definite_invalid_rows", -1)),
            "zero_activity_candidate_policy": quality.get(
                "zero_activity_candidate_policy"
            ),
        },
        "session": {
            "contract_version": session.get("contract_version"),
            "unique_session_keys": int(session.get("unique_session_keys", -1)),
            "duplicate_session_rows": int(session.get("duplicate_session_rows", -1)),
            "non_exchange_session_rows": int(
                session.get("non_exchange_session_rows", -1)
            ),
            "missing_sessions_within_lifespans": int(
                session.get("missing_sessions_within_lifespans", -1)
            ),
            "raw_row_accounting_exact": bool(session.get("raw_row_accounting_exact")),
            "parent_classification_accounting_exact": bool(
                session.get("parent_classification_accounting_exact")
            ),
            "unique_session_accounting_exact": bool(
                session.get("unique_session_accounting_exact")
            ),
        },
    }


def build_fingerprint_payload(
    *,
    page_entries: list[dict[str, object]],
    anomaly_sha256: str,
    quality: dict[str, Any],
    session: dict[str, Any],
    year: int | None = None,
) -> dict[str, object]:
    filtered = sorted(
        (
            dict(entry)
            for entry in page_entries
            if year is None or int(entry["year"]) == year
        ),
        key=lambda entry: (
            int(entry["year"]),
            int(entry["batch_index"]),
            int(entry["page_index"]),
            str(entry["sha256"]),
        ),
    )
    return {
        "contract_version": ALPACA_BACKFILL_VALIDATED_EVIDENCE_CONTRACT_VERSION,
        "acquisition_contract_version": ALPACA_BACKFILL_ACQUISITION_CONTRACT_VERSION,
        "quality_contract_version": ALPACA_BACKFILL_QUALITY_BASELINE_CONTRACT_VERSION,
        "session_quality_contract_version": ALPACA_BACKFILL_SESSION_QUALITY_CONTRACT_VERSION,
        "zero_activity_placeholder_class": ZERO_ACTIVITY_PLACEHOLDER_CLASS,
        "page_entries": filtered,
        "anomaly_sha256": anomaly_sha256,
        "parent_semantics": selected_parent_semantics(quality, session),
        "year_scope": year,
    }


def evidence_row_from_record(
    *,
    record: object,
    symbol: str,
    year: int,
    batch_index: int,
    page_index: int,
    page_sha256: str,
    record_index: int,
) -> dict[str, object]:
    unit_start, unit_end = _unit_window(year)
    inspected = inspect_daily_bar(record, unit_start=unit_start, unit_end=unit_end)
    if inspected.definite_invalid or inspected.session_date is None:
        raise RuntimeError(
            "validated evidence cache encountered row inconsistent with accepted Gate 5-A"
        )
    if not isinstance(record, dict) or inspected.timestamp_text is None:
        raise RuntimeError("validated evidence cache requires a timestamped dictionary bar")
    return {
        "source_year": year,
        "source_batch_index": batch_index,
        "source_page_index": page_index,
        "source_page_sha256": page_sha256,
        "source_record_index": record_index,
        "provider_symbol": symbol,
        "timestamp_utc": inspected.timestamp_text,
        "session_date": inspected.session_date.isoformat(),
        "open": _finite(record.get("o")),
        "high": _finite(record.get("h")),
        "low": _finite(record.get("l")),
        "close": _finite(record.get("c")),
        "volume": _finite(record.get("v")),
        "trade_count": _finite(record.get("n")),
        "vwap": _finite(record.get("vw")),
        "bar_class": (
            ZERO_ACTIVITY_PLACEHOLDER_CLASS
            if inspected.zero_activity_placeholder
            else TRADE_BACKED
        ),
    }


class AlpacaBackfillValidatedEvidenceBuilder:
    """Build/resume one Parquet representation of already accepted raw provider evidence."""

    def __init__(self, settings: AtlasSettings) -> None:
        root = settings.resolved_path(settings.data.paths.derived) / "historical_backfill" / "alpaca"
        self.acquisition_root = root / "acquisition"
        self.quality_root = root / "quality"
        self.cache_root = root / "validated_evidence" / CACHE_VERSION_DIR
        self.unit_manifest_root = self.acquisition_root / "units"
        self.anomaly_path = self.acquisition_root / "response_symbol_anomalies.parquet"
        self.quality_report_path = self.quality_root / "quality_baseline_report.json"
        self.session_report_path = self.quality_root / "session_coverage_report.json"
        self.report_path = self.cache_root / "evidence_manifest.json"

    def _load_parents(self) -> tuple[dict[str, Any], dict[str, Any]]:
        required = (self.quality_report_path, self.session_report_path, self.anomaly_path)
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise RuntimeError(f"validated evidence cache missing parent artifacts: {missing}")
        quality = json.loads(self.quality_report_path.read_text(encoding="utf-8"))
        session = json.loads(self.session_report_path.read_text(encoding="utf-8"))
        if quality.get("contract_version") != ALPACA_BACKFILL_QUALITY_BASELINE_CONTRACT_VERSION:
            raise RuntimeError("validated evidence cache Gate 5-A contract mismatch")
        if session.get("contract_version") != ALPACA_BACKFILL_SESSION_QUALITY_CONTRACT_VERSION:
            raise RuntimeError("validated evidence cache Gate 5-B contract mismatch")
        if quality.get("canonical_data_modified") is not False or session.get("canonical_data_modified") is not False:
            raise RuntimeError("validated evidence cache parent modified canonical data")
        if int(quality.get("definite_invalid_rows", -1)) != 0:
            raise RuntimeError("validated evidence cache requires zero Gate 5-A defects")
        if int(session.get("duplicate_session_rows", -1)) != 0:
            raise RuntimeError("validated evidence cache requires zero duplicate session rows")
        if int(session.get("non_exchange_session_rows", -1)) != 0:
            raise RuntimeError("validated evidence cache requires zero non-XNYS session rows")
        if int(session.get("missing_sessions_within_lifespans", -1)) != 0:
            raise RuntimeError("validated evidence cache requires zero absent lifespan sessions")
        if not all(
            session.get(name) is True
            for name in (
                "raw_row_accounting_exact",
                "parent_classification_accounting_exact",
                "unique_session_accounting_exact",
            )
        ):
            raise RuntimeError("validated evidence cache requires accepted Gate 5-B accounting")
        return quality, session

    def _load_anomaly_keys(self) -> dict[tuple[int, int, str], int]:
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
        return {
            (int(year), int(batch), str(symbol)): int(count)
            for year, batch, symbol, count in rows
        }

    def _manifest_page_entries(
        self,
    ) -> tuple[list[Path], list[dict[str, object]], dict[int, list[Path]]]:
        manifests = sorted(self.unit_manifest_root.glob("*/*.json"))
        page_entries: list[dict[str, object]] = []
        by_year: dict[int, list[Path]] = {}
        for manifest_path in manifests:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("contract_version") != ALPACA_BACKFILL_ACQUISITION_CONTRACT_VERSION:
                raise RuntimeError(f"validated evidence incompatible unit manifest: {manifest_path}")
            if manifest.get("status") != "COMPLETE" or manifest.get("canonical_data_modified") is not False:
                raise RuntimeError(f"validated evidence incomplete/unsafe unit manifest: {manifest_path}")
            year = int(manifest_path.parent.name)
            batch_index = int(manifest_path.stem.split("_")[-1])
            by_year.setdefault(year, []).append(manifest_path)
            for page_index, page in enumerate(manifest.get("raw_pages") or []):
                sha256 = str(page.get("sha256") or "")
                if not sha256:
                    raise RuntimeError(f"validated evidence raw page lacks SHA: {manifest_path}")
                page_entries.append(
                    {
                        "year": year,
                        "batch_index": batch_index,
                        "page_index": page_index,
                        "sha256": sha256,
                    }
                )
        return manifests, page_entries, by_year

    def _source_fingerprints(
        self,
        page_entries: list[dict[str, object]],
        quality: dict[str, Any],
        session: dict[str, Any],
    ) -> tuple[str, dict[int, str]]:
        anomaly_sha = sha256_file(self.anomaly_path)
        global_fp = stable_source_fingerprint(
            build_fingerprint_payload(
                page_entries=page_entries,
                anomaly_sha256=anomaly_sha,
                quality=quality,
                session=session,
            )
        )
        year_fps = {
            year: stable_source_fingerprint(
                build_fingerprint_payload(
                    page_entries=page_entries,
                    anomaly_sha256=anomaly_sha,
                    quality=quality,
                    session=session,
                    year=year,
                )
            )
            for year in range(ALPACA_BACKFILL_START.year, ALPACA_BACKFILL_END.year + 1)
        }
        return global_fp, year_fps

    def _partition_paths(self, year: int) -> tuple[Path, Path]:
        root = self.cache_root / f"year={year}"
        return root / "bars.parquet", root / "partition_manifest.json"

    @staticmethod
    def _valid_partition(
        manifest_path: Path,
        parquet_path: Path,
        fingerprint: str,
    ) -> dict[str, object] | None:
        if not manifest_path.is_file() or not parquet_path.is_file():
            return None
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            if payload.get("contract_version") != ALPACA_BACKFILL_VALIDATED_EVIDENCE_CONTRACT_VERSION:
                return None
            if payload.get("source_fingerprint") != fingerprint:
                return None
            if sha256_file(parquet_path) != payload.get("parquet_sha256"):
                return None
            return payload
        except Exception:
            return None

    @staticmethod
    def _append_frame(con: duckdb.DuckDBPyConnection, rows: list[dict[str, object]]) -> None:
        if not rows:
            return
        frame = pd.DataFrame(rows, columns=EVIDENCE_COLUMNS)
        con.register("_evidence_page", frame)
        try:
            con.execute(
                "INSERT INTO evidence_year SELECT "
                "CAST(source_year AS INTEGER), CAST(source_batch_index AS INTEGER), "
                "CAST(source_page_index AS INTEGER), CAST(source_page_sha256 AS VARCHAR), "
                "CAST(source_record_index AS INTEGER), CAST(provider_symbol AS VARCHAR), "
                "CAST(timestamp_utc AS VARCHAR), CAST(session_date AS DATE), "
                "CAST(open AS DOUBLE), CAST(high AS DOUBLE), CAST(low AS DOUBLE), "
                "CAST(close AS DOUBLE), CAST(volume AS DOUBLE), CAST(trade_count AS DOUBLE), "
                "CAST(vwap AS DOUBLE), CAST(bar_class AS VARCHAR) FROM _evidence_page"
            )
        finally:
            con.unregister("_evidence_page")

    def _build_year(
        self,
        year: int,
        manifests: list[Path],
        anomaly_keys: dict[tuple[int, int, str], int],
        fingerprint: str,
    ) -> tuple[dict[str, object], dict[tuple[int, int, str], int]]:
        parquet_path, partition_manifest_path = self._partition_paths(year)
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        con = duckdb.connect(":memory:")
        quarantine_seen: dict[tuple[int, int, str], int] = {}
        raw_pages = 0
        try:
            con.execute(EVIDENCE_TABLE_SCHEMA)
            for manifest_path in manifests:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                batch_index = int(manifest_path.stem.split("_")[-1])
                for page_index, page in enumerate(manifest.get("raw_pages") or []):
                    payload_path = Path(str(page.get("payload_path") or ""))
                    expected_sha = str(page.get("sha256") or "")
                    if not payload_path.is_file():
                        raise RuntimeError(f"validated evidence missing raw page: {payload_path}")
                    raw_bytes = gzip.decompress(payload_path.read_bytes())
                    if _sha256_bytes(raw_bytes) != expected_sha:
                        raise RuntimeError(f"validated evidence raw page hash failure: {payload_path}")
                    raw_pages += 1
                    payload = json.loads(raw_bytes)
                    bars = payload.get("bars") if isinstance(payload, dict) else None
                    if not isinstance(bars, dict):
                        raise RuntimeError(f"validated evidence invalid raw page shape: {payload_path}")
                    page_rows: list[dict[str, object]] = []
                    for raw_symbol, values in bars.items():
                        symbol = str(raw_symbol)
                        if not isinstance(values, list):
                            raise RuntimeError(f"validated evidence invalid bar list: {payload_path}")
                        anomaly_key = (year, batch_index, symbol)
                        if anomaly_key in anomaly_keys:
                            quarantine_seen[anomaly_key] = int(quarantine_seen.get(anomaly_key, 0)) + len(values)
                            continue
                        for record_index, record in enumerate(values):
                            page_rows.append(
                                evidence_row_from_record(
                                    record=record,
                                    symbol=symbol,
                                    year=year,
                                    batch_index=batch_index,
                                    page_index=page_index,
                                    page_sha256=expected_sha,
                                    record_index=record_index,
                                )
                            )
                    self._append_frame(con, page_rows)

            counts = con.execute(
                "SELECT count(*), "
                "sum(CASE WHEN bar_class=? THEN 1 ELSE 0 END), "
                "sum(CASE WHEN bar_class=? THEN 1 ELSE 0 END) FROM evidence_year",
                [TRADE_BACKED, ZERO_ACTIVITY_PLACEHOLDER_CLASS],
            ).fetchone()
            assert counts is not None
            duplicate = con.execute(
                "SELECT count(*) FROM (SELECT provider_symbol, session_date, count(*) AS n "
                "FROM evidence_year GROUP BY 1,2 HAVING count(*) > 1)"
            ).fetchone()
            if duplicate is None or int(duplicate[0]) != 0:
                raise RuntimeError(f"validated evidence year {year} contains duplicate session keys")
            temp = unique_temp_path(parquet_path)
            con.execute(
                "COPY (SELECT * FROM evidence_year ORDER BY provider_symbol, session_date, "
                "timestamp_utc, source_batch_index, source_page_index, source_record_index) "
                "TO ? (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)",
                [str(temp)],
            )
            replace_with_retry(temp, parquet_path)
        finally:
            con.close()

        partition = {
            "year": year,
            "rows": int(counts[0]),
            "trade_backed_rows": int(counts[1] or 0),
            "zero_activity_placeholder_rows": int(counts[2] or 0),
            "parquet_path": str(parquet_path),
            "parquet_sha256": sha256_file(parquet_path),
            "source_fingerprint": fingerprint,
            "raw_pages_revalidated": raw_pages,
            "canonical_data_modified": False,
        }
        atomic_write_text(
            partition_manifest_path,
            json.dumps(
                {
                    "contract_version": ALPACA_BACKFILL_VALIDATED_EVIDENCE_CONTRACT_VERSION,
                    **partition,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
        return partition, quarantine_seen

    def run(self, *, force: bool = False) -> dict[str, object]:
        quality, session = self._load_parents()
        manifests, page_entries, manifests_by_year = self._manifest_page_entries()
        if len(manifests) != int(quality.get("retained_unit_manifests", -1)):
            raise RuntimeError("validated evidence unit manifest count differs from Gate 5-A")
        if len(page_entries) != int(quality.get("retained_raw_bar_pages", -1)):
            raise RuntimeError("validated evidence raw page count differs from Gate 5-A")
        global_fp, year_fps = self._source_fingerprints(page_entries, quality, session)
        anomaly_keys = self._load_anomaly_keys()
        self.cache_root.mkdir(parents=True, exist_ok=True)
        partitions: list[dict[str, object]] = []
        rebuilt_years: set[int] = set()
        rebuilt_quarantine: dict[tuple[int, int, str], int] = {}

        for year in range(ALPACA_BACKFILL_START.year, ALPACA_BACKFILL_END.year + 1):
            parquet_path, partition_manifest_path = self._partition_paths(year)
            existing = None if force else self._valid_partition(
                partition_manifest_path,
                parquet_path,
                year_fps[year],
            )
            if existing is not None:
                partitions.append(existing)
                continue
            partition, quarantine_seen = self._build_year(
                year,
                manifests_by_year.get(year, []),
                anomaly_keys,
                year_fps[year],
            )
            partitions.append(partition)
            rebuilt_years.add(year)
            rebuilt_quarantine.update(quarantine_seen)

        for key, expected in anomaly_keys.items():
            if key[0] in rebuilt_years and rebuilt_quarantine.get(key, 0) != expected:
                raise RuntimeError(
                    f"validated evidence quarantine mismatch for rebuilt unit {key}: "
                    f"{rebuilt_quarantine.get(key, 0)} != {expected}"
                )

        rows = sum(int(item["rows"]) for item in partitions)
        trade_rows = sum(int(item["trade_backed_rows"]) for item in partitions)
        placeholder_rows = sum(int(item["zero_activity_placeholder_rows"]) for item in partitions)
        report = {
            "contract_version": ALPACA_BACKFILL_VALIDATED_EVIDENCE_CONTRACT_VERSION,
            "acquisition_contract_version": ALPACA_BACKFILL_ACQUISITION_CONTRACT_VERSION,
            "quality_contract_version": ALPACA_BACKFILL_QUALITY_BASELINE_CONTRACT_VERSION,
            "session_quality_contract_version": ALPACA_BACKFILL_SESSION_QUALITY_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "canonical_data_modified": False,
            "cache_role": CACHE_ROLE,
            "source_fingerprint": global_fp,
            "retained_unit_manifests": len(manifests),
            "retained_raw_bar_pages": len(page_entries),
            "raw_payload_hash_failures": 0,
            "identity_safe_rows": rows,
            "trade_backed_rows": trade_rows,
            "zero_activity_placeholder_rows": placeholder_rows,
            "quarantined_response_rows": int(quality.get("quarantined_response_bar_rows", -1)),
            "observed_symbols": int(quality.get("observed_symbols", -1)),
            "partitions": partitions,
            "row_accounting_exact": rows == int(quality.get("identity_safe_bar_rows", -1)),
            "classification_accounting_exact": (
                trade_rows == int(quality.get("trade_backed_usable_rows", -1))
                and placeholder_rows == int(quality.get("zero_activity_placeholder_rows", -1))
                and rows == trade_rows + placeholder_rows
            ),
            "report_path": str(self.report_path),
        }
        if not report["row_accounting_exact"] or not report["classification_accounting_exact"]:
            raise RuntimeError("validated evidence cache accounting invariant failed")
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report


class AlpacaBackfillValidatedEvidenceValidator:
    """Fast cache validator; verifies fingerprints and Parquet without reparsing raw JSON."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.builder = AlpacaBackfillValidatedEvidenceBuilder(settings)

    def run(self) -> dict[str, object]:
        quality, session = self.builder._load_parents()
        if not self.builder.report_path.is_file():
            raise RuntimeError("validated evidence cache manifest is missing")
        report = json.loads(self.builder.report_path.read_text(encoding="utf-8"))
        if report.get("contract_version") != ALPACA_BACKFILL_VALIDATED_EVIDENCE_CONTRACT_VERSION:
            raise RuntimeError("validated evidence cache contract mismatch")
        manifests, page_entries, _ = self.builder._manifest_page_entries()
        global_fp, year_fps = self.builder._source_fingerprints(page_entries, quality, session)
        partitions: list[dict[str, object]] = []
        hashes_exact = True
        for year in range(ALPACA_BACKFILL_START.year, ALPACA_BACKFILL_END.year + 1):
            parquet_path, partition_manifest_path = self.builder._partition_paths(year)
            item = self.builder._valid_partition(
                partition_manifest_path,
                parquet_path,
                year_fps[year],
            )
            if item is None:
                hashes_exact = False
            else:
                partitions.append(item)

        counts = {"rows": -1, "trade": -1, "placeholder": -1, "symbols": -1, "duplicates": -1, "unknown_classes": -1}
        paths = [Path(str(item["parquet_path"])) for item in partitions]
        if hashes_exact and len(paths) == 6:
            con = duckdb.connect(":memory:")
            try:
                con.read_parquet([str(path) for path in paths]).create_view("evidence")
                row = con.execute(
                    "SELECT count(*), "
                    "sum(CASE WHEN bar_class=? THEN 1 ELSE 0 END), "
                    "sum(CASE WHEN bar_class=? THEN 1 ELSE 0 END), "
                    "count(DISTINCT provider_symbol), "
                    "sum(CASE WHEN bar_class NOT IN (?, ?) THEN 1 ELSE 0 END) FROM evidence",
                    [TRADE_BACKED, ZERO_ACTIVITY_PLACEHOLDER_CLASS, TRADE_BACKED, ZERO_ACTIVITY_PLACEHOLDER_CLASS],
                ).fetchone()
                assert row is not None
                counts.update({"rows": int(row[0]), "trade": int(row[1] or 0), "placeholder": int(row[2] or 0), "symbols": int(row[3]), "unknown_classes": int(row[4] or 0)})
                dup = con.execute(
                    "SELECT count(*) FROM (SELECT provider_symbol, session_date, count(*) AS n "
                    "FROM evidence GROUP BY 1,2 HAVING count(*) > 1)"
                ).fetchone()
                counts["duplicates"] = int(dup[0]) if dup is not None else -1
            finally:
                con.close()

        checks = {
            "source_fingerprint_exact": report.get("source_fingerprint") == global_fp,
            "partition_hashes_exact": hashes_exact and len(partitions) == 6,
            "row_accounting_exact": counts["rows"] == int(quality.get("identity_safe_bar_rows", -1)),
            "classification_accounting_exact": (
                counts["trade"] == int(quality.get("trade_backed_usable_rows", -1))
                and counts["placeholder"] == int(quality.get("zero_activity_placeholder_rows", -1))
                and counts["rows"] == counts["trade"] + counts["placeholder"]
            ),
            "symbol_coverage_exact": counts["symbols"] == int(quality.get("observed_symbols", -1)),
            "duplicate_session_keys_zero": counts["duplicates"] == 0,
            "known_bar_classes_only": counts["unknown_classes"] == 0,
            "canonical_data_untouched": report.get("canonical_data_modified") is False,
        }
        return {
            "contract_version": report.get("contract_version"),
            "source_fingerprint": report.get("source_fingerprint"),
            "retained_unit_manifests": len(manifests),
            "retained_raw_bar_pages": len(page_entries),
            "counts": counts,
            "checks": checks,
            "pass": all(checks.values()),
        }
