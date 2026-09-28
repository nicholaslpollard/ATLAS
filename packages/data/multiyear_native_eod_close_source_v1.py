from __future__ import annotations

"""Targeted original-native daily CLOSE reader for frozen option source dates.

Only C:-bound accepted native 1Day units containing requested symbols/years are
touched. No master-return or protected 2026 outcomes, stock re-selection,
MarketData request, broker authority, or assumed option/stock timestamp match.
"""

import math
import os
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any, Callable

import duckdb
import pandas as pd

from packages.backtesting.b35_development_source import _assert_native_path
from packages.backtesting.successor_runner_contract import canonical_sha256
from packages.core.settings import AtlasSettings
from packages.data.alpaca_v2_acquisition import UNIT_CONTRACT
from packages.data.marketdata_accepted_stock_candidate_export_v1 import (
    _accepted_native_plan, _file_sha, _read_json,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_demand_quote_cache_v1 import _write_new
from packages.data.multiyear_option_quote_bridge_v1 import NATIVE_FP
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.data.multiyear_option_stock_eod_preflight_v1 import CONTRACT as DEMAND_CONTRACT

CONTRACT = "atlas-targeted-multiyear-native-raw-eod-close-source-v1"
OUTPUT_REL = "data/options/derived/multiyear_native_raw_eod_close_source_v1"
MAX_WORKERS = 4


class NativeEodCloseError(ValueError):
    pass


def _read_one_unit(
    record: dict[str, Any], layout: Any, wanted: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Verify original checkpoint + Parquet SHA before reading a small exact join."""
    year, batch, unit_id = int(record["year"]), int(record["batch_index"]), str(record["unit_id"])
    if year > 2025 or not 2021 <= year:
        raise NativeEodCloseError("protected native year forbidden")
    part = Path(f"year={year:04d}") / f"batch={batch:04d}"
    prefix = unit_id[:20]
    checkpoint_path = layout.checkpoints / "native_units" / "1d" / part / f"{prefix}.json"
    canonical_path = layout.canonical_daily / part / f"{prefix}.parquet"
    _assert_native_path(checkpoint_path, expected=checkpoint_path, root=layout.root,
                        label="requested native daily checkpoint")
    _assert_native_path(canonical_path, expected=canonical_path, root=layout.root,
                        label="requested original raw daily canonical")
    checkpoint = _read_json(checkpoint_path, "requested original native checkpoint")
    if (checkpoint.get("contract") != UNIT_CONTRACT
        or checkpoint.get("status") not in {"COMPLETE", "COMPLETE_WITH_QUARANTINE"}
        or checkpoint.get("unit_id") != unit_id
        or checkpoint.get("policy_sha256") != record.get("policy_sha256")
        or checkpoint.get("universe_sha256") != record.get("universe_sha256")
        or canonical_sha256(checkpoint.get("unit")) != canonical_sha256(record)):
        raise NativeEodCloseError("original native checkpoint/plan identity drifted")
    canonical = checkpoint.get("canonical")
    if not isinstance(canonical, dict) or not canonical_path.is_file():
        raise NativeEodCloseError("original native daily Parquet absent")
    if Path(str(canonical.get("path") or "")).absolute() != canonical_path.absolute():
        raise NativeEodCloseError("native canonical path binding changed")
    sha = str(canonical.get("sha256") or "")
    if len(sha) != 64 or _file_sha(canonical_path) != sha:
        raise NativeEodCloseError("original native daily Parquet SHA changed")
    rejected = {
        str(x.get("symbol") or "") for x in checkpoint.get("provider_rejections") or []
        if isinstance(x, dict)
    }
    if rejected.intersection(x["ticker"] for x in wanted):
        raise NativeEodCloseError("original native provider rejection for required ticker")
    connection = duckdb.connect()
    try:
        connection.execute("PRAGMA threads=1")
        connection.execute("PRAGMA preserve_insertion_order=false")
        data = pd.DataFrame([
            {"symbol": row["ticker"], "session_date": date.fromisoformat(row["session_et"])}
            for row in wanted
        ]).drop_duplicates()
        connection.register("needed_original_native_closes", data)
        actual = connection.execute(
            """
            SELECT p.symbol,p.session_date,p.open,p.close,p.provider,p.dataset,
                   p.timeframe,p.session_segment,p.is_adjusted,p.source_id
            FROM read_parquet(?,hive_partitioning=false) p
            JOIN needed_original_native_closes r
              ON p.symbol=r.symbol AND p.session_date=r.session_date
            """,
            [str(canonical_path)],
        ).fetchall()
    finally:
        connection.close()
    observed = {}
    for ticker, session, opening, closing, provider, dataset, timeframe, segment, adjusted, source_id in actual:
        session = session if isinstance(session, date) else pd.Timestamp(session).date()
        key = (str(ticker), session)
        if key in observed:
            raise NativeEodCloseError("duplicate original native daily source bar")
        if (provider, dataset, timeframe, segment, adjusted, source_id) != (
            "alpaca", "stock_daily_aggregates", "1d", "regular", False,
            f"alpaca:sip:1Day:raw:asof=-:v2:unit={unit_id}",
        ):
            raise NativeEodCloseError("original daily bar source provenance changed")
        if any(isinstance(v, bool) or v is None for v in (opening, closing)):
            raise NativeEodCloseError("invalid native raw open/close")
        try:
            raw_open, raw_close = float(opening), float(closing)
        except (ValueError, TypeError, OverflowError) as exc:
            raise NativeEodCloseError("native raw price cannot be represented") from exc
        if not all(math.isfinite(v) and v > 0 for v in (raw_open, raw_close)):
            raise NativeEodCloseError("invalid native raw open/close")
        observed[key] = (str(raw_open), str(raw_close))
    output = []
    for item in wanted:
        key = (item["ticker"], date.fromisoformat(item["session_et"]))
        pair = observed.get(key)
        output.append({
            "request_identity": item["request_identity"],
            "instrument_id": item["instrument_id"],
            "ticker": item["ticker"], "session_et": item["session_et"],
            "status": "VERIFIED_NATIVE_RAW_EOD_CLOSE" if pair else "NO_RAW_NATIVE_DAILY_BAR_FOR_EXACT_SESSION",
            "raw_as_traded_open": pair[0] if pair else None,
            "raw_as_traded_close": pair[1] if pair else None,
            "native_unit_id": unit_id,
            "native_canonical_sha256": sha,
            "option_clock_match_proven": False,
            "historical_fill_proven": False,
        })
    return output, {
        "native_unit_id": unit_id, "native_canonical_sha256": sha,
        "requested_exact_pairs": len(wanted),
        "verified_exact_pairs": sum(x["status"] == "VERIFIED_NATIVE_RAW_EOD_CLOSE" for x in output),
    }


def resolve_native_eod_closes(
    settings: AtlasSettings, native: dict[str, Any], demand: dict[str, Any],
    *, workers: int = 3,
    unit_reader: Callable[[dict[str, Any], Any, list[dict[str, Any]]],
                          tuple[list[dict[str, Any]], dict[str, Any]]] = _read_one_unit,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Read only relevant signed V2 native units; keep missing exact bars as gaps."""
    for doc, field in ((native, "source_fingerprint"), (demand, "demand_fingerprint")):
        _check_signature(doc, field)
    if (
        native.get("source_fingerprint") != NATIVE_FP
        or native.get("provider_requests") != 0
        or native.get("protected_outcomes_read") != 0
        or demand.get("contract") != DEMAND_CONTRACT
        or demand.get("status") != "OFFLINE_NATIVE_STOCK_EOD_DEMAND_NOT_SOURCE_PROOF"
        or demand.get("accepted_native_fingerprint") != native["source_fingerprint"]
        or demand.get("provider_requests") != 0
        or demand.get("protected_2026_outcomes_read") != 0
        or demand.get("native_raw_closes_read") != 0
        or demand.get("portfolio_pnl_authority") is not False
        or not isinstance(demand.get("requests"), list)
        or type(workers) is not int or not 1 <= workers <= MAX_WORKERS
    ):
        raise NativeEodCloseError("native source/demand authority or concurrency changed")
    needed = demand["requests"]
    if not needed:
        raise NativeEodCloseError("no accepted exact native daily CLOSE demand")
    query_ids = {x["request_identity"] for x in needed}
    pairs = {(x["ticker"], date.fromisoformat(x["session_et"])) for x in needed}
    if len(query_ids) != len(needed) or len(pairs) != len(needed):
        raise NativeEodCloseError("duplicate or ambiguous exact native CLOSE request")
    if any(x["session_et"][:4] == "2026" or x["stock_close_has_not_been_read"] is not True
           or x["required_native_field"] != "RAW_AS_TRADED_1DAY_REGULAR_CLOSE"
           for x in needed):
        raise NativeEodCloseError("protected/adjusted native request cannot be read")
    settings.assert_external_storage_binding("options")
    source_report = native.get("accepted_native_source")
    if not isinstance(source_report, dict):
        raise NativeEodCloseError("original accepted native source provenance missing")
    records, accepted, layout = _accepted_native_plan(settings, source_report, pairs)
    by_pair = {}
    sought = {(ticker, day.year) for ticker, day in pairs}
    for record in records:
        for symbol in record["symbols"]:
            key = (str(symbol), int(record["year"]))
            if key in sought:
                if key in by_pair:
                    raise NativeEodCloseError("same symbol/year has ambiguous native units")
                by_pair[key] = record
    groups: dict[str, tuple[dict[str, Any], list[dict[str, Any]]]] = {}
    for item in needed:
        unit = by_pair.get((item["ticker"], date.fromisoformat(item["session_et"]).year))
        if unit is None:
            raise NativeEodCloseError("native acquisition plan lacks exact ticker/year unit")
        uid = unit["unit_id"]
        if uid not in groups:
            groups[uid] = (unit, [])
        groups[uid][1].append(item)
    results: list[dict[str, Any]] = []
    bindings = []
    max_workers = min(workers, max(1, (os.cpu_count() or 4) - 1), len(groups))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(unit_reader, rec, layout, items): uid
            for uid, (rec, items) in groups.items()
        }
        # Wait for every submitted verifier; an error leaves all original files untouched.
        errors = []
        for completed, future in enumerate(as_completed(futures), 1):
            try:
                rows, binding = future.result()
                results.extend(rows)
                bindings.append(binding)
            except Exception as exc:
                errors.append((futures[future], exc))
            if progress and (completed == 1 or completed % 20 == 0 or completed == len(futures)):
                progress({
                    "stage": "TARGETED_NATIVE_UNIT_CLOSE_READ",
                    "verified_units": completed, "total_needed_units": len(futures),
                    "source_rows": len(results), "provider_requests": 0,
                })
    if errors:
        unit, error = errors[0]
        raise NativeEodCloseError(
            f"original native unit verification stopped: {unit} / "
            f"{type(error).__name__}: {error}"
        ) from error
    if len(results) != len(needed) or {x["request_identity"] for x in results} != query_ids:
        raise NativeEodCloseError("native requested daily CLOSE coverage or uniqueness changed")
    statuses = Counter(x["status"] for x in results)
    report = {
        "contract": CONTRACT,
        "status": "TARGETED_ACCEPTED_NATIVE_DAILY_CLOSE_SOURCE_ONLY",
        "original_native_fingerprint": native["source_fingerprint"],
        "original_stock_close_demand_fingerprint": demand["demand_fingerprint"],
        "native_acceptance_fingerprint": accepted["native_acceptance_fingerprint"],
        "native_plan_sha256": accepted["native_plan_sha256"],
        "unique_native_daily_units_verified": len(bindings),
        "unique_requested_native_closes": len(needed),
        "verified_exact_native_raw_closes": statuses["VERIFIED_NATIVE_RAW_EOD_CLOSE"],
        "exact_daily_bar_gaps": statuses["NO_RAW_NATIVE_DAILY_BAR_FOR_EXACT_SESSION"],
        "by_status": dict(sorted(statuses.items())),
        "native_unit_bindings": sorted(bindings, key=lambda x: x["native_unit_id"]),
        "rows": sorted(results, key=lambda x: x["request_identity"]),
        "provider_requests": 0, "protected_2026_outcomes_read": 0,
        "provider_option_update_is_not_verified_stock_close_clock": True,
        "option_fill_or_portfolio_pnl_authority": False,
    }
    report["source_fingerprint"] = _fingerprint(report)
    return report


def persist_native_eod_closes(settings: AtlasSettings, report: dict[str, Any]) -> tuple[Path, str]:
    settings.assert_external_storage_binding("options")
    _check_signature(report, "source_fingerprint")
    path = settings.resolved_path(f"{OUTPUT_REL}_{report['source_fingerprint'][:16]}.json")
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or _read_object(path) != report:
            raise NativeEodCloseError("original derived native EOD close source differs")
        return path, "REUSED_IDENTICAL_NATIVE_CLOSE_SOURCE"
    _write_new(path, report)
    return path, "WRITTEN_IMMUTABLE_NATIVE_CLOSE_SOURCE"
