from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any, Iterable

import duckdb

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.provider_source_qualification import stable_fingerprint
from packages.data.tradier_source_qualification import (
    UniverseSymbolSource,
    latest_universe_symbol_source,
)
from packages.providers.tradier.client import TradierMarketDataClient


CONTRACT = {
    "contract_id": "atlas-tradier-whole-universe-cadence-diagnostic-v1",
    "provider": "tradier",
    "environment": "production",
    "population": "ALPACA_SIP_V2_CURRENT_ACTIVE_TRADABLE_US_EQUITY",
    "cycles": 20,
    "broad_interval_seconds": 30,
    "retry_delay_seconds": 10,
    "max_provider_reads": 40,
    "broad_request": "one POST /v1/markets/quotes for complete resolved population",
    "retry_request": (
        "one POST for first-pass unresolved Phase 7 discovery symbols when the "
        "local Phase 7 universe is available; otherwise unresolved broad-population "
        "symbols. Unresolved means missing, invalid geometry, unknown freshness, "
        "quote age over 30 seconds, or future-timestamp anomaly"
    ),
    "diagnostic_thresholds_only": {
        "quote_age_seconds": [5, 15, 30, 60],
        "trade_age_seconds": [5, 30, 60, 120],
        "spread_bps": [50, 100, 250],
        "average_volume": [50_000, 100_000, 500_000, 1_000_000],
    },
    "cadence_views_seconds": [30, 60, 120, 300],
    "persistence": {
        "raw_responses_gzip": True,
        "per_snapshot_receipt_sha256": True,
        "final_report": True,
    },
    "authority": {
        "provider_reads": True,
        "provider_writes": False,
        "broker_reads": False,
        "broker_writes": False,
        "orders": False,
        "strategy_evidence": False,
        "provider_policy_change": False,
        "current_data_authority": False,
        "paper": False,
        "live": False,
        "promotion": False,
        "confluence": False,
    },
}
CONTRACT_FINGERPRINT = stable_fingerprint(CONTRACT)

CURRENT_ASSET_SNAPSHOT_RELATIVE = Path(
    "data/v2_build/alpaca_sip_v2/canonical/identity/assets_snapshot.parquet"
)


class TradierCadenceDiagnosticError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Population:
    path: Path
    sha256: str
    symbols: tuple[str, ...]
    symbols_fingerprint: str
    phase7: UniverseSymbolSource | None


@dataclass(frozen=True, slots=True)
class RowQuality:
    symbol: str
    returned: bool
    geometry_valid: bool
    quote_age_seconds: float | None
    trade_age_seconds: float | None
    spread_bps: float | None
    average_volume: float | None
    volume: float | None
    bid_timestamp_utc: datetime | None
    ask_timestamp_utc: datetime | None
    trade_timestamp_utc: datetime | None
    future_timestamp: bool

    @property
    def freshness_unresolved(self) -> bool:
        return (
            not self.returned
            or not self.geometry_valid
            or self.quote_age_seconds is None
            or self.quote_age_seconds > 30.0
            or self.future_timestamp
        )

    @property
    def diagnostic_usable_30s_100bps(self) -> bool:
        return (
            self.returned
            and self.geometry_valid
            and self.quote_age_seconds is not None
            and self.quote_age_seconds <= 30.0
            and self.spread_bps is not None
            and self.spread_bps <= 100.0
            and not self.future_timestamp
        )


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _lower_column_map(columns: Iterable[str]) -> dict[str, str]:
    return {str(column).lower(): str(column) for column in columns}


def _require_column(mapping: dict[str, str], *names: str) -> str:
    for name in names:
        if name.lower() in mapping:
            return mapping[name.lower()]
    raise TradierCadenceDiagnosticError(
        "current asset snapshot is missing required column alternatives: "
        + ", ".join(names)
    )


