from __future__ import annotations

"""Verify the whole frozen 2022 native OPEN cohort once for bulk source freeze."""

import math
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Callable

from packages.core.settings import AtlasSettings
from packages.data import marketdata_additive_2022_shards_v1 as shards

FROZEN_CENSUS = "dabca20038131947b5ee4cb586e7fe6c1fa9e376d4666c01967f30e88866410c"
FIRST_NEW = 26
LAST = 70


def batched_native_reader(
    settings: AtlasSettings,
    load_once: Callable[..., Any],
    prior: tuple[dict[str, Any], set[str], set[tuple[str, str, str]]],
    *,
    duckdb_threads: int = 4,
    native_reader: Callable[..., Any] = shards.exporter._read_entry_opens,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> Callable[..., Any]:
    """Source-only. Verify original native units once, hand shards exact subsets.

    Read the FULL 26..70 cohort whenever any shard is unbound, so a partial
    restart cannot silently change source metadata based on which shards
    happened to finish before the previous stop. Fully bound resume skips it.
    """
    if all(shards._binding_path(settings, i).is_file() for i in range(FIRST_NEW, LAST+1)):
        if progress:
            progress({"stage": "NATIVE_ALL_ALREADY_BOUND", "shards": LAST-FIRST_NEW+1})
        return native_reader
    opportunities, source = load_once(
        settings.project_root, start_session=date(shards.YEAR, 1, 1),
        end_session=date(shards.YEAR, 12, 31), duckdb_threads=duckdb_threads,
    )
    if not isinstance(source, dict) or not source.get("source_integrity_fingerprint"):
        raise shards.CandidateChainCacheError("accepted native replay integrity absent")
    eligible = [
        item for item in opportunities
        if item.signal_session.year == shards.YEAR and item.native_timeframe == "1d"
        and item.direction == "LONG"
        and item.entry_utc.astimezone(shards.EASTERN).year == shards.YEAR
        and isinstance(item.ticker, str)
        and shards.TICKER_PATTERN.fullmatch(item.ticker)
    ]
    if not eligible or len({item.opportunity_id for item in eligible}) != len(eligible):
        raise shards.CandidateChainCacheError("bulk daily LONG source empty/duplicate")
    grouped: dict[tuple[str,str,str],list[Any]] = defaultdict(list)
    for item in eligible:
        if item.opportunity_id in prior[1]:
            continue
        try:
            key = shards._key(item)
        except shards.exporter.CandidateStockExportError as exc:
            if str(exc) != "no bounded exchange monthly expiry is available":
                raise
            continue
        if key not in prior[2]:
            grouped[key].append(item)
    keys = sorted(grouped, key=lambda key: (
        shards._fingerprint({"salt": shards.SALT, "key": key}), key,
    ))
    if (len(keys) != 2812 or math.ceil(len(keys)/shards.KEYS_PER_SHARD) != LAST+1
            or shards._fingerprint(keys) != FROZEN_CENSUS):
        raise shards.CandidateChainCacheError("original 2022 physical source census changed")
    keys = keys[FIRST_NEW*shards.KEYS_PER_SHARD:]
    representatives = [min(grouped[key], key=lambda x: x.opportunity_id) for key in keys]
    if len({x.opportunity_id for x in representatives}) != len(representatives):
        raise shards.CandidateChainCacheError("native representative opportunity duplicated")
    if progress:
        progress({"stage": "BULK_NATIVE_RAW_PREFLIGHT", "new_shards": LAST-FIRST_NEW+1,
                  "unique_raw_entry_opens": len(representatives), "provider_reads": 0})

    def native_progress(stage: str, details: dict[str, Any]) -> None:
        if (progress and (stage != "NATIVE_RAW_UNIT_VERIFIED"
                          or details.get("verified_units", 0) % 10 == 0
                          or details.get("verified_units") == details.get("total_units"))):
            progress({"stage": "BULK_NATIVE_RAW_PROGRESS", "native_stage": stage, **details})

    opens, daily = native_reader(
        settings.project_root, representatives, progress=native_progress,
    )
    if (set(opens) != {x.opportunity_id for x in representatives}
            or daily.get("protected_master_return_rows_read") != 0
            or not daily.get("source_fingerprint") or not daily.get("native_raw_source")
            or not daily.get("manifest_sha256")):
        raise shards.CandidateChainCacheError("bulk native OPEN provenance or coverage changed")
    if progress:
        progress({"stage": "BULK_NATIVE_RAW_VERIFIED_ONCE", "verified_opens": len(opens),
                  "replay_source_integrity": source["source_integrity_fingerprint"],
                  "protected_master_return_rows_read": 0, "provider_reads": 0})

    def read_subset(project_root: Path, selected: Any) -> tuple[dict[str,float],dict[str,Any]]:
        if Path(project_root).resolve() != settings.project_root.resolve():
            raise shards.CandidateChainCacheError("bulk native project root changed")
        ids = [x.opportunity_id for x in selected]
        if len(ids) != len(set(ids)) or not set(ids).issubset(opens):
            raise shards.CandidateChainCacheError("bulk native subset contains unverified source")
        return {identity: opens[identity] for identity in ids}, daily
    return read_subset
