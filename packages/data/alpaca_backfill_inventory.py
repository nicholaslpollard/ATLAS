from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import duckdb
import pandas as pd

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_policy import (
    ALPACA_BACKFILL_ADJUSTMENT,
    ALPACA_BACKFILL_ASOF,
    ALPACA_BACKFILL_CONTRACT_VERSION,
    ALPACA_BACKFILL_END,
    ALPACA_BACKFILL_FEED,
    ALPACA_BACKFILL_START,
    ALPACA_BACKFILL_TIMEFRAME,
)
from packages.data.alpaca_backfill_storage import AlpacaRawPayloadStore
from packages.providers.alpaca import AlpacaMarketDataClient


ALPACA_BACKFILL_INVENTORY_CONTRACT_VERSION = (
    "historical-backfill-inventory-v1-active-inactive-massive-corporate-actions-pilot"
)
PILOT_START = "2016-01-04"
PILOT_END = "2016-02-01"
PILOT_TARGET_SYMBOLS = 100
KNOWN_OTC_EXCHANGES = {"OTC"}


@dataclass(frozen=True, slots=True)
class AlpacaBackfillInventoryReport:
    contract_version: str
    parent_contract_version: str
    generated_at_utc: str
    canonical_data_modified: bool
    credential_profile: str
    backfill_start: str
    backfill_end: str
    feed: str
    adjustment: str
    asof: str
    timeframe: str
    source_counts: dict[str, int]
    inventory_rows: int
    sip_candidate_symbols: int
    known_otc_only_excluded: int
    provenance_combination_counts: dict[str, int]
    corporate_action_pages: int
    raw_discovery_payloads: int
    pilot_symbols: int
    pilot_observed_symbols: int
    pilot_bar_rows: int
    pilot_pages: int
    inventory_path: str
    report_path: str


