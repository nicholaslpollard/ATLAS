from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

import duckdb
import pandas as pd

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_inventory import ALPACA_BACKFILL_INVENTORY_CONTRACT_VERSION
from packages.data.alpaca_backfill_policy import (
    ALPACA_BACKFILL_ADJUSTMENT,
    ALPACA_BACKFILL_ASOF,
    ALPACA_BACKFILL_CONTRACT_VERSION,
    ALPACA_BACKFILL_END,
    ALPACA_BACKFILL_FEED,
    ALPACA_BACKFILL_PAGE_LIMIT,
    ALPACA_BACKFILL_START,
    ALPACA_BACKFILL_SYMBOL_BATCH_SIZE,
    ALPACA_BACKFILL_TIMEFRAME,
)
from packages.data.alpaca_backfill_storage import AlpacaRawPayloadStore
from packages.providers.alpaca import AlpacaMarketDataClient


ALPACA_BACKFILL_ACQUISITION_CONTRACT_VERSION = (
    "historical-backfill-acquisition-v1-year-batch-resumable-raw-sip"
)
ALPACA_BACKFILL_REQUESTS_PER_MINUTE = 180
UNIT_STATUS_COMPLETE = "COMPLETE"


@dataclass(frozen=True, slots=True)
class AcquisitionUnit:
    year: int
    batch_index: int
    start: str
    end: str
    symbols: tuple[str, ...]
    inventory_fingerprint: str
    unit_id: str


@dataclass(frozen=True, slots=True)
class AlpacaBackfillAcquisitionReport:
    contract_version: str
    parent_contract_version: str
    inventory_contract_version: str
    generated_at_utc: str
    canonical_data_modified: bool
    credential_profile: str
    backfill_start: str
    backfill_end: str
    feed: str
    adjustment: str
    asof: str
    timeframe: str
    page_limit: int
    symbol_batch_size: int
    requests_per_minute: int
    inventory_fingerprint: str
    candidate_symbols: int
    year_partitions: int
    planned_units: int
    completed_units: int
    missing_units: int
    complete: bool
    raw_payload_pages: int
    bar_rows: int
    observed_symbols: int
    zero_bar_symbols: int
    executed_units_this_run: int
    skipped_completed_units_this_run: int
    inventory_path: str
    observed_summary_path: str
    unit_manifest_root: str
    report_path: str


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


def _year_windows(start: date, end: date) -> list[tuple[int, date, date]]:
    windows: list[tuple[int, date, date]] = []
    for year in range(start.year, end.year + 1):
        window_start = max(start, date(year, 1, 1))
        window_end = min(end, date(year, 12, 31))
        if window_start <= window_end:
            windows.append((year, window_start, window_end))
    return windows


