from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable

import duckdb

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.provider_source_qualification import stable_fingerprint
from packages.providers.tradier.client import TradierMarketDataClient


TRADIER_SOURCE_QUALIFICATION_CONTRACT = {
    "contract_id": "atlas-tradier-production-market-data-source-qualification-v1",
    "provider": "tradier",
    "environment": "production",
    "credential_env": "TRADIER_API_KEY",
    "source_role": "CANDIDATE_CURRENT_MARKET_DATA_PROVIDER_ONLY",
    "documented_provider_facts": {
        "production_equity_data": "REALTIME_CONSOLIDATED_US_EXCHANGES",
        "production_options_data": "REALTIME_CONSOLIDATED_US_EXCHANGES",
        "sandbox_market_data_delay_minutes": 15,
        "production_market_data_requests_per_minute": 120,
        "post_quotes_for_larger_symbol_lists": True,
        "published_post_quote_symbol_limit": None,
        "one_market_data_stream_session": True,
        "published_stream_symbol_limit": None,
        "provider_streaming_guidance": "SEVERAL_HUNDRED_SYMBOLS_NOT_ENTIRE_EXCHANGE",
    },
    "rest_probe": {
        "method": "POST",
        "path": "/v1/markets/quotes",
        "default_batch_sizes": [1, 10, 100, 250, 500, 1000],
        "deterministic_symbol_sampling": True,
        "greeks": False,
        "include_lot_size": False,
        "persist_quote_values": False,
        "record_payload_hash": True,
        "record_symbol_coverage": True,
        "record_latency": True,
        "record_response_bytes": True,
        "record_rate_limit_headers": True,
        "stop_after_first_failed_stage": True,
    },
    "stream_probe": {
        "implemented_in_v1": False,
        "reason": (
            "REST batch capability must be measured first; streaming receives a "
            "separate accepted qualification because provider guidance discourages "
            "exchange-wide subscriptions and publishes no hard symbol cap."
        ),
    },
    "authority": {
        "provider_policy_change": False,
        "current_data_authority": False,
        "historical_data_authority": False,
        "strategy_evidence": False,
        "broker_account_reads": False,
        "provider_writes": False,
        "broker_writes": False,
        "order_creation": False,
        "paper": False,
        "live": False,
        "promotion": False,
        "confluence": False,
    },
}


TRADIER_SOURCE_QUALIFICATION_CONTRACT_FINGERPRINT = stable_fingerprint(
    TRADIER_SOURCE_QUALIFICATION_CONTRACT
)


@dataclass(frozen=True, slots=True)
class UniverseSymbolSource:
    as_of_date: date
    path: Path
    symbols: tuple[str, ...]
    sha256: str


def _sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_snapshot_date(path: Path) -> date:
    parent = path.parent
    if not parent.name.startswith("date="):
        raise ValueError(f"universe snapshot path lacks date partition: {path}")
    return date.fromisoformat(parent.name.split("=", 1)[1])


def latest_universe_symbol_source(settings: AtlasSettings) -> UniverseSymbolSource:
    root = (
        settings.resolved_path(settings.data.paths.derived)
        / "universe"
        / "snapshots"
    )
    candidates = sorted(root.glob("year=*/date=*/part-000.parquet"))
    if not candidates:
        raise FileNotFoundError(
            "Tradier qualification requires an existing Phase 7 universe snapshot"
        )
    path = max(candidates, key=_parse_snapshot_date)
    as_of_date = _parse_snapshot_date(path)

    con = duckdb.connect(database=":memory:")
    try:
        rows = con.execute(
            """
            SELECT DISTINCT ticker
            FROM read_parquet(?)
            WHERE discovery_eligible = TRUE
              AND ticker IS NOT NULL
              AND trim(ticker) <> ''
            ORDER BY ticker
            """,
            [str(path)],
        ).fetchall()
    finally:
        con.close()
    symbols = tuple(str(row[0]).strip() for row in rows if str(row[0]).strip())
    if not symbols:
        raise ValueError(f"universe snapshot has no discovery-eligible symbols: {path}")
    return UniverseSymbolSource(
        as_of_date=as_of_date,
        path=path,
        symbols=symbols,
        sha256=_sha256_file(path),
    )