def load_current_population(settings: AtlasSettings) -> Population:
    path = settings.project_root / CURRENT_ASSET_SNAPSHOT_RELATIVE
    if not path.is_file():
        raise TradierCadenceDiagnosticError(
            f"current Alpaca SIP V2 asset snapshot is unavailable: {path}"
        )

    con = duckdb.connect(database=":memory:")
    try:
        frame = con.execute(
            "SELECT * FROM read_parquet(?)",
            [str(path)],
        ).fetch_df()
    finally:
        con.close()
    if frame.empty:
        raise TradierCadenceDiagnosticError("current asset snapshot is empty")

    columns = _lower_column_map(frame.columns)
    symbol_col = _require_column(columns, "symbol", "ticker")
    tradable_col = _require_column(columns, "tradable")

    mask = frame[tradable_col].fillna(False).astype(bool)

    if "status" in columns:
        status_col = columns["status"]
        mask &= frame[status_col].astype(str).str.lower().eq("active")
    elif "active" in columns:
        active_col = columns["active"]
        mask &= frame[active_col].fillna(False).astype(bool)
    else:
        raise TradierCadenceDiagnosticError(
            "current asset snapshot cannot prove active state"
        )

    if "asset_class" in columns:
        class_col = columns["asset_class"]
        mask &= frame[class_col].astype(str).str.lower().eq("us_equity")
    elif "class" in columns:
        class_col = columns["class"]
        mask &= frame[class_col].astype(str).str.lower().eq("us_equity")
    else:
        raise TradierCadenceDiagnosticError(
            "current asset snapshot cannot prove us_equity class"
        )

    symbols = tuple(
        sorted(
            {
                str(value).strip()
                for value in frame.loc[mask, symbol_col].tolist()
                if str(value).strip()
            }
        )
    )
    if not symbols:
        raise TradierCadenceDiagnosticError(
            "current asset snapshot produced no active/tradable US-equity symbols"
        )

    try:
        phase7 = latest_universe_symbol_source(settings)
    except (FileNotFoundError, ValueError):
        phase7 = None

    return Population(
        path=path.resolve(),
        sha256=_sha256_file(path),
        symbols=symbols,
        symbols_fingerprint=stable_fingerprint(symbols),
        phase7=phase7,
    )