def _clean_symbol(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    symbol = value.strip()
    if not symbol or "," in symbol or any(ch.isspace() for ch in symbol):
        return None
    return symbol


def _asset_records(payload: Any) -> list[dict[str, object]]:
    if not isinstance(payload, list):
        return []
    records: list[dict[str, object]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        symbol = _clean_symbol(item.get("symbol"))
        if symbol is None:
            continue
        records.append(
            {
                "symbol": symbol,
                "exchange": str(item.get("exchange") or "").strip().upper(),
                "asset_id": str(item.get("id") or "").strip() or None,
                "name": str(item.get("name") or "").strip() or None,
                "status": str(item.get("status") or "").strip().lower() or None,
            }
        )
    return records


def _corporate_action_symbols(payload: Any) -> set[str]:
    """Extract literal symbol fields without attempting identity mapping."""
    symbols: set[str] = set()
    symbol_keys = {
        "symbol",
        "old_symbol",
        "new_symbol",
        "initiating_symbol",
        "target_symbol",
        "acquirer_symbol",
    }

    def visit(value: Any, key: str | None = None) -> None:
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                visit(child_value, str(child_key))
            return
        if isinstance(value, list):
            for child in value:
                visit(child, key)
            return
        if key in symbol_keys:
            symbol = _clean_symbol(value)
            if symbol is not None:
                symbols.add(symbol)

    visit(payload)
    return symbols


def _bar_counts(payload: Any) -> dict[str, int]:
    if not isinstance(payload, dict):
        return {}
    bars = payload.get("bars")
    counts: dict[str, int] = {}
    if isinstance(bars, dict):
        for key, values in bars.items():
            symbol = _clean_symbol(key)
            if symbol is not None and isinstance(values, list):
                counts[symbol] = len(values)
    elif isinstance(bars, list):
        for item in bars:
            if not isinstance(item, dict):
                continue
            symbol = _clean_symbol(item.get("S") or item.get("symbol"))
            if symbol is not None:
                counts[symbol] = counts.get(symbol, 0) + 1
    return counts


def _deterministic_sample(symbols: Iterable[str], count: int) -> list[str]:
    unique = sorted(set(symbols))
    ranked = sorted(unique, key=lambda symbol: (hashlib.sha256(symbol.encode("utf-8")).digest(), symbol))
    return ranked[: min(count, len(ranked))]


class AlpacaBackfillInventoryBuilder:
    """Build a broad candidate symbol surface before downloading historical bars.

    Current active/inactive asset state is discovery evidence only. Historical population
    membership is established later only by actually observed raw-SIP bars and identity
    segmentation; no current status is projected backward.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.client = AlpacaMarketDataClient(settings)
        self.raw_store = AlpacaRawPayloadStore(settings)
        root = settings.resolved_path(settings.data.paths.derived) / "historical_backfill" / "alpaca"
        self.inventory_path = root / "inventory" / "candidate_symbols.parquet"
        self.report_path = root / "inventory" / "inventory_report.json"

    def _massive_observed_symbols(self) -> set[str]:
        canonical = self.settings.resolved_path(self.settings.data.paths.canonical)
        glob = (canonical / "stocks" / "1d" / "**" / "*.parquet").as_posix()
        if not (canonical / "stocks" / "1d").exists():
            return set()
        con = duckdb.connect(":memory:")
        try:
            rows = con.execute(
                "SELECT DISTINCT symbol FROM read_parquet(?, hive_partitioning=true) "
                "WHERE symbol IS NOT NULL ORDER BY symbol",
                [glob],
            ).fetchall()
        finally:
            con.close()
        return {symbol for (value,) in rows if (symbol := _clean_symbol(value)) is not None}

    def _persist_inventory(self, rows: list[dict[str, object]]) -> None:
        frame = pd.DataFrame(rows)
        self.inventory_path.parent.mkdir(parents=True, exist_ok=True)
        temp = unique_temp_path(self.inventory_path)
        con = duckdb.connect(":memory:")
        try:
            con.register("inventory_df", frame)
            con.execute(
                "COPY (SELECT * FROM inventory_df ORDER BY symbol) TO ? "
                "(FORMAT PARQUET, COMPRESSION ZSTD)",
                [str(temp)],
            )
        finally:
            con.close()
        replace_with_retry(temp, self.inventory_path)

    @staticmethod
    def _record_provenance(
        rows: dict[str, dict[str, object]],
        symbol: str,
        source: str,
    ) -> dict[str, object]:
        record = rows.setdefault(
            symbol,
            {
                "symbol": symbol,
                "from_active_assets": False,
                "from_inactive_assets": False,
                "from_massive_observed": False,
                "from_corporate_actions": False,
                "asset_exchange": None,
                "active_asset_id": None,
                "inactive_asset_id": None,
                "asset_name": None,
            },
        )
        record[f"from_{source}"] = True
        return record

    def run(self) -> AlpacaBackfillInventoryReport:
        raw_records = []
        active_page = self.client.get_assets(status="active")
        inactive_page = self.client.get_assets(status="inactive")
        raw_records.append(
            self.raw_store.persist(active_page, category="discovery", partition="assets_active")
        )
        raw_records.append(
            self.raw_store.persist(inactive_page, category="discovery", partition="assets_inactive")
        )
        active_assets = _asset_records(active_page.payload)
        inactive_assets = _asset_records(inactive_page.payload)
        massive_symbols = self._massive_observed_symbols()

        ca_symbols: set[str] = set()
        ca_pages = 0
        for index, page in enumerate(
            self.client.corporate_action_pages(
                start=ALPACA_BACKFILL_START.isoformat(),
                end=ALPACA_BACKFILL_END.isoformat(),
            )
        ):
            ca_pages += 1
            ca_symbols.update(_corporate_action_symbols(page.payload))
            raw_records.append(
                self.raw_store.persist(
                    page,
                    category="discovery",
                    partition=f"corporate_actions_2016_2021_page_{index:04d}",
                )
            )

        records: dict[str, dict[str, object]] = {}
        for asset in active_assets:
            symbol = str(asset["symbol"])
            record = self._record_provenance(records, symbol, "active_assets")
            record["asset_exchange"] = asset["exchange"] or record["asset_exchange"]
            record["active_asset_id"] = asset["asset_id"]
            record["asset_name"] = asset["name"] or record["asset_name"]
        for asset in inactive_assets:
            symbol = str(asset["symbol"])
            record = self._record_provenance(records, symbol, "inactive_assets")
            record["asset_exchange"] = asset["exchange"] or record["asset_exchange"]
            record["inactive_asset_id"] = asset["asset_id"]
            record["asset_name"] = asset["name"] or record["asset_name"]
        for symbol in massive_symbols:
            self._record_provenance(records, symbol, "massive_observed")
        for symbol in ca_symbols:
            self._record_provenance(records, symbol, "corporate_actions")

        combination_counts: Counter[str] = Counter()
        known_otc_only_excluded = 0
        sip_candidates: list[str] = []
        inventory_rows: list[dict[str, object]] = []
        for symbol in sorted(records):
            record = records[symbol]
            sources = [
                label
                for label, field in (
                    ("active", "from_active_assets"),
                    ("inactive", "from_inactive_assets"),
                    ("massive", "from_massive_observed"),
                    ("corp_action", "from_corporate_actions"),
                )
                if bool(record[field])
            ]
            combination_counts["+".join(sources)] += 1
            exchange = str(record.get("asset_exchange") or "").upper()
            independent_listed_evidence = bool(
                record["from_massive_observed"] or record["from_corporate_actions"]
            )
            known_otc_only = exchange in KNOWN_OTC_EXCHANGES and not independent_listed_evidence
            sip_candidate = not known_otc_only
            if sip_candidate:
                sip_candidates.append(symbol)
            else:
                known_otc_only_excluded += 1
            inventory_rows.append(
                {
                    **record,
                    "discovery_sources": ",".join(sources),
                    "known_otc_only": known_otc_only,
                    "sip_acquisition_candidate": sip_candidate,
                }
            )

        self._persist_inventory(inventory_rows)

        pilot = _deterministic_sample(sip_candidates, PILOT_TARGET_SYMBOLS)
        pilot_counts: defaultdict[str, int] = defaultdict(int)
        pilot_pages = 0
        for index, page in enumerate(
            self.client.historical_bar_pages(symbols=pilot, start=PILOT_START, end=PILOT_END)
        ):
            pilot_pages += 1
            for symbol, count in _bar_counts(page.payload).items():
                pilot_counts[symbol] += count
            raw_records.append(
                self.raw_store.persist(
                    page,
                    category="inventory_pilot",
                    partition=f"2016_01_page_{index:04d}",
                )
            )

        source_counts = {
            "active_asset_symbols": len({str(item["symbol"]) for item in active_assets}),
            "inactive_asset_symbols": len({str(item["symbol"]) for item in inactive_assets}),
            "massive_observed_symbols": len(massive_symbols),
            "corporate_action_symbols": len(ca_symbols),
        }
        report = AlpacaBackfillInventoryReport(
            contract_version=ALPACA_BACKFILL_INVENTORY_CONTRACT_VERSION,
            parent_contract_version=ALPACA_BACKFILL_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            canonical_data_modified=False,
            credential_profile=self.client.credential_profile_name,
            backfill_start=ALPACA_BACKFILL_START.isoformat(),
            backfill_end=ALPACA_BACKFILL_END.isoformat(),
            feed=ALPACA_BACKFILL_FEED,
            adjustment=ALPACA_BACKFILL_ADJUSTMENT,
            asof=ALPACA_BACKFILL_ASOF,
            timeframe=ALPACA_BACKFILL_TIMEFRAME,
            source_counts=source_counts,
            inventory_rows=len(inventory_rows),
            sip_candidate_symbols=len(sip_candidates),
            known_otc_only_excluded=known_otc_only_excluded,
            provenance_combination_counts=dict(sorted(combination_counts.items())),
            corporate_action_pages=ca_pages,
            raw_discovery_payloads=len(raw_records),
            pilot_symbols=len(pilot),
            pilot_observed_symbols=sum(1 for symbol in pilot if pilot_counts.get(symbol, 0) > 0),
            pilot_bar_rows=sum(pilot_counts.values()),
            pilot_pages=pilot_pages,
            inventory_path=str(self.inventory_path),
            report_path=str(self.report_path),
        )
        atomic_write_text(
            self.report_path,
            json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
        )
        return report