def deterministic_symbol_sample(
    symbols: Iterable[str],
    *,
    count: int,
) -> tuple[str, ...]:
    clean = tuple(dict.fromkeys(str(item).strip() for item in symbols if str(item).strip()))
    if count < 1:
        raise ValueError("qualification sample count must be positive")
    if not clean:
        return ()

    anchors = ("SPY", "QQQ", "AAPL", "MSFT", "NVDA")
    selected: list[str] = [symbol for symbol in anchors if symbol in clean]
    remaining = [symbol for symbol in clean if symbol not in selected]
    remaining.sort(
        key=lambda symbol: (
            hashlib.sha256(symbol.encode("utf-8")).hexdigest(),
            symbol,
        )
    )
    selected.extend(remaining)
    return tuple(selected[: min(count, len(selected))])


def _rate_limit_headers(headers: dict[str, str]) -> dict[str, str | None]:
    lowered = {str(key).lower(): str(value) for key, value in headers.items()}
    return {
        "allowed": lowered.get("x-ratelimit-allowed"),
        "used": lowered.get("x-ratelimit-used"),
        "available": lowered.get("x-ratelimit-available"),
        "expiry": lowered.get("x-ratelimit-expiry"),
    }


def _quote_field_counts(rows: tuple[dict[str, Any], ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for key, value in row.items():
            if value is not None:
                counts[str(key)] = counts.get(str(key), 0) + 1
    return dict(sorted(counts.items()))


def run_tradier_rest_source_qualification(
    settings: AtlasSettings,
    *,
    batch_sizes: Iterable[int] | None = None,
    symbols: Iterable[str] | None = None,
    client: TradierMarketDataClient | None = None,
) -> dict[str, object]:
    if symbols is None:
        source = latest_universe_symbol_source(settings)
        source_symbols = source.symbols
        source_metadata: dict[str, object] = {
            "type": "PHASE7_DISCOVERY_ELIGIBLE_UNIVERSE",
            "as_of_date": source.as_of_date.isoformat(),
            "path": str(source.path.resolve()),
            "sha256": source.sha256,
            "symbol_count": len(source.symbols),
        }
    else:
        source_symbols = tuple(
            dict.fromkeys(str(item).strip() for item in symbols if str(item).strip())
        )
        if not source_symbols:
            raise ValueError("explicit Tradier qualification symbols are empty")
        source_metadata = {
            "type": "EXPLICIT_SYMBOLS",
            "symbol_count": len(source_symbols),
            "symbols_fingerprint": stable_fingerprint(sorted(source_symbols)),
        }

    sizes = tuple(
        int(value)
        for value in (
            batch_sizes
            if batch_sizes is not None
            else settings.tradier.market_data.qualification_batch_sizes
        )
    )
    if not sizes or any(value < 1 for value in sizes):
        raise ValueError("Tradier qualification batch sizes must all be positive")
    sizes = tuple(sorted(dict.fromkeys(sizes)))

    market_client = client or TradierMarketDataClient(settings)
    stages: list[dict[str, object]] = []
    terminal_error: str | None = None
    generated_at_utc = datetime.now(UTC)

    for requested_size in sizes:
        sample = deterministic_symbol_sample(source_symbols, count=requested_size)
        if not sample:
            break
        started = perf_counter()
        try:
            batch = market_client.post_quotes(sample)
        except Exception as exc:
            stages.append(
                {
                    "requested_size": requested_size,
                    "actual_requested_symbols": len(sample),
                    "status": "FAIL",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "wall_seconds": max(0.0, perf_counter() - started),
                }
            )
            terminal_error = f"{type(exc).__name__}: {exc}"
            break

        returned = batch.returned_symbols
        requested_set = set(sample)
        returned_set = set(returned)
        missing = sorted(requested_set - returned_set)
        unexpected = sorted(returned_set - requested_set)
        row_symbols = [
            str(row.get("symbol") or "").strip()
            for row in batch.returned_rows
            if str(row.get("symbol") or "").strip()
        ]
        duplicate_rows = len(row_symbols) - len(set(row_symbols))
        coverage = len(requested_set & returned_set) / len(requested_set)

        stages.append(
            {
                "requested_size": requested_size,
                "actual_requested_symbols": len(sample),
                "requested_symbols_fingerprint": stable_fingerprint(sorted(sample)),
                "status": "PASS" if not unexpected and duplicate_rows == 0 else "REVIEW",
                "http_status": batch.response.http_status,
                "provider_elapsed_seconds": batch.response.elapsed_seconds,
                "wall_seconds": max(0.0, perf_counter() - started),
                "response_bytes": batch.response.response_bytes,
                "returned_row_count": len(batch.returned_rows),
                "returned_unique_symbols": len(returned_set),
                "coverage_fraction": coverage,
                "missing_symbol_count": len(missing),
                "missing_symbols": missing[:50],
                "unexpected_symbol_count": len(unexpected),
                "unexpected_symbols": unexpected[:50],
                "duplicate_symbol_rows": duplicate_rows,
                "payload_fingerprint": stable_fingerprint(batch.returned_rows),
                "non_null_field_counts": _quote_field_counts(batch.returned_rows),
                "rate_limit": _rate_limit_headers(batch.response.response_headers),
            }
        )

        if len(sample) < requested_size:
            break

    attempted = [item for item in stages if item.get("status") != "FAIL"]
    complete_stage_count = sum(
        1
        for item in attempted
        if float(item.get("coverage_fraction") or 0.0) >= 0.98
        and int(item.get("unexpected_symbol_count") or 0) == 0
        and int(item.get("duplicate_symbol_rows") or 0) == 0
    )
    status = (
        "FAIL"
        if terminal_error and not attempted
        else "DIAGNOSTIC_COMPLETE_WITH_LIMITATIONS"
        if terminal_error or complete_stage_count < len(attempted)
        else "DIAGNOSTIC_COMPLETE"
    )

    report: dict[str, object] = {
        "status": status,
        "contract": TRADIER_SOURCE_QUALIFICATION_CONTRACT["contract_id"],
        "contract_fingerprint": TRADIER_SOURCE_QUALIFICATION_CONTRACT_FINGERPRINT,
        "generated_at_utc": generated_at_utc.isoformat(),
        "provider": "tradier",
        "environment": "production",
        "credential_env": settings.tradier.credentials.api_key_env,
        "source": source_metadata,
        "requested_batch_sizes": list(sizes),
        "stage_count": len(stages),
        "complete_stage_count": complete_stage_count,
        "terminal_error": terminal_error,
        "stages": stages,
        "authority": TRADIER_SOURCE_QUALIFICATION_CONTRACT["authority"],
        "interpretation": {
            "rest_quote_batch_capability_measured": bool(attempted),
            "streaming_not_yet_qualified": True,
            "authoritative_live_provider_policy_changed": False,
            "no_trading_authority_created": True,
        },
    }
    report["evidence_fingerprint"] = stable_fingerprint(report)

    output = (
        settings.resolved_path(settings.data.paths.research)
        if hasattr(settings.data.paths, "research")
        else settings.project_root / "data" / "research"
    )
    # DataPaths predates the research root; preserve the repository's existing
    # ignored data/research convention rather than changing the global path schema.
    output = settings.project_root / "data" / "research" / "provider_qualification" / "tradier" / "rest"
    output.mkdir(parents=True, exist_ok=True)
    stamp = generated_at_utc.strftime("%Y%m%dT%H%M%SZ")
    report_path = output / f"{stamp}.json"
    atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
    report["report_path"] = str(report_path.resolve())
    return report