def _inventory_fingerprint(symbols: Iterable[str]) -> str:
    payload = "\n".join(symbols).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _unit_id(
    *,
    year: int,
    batch_index: int,
    start: str,
    end: str,
    symbols: tuple[str, ...],
    inventory_fingerprint: str,
) -> str:
    payload = json.dumps(
        {
            "contract": ALPACA_BACKFILL_ACQUISITION_CONTRACT_VERSION,
            "inventory_fingerprint": inventory_fingerprint,
            "year": year,
            "batch_index": batch_index,
            "start": start,
            "end": end,
            "symbols": list(symbols),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _bar_stats(payload: Any) -> dict[str, dict[str, object]]:
    if not isinstance(payload, dict):
        return {}
    bars = payload.get("bars")
    if not isinstance(bars, dict):
        return {}
    stats: dict[str, dict[str, object]] = {}
    for raw_symbol, values in bars.items():
        symbol = _clean_symbol(raw_symbol)
        if symbol is None or not isinstance(values, list):
            continue
        timestamps = [
            str(item.get("t"))
            for item in values
            if isinstance(item, dict) and item.get("t") is not None
        ]
        stats[symbol] = {
            "bar_rows": len(values),
            "first_timestamp": min(timestamps) if timestamps else None,
            "last_timestamp": max(timestamps) if timestamps else None,
        }
    return stats


def _merge_stats(
    target: dict[str, dict[str, object]], source: dict[str, dict[str, object]]
) -> None:
    for symbol, incoming in source.items():
        current = target.setdefault(
            symbol,
            {"bar_rows": 0, "first_timestamp": None, "last_timestamp": None},
        )
        current["bar_rows"] = int(current["bar_rows"]) + int(incoming.get("bar_rows", 0))
        incoming_first = incoming.get("first_timestamp")
        incoming_last = incoming.get("last_timestamp")
        current_first = current.get("first_timestamp")
        current_last = current.get("last_timestamp")
        if incoming_first is not None and (current_first is None or str(incoming_first) < str(current_first)):
            current["first_timestamp"] = str(incoming_first)
        if incoming_last is not None and (current_last is None or str(incoming_last) > str(current_last)):
            current["last_timestamp"] = str(incoming_last)


class AlpacaBackfillAcquirer:
    """Acquire immutable raw SIP daily bars using deterministic year/batch units.

    Unit manifests are the restart boundary. A manifest is reusable only when its
    deterministic unit id, inventory fingerprint, source semantics, and raw payload files
    still match. Production canonical history is never written by this class.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.client = AlpacaMarketDataClient(settings)
        self.raw_store = AlpacaRawPayloadStore(settings)
        root = settings.resolved_path(settings.data.paths.derived) / "historical_backfill" / "alpaca"
        self.inventory_path = root / "inventory" / "candidate_symbols.parquet"
        self.inventory_report_path = root / "inventory" / "inventory_report.json"
        self.acquisition_root = root / "acquisition"
        self.unit_manifest_root = self.acquisition_root / "units"
        self.observed_summary_path = self.acquisition_root / "observed_symbols.parquet"
        self.report_path = self.acquisition_root / "acquisition_report.json"

    def _load_candidates(self) -> list[str]:
        if not self.inventory_path.is_file() or not self.inventory_report_path.is_file():
            raise RuntimeError("Gate 2 inventory artifacts are required before Gate 3 acquisition")
        inventory_report = json.loads(self.inventory_report_path.read_text(encoding="utf-8"))
        if inventory_report.get("contract_version") != ALPACA_BACKFILL_INVENTORY_CONTRACT_VERSION:
            raise RuntimeError("Gate 2 inventory contract does not match the locked acquisition parent")
        con = duckdb.connect(":memory:")
        try:
            rows = con.execute(
                "SELECT symbol FROM read_parquet(?) "
                "WHERE sip_acquisition_candidate = TRUE ORDER BY symbol",
                [str(self.inventory_path)],
            ).fetchall()
        finally:
            con.close()
        symbols = [symbol for (value,) in rows if (symbol := _clean_symbol(value)) is not None]
        expected = int(inventory_report.get("sip_candidate_symbols", 0))
        if len(symbols) != expected:
            raise RuntimeError(
                f"Gate 2 inventory candidate count mismatch: report={expected} parquet={len(symbols)}"
            )
        return symbols

    def build_plan(self) -> tuple[list[str], str, list[AcquisitionUnit]]:
        symbols = self._load_candidates()
        fingerprint = _inventory_fingerprint(symbols)
        batches = list(_chunks(symbols, ALPACA_BACKFILL_SYMBOL_BATCH_SIZE))
        units: list[AcquisitionUnit] = []
        for year, window_start, window_end in _year_windows(ALPACA_BACKFILL_START, ALPACA_BACKFILL_END):
            for batch_index, batch in enumerate(batches):
                start = window_start.isoformat()
                end = window_end.isoformat()
                units.append(
                    AcquisitionUnit(
                        year=year,
                        batch_index=batch_index,
                        start=start,
                        end=end,
                        symbols=batch,
                        inventory_fingerprint=fingerprint,
                        unit_id=_unit_id(
                            year=year,
                            batch_index=batch_index,
                            start=start,
                            end=end,
                            symbols=batch,
                            inventory_fingerprint=fingerprint,
                        ),
                    )
                )
        return symbols, fingerprint, units

    def _manifest_path(self, unit: AcquisitionUnit) -> Path:
        return self.unit_manifest_root / str(unit.year) / f"batch_{unit.batch_index:04d}.json"

    def _load_completed_manifest(self, unit: AcquisitionUnit) -> dict[str, Any] | None:
        path = self._manifest_path(unit)
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        locked = (
            payload.get("contract_version") == ALPACA_BACKFILL_ACQUISITION_CONTRACT_VERSION
            and payload.get("parent_contract_version") == ALPACA_BACKFILL_CONTRACT_VERSION
            and payload.get("unit_id") == unit.unit_id
            and payload.get("inventory_fingerprint") == unit.inventory_fingerprint
            and payload.get("status") == UNIT_STATUS_COMPLETE
            and payload.get("feed") == ALPACA_BACKFILL_FEED
            and payload.get("adjustment") == ALPACA_BACKFILL_ADJUSTMENT
            and payload.get("asof") == ALPACA_BACKFILL_ASOF
            and payload.get("timeframe") == ALPACA_BACKFILL_TIMEFRAME
        )
        if not locked:
            raise RuntimeError(f"stale or incompatible acquisition unit manifest: {path}")
        for record in payload.get("raw_pages") or []:
            raw_path = Path(str(record.get("payload_path", "")))
            metadata_path = Path(str(record.get("metadata_path", "")))
            if not raw_path.is_file() or not metadata_path.is_file():
                raise RuntimeError(f"acquisition unit references missing raw payload evidence: {path}")
        return payload

    def _acquire_unit(self, unit: AcquisitionUnit) -> dict[str, Any]:
        raw_pages: list[dict[str, object]] = []
        symbol_stats: dict[str, dict[str, object]] = {}
        page_count = 0
        for page_index, page in enumerate(
            self.client.historical_bar_pages(
                symbols=list(unit.symbols),
                start=unit.start,
                end=unit.end,
            )
        ):
            page_count += 1
            _merge_stats(symbol_stats, _bar_stats(page.payload))
            raw_record = self.raw_store.persist(
                page,
                category="bars",
                partition=f"{unit.year}_batch_{unit.batch_index:04d}_page_{page_index:04d}",
            )
            raw_pages.append(
                {
                    "page_index": page_index,
                    "sha256": raw_record.sha256,
                    "payload_path": raw_record.payload_path,
                    "metadata_path": raw_record.metadata_path,
                    "page_token_used": raw_record.page_token_used,
                    "next_page_token": raw_record.next_page_token,
                    "uncompressed_bytes": raw_record.uncompressed_bytes,
                    "compressed_bytes": raw_record.compressed_bytes,
                }
            )

        manifest = {
            "contract_version": ALPACA_BACKFILL_ACQUISITION_CONTRACT_VERSION,
            "parent_contract_version": ALPACA_BACKFILL_CONTRACT_VERSION,
            "inventory_contract_version": ALPACA_BACKFILL_INVENTORY_CONTRACT_VERSION,
            "unit_id": unit.unit_id,
            "inventory_fingerprint": unit.inventory_fingerprint,
            "status": UNIT_STATUS_COMPLETE,
            "canonical_data_modified": False,
            "year": unit.year,
            "batch_index": unit.batch_index,
            "start": unit.start,
            "end": unit.end,
            "symbols": list(unit.symbols),
            "symbols_sha256": hashlib.sha256("\n".join(unit.symbols).encode("utf-8")).hexdigest(),
            "symbol_count": len(unit.symbols),
            "feed": ALPACA_BACKFILL_FEED,
            "adjustment": ALPACA_BACKFILL_ADJUSTMENT,
            "asof": ALPACA_BACKFILL_ASOF,
            "timeframe": ALPACA_BACKFILL_TIMEFRAME,
            "page_limit": ALPACA_BACKFILL_PAGE_LIMIT,
            "page_count": page_count,
            "bar_rows": sum(int(item["bar_rows"]) for item in symbol_stats.values()),
            "observed_symbol_count": sum(
                1 for item in symbol_stats.values() if int(item["bar_rows"]) > 0
            ),
            "symbol_stats": symbol_stats,
            "raw_pages": raw_pages,
            "completed_at_utc": datetime.now(UTC).isoformat(),
        }
        path = self._manifest_path(unit)
        atomic_write_text(path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        return manifest

    def _persist_observed_summary(
        self,
        symbols: list[str],
        units: list[AcquisitionUnit],
    ) -> tuple[int, int]:
        aggregate: dict[str, dict[str, object]] = {
            symbol: {
                "symbol": symbol,
                "bar_rows": 0,
                "first_timestamp": None,
                "last_timestamp": None,
                "years_observed": set(),
                "units_observed": 0,
            }
            for symbol in symbols
        }
        for unit in units:
            payload = self._load_completed_manifest(unit)
            if payload is None:
                continue
            for symbol, stats in (payload.get("symbol_stats") or {}).items():
                if symbol not in aggregate:
                    raise RuntimeError(f"unit manifest contains symbol outside locked inventory: {symbol}")
                rows = int(stats.get("bar_rows", 0))
                if rows <= 0:
                    continue
                item = aggregate[symbol]
                item["bar_rows"] = int(item["bar_rows"]) + rows
                item["units_observed"] = int(item["units_observed"]) + 1
                cast_years = item["years_observed"]
                assert isinstance(cast_years, set)
                cast_years.add(unit.year)
                first = stats.get("first_timestamp")
                last = stats.get("last_timestamp")
                if first is not None and (
                    item["first_timestamp"] is None or str(first) < str(item["first_timestamp"])
                ):
                    item["first_timestamp"] = str(first)
                if last is not None and (
                    item["last_timestamp"] is None or str(last) > str(item["last_timestamp"])
                ):
                    item["last_timestamp"] = str(last)

        rows: list[dict[str, object]] = []
        for symbol in symbols:
            item = aggregate[symbol]
            years = item.pop("years_observed")
            assert isinstance(years, set)
            rows.append(
                {
                    **item,
                    "observed": int(item["bar_rows"]) > 0,
                    "years_observed": ",".join(str(value) for value in sorted(years)),
                    "year_count": len(years),
                }
            )

        frame = pd.DataFrame(rows)
        self.observed_summary_path.parent.mkdir(parents=True, exist_ok=True)
        temp = unique_temp_path(self.observed_summary_path)
        con = duckdb.connect(":memory:")
        try:
            con.register("observed_df", frame)
            con.execute(
                "COPY (SELECT * FROM observed_df ORDER BY symbol) TO ? "
                "(FORMAT PARQUET, COMPRESSION ZSTD)",
                [str(temp)],
            )
        finally:
            con.close()
        replace_with_retry(temp, self.observed_summary_path)
        observed = sum(1 for row in rows if bool(row["observed"]))
        bar_rows = sum(int(row["bar_rows"]) for row in rows)
        return observed, bar_rows

    def run(
        self,
        *,
        year: int | None = None,
        max_units: int | None = None,
        progress: Callable[[int, int, AcquisitionUnit, dict[str, Any], bool], None] | None = None,
    ) -> AlpacaBackfillAcquisitionReport:
        if self.settings.alpaca.market_data.requests_per_minute != ALPACA_BACKFILL_REQUESTS_PER_MINUTE:
            raise RuntimeError(
                "Alpaca historical request-rate setting differs from the locked Gate 3 safety policy"
            )
        symbols, fingerprint, units = self.build_plan()
        target_units = [unit for unit in units if year is None or unit.year == year]
        if year is not None and year not in {unit.year for unit in units}:
            raise ValueError(f"year {year} is outside the locked backfill range")
        executed = 0
        skipped = 0
        selected_seen = 0
        for unit in target_units:
            existing = self._load_completed_manifest(unit)
            if existing is not None:
                skipped += 1
                selected_seen += 1
                if progress is not None:
                    progress(selected_seen, len(target_units), unit, existing, True)
                continue
            if max_units is not None and executed >= max_units:
                break
            payload = self._acquire_unit(unit)
            executed += 1
            selected_seen += 1
            if progress is not None:
                progress(selected_seen, len(target_units), unit, payload, False)

        completed_manifests: list[dict[str, Any]] = []
        missing = 0
        for unit in units:
            payload = self._load_completed_manifest(unit)
            if payload is None:
                missing += 1
            else:
                completed_manifests.append(payload)

        observed_symbols, bar_rows = self._persist_observed_summary(symbols, units)
        raw_pages = sum(int(item.get("page_count", 0)) for item in completed_manifests)
        report = AlpacaBackfillAcquisitionReport(
            contract_version=ALPACA_BACKFILL_ACQUISITION_CONTRACT_VERSION,
            parent_contract_version=ALPACA_BACKFILL_CONTRACT_VERSION,
            inventory_contract_version=ALPACA_BACKFILL_INVENTORY_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            canonical_data_modified=False,
            credential_profile=self.client.credential_profile_name,
            backfill_start=ALPACA_BACKFILL_START.isoformat(),
            backfill_end=ALPACA_BACKFILL_END.isoformat(),
            feed=ALPACA_BACKFILL_FEED,
            adjustment=ALPACA_BACKFILL_ADJUSTMENT,
            asof=ALPACA_BACKFILL_ASOF,
            timeframe=ALPACA_BACKFILL_TIMEFRAME,
            page_limit=ALPACA_BACKFILL_PAGE_LIMIT,
            symbol_batch_size=ALPACA_BACKFILL_SYMBOL_BATCH_SIZE,
            requests_per_minute=ALPACA_BACKFILL_REQUESTS_PER_MINUTE,
            inventory_fingerprint=fingerprint,
            candidate_symbols=len(symbols),
            year_partitions=len(_year_windows(ALPACA_BACKFILL_START, ALPACA_BACKFILL_END)),
            planned_units=len(units),
            completed_units=len(completed_manifests),
            missing_units=missing,
            complete=missing == 0,
            raw_payload_pages=raw_pages,
            bar_rows=bar_rows,
            observed_symbols=observed_symbols,
            zero_bar_symbols=len(symbols) - observed_symbols,
            executed_units_this_run=executed,
            skipped_completed_units_this_run=skipped,
            inventory_path=str(self.inventory_path),
            observed_summary_path=str(self.observed_summary_path),
            unit_manifest_root=str(self.unit_manifest_root),
            report_path=str(self.report_path),
        )
        atomic_write_text(
            self.report_path,
            json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
        )
        return report