def _number(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def provider_epoch_to_utc(value: object) -> datetime | None:
    number = _number(value)
    if number is None or number <= 0:
        return None
    # Tradier currently emits millisecond Unix epochs for quote/trade dates.
    # Keep defensive support for seconds/microseconds while rejecting values
    # too small to be modern market timestamps.
    if number >= 1e15:
        seconds = number / 1_000_000.0
    elif number >= 1e12:
        seconds = number / 1_000.0
    elif number >= 1e9:
        seconds = number
    else:
        return None
    try:
        return datetime.fromtimestamp(seconds, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


def _age_seconds(timestamp: datetime | None, captured_at: datetime) -> tuple[float | None, bool]:
    if timestamp is None:
        return None, False
    delta = (captured_at - timestamp).total_seconds()
    if delta < -2.0:
        return None, True
    return max(0.0, delta), False


def normalize_quality(
    row: dict[str, Any] | None,
    *,
    symbol: str,
    captured_at: datetime,
) -> RowQuality:
    if row is None:
        return RowQuality(
            symbol=symbol,
            returned=False,
            geometry_valid=False,
            quote_age_seconds=None,
            trade_age_seconds=None,
            spread_bps=None,
            average_volume=None,
            volume=None,
            bid_timestamp_utc=None,
            ask_timestamp_utc=None,
            trade_timestamp_utc=None,
            future_timestamp=False,
        )

    bid = _number(row.get("bid"))
    ask = _number(row.get("ask"))
    bid_ts = provider_epoch_to_utc(row.get("bid_date"))
    ask_ts = provider_epoch_to_utc(row.get("ask_date"))
    trade_ts = provider_epoch_to_utc(row.get("trade_date"))
    bid_age, bid_future = _age_seconds(bid_ts, captured_at)
    ask_age, ask_future = _age_seconds(ask_ts, captured_at)
    trade_age, trade_future = _age_seconds(trade_ts, captured_at)

    geometry = (
        bid is not None
        and ask is not None
        and bid > 0.0
        and ask > 0.0
        and ask >= bid
    )
    spread = None
    if geometry:
        mid = (bid + ask) / 2.0
        if mid > 0:
            spread = (ask - bid) / mid * 10_000.0

    quote_age = None
    if bid_age is not None and ask_age is not None:
        quote_age = max(bid_age, ask_age)

    return RowQuality(
        symbol=symbol,
        returned=True,
        geometry_valid=geometry,
        quote_age_seconds=quote_age,
        trade_age_seconds=trade_age,
        spread_bps=spread,
        average_volume=_number(row.get("average_volume")),
        volume=_number(row.get("volume")),
        bid_timestamp_utc=bid_ts,
        ask_timestamp_utc=ask_ts,
        trade_timestamp_utc=trade_ts,
        future_timestamp=bid_future or ask_future or trade_future,
    )


def _percentile(values: Iterable[float], fraction: float) -> float | None:
    ordered = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not ordered:
        return None
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def quality_summary(
    requested: tuple[str, ...],
    rows: tuple[dict[str, Any], ...],
    *,
    captured_at: datetime,
) -> tuple[dict[str, object], dict[str, RowQuality]]:
    by_symbol = {
        str(row.get("symbol") or "").strip(): row
        for row in rows
        if str(row.get("symbol") or "").strip()
    }
    quality = {
        symbol: normalize_quality(
            by_symbol.get(symbol),
            symbol=symbol,
            captured_at=captured_at,
        )
        for symbol in requested
    }

    returned = [item for item in quality.values() if item.returned]
    missing = sorted(symbol for symbol, item in quality.items() if not item.returned)
    unresolved = sorted(
        symbol for symbol, item in quality.items() if item.freshness_unresolved
    )
    usable = [
        item for item in quality.values()
        if item.diagnostic_usable_30s_100bps
    ]
    quote_ages = [
        item.quote_age_seconds
        for item in returned
        if item.quote_age_seconds is not None
    ]
    trade_ages = [
        item.trade_age_seconds
        for item in returned
        if item.trade_age_seconds is not None
    ]
    spreads = [
        item.spread_bps
        for item in returned
        if item.spread_bps is not None
    ]

    def count_quote(limit: float) -> int:
        return sum(
            item.quote_age_seconds is not None
            and item.quote_age_seconds <= limit
            and not item.future_timestamp
            for item in returned
        )

    def count_trade(limit: float) -> int:
        return sum(
            item.trade_age_seconds is not None
            and item.trade_age_seconds <= limit
            and not item.future_timestamp
            for item in returned
        )

    summary: dict[str, object] = {
        "requested": len(requested),
        "returned": len(returned),
        "coverage_fraction": len(returned) / len(requested) if requested else 0.0,
        "missing_count": len(missing),
        "missing_symbols": missing,
        "missing_fingerprint": stable_fingerprint(missing),
        "valid_geometry_count": sum(item.geometry_valid for item in returned),
        "future_timestamp_count": sum(item.future_timestamp for item in returned),
        "unknown_quote_freshness_count": sum(
            item.quote_age_seconds is None for item in returned
        ),
        "freshness_unresolved_count": len(unresolved),
        "freshness_unresolved_symbols": unresolved,
        "freshness_unresolved_fingerprint": stable_fingerprint(unresolved),
        "diagnostic_usable_30s_100bps_count": len(usable),
        "diagnostic_usable_30s_100bps_fraction": (
            len(usable) / len(requested) if requested else 0.0
        ),
        "quote_age_counts": {
            str(limit): count_quote(limit)
            for limit in (5, 15, 30, 60)
        },
        "trade_age_counts": {
            str(limit): count_trade(limit)
            for limit in (5, 30, 60, 120)
        },
        "quote_age_seconds": {
            "median": median(quote_ages) if quote_ages else None,
            "p90": _percentile(quote_ages, 0.90),
            "p99": _percentile(quote_ages, 0.99),
        },
        "trade_age_seconds": {
            "median": median(trade_ages) if trade_ages else None,
            "p90": _percentile(trade_ages, 0.90),
            "p99": _percentile(trade_ages, 0.99),
        },
        "spread_bps": {
            "median": median(spreads) if spreads else None,
            "p90": _percentile(spreads, 0.90),
            "p99": _percentile(spreads, 0.99),
        },
        "average_volume_sensitivity": {
            str(limit): sum(
                item.diagnostic_usable_30s_100bps
                and item.average_volume is not None
                and item.average_volume >= limit
                for item in returned
            )
            for limit in (50_000, 100_000, 500_000, 1_000_000)
        },
    }
    return summary, quality


def _phase7_summary(
    phase7_symbols: tuple[str, ...] | None,
    quality: dict[str, RowQuality],
) -> dict[str, object] | None:
    if not phase7_symbols:
        return None
    selected = [quality[symbol] for symbol in phase7_symbols if symbol in quality]
    if not selected:
        return None
    absent_from_broad = len(phase7_symbols) - len(selected)
    returned = sum(item.returned for item in selected)
    usable = sum(item.diagnostic_usable_30s_100bps for item in selected)
    return {
        "phase7_symbol_count": len(phase7_symbols),
        "requested_symbols_present_in_broad_population": len(selected),
        "absent_from_broad_population": absent_from_broad,
        "returned": returned,
        "coverage_fraction": returned / len(selected),
        "diagnostic_usable_30s_100bps": usable,
        "diagnostic_usable_fraction": usable / len(selected),
    }


def recovery_summary(
    before: dict[str, RowQuality],
    after: dict[str, RowQuality],
    cohort: tuple[str, ...],
) -> dict[str, object]:
    missing_recovered = 0
    freshness_recovered = 0
    newer_quote = 0
    still_unresolved = 0
    for symbol in cohort:
        left = before[symbol]
        right = after.get(symbol, left)
        if not left.returned and right.returned:
            missing_recovered += 1
        if left.freshness_unresolved and not right.freshness_unresolved:
            freshness_recovered += 1
        left_ts = min(
            (ts for ts in (left.bid_timestamp_utc, left.ask_timestamp_utc) if ts),
            default=None,
        )
        right_ts = min(
            (ts for ts in (right.bid_timestamp_utc, right.ask_timestamp_utc) if ts),
            default=None,
        )
        if right_ts is not None and (left_ts is None or right_ts > left_ts):
            newer_quote += 1
        if right.freshness_unresolved:
            still_unresolved += 1
    return {
        "cohort_count": len(cohort),
        "missing_recovered": missing_recovered,
        "freshness_recovered": freshness_recovered,
        "newer_quote_timestamp": newer_quote,
        "still_unresolved": still_unresolved,
    }


def _persist_raw(
    root: Path,
    *,
    label: str,
    metadata: dict[str, object],
    rows: tuple[dict[str, Any], ...],
) -> tuple[Path, str]:
    raw_dir = root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    envelope = {
        "metadata": metadata,
        "rows": rows,
    }
    data = (
        json.dumps(
            envelope,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        + "\n"
    ).encode("utf-8")
    compressed = gzip.compress(data, compresslevel=6, mtime=0)
    path = raw_dir / f"{label}.json.gz"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(compressed)
    os.replace(tmp, path)
    digest = _sha256_file(path)
    receipt = {
        "label": label,
        "path": str(path.resolve()),
        "sha256": digest,
        "compressed_bytes": path.stat().st_size,
        "row_count": len(rows),
        "metadata_fingerprint": stable_fingerprint(metadata),
    }
    atomic_write_text(
        raw_dir / f"{label}.receipt.json",
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
    )
    return path, digest


def _rate_limit(headers: dict[str, str]) -> dict[str, str | None]:
    lowered = {str(key).lower(): str(value) for key, value in headers.items()}
    return {
        "allowed": lowered.get("x-ratelimit-allowed"),
        "used": lowered.get("x-ratelimit-used"),
        "available": lowered.get("x-ratelimit-available"),
        "expiry": lowered.get("x-ratelimit-expiry"),
    }


def _snapshot_record(
    *,
    kind: str,
    cycle: int,
    requested: tuple[str, ...],
    batch: Any,
    captured_at: datetime,
    root: Path,
    phase7_symbols: tuple[str, ...] | None,
) -> tuple[dict[str, object], dict[str, RowQuality]]:
    summary, quality = quality_summary(
        requested,
        batch.returned_rows,
        captured_at=captured_at,
    )
    label = f"cycle-{cycle:02d}-{kind}"
    metadata = {
        "contract_fingerprint": CONTRACT_FINGERPRINT,
        "kind": kind,
        "cycle": cycle,
        "captured_at_utc": captured_at.isoformat(),
        "requested_count": len(requested),
        "requested_fingerprint": stable_fingerprint(requested),
        "provider_elapsed_seconds": batch.response.elapsed_seconds,
        "response_bytes": batch.response.response_bytes,
        "rate_limit": _rate_limit(batch.response.response_headers),
    }
    raw_path, raw_sha = _persist_raw(
        root,
        label=label,
        metadata=metadata,
        rows=batch.returned_rows,
    )
    return (
        {
            **metadata,
            **summary,
            "raw_path": str(raw_path.resolve()),
            "raw_sha256": raw_sha,
            "phase7_subset": _phase7_summary(phase7_symbols, quality),
        },
        quality,
    )


def _adjacent_cadence_views(
    broad_records: list[dict[str, object]],
    broad_quality: list[dict[str, RowQuality]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for seconds in CONTRACT["cadence_views_seconds"]:
        step = int(seconds) // int(CONTRACT["broad_interval_seconds"])
        if step < 1 or len(broad_quality) <= step:
            continue
        comparisons = 0
        quote_advanced_total = 0
        comparable_total = 0
        missing_recovered_total = 0
        missing_before_total = 0
        for left_index in range(0, len(broad_quality) - step):
            right_index = left_index + step
            left = broad_quality[left_index]
            right = broad_quality[right_index]
            comparisons += 1
            for symbol, before in left.items():
                after = right.get(symbol)
                if after is None:
                    continue
                before_ts = min(
                    (ts for ts in (before.bid_timestamp_utc, before.ask_timestamp_utc) if ts),
                    default=None,
                )
                after_ts = min(
                    (ts for ts in (after.bid_timestamp_utc, after.ask_timestamp_utc) if ts),
                    default=None,
                )
                if before_ts is not None and after_ts is not None:
                    comparable_total += 1
                    if after_ts > before_ts:
                        quote_advanced_total += 1
                if not before.returned:
                    missing_before_total += 1
                    if after.returned:
                        missing_recovered_total += 1
        result[str(seconds)] = {
            "comparison_pairs": comparisons,
            "quote_timestamp_advanced_fraction": (
                quote_advanced_total / comparable_total
                if comparable_total
                else None
            ),
            "missing_recovered_by_later_broad_fraction": (
                missing_recovered_total / missing_before_total
                if missing_before_total
                else None
            ),
            "comparable_symbol_pairs": comparable_total,
            "missing_symbol_pairs": missing_before_total,
        }
    return result


def run_tradier_whole_universe_cadence_v1(
    settings: AtlasSettings,
    *,
    sleeper=time.sleep,
    monotonic=time.monotonic,
    client: TradierMarketDataClient | None = None,
) -> dict[str, object]:
    population = load_current_population(settings)
    market_client = client or TradierMarketDataClient(settings)
    phase7_symbols = population.phase7.symbols if population.phase7 else None
    broad_symbol_set = set(population.symbols)
    retry_eligible = (
        set(phase7_symbols).intersection(broad_symbol_set)
        if phase7_symbols
        else broad_symbol_set
    )
    retry_population_label = (
        "PHASE7_DISCOVERY_ELIGIBLE_INTERSECTION"
        if phase7_symbols
        else "BROAD_CURRENT_ASSET_POPULATION"
    )

    generated = datetime.now(UTC)
    run_id = generated.strftime("%Y%m%dT%H%M%SZ")
    root = (
        settings.project_root
        / "data"
        / "research"
        / "provider_qualification"
        / "tradier"
        / "whole_universe_cadence_v1"
        / run_id
    )
    root.mkdir(parents=True, exist_ok=True)

    broad_records: list[dict[str, object]] = []
    retry_records: list[dict[str, object]] = []
    broad_quality: list[dict[str, RowQuality]] = []
    provider_reads = 0
    started_mono = monotonic()
    terminal_error: str | None = None

    for cycle in range(1, int(CONTRACT["cycles"]) + 1):
        target = started_mono + (cycle - 1) * float(CONTRACT["broad_interval_seconds"])
        wait = target - monotonic()
        if wait > 0:
            sleeper(wait)

        print(
            f"  cycle {cycle:02d}/{CONTRACT['cycles']} BROAD "
            f"requesting {len(population.symbols):,} symbols...",
            flush=True,
        )
        try:
            broad_batch = market_client.post_quotes(population.symbols)
        except Exception as exc:
            terminal_error = f"{type(exc).__name__}: {exc}"
            print(f"    STOP: broad request failed: {terminal_error}", flush=True)
            break
        provider_reads += 1
        captured = datetime.now(UTC)
        record, quality = _snapshot_record(
            kind="broad",
            cycle=cycle,
            requested=population.symbols,
            batch=broad_batch,
            captured_at=captured,
            root=root,
            phase7_symbols=phase7_symbols,
        )
        broad_records.append(record)
        broad_quality.append(quality)

        q30 = int(dict(record["quote_age_counts"])["30"])
        usable = int(record["diagnostic_usable_30s_100bps_count"])
        rate = dict(record["rate_limit"])
        print(
            "    broad: "
            f"returned={int(record['returned']):,}/{int(record['requested']):,} "
            f"coverage={float(record['coverage_fraction']):.3%} "
            f"quote<=30s={q30:,} "
            f"usable30/100={usable:,} "
            f"missing={int(record['missing_count']):,} "
            f"unresolved={int(record['freshness_unresolved_count']):,} "
            f"latency={float(record['provider_elapsed_seconds']):.3f}s "
            f"rate_avail={rate.get('available')}",
            flush=True,
        )

        cohort = tuple(
            symbol
            for symbol in record["freshness_unresolved_symbols"]
            if symbol in retry_eligible
        )
        record["retry_population"] = retry_population_label
        record["retry_eligible_symbol_count"] = len(retry_eligible)
        if not cohort:
            print("    retry: skipped; no unresolved symbols", flush=True)
            continue

        retry_target = target + float(CONTRACT["retry_delay_seconds"])
        retry_wait = retry_target - monotonic()
        if retry_wait > 0:
            sleeper(retry_wait)

        print(
            f"    retry +{CONTRACT['retry_delay_seconds']}s "
            f"[{retry_population_label}]: "
            f"requesting {len(cohort):,} unresolved symbols...",
            flush=True,
        )
        try:
            retry_batch = market_client.post_quotes(cohort)
        except Exception as exc:
            terminal_error = f"{type(exc).__name__}: {exc}"
            print(f"    STOP: retry request failed: {terminal_error}", flush=True)
            break
        provider_reads += 1
        retry_captured = datetime.now(UTC)
        retry_record, retry_quality = _snapshot_record(
            kind="retry",
            cycle=cycle,
            requested=cohort,
            batch=retry_batch,
            captured_at=retry_captured,
            root=root,
            phase7_symbols=None,
        )
        recovery = recovery_summary(quality, retry_quality, cohort)
        retry_record["recovery"] = recovery
        retry_records.append(retry_record)
        print(
            "    retry: "
            f"returned={int(retry_record['returned']):,}/{len(cohort):,} "
            f"missing_recovered={int(recovery['missing_recovered']):,} "
            f"freshness_recovered={int(recovery['freshness_recovered']):,} "
            f"newer_quote={int(recovery['newer_quote_timestamp']):,} "
            f"still_unresolved={int(recovery['still_unresolved']):,}",
            flush=True,
        )

        if provider_reads >= int(CONTRACT["max_provider_reads"]):
            break

    persistent_missing: set[str] = set()
    missing_union: set[str] = set()
    if broad_records:
        missing_sets = [set(item["missing_symbols"]) for item in broad_records]
        persistent_missing = set.intersection(*missing_sets)
        missing_union = set.union(*missing_sets)

    report: dict[str, object] = {
        "status": (
            "DIAGNOSTIC_COMPLETE"
            if len(broad_records) == int(CONTRACT["cycles"]) and terminal_error is None
            else "DIAGNOSTIC_COMPLETE_WITH_LIMITATIONS"
            if broad_records
            else "FAIL"
        ),
        "contract": CONTRACT["contract_id"],
        "contract_fingerprint": CONTRACT_FINGERPRINT,
        "run_id": run_id,
        "generated_at_utc": generated.isoformat(),
        "population": {
            "path": str(population.path),
            "sha256": population.sha256,
            "symbol_count": len(population.symbols),
            "symbols_fingerprint": population.symbols_fingerprint,
            "phase7_available": population.phase7 is not None,
            "phase7_as_of": (
                population.phase7.as_of_date.isoformat()
                if population.phase7
                else None
            ),
            "phase7_symbol_count": (
                len(population.phase7.symbols)
                if population.phase7
                else None
            ),
            "phase7_sha256": (
                population.phase7.sha256
                if population.phase7
                else None
            ),
            "retry_population": retry_population_label,
            "retry_eligible_symbol_count": len(retry_eligible),
        },
        "provider_reads": provider_reads,
        "broad_cycles_completed": len(broad_records),
        "retry_cycles_completed": len(retry_records),
        "wall_seconds": max(0.0, monotonic() - started_mono),
        "terminal_error": terminal_error,
        "persistent_missing": {
            "count": len(persistent_missing),
            "fingerprint": stable_fingerprint(sorted(persistent_missing)),
            "symbols": sorted(persistent_missing),
        },
        "ever_missing": {
            "count": len(missing_union),
            "fingerprint": stable_fingerprint(sorted(missing_union)),
            "symbols": sorted(missing_union),
        },
        "cadence_views": _adjacent_cadence_views(broad_records, broad_quality),
        "broad": broad_records,
        "retries": retry_records,
        "authority": CONTRACT["authority"],
        "interpretation": {
            "diagnostic_thresholds_are_not_production_policy": True,
            "cadence_not_frozen_by_this_run": True,
            "provider_policy_unchanged": True,
            "no_trading_authority_created": True,
        },
    }
    report["evidence_fingerprint"] = stable_fingerprint(report)
    report_path = root / "report.json"
    atomic_write_text(
        report_path,
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
    )
    report["report_path"] = str(report_path.resolve())
    return report
