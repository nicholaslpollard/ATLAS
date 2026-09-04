from __future__ import annotations

import gzip
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

import duckdb
import pandas as pd

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_identity import (
    ObservedBounds,
    _classify_name_change,
    _cycle_nodes,
    _normalize_event,
    _relationship_rows,
)
from packages.data.alpaca_v2_acquisition import (
    ACQUISITION_CONTRACT,
    BOOTSTRAP_CONTRACT,
    COMPLETE_UNIT_STATUSES,
    SOURCE_SNAPSHOT_CONTRACT,
    V2_ASOF,
    V2_FEED,
    V2_PAGE_LIMIT,
    V2TimeLimitReached,
    AlpacaV2NativeAcquirer,
    NativeAcquisitionUnit,
    _read_gzip_verified,
    _sha256_bytes,
    _stable_json,
    build_native_plan,
)
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.providers.alpaca import (
    AlpacaInvalidSymbolError,
    AlpacaMarketDataClient,
)
from packages.schemas.canonical_market import canonical_stock_daily_schema_matches


POSTBUILD_CONTRACT = "atlas-alpaca-sip-v2-postbuild-v1"
NATIVE_ACCEPTANCE_CONTRACT = "atlas-alpaca-sip-v2-native-acceptance-v1"
DAILY_QUALITY_CONTRACT = "atlas-alpaca-sip-v2-daily-quality-v1"
IDENTITY_LIFECYCLE_CONTRACT = (
    "atlas-alpaca-sip-v2-identity-lifecycle-v1-direct-asset-id-no-silent-stitch"
)
SPLIT_DAILY_CONTRACT = (
    "atlas-alpaca-sip-v2-split-adjusted-daily-v1-provider-native-sip-asof-literal"
)
SPLIT_DAILY_UNIT_CONTRACT = "atlas-alpaca-sip-v2-split-adjusted-daily-unit-v1"
RESEARCH_DAILY_CONTRACT = (
    "atlas-alpaca-sip-v2-research-daily-v1-development-only-direct-identity-"
    "contiguous-split-adjusted"
)
V2_REFERENCE_DEVELOPMENT_END = date(2026, 5, 11)

SUPPORTED_CORPORATE_ACTION_TYPES = {
    "cash_dividends",
    "reverse_splits",
    "stock_mergers",
    "name_changes",
    "forward_splits",
    "cash_mergers",
    "stock_dividends",
    "unit_splits",
    "stock_and_cash_mergers",
    "spin_offs",
    "rights_distributions",
    "redemptions",
    "worthless_removals",
    "partial_calls",
    "reorganizations",
    "capital_gains_distributions",
}

INITIAL_SEGMENT_REQUIRED_EVENT_TYPES = {
    "cash_mergers",
    "name_changes",
    "partial_calls",
    "redemptions",
    "reorganizations",
    "rights_distributions",
    "spin_offs",
    "stock_and_cash_mergers",
    "stock_dividends",
    "stock_mergers",
    "unit_splits",
    "worthless_removals",
}

_COMMON_STOCK_POSITIVE = re.compile(
    r"\b(COMMON STOCK|COMMON SHARES?|ORDINARY SHARES?)\b",
    flags=re.IGNORECASE,
)
_COMMON_STOCK_EXCLUSION = re.compile(
    r"\b(ETF|ETN|EXCHANGE[- ]TRADED|FUND|WARRANTS?|RIGHTS?|UNITS?|"
    r"PREFERRED|PREFERENCE|DEPOSITARY|DEPOSITORY|ADR|ADS|BONDS?|NOTES?)\b",
    flags=re.IGNORECASE,
)


class AlpacaV2PostBuildError(RuntimeError):
    pass


class AlpacaV2NotCompleteError(AlpacaV2PostBuildError):
    pass


class AlpacaV2ValidationError(AlpacaV2PostBuildError):
    pass


@dataclass(frozen=True, slots=True)
class NativeAcceptanceResult:
    report: dict[str, Any]
    units: tuple[NativeAcquisitionUnit, ...]
    inventory: pd.DataFrame
    excluded_symbols: frozenset[str]


@dataclass(frozen=True, slots=True)
class DailyQualityResult:
    report: dict[str, Any]
    observed: pd.DataFrame


@dataclass(frozen=True, slots=True)
class IdentityLifecycleResult:
    report: dict[str, Any]
    symbol_map: pd.DataFrame


@dataclass(frozen=True, slots=True)
class SplitDailyResult:
    report: dict[str, Any]
    inventory: pd.DataFrame


@dataclass(frozen=True, slots=True)
class ResearchDailyResult:
    report: dict[str, Any]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_hash(value: object) -> str:
    return _sha256_bytes(_stable_json(value))


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AlpacaV2ValidationError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise AlpacaV2ValidationError(f"{label} must be a JSON object: {path}")
    return value


def _sql_paths(paths: Iterable[Path]) -> str:
    resolved = tuple(Path(path) for path in paths)
    if not resolved:
        raise AlpacaV2ValidationError("Parquet source inventory is empty")
    return "[" + ",".join(sql_string(path) for path in resolved) + "]"


def _write_frame(path: Path, frame: pd.DataFrame, *, order_by: str) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = unique_temp_path(path)
    con = connect_utc(":memory:")
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
    return {
        "path": str(path),
        "sha256": _sha256_file(path),
        "bytes": path.stat().st_size,
        "rows": len(frame),
    }


def _iter_gzip_json(path: Path) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AlpacaV2ValidationError(
                    f"invalid gzip JSON line {line_number}: {path}"
                ) from exc
            if not isinstance(value, dict):
                raise AlpacaV2ValidationError(
                    f"gzip JSON record must be an object at line {line_number}: {path}"
                )
            yield value


def _clean_symbol(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    result = value.strip()
    if not result or "," in result or any(character.isspace() for character in result):
        return None
    return result


def _security_type_from_names(names: Iterable[str]) -> tuple[str, tuple[str, ...]]:
    cleaned = tuple(sorted({str(value).strip() for value in names if str(value).strip()}))
    reasons: list[str] = []
    if not cleaned:
        return "UNCONFIRMED", ("MISSING_ASSET_NAME",)
    if any(_COMMON_STOCK_EXCLUSION.search(value) for value in cleaned):
        reasons.append("NON_COMMON_SECURITY_NAME")
    if not all(_COMMON_STOCK_POSITIVE.search(value) for value in cleaned):
        reasons.append("COMMON_STOCK_NAME_NOT_CONFIRMED")
    if reasons:
        return "UNCONFIRMED", tuple(sorted(set(reasons)))
    return "COMMON_STOCK", ()


class AlpacaV2PostBuildCoordinator:
    """Validate and materialize V2 without reading any persisted V1 market layer."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.data_root = (settings.project_root / "data").resolve()
        self.layout = V2Layout.beneath(self.data_root)
        self.calendar = MarketCalendar(exchange=settings.data.calendar.exchange)
        self.native_inventory_path = self.layout.validation / "native_unit_inventory.parquet"
        self.native_report_path = self.layout.validation / "native_acceptance.json"
        self.daily_observed_path = self.layout.validation / "daily_observed_symbols.parquet"
        self.daily_report_path = self.layout.validation / "daily_quality.json"
        self.identity_event_path = self.layout.identity / "v2_corporate_action_events.parquet"
        self.identity_relationship_path = (
            self.layout.identity / "v2_corporate_action_relationships.parquet"
        )
        self.rename_candidate_path = self.layout.identity / "v2_name_change_candidates.parquet"
        self.identity_map_path = self.layout.identity / "v2_symbol_identity_map.parquet"
        self.identity_report_path = self.layout.validation / "identity_lifecycle.json"

    def _native_documents(
        self,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
        bootstrap = _read_json(self.layout.checkpoints / "bootstrap.json", "V2 bootstrap")
        source = _read_json(self.layout.manifests / "source_snapshot.json", "source snapshot")
        plan = _read_json(
            self.layout.manifests / "native_acquisition_plan.json",
            "native acquisition plan",
        )
        report = _read_json(
            self.layout.manifests / "native_acquisition_report.json",
            "native acquisition report",
        )
        if bootstrap.get("contract") != BOOTSTRAP_CONTRACT:
            raise AlpacaV2ValidationError("V2 bootstrap contract drifted")
        if source.get("contract") != SOURCE_SNAPSHOT_CONTRACT:
            raise AlpacaV2ValidationError("V2 source snapshot contract drifted")
        if plan.get("contract") != ACQUISITION_CONTRACT:
            raise AlpacaV2ValidationError("V2 native plan contract drifted")
        if report.get("contract") != ACQUISITION_CONTRACT:
            raise AlpacaV2ValidationError("V2 native report contract drifted")
        run_ids = {str(item.get("run_id") or "") for item in (bootstrap, source, plan, report)}
        if len(run_ids) != 1 or "" in run_ids:
            raise AlpacaV2ValidationError("V2 bootstrap/source/plan/report run IDs disagree")
        if any(item.get("v1_ancestry") != "FORBIDDEN" for item in (bootstrap, source, plan, report)):
            raise AlpacaV2ValidationError("V2 ancestry contract no longer forbids V1")
        return bootstrap, source, plan, report

    def validate_native(
        self,
        *,
        progress: Callable[[dict[str, object]], None] | None = None,
    ) -> NativeAcceptanceResult:
        bootstrap, source, plan_manifest, acquisition_report = self._native_documents()
        if (
            acquisition_report.get("status") != "COMPLETE"
            or acquisition_report.get("native_base_complete") is not True
            or int(acquisition_report.get("missing_units", -1)) != 0
        ):
            completed = int(acquisition_report.get("completed_units", 0))
            total = int(acquisition_report.get("total_units", 0))
            raise AlpacaV2NotCompleteError(
                f"native V2 acquisition is not complete ({completed:,}/{total:,} units)"
            )

        symbols = [str(value) for value in source.get("symbols") or []]
        if symbols != sorted(set(symbols)) or not symbols:
            raise AlpacaV2ValidationError("V2 source universe is empty or non-deterministic")
        units = build_native_plan(
            symbols=symbols,
            start=date.fromisoformat(str(bootstrap["start_date"])),
            cutoff=date.fromisoformat(str(bootstrap["cutoff_session"])),
            universe_sha256=str(source["universe_sha256"]),
            policy_sha256=str(bootstrap["request_policy_sha256"]),
        )
        if len(units) != int(plan_manifest.get("total_units", -1)):
            raise AlpacaV2ValidationError("rebuilt native plan unit count does not match manifest")
        plan_lines = b"".join(_stable_json(asdict(unit)) + b"\n" for unit in units)
        if _sha256_bytes(plan_lines) != plan_manifest.get("plan_sha256"):
            raise AlpacaV2ValidationError("rebuilt native plan fingerprint does not match manifest")
        plan_path = Path(str(plan_manifest.get("plan_path") or ""))
        if not plan_path.is_file() or _sha256_file(plan_path) != plan_manifest.get(
            "plan_file_sha256"
        ):
            raise AlpacaV2ValidationError("compressed native plan hash does not match manifest")

        acquirer = AlpacaV2NativeAcquirer(
            self.settings,
            start_date=date.fromisoformat(str(bootstrap["start_date"])),
        )
        verified_source = acquirer._load_source_manifest()
        if verified_source is None:
            raise AlpacaV2ValidationError("V2 source snapshot could not be verified")
        verified_document, verified_symbols = verified_source
        if verified_symbols != symbols or verified_document != source:
            raise AlpacaV2ValidationError(
                "verified V2 source snapshot disagrees with the frozen source document"
            )
        inventory_rows: list[dict[str, object]] = []
        status_counts: Counter[str] = Counter()
        quarantine_reason_counts: Counter[str] = Counter()
        excluded_symbols: set[str] = set()
        fatal: list[str] = []
        canonical_rows = 0
        raw_bytes = 0
        canonical_bytes = 0

        for index, unit in enumerate(units, start=1):
            paths = acquirer._unit_paths(unit)
            checkpoint_path = paths["checkpoint"]
            if not checkpoint_path.is_file():
                fatal.append(f"MISSING_CHECKPOINT:{unit.unit_id}")
                continue
            checkpoint = _read_json(checkpoint_path, f"native unit checkpoint {unit.label}")
            if not acquirer._validate_unit_checkpoint(unit, checkpoint):
                fatal.append(f"IN_PROGRESS_CHECKPOINT:{unit.unit_id}")
                continue
            checkpoint_sha = _sha256_file(checkpoint_path)
            status = str(checkpoint.get("status") or "UNKNOWN")
            status_counts[status] += 1
            canonical = checkpoint.get("canonical") or {}
            raw_bundle = checkpoint.get("raw_bundle") or {}
            if status == "BLOCKED_VALIDATION":
                fatal.append(f"BLOCKED_VALIDATION:{unit.unit_id}")
            if int(canonical.get("duplicate_rows", 0)) != 0:
                fatal.append(f"DUPLICATE_ROWS:{unit.unit_id}")
            outside = int(canonical.get("outside_session_rows", 0))
            if unit.canonical_timeframe == "1d" and outside:
                fatal.append(f"DAILY_OUTSIDE_SESSION_ROWS:{unit.unit_id}:{outside}")

            for record in checkpoint.get("provider_rejections") or []:
                symbol = _clean_symbol(record.get("symbol")) if isinstance(record, dict) else None
                if symbol is not None:
                    excluded_symbols.add(symbol)
                    quarantine_reason_counts["PROVIDER_REJECTED_LITERAL"] += 1
            quarantine = checkpoint.get("quarantine")
            if isinstance(quarantine, dict):
                quarantine_path = Path(str(quarantine.get("path") or ""))
                for record in _iter_gzip_json(quarantine_path):
                    reason = str(record.get("reason") or "UNKNOWN_ROW_ANOMALY")
                    quarantine_reason_counts[reason] += 1
                    symbol = _clean_symbol(record.get("symbol"))
                    if symbol is not None:
                        excluded_symbols.add(symbol)

            row_count = int(canonical.get("canonical_rows", 0))
            canonical_rows += row_count
            raw_bytes += int(raw_bundle.get("bytes", 0))
            canonical_bytes += int(canonical.get("bytes", 0))
            inventory_rows.append(
                {
                    "unit_id": unit.unit_id,
                    "provider_timeframe": unit.provider_timeframe,
                    "canonical_timeframe": unit.canonical_timeframe,
                    "window_start": unit.window_start,
                    "window_end_exclusive": unit.window_end_exclusive,
                    "year": unit.year,
                    "month": unit.month,
                    "batch_index": unit.batch_index,
                    "symbols_json": json.dumps(list(unit.symbols), separators=(",", ":")),
                    "status": status,
                    "checkpoint_path": str(checkpoint_path),
                    "checkpoint_sha256": checkpoint_sha,
                    "canonical_path": canonical.get("path"),
                    "canonical_sha256": canonical.get("sha256"),
                    "canonical_rows": row_count,
                    "canonical_bytes": int(canonical.get("bytes", 0)),
                    "raw_bundle_path": raw_bundle.get("path"),
                    "raw_bundle_sha256": raw_bundle.get("sha256"),
                    "raw_bundle_bytes": int(raw_bundle.get("bytes", 0)),
                    "page_count": int(checkpoint.get("page_count", 0)),
                    "quarantined_rows": int(checkpoint.get("quarantined_rows", 0)),
                    "outside_session_rows": outside,
                    "provider_rejections": len(checkpoint.get("provider_rejections") or []),
                }
            )
            if progress is not None and (index == len(units) or index % 500 == 0):
                progress(
                    {
                        "event": "native_validation",
                        "completed": index,
                        "total": len(units),
                    }
                )

        if len(inventory_rows) != len(units):
            fatal.append(f"INVENTORY_COUNT:{len(inventory_rows)}:{len(units)}")
        if canonical_rows != int(acquisition_report.get("canonical_rows", -1)):
            fatal.append("CANONICAL_ROW_ACCOUNTING_MISMATCH")
        if sum(status_counts.values()) != int(acquisition_report.get("completed_units", -1)):
            fatal.append("COMPLETED_UNIT_ACCOUNTING_MISMATCH")
        if any(status not in COMPLETE_UNIT_STATUSES for status in status_counts):
            fatal.append("UNKNOWN_COMPLETED_UNIT_STATUS")

        inventory = pd.DataFrame(inventory_rows)
        inventory_record = _write_frame(
            self.native_inventory_path,
            inventory,
            order_by="canonical_timeframe, year, month NULLS FIRST, batch_index, unit_id",
        )
        source_binding = {
            "bootstrap_sha256": _sha256_file(self.layout.checkpoints / "bootstrap.json"),
            "source_snapshot_sha256": _sha256_file(
                self.layout.manifests / "source_snapshot.json"
            ),
            "plan_manifest_sha256": _sha256_file(
                self.layout.manifests / "native_acquisition_plan.json"
            ),
            "acquisition_report_sha256": _sha256_file(
                self.layout.manifests / "native_acquisition_report.json"
            ),
            "unit_inventory_sha256": inventory_record["sha256"],
        }
        acceptance_fingerprint = _stable_hash(
            {
                "contract": NATIVE_ACCEPTANCE_CONTRACT,
                "run_id": bootstrap["run_id"],
                "source_binding": source_binding,
                "unit_count": len(units),
                "canonical_rows": canonical_rows,
                "excluded_symbols": sorted(excluded_symbols),
                "fatal": sorted(fatal),
            }
        )
        report = {
            "contract": NATIVE_ACCEPTANCE_CONTRACT,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "status": "PASS" if not fatal else "FAIL",
            "run_id": bootstrap["run_id"],
            "start_date": bootstrap["start_date"],
            "cutoff_session": bootstrap["cutoff_session"],
            "source_binding": source_binding,
            "acceptance_fingerprint": acceptance_fingerprint,
            "total_units": len(units),
            "status_counts": dict(sorted(status_counts.items())),
            "canonical_rows": canonical_rows,
            "raw_bundle_bytes": raw_bytes,
            "canonical_bytes": canonical_bytes,
            "quarantine_reason_counts": dict(sorted(quarantine_reason_counts.items())),
            "excluded_symbols": sorted(excluded_symbols),
            "excluded_symbol_count": len(excluded_symbols),
            "fatal_failures": sorted(fatal),
            "unit_inventory": inventory_record,
            "v1_rows_read": 0,
            "v1_ancestry": "FORBIDDEN",
            "production_promoted": False,
            "protected_return_rows_read": 0,
            "provider_writes": 0,
            "broker_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
        }
        atomic_write_text(
            self.native_report_path,
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            fsync=True,
        )
        if fatal:
            raise AlpacaV2ValidationError(
                "native V2 acceptance failed: " + ", ".join(sorted(fatal)[:10])
            )
        return NativeAcceptanceResult(
            report=report,
            units=tuple(units),
            inventory=inventory,
            excluded_symbols=frozenset(excluded_symbols),
        )

    def validate_daily(self, native: NativeAcceptanceResult) -> DailyQualityResult:
        daily_inventory = native.inventory.loc[
            native.inventory["canonical_timeframe"] == "1d"
        ].copy()
        if daily_inventory.empty:
            raise AlpacaV2ValidationError("native V2 contains no daily unit inventory")
        paths = tuple(Path(str(value)) for value in daily_inventory["canonical_path"])
        source_sql = f"read_parquet({_sql_paths(paths)}, hive_partitioning=false)"
        start = date.fromisoformat(str(native.report["start_date"]))
        cutoff = date.fromisoformat(str(native.report["cutoff_session"]))
        sessions = self.calendar.sessions_in_range(start, cutoff)
        schedule_rows = []
        for ordinal, session in enumerate(sessions):
            regular_open, regular_close = self.calendar.regular_open_close(session)
            schedule_rows.append(
                {
                    "session_date": session,
                    "session_ordinal": ordinal,
                    "regular_open_utc": regular_open,
                    "regular_close_utc": regular_close,
                }
            )
        schedule = pd.DataFrame(schedule_rows)
        universe_path = self.layout.identity / "acquisition_universe.parquet"
        source_manifest = _read_json(
            self.layout.manifests / "source_snapshot.json", "V2 source snapshot"
        )
        symbols = {str(value) for value in source_manifest.get("symbols") or []}

        con = connect_utc(":memory:")
        con.execute("PRAGMA threads=4")
        con.register("v2_schedule", schedule)
        try:
            description = con.execute(f"DESCRIBE SELECT * FROM {source_sql}").fetchall()
            if not canonical_stock_daily_schema_matches(description):
                raise AlpacaV2ValidationError("daily V2 physical schema is not exact")
            totals = con.execute(
                f"""
                SELECT
                    count(*) AS rows,
                    count(DISTINCT symbol) AS symbols,
                    min(session_date) AS first_session,
                    max(session_date) AS last_session,
                    count(*) FILTER (
                        WHERE provider <> 'alpaca'
                           OR dataset <> 'stock_daily_aggregates'
                           OR timeframe <> '1d'
                           OR session_segment <> 'regular'
                           OR is_adjusted <> FALSE
                           OR source_id NOT LIKE 'alpaca:sip:1Day:raw:asof=-:v2:unit=%'
                    ) AS provenance_failures,
                    count(*) FILTER (
                        WHERE NOT isfinite(open) OR NOT isfinite(high)
                           OR NOT isfinite(low) OR NOT isfinite(close)
                           OR NOT isfinite(volume)
                           OR open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
                           OR volume < 0 OR high < low OR high < open OR high < close
                           OR low > open OR low > close
                           OR (vwap IS NOT NULL AND (NOT isfinite(vwap) OR vwap <= 0))
                           OR (transaction_count IS NOT NULL AND transaction_count < 0)
                    ) AS value_failures,
                    count(*) FILTER (WHERE CAST(provider_timestamp_utc AS DATE) <> session_date)
                        AS provider_date_failures
                FROM {source_sql}
                """
            ).fetchone()
            duplicates = int(
                con.execute(
                    f"""
                    SELECT coalesce(sum(n - 1), 0)
                    FROM (
                        SELECT symbol, session_date, count(*) AS n
                        FROM {source_sql}
                        GROUP BY symbol, session_date
                        HAVING count(*) > 1
                    )
                    """
                ).fetchone()[0]
            )
            schedule_failures = int(
                con.execute(
                    f"""
                    SELECT count(*)
                    FROM {source_sql} b
                    LEFT JOIN v2_schedule s USING (session_date)
                    WHERE s.session_date IS NULL
                       OR b.timestamp_utc <> s.regular_open_utc
                    """
                ).fetchone()[0]
            )
            observed = con.execute(
                f"""
                WITH ordered AS (
                    SELECT b.symbol, b.session_date, s.session_ordinal,
                           lag(s.session_ordinal) OVER (
                               PARTITION BY b.symbol ORDER BY b.session_date
                           ) AS previous_ordinal
                    FROM {source_sql} b
                    JOIN v2_schedule s USING (session_date)
                )
                SELECT
                    symbol,
                    min(session_date) AS first_session,
                    max(session_date) AS last_session,
                    count(*)::BIGINT AS observed_sessions,
                    (max(session_ordinal) - min(session_ordinal) + 1)::BIGINT
                        AS expected_sessions_between_bounds,
                    ((max(session_ordinal) - min(session_ordinal) + 1) - count(*))::BIGINT
                        AS missing_sessions_between_bounds,
                    coalesce(max(session_ordinal - previous_ordinal - 1), 0)::BIGINT
                        AS maximum_internal_gap_sessions
                FROM ordered
                GROUP BY symbol
                ORDER BY symbol
                """
            ).fetchdf()
        finally:
            con.unregister("v2_schedule")
            con.close()

        assert totals is not None
        observed_symbols = set(observed["symbol"].astype(str))
        outside_universe = sorted(observed_symbols.difference(symbols))
        expected_rows = int(daily_inventory["canonical_rows"].sum())
        checks = {
            "row_accounting_exact": int(totals[0]) == expected_rows,
            "date_bounds_exact": totals[2] == start and totals[3] == cutoff,
            "provenance_exact": int(totals[4]) == 0,
            "values_valid": int(totals[5]) == 0,
            "provider_dates_valid": int(totals[6]) == 0,
            "global_duplicates_zero": duplicates == 0,
            "xnys_schedule_exact": schedule_failures == 0,
            "symbols_within_frozen_universe": not outside_universe,
        }
        observed_record = _write_frame(
            self.daily_observed_path,
            observed,
            order_by="symbol",
        )
        quality_fingerprint = _stable_hash(
            {
                "contract": DAILY_QUALITY_CONTRACT,
                "native_acceptance_fingerprint": native.report["acceptance_fingerprint"],
                "start_date": start.isoformat(),
                "cutoff_session": cutoff.isoformat(),
                "daily_rows": int(totals[0]),
                "daily_symbols": int(totals[1]),
                "observed_symbols_sha256": observed_record["sha256"],
                "checks": checks,
            }
        )
        report = {
            "contract": DAILY_QUALITY_CONTRACT,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "status": "PASS" if all(checks.values()) else "FAIL",
            "native_acceptance_fingerprint": native.report["acceptance_fingerprint"],
            "quality_fingerprint": quality_fingerprint,
            "start_date": start.isoformat(),
            "cutoff_session": cutoff.isoformat(),
            "daily_units": len(daily_inventory),
            "daily_rows": int(totals[0]),
            "daily_symbols": int(totals[1]),
            "first_session": str(totals[2]),
            "last_session": str(totals[3]),
            "provenance_failures": int(totals[4]),
            "value_failures": int(totals[5]),
            "provider_date_failures": int(totals[6]),
            "global_duplicate_rows": duplicates,
            "schedule_failures": schedule_failures,
            "outside_universe_symbols": outside_universe,
            "symbols_with_internal_gaps": int(
                (observed["missing_sessions_between_bounds"] > 0).sum()
            ),
            "observed_symbols": observed_record,
            "checks": checks,
            "v1_rows_read": 0,
            "protected_return_rows_read": 0,
            "production_promoted": False,
        }
        atomic_write_text(
            self.daily_report_path,
            json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
            fsync=True,
        )
        if report["status"] != "PASS":
            failed = [name for name, passed in checks.items() if not passed]
            raise AlpacaV2ValidationError(
                "daily V2 quality failed: " + ", ".join(failed)
            )
        return DailyQualityResult(report=report, observed=observed)

    def build_identity_lifecycle(
        self,
        native: NativeAcceptanceResult,
        daily: DailyQualityResult,
    ) -> IdentityLifecycleResult:
        source = _read_json(self.layout.manifests / "source_snapshot.json", "source snapshot")
        action_manifest = _read_json(
            self.layout.manifests / "corporate_actions.json",
            "corporate action manifest",
        )
        if (
            action_manifest.get("contract") != SOURCE_SNAPSHOT_CONTRACT
            or action_manifest.get("status") != "COMPLETE"
            or action_manifest.get("start") != native.report["start_date"]
            or action_manifest.get("cutoff") != native.report["cutoff_session"]
            or action_manifest.get("native_actions")
            != source.get("corporate_actions_native")
            or action_manifest.get("raw_bundle")
            != source.get("corporate_actions_raw_bundle")
            or int(action_manifest.get("page_count", -1))
            != len(action_manifest.get("pages") or [])
        ):
            raise AlpacaV2ValidationError(
                "V2 corporate-action manifest is not exactly bound to the source snapshot"
            )
        page_hashes = {
            index: str(record.get("sha256") or "")
            for index, record in enumerate(action_manifest.get("pages") or [])
            if isinstance(record, dict)
        }
        native_actions = Path(str((source.get("corporate_actions_native") or {}).get("path") or ""))
        if not native_actions.is_file():
            raise AlpacaV2ValidationError("V2 native corporate-action ledger is missing")

        events: list[dict[str, object]] = []
        unknown_types: set[str] = set()
        for item in _iter_gzip_json(native_actions):
            event_type = str(item.get("action_type") or "")
            payload = item.get("payload")
            page_index = int(item.get("source_page_index", -1))
            record_index = int(item.get("source_record_index", -1))
            if not event_type or not isinstance(payload, dict) or page_index not in page_hashes:
                raise AlpacaV2ValidationError("malformed V2 native corporate-action record")
            if event_type not in SUPPORTED_CORPORATE_ACTION_TYPES:
                unknown_types.add(event_type)
            event = _normalize_event(
                event_type,
                payload,
                partition=f"v2_corporate_actions_page_{page_index:06d}",
                raw_sha256=page_hashes[page_index],
                event_index=record_index,
            )
            if event_type in {"redemptions", "worthless_removals", "partial_calls"}:
                event["identity_semantics"] = "TERMINATION_OR_REDEMPTION"
            elif event_type == "reorganizations":
                event["identity_semantics"] = "REORGANIZATION_REVIEW"
            elif event_type == "capital_gains_distributions":
                event["identity_semantics"] = "DISTRIBUTION"
            events.append(event)
        if len(events) != int(action_manifest.get("action_record_count", -1)):
            raise AlpacaV2ValidationError(
                "V2 corporate-action native row count disagrees with its manifest"
            )

        relationships: list[dict[str, object]] = []
        for event in events:
            relationships.extend(_relationship_rows(event))

        observed: dict[str, ObservedBounds] = {}
        for row in daily.observed.to_dict(orient="records"):
            symbol = _clean_symbol(row.get("symbol"))
            if symbol is None:
                continue
            observed[symbol] = ObservedBounds(
                first_date=pd.Timestamp(row["first_session"]).date(),
                last_date=pd.Timestamp(row["last_session"]).date(),
                observed=True,
            )
        name_events = [event for event in events if event["event_type"] == "name_changes"]
        source_targets: dict[str, set[str]] = defaultdict(set)
        target_sources: dict[str, set[str]] = defaultdict(set)
        graph_edges: list[tuple[str, str]] = []
        for event in name_events:
            old = _clean_symbol(event.get("source_symbol"))
            new = _clean_symbol(event.get("target_symbol"))
            if old is None or new is None:
                continue
            source_targets[old].add(new)
            target_sources[new].add(old)
            graph_edges.append((old, new))
        cycles = _cycle_nodes(graph_edges)
        anomaly_casefold = {symbol.casefold() for symbol in native.excluded_symbols}
        rename_candidates = [
            _classify_name_change(
                event,
                observed=observed,
                source_target_count={key: len(value) for key, value in source_targets.items()},
                target_source_count={key: len(value) for key, value in target_sources.items()},
                cycle_nodes=cycles,
                anomaly_casefold_keys=anomaly_casefold,
            )
            for event in name_events
        ]
        rename_symbols = {
            symbol
            for event in name_events
            for symbol in (
                _clean_symbol(event.get("source_symbol")),
                _clean_symbol(event.get("target_symbol")),
            )
            if symbol is not None
        }
        segment_event_types_by_symbol: dict[str, set[str]] = defaultdict(set)
        for event in events:
            event_type = str(event.get("event_type") or "")
            if event_type not in INITIAL_SEGMENT_REQUIRED_EVENT_TYPES:
                continue
            for field in ("source_symbol", "target_symbol", "alternate_symbol"):
                event_symbol = _clean_symbol(event.get(field))
                if event_symbol is not None:
                    segment_event_types_by_symbol[event_symbol].add(event_type)

        assets_path = Path(str((source.get("assets_parquet") or {}).get("path") or ""))
        con = connect_utc(":memory:")
        try:
            assets = con.execute(
                "SELECT * FROM read_parquet(?, hive_partitioning=false) ORDER BY symbol, "
                "requested_status, provider_asset_id",
                [str(assets_path)],
            ).fetchdf()
        finally:
            con.close()
        asset_ids_by_symbol: dict[str, set[str]] = defaultdict(set)
        symbols_by_asset_id: dict[str, set[str]] = defaultdict(set)
        names_by_symbol: dict[str, set[str]] = defaultdict(set)
        classes_by_symbol: dict[str, set[str]] = defaultdict(set)
        statuses_by_symbol: dict[str, set[str]] = defaultdict(set)
        for row in assets.to_dict(orient="records"):
            symbol = _clean_symbol(row.get("symbol"))
            if symbol is None:
                continue
            asset_id = str(row.get("provider_asset_id") or "").strip()
            if asset_id:
                asset_ids_by_symbol[symbol].add(asset_id)
                symbols_by_asset_id[asset_id].add(symbol)
            name = str(row.get("name") or "").strip()
            if name:
                names_by_symbol[symbol].add(name)
            asset_class = str(row.get("asset_class") or "").strip()
            if asset_class:
                classes_by_symbol[symbol].add(asset_class)
            status = str(row.get("provider_status") or "").strip()
            if status:
                statuses_by_symbol[symbol].add(status)

        map_rows: list[dict[str, object]] = []
        for row in daily.observed.to_dict(orient="records"):
            symbol = str(row["symbol"])
            reasons: list[str] = []
            ids = sorted(asset_ids_by_symbol.get(symbol, set()))
            if not ids:
                reasons.append("NO_PROVIDER_ASSET_ID")
            elif len(ids) > 1:
                reasons.append("MULTIPLE_PROVIDER_ASSET_IDS_FOR_SYMBOL")
            if any(len(symbols_by_asset_id[asset_id]) > 1 for asset_id in ids):
                reasons.append("PROVIDER_ASSET_ID_MAPS_MULTIPLE_SYMBOLS")
            if symbol in rename_symbols:
                reasons.append("NAME_CHANGE_REQUIRES_SEPARATE_SEGMENT_POLICY")
            for event_type in sorted(segment_event_types_by_symbol.get(symbol, set())):
                if event_type != "name_changes":
                    reasons.append(
                        "CORPORATE_ACTION_REQUIRES_SEPARATE_SEGMENT_POLICY:"
                        f"{event_type}"
                    )
            if symbol in native.excluded_symbols:
                reasons.append("ACQUISITION_OR_RESPONSE_QUARANTINE")
            classes = sorted(classes_by_symbol.get(symbol, set()))
            if classes != ["us_equity"]:
                reasons.append("ASSET_CLASS_NOT_EXACT_US_EQUITY")
            security_type, type_reasons = _security_type_from_names(
                names_by_symbol.get(symbol, set())
            )
            reasons.extend(type_reasons)
            reasons = sorted(set(reasons))
            clear = not reasons
            instrument_id = f"alpaca_asset:{ids[0]}" if clear else None
            map_rows.append(
                {
                    "symbol": symbol,
                    "instrument_id": instrument_id,
                    "identity_clear": clear,
                    "identity_status": "DIRECT_PROVIDER_ASSET_ID" if clear else "EXCLUDED",
                    "security_type": security_type,
                    "provider_asset_ids": ",".join(ids),
                    "provider_statuses": ",".join(sorted(statuses_by_symbol.get(symbol, set()))),
                    "asset_classes": ",".join(classes),
                    "asset_names_json": json.dumps(
                        sorted(names_by_symbol.get(symbol, set())), separators=(",", ":")
                    ),
                    "first_session": row["first_session"],
                    "last_session": row["last_session"],
                    "observed_sessions": int(row["observed_sessions"]),
                    "missing_sessions_between_bounds": int(
                        row["missing_sessions_between_bounds"]
                    ),
                    "maximum_internal_gap_sessions": int(
                        row["maximum_internal_gap_sessions"]
                    ),
                    "reason_codes": ",".join(reasons),
                }
            )
        symbol_map = pd.DataFrame(map_rows)

        event_frame = pd.DataFrame(events)
        relationship_frame = pd.DataFrame(relationships)
        rename_frame = pd.DataFrame(rename_candidates)
        if event_frame.empty:
            event_frame = pd.DataFrame(
                columns=[
                    "event_key",
                    "provider_event_id",
                    "event_type",
                    "identity_semantics",
                    "event_date",
                    "source_symbol",
                    "target_symbol",
                ]
            )
        if relationship_frame.empty:
            relationship_frame = pd.DataFrame(
                columns=[
                    "relationship_id",
                    "event_key",
                    "event_type",
                    "event_date",
                    "source_symbol",
                    "target_symbol",
                ]
            )
        if rename_frame.empty:
            rename_frame = pd.DataFrame(
                columns=[
                    "event_key",
                    "event_date",
                    "old_symbol",
                    "new_symbol",
                    "status",
                    "safe_to_stitch",
                    "review_reasons",
                ]
            )
        event_record = _write_frame(
            self.identity_event_path,
            event_frame,
            order_by="event_type, event_date NULLS LAST, event_key",
        )
        relationship_record = _write_frame(
            self.identity_relationship_path,
            relationship_frame,
            order_by="event_date NULLS LAST, event_type, relationship_id",
        )
        rename_record = _write_frame(
            self.rename_candidate_path,
            rename_frame,
            order_by="event_date NULLS LAST, old_symbol NULLS LAST, new_symbol NULLS LAST, event_key",
        )
        map_record = _write_frame(
            self.identity_map_path,
            symbol_map,
            order_by="symbol",
        )

        provider_ids = [
            str(event["provider_event_id"])
            for event in events
            if event.get("provider_event_id") is not None
        ]
        duplicate_event_ids = sum(
            count - 1 for count in Counter(provider_ids).values() if count > 1
        )
        checks = {
            "unknown_corporate_action_types_zero": not unknown_types,
            "duplicate_provider_event_ids_zero": duplicate_event_ids == 0,
            "identity_map_has_no_duplicate_symbols": not symbol_map.duplicated(["symbol"]).any(),
            "clear_identity_has_unique_instrument_ids": not symbol_map.loc[
                symbol_map["identity_clear"], "instrument_id"
            ].duplicated().any(),
            "clear_identity_is_common_stock": bool(
                symbol_map.loc[symbol_map["identity_clear"], "security_type"]
                .eq("COMMON_STOCK")
                .all()
            ),
        }
        identity_fingerprint = _stable_hash(
            {
                "contract": IDENTITY_LIFECYCLE_CONTRACT,
                "native_acceptance_fingerprint": native.report["acceptance_fingerprint"],
                "daily_quality_fingerprint": daily.report["quality_fingerprint"],
                "events_sha256": event_record["sha256"],
                "relationships_sha256": relationship_record["sha256"],
                "rename_candidates_sha256": rename_record["sha256"],
                "symbol_identity_map_sha256": map_record["sha256"],
                "checks": checks,
                "continuity_policy": (
                    "one-direct-provider-asset-id; one-literal-symbol; common-stock-name; "
                    "no-continuity-changing-action-stitch; source-anomalies-excluded"
                ),
            }
        )
        report = {
            "contract": IDENTITY_LIFECYCLE_CONTRACT,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "status": "PASS" if all(checks.values()) else "FAIL",
            "native_acceptance_fingerprint": native.report["acceptance_fingerprint"],
            "daily_quality_contract": daily.report["contract"],
            "daily_quality_fingerprint": daily.report["quality_fingerprint"],
            "identity_fingerprint": identity_fingerprint,
            "corporate_action_events": len(events),
            "event_type_counts": dict(sorted(Counter(str(x["event_type"]) for x in events).items())),
            "unknown_event_types": sorted(unknown_types),
            "duplicate_provider_event_ids": duplicate_event_ids,
            "relationship_rows": len(relationships),
            "name_change_candidates": len(rename_candidates),
            "safe_name_change_evidence_not_stitched": sum(
                bool(row.get("safe_to_stitch")) for row in rename_candidates
            ),
            "observed_symbols": len(symbol_map),
            "identity_clear_common_stock_symbols": int(symbol_map["identity_clear"].sum()),
            "excluded_symbols": int((~symbol_map["identity_clear"]).sum()),
            "exclusion_reason_counts": dict(
                sorted(
                    Counter(
                        reason
                        for value in symbol_map.loc[
                            ~symbol_map["identity_clear"], "reason_codes"
                        ].astype(str)
                        for reason in value.split(",")
                        if reason
                    ).items()
                )
            ),
            "events": event_record,
            "relationships": relationship_record,
            "rename_candidates": rename_record,
            "symbol_identity_map": map_record,
            "checks": checks,
            "continuity_policy": (
                "Only one exact provider asset ID mapped to one literal symbol is accepted in "
                "the initial V2 policy. "
                "Name changes, mergers, reorganizations, derived-security distributions, "
                "termination/redemption events, ticker reuse, ambiguous security type, and "
                "source anomalies are preserved and excluded rather than silently stitched."
            ),
            "inactive_assets_filtered_out": False,
            "v1_rows_read": 0,
            "protected_return_rows_read": 0,
            "production_promoted": False,
        }
        atomic_write_text(
            self.identity_report_path,
            json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
            fsync=True,
        )
        if report["status"] != "PASS":
            failed = [name for name, passed in checks.items() if not passed]
            raise AlpacaV2ValidationError(
                "V2 identity/lifecycle validation failed: " + ", ".join(failed)
            )
        return IdentityLifecycleResult(report=report, symbol_map=symbol_map)

    def build_research_daily(
        self,
        native: NativeAcceptanceResult,
        daily: DailyQualityResult,
        identity: IdentityLifecycleResult,
        split: SplitDailyResult,
    ) -> ResearchDailyResult:
        if split.report.get("status") != "COMPLETE":
            raise AlpacaV2NotCompleteError("split-adjusted daily acquisition is not complete")
        native_fingerprint = native.report.get("acceptance_fingerprint")
        if (
            daily.report.get("native_acceptance_fingerprint") != native_fingerprint
            or identity.report.get("native_acceptance_fingerprint") != native_fingerprint
            or (split.report.get("policy") or {}).get(
                "native_acceptance_fingerprint"
            )
            != native_fingerprint
            or daily.report.get("quality_fingerprint")
            != identity.report.get("daily_quality_fingerprint")
        ):
            raise AlpacaV2ValidationError(
                "V2 post-build stages do not bind the same accepted native/daily source"
            )
        raw_inventory = native.inventory.loc[
            native.inventory["canonical_timeframe"] == "1d"
        ].copy()
        adjusted_inventory = split.inventory.copy()
        if raw_inventory.empty or adjusted_inventory.empty:
            raise AlpacaV2ValidationError("raw/adjusted daily inventories must be non-empty")
        raw_ids = set(raw_inventory["unit_id"].astype(str))
        adjusted_ids = set(adjusted_inventory["unit_id"].astype(str))
        if raw_ids != adjusted_ids:
            raise AlpacaV2ValidationError("raw and split-adjusted daily unit inventories differ")

        split_excluded_symbols = {
            str(value) for value in split.report.get("excluded_symbols") or []
        }
        eligible = identity.symbol_map.loc[
            identity.symbol_map["identity_clear"]
            & identity.symbol_map["security_type"].eq("COMMON_STOCK")
            & identity.symbol_map["missing_sessions_between_bounds"].eq(0)
            & ~identity.symbol_map["symbol"].isin(split_excluded_symbols)
        ].copy()
        if eligible.empty:
            raise AlpacaV2ValidationError(
                "V2 identity policy produced no contiguous identity-clear common stocks"
            )

        raw_paths = tuple(Path(str(value)) for value in raw_inventory["canonical_path"])
        adjusted_paths = tuple(
            Path(str(value)) for value in adjusted_inventory["canonical_path"]
        )
        raw_sql = f"read_parquet({_sql_paths(raw_paths)}, hive_partitioning=false)"
        adjusted_sql = (
            f"read_parquet({_sql_paths(adjusted_paths)}, hive_partitioning=false)"
        )
        con = connect_utc(":memory:")
        con.execute("PRAGMA threads=4")
        con.register("eligible_reconcile", eligible[["symbol"]])
        try:
            adjusted_description = con.execute(
                f"DESCRIBE SELECT * FROM {adjusted_sql}"
            ).fetchall()
            if not canonical_stock_daily_schema_matches(adjusted_description):
                raise AlpacaV2ValidationError(
                    "split-adjusted daily physical schema is not exact"
                )
            counts = con.execute(
                f"""
                SELECT
                    (SELECT count(*) FROM {raw_sql} r
                     JOIN eligible_reconcile e USING (symbol)) AS eligible_raw_rows,
                    (SELECT count(*) FROM {adjusted_sql} a
                     JOIN eligible_reconcile e USING (symbol)) AS eligible_adjusted_rows,
                    (SELECT count(*) FROM {raw_sql} r
                     JOIN eligible_reconcile e USING (symbol)
                     LEFT JOIN {adjusted_sql} a USING (symbol, session_date)
                     WHERE a.symbol IS NULL) AS missing_adjusted,
                    (SELECT count(*) FROM {adjusted_sql} a
                     JOIN eligible_reconcile e USING (symbol)
                     LEFT JOIN {raw_sql} r USING (symbol, session_date)
                     WHERE r.symbol IS NULL) AS missing_raw,
                    (SELECT count(*) FROM {adjusted_sql} a
                     LEFT JOIN {raw_sql} r USING (symbol, session_date)
                     WHERE r.symbol IS NULL) AS any_adjusted_key_missing_raw
                """
            ).fetchone()
            factor_failures = int(
                con.execute(
                    f"""
                    WITH paired AS (
                        SELECT r.symbol, r.session_date,
                               a.open / r.open AS factor_open,
                               a.high / r.high AS factor_high,
                               a.low / r.low AS factor_low,
                               a.close / r.close AS factor_close,
                               a.volume AS adjusted_volume,
                               r.volume AS raw_volume,
                               a.provider, a.dataset, a.timeframe, a.session_segment,
                               a.is_adjusted, a.source_id
                        FROM {raw_sql} r
                        JOIN {adjusted_sql} a USING (symbol, session_date)
                        JOIN eligible_reconcile e ON e.symbol = r.symbol
                    )
                    SELECT count(*)
                    FROM paired
                    WHERE NOT isfinite(factor_close) OR factor_close <= 0
                       OR abs(factor_open - factor_close) > 1e-5
                       OR abs(factor_high - factor_close) > 1e-5
                       OR abs(factor_low - factor_close) > 1e-5
                       OR (
                           raw_volume > 0
                           AND abs(adjusted_volume * factor_close - raw_volume)
                               > greatest(1.0, abs(raw_volume)) * 1e-5
                       )
                       OR provider <> 'alpaca'
                       OR dataset <> 'stock_daily_aggregates_split_adjusted'
                       OR timeframe <> '1d'
                       OR session_segment <> 'regular'
                       OR is_adjusted <> TRUE
                       OR source_id NOT LIKE 'alpaca:sip:1Day:split:asof=-:v2:unit=%'
                    """
                ).fetchone()[0]
            )
            adjusted_duplicates = int(
                con.execute(
                    f"""
                    SELECT coalesce(sum(n - 1), 0)
                    FROM (
                        SELECT symbol, session_date, count(*) AS n
                        FROM {adjusted_sql}
                        GROUP BY symbol, session_date
                        HAVING count(*) > 1
                    )
                    """
                ).fetchone()[0]
            )
            adjusted_value_failures = int(
                con.execute(
                    f"""
                    SELECT count(*)
                    FROM {adjusted_sql}
                    WHERE provider <> 'alpaca'
                       OR dataset <> 'stock_daily_aggregates_split_adjusted'
                       OR timeframe <> '1d'
                       OR session_segment <> 'regular'
                       OR is_adjusted <> TRUE
                       OR source_id NOT LIKE 'alpaca:sip:1Day:split:asof=-:v2:unit=%'
                       OR NOT isfinite(open) OR NOT isfinite(high)
                       OR NOT isfinite(low) OR NOT isfinite(close)
                       OR NOT isfinite(volume)
                       OR open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
                       OR volume < 0 OR high < greatest(open, close)
                       OR low > least(open, close) OR high < low
                    """
                ).fetchone()[0]
            )
        finally:
            con.unregister("eligible_reconcile")
            con.close()
        assert counts is not None
        checks = {
            "eligible_raw_adjusted_row_counts_equal": int(counts[0]) == int(counts[1]),
            "eligible_raw_keys_missing_adjusted_zero": int(counts[2]) == 0,
            "eligible_adjusted_keys_missing_raw_zero": int(counts[3]) == 0,
            "all_adjusted_keys_exist_in_raw": int(counts[4]) == 0,
            "split_factor_and_provenance_failures_zero": factor_failures == 0,
            "adjusted_duplicates_zero": adjusted_duplicates == 0,
            "adjusted_values_and_provenance_valid": adjusted_value_failures == 0,
        }
        if not all(checks.values()):
            raise AlpacaV2ValidationError(
                "raw/split-adjusted daily reconciliation failed: "
                + ", ".join(name for name, passed in checks.items() if not passed)
            )

        start = date.fromisoformat(str(native.report["start_date"]))
        source_cutoff = date.fromisoformat(str(native.report["cutoff_session"]))
        if (
            daily.report.get("start_date") != start.isoformat()
            or daily.report.get("cutoff_session") != source_cutoff.isoformat()
        ):
            raise AlpacaV2ValidationError(
                "V2 daily quality scope disagrees with native acceptance"
            )
        cutoff = min(source_cutoff, V2_REFERENCE_DEVELOPMENT_END)
        if start > cutoff:
            raise AlpacaV2ValidationError(
                "V2 source begins after the frozen reference DEVELOPMENT cutoff"
            )
        schedule = pd.DataFrame(
            [
                {
                    "session_date": session,
                    "signal_available_at_utc": self.calendar.regular_open_close(session)[1],
                }
                for session in self.calendar.sessions_in_range(start, cutoff)
            ]
        )
        source_fingerprint = _stable_hash(
            {
                "contract": RESEARCH_DAILY_CONTRACT,
                "native_acceptance_fingerprint": native.report["acceptance_fingerprint"],
                "daily_quality_fingerprint": daily.report["quality_fingerprint"],
                "identity_fingerprint": identity.report["identity_fingerprint"],
                "split_daily_fingerprint": split.report["source_fingerprint"],
                "source_cutoff_session": source_cutoff.isoformat(),
                "research_cutoff_session": cutoff.isoformat(),
                "protected_row_materialization": "FORBIDDEN",
                "split_source_excluded_symbols": sorted(split_excluded_symbols),
                "eligibility_policy": (
                    "direct-provider-asset-id; exact common-stock name; no continuity-"
                    "changing action stitch; no acquisition anomaly; no split-source "
                    "anomaly; zero internal XNYS daily gaps"
                ),
            }
        )
        root = self.layout.derived / "research_daily" / source_fingerprint[:16]
        manifest_path = self.layout.manifests / "research_daily.json"
        if manifest_path.is_file():
            existing = _read_json(manifest_path, "V2 research daily manifest")
            if existing.get("source_fingerprint") != source_fingerprint:
                raise AlpacaV2ValidationError(
                    "existing V2 research daily manifest binds a different source; "
                    "preserve it and create a new generation"
                )
            for record in existing.get("partitions") or []:
                path = Path(str(record.get("path") or ""))
                if not path.is_file() or _sha256_file(path) != record.get("sha256"):
                    raise AlpacaV2ValidationError(
                        "existing V2 research daily partition hash mismatch"
                    )
            return ResearchDailyResult(report=existing)

        lineage_id = f"alpaca-v2:{source_fingerprint}"
        con = connect_utc(":memory:")
        con.execute("PRAGMA threads=4")
        con.register(
            "eligible_identity",
            eligible[
                [
                    "symbol",
                    "instrument_id",
                    "security_type",
                    "identity_clear",
                ]
            ],
        )
        con.register("v2_schedule", schedule)
        partitions: list[dict[str, object]] = []
        total_rows = 0
        try:
            for year in range(start.year, cutoff.year + 1):
                year_start = max(start, date(year, 1, 1))
                year_end = min(cutoff, date(year, 12, 31))
                target = root / f"year={year:04d}" / "part-000.parquet"
                target.parent.mkdir(parents=True, exist_ok=True)
                temp = unique_temp_path(target)
                con.execute(
                    f"""
                    COPY (
                        SELECT
                            i.instrument_id::VARCHAR AS instrument_id,
                            a.symbol::VARCHAR AS ticker,
                            a.session_date::DATE AS session_date,
                            a.timestamp_utc::TIMESTAMPTZ AS timestamp_utc,
                            s.signal_available_at_utc::TIMESTAMPTZ
                                AS signal_available_at_utc,
                            a.open::DOUBLE AS open,
                            a.high::DOUBLE AS high,
                            a.low::DOUBLE AS low,
                            a.close::DOUBLE AS close,
                            a.volume::DOUBLE AS volume,
                            r.close::DOUBLE AS unadjusted_close,
                            TRUE::BOOLEAN AS pit_active,
                            CASE
                                WHEN i.security_type = 'COMMON_STOCK' THEN 'CS'
                                ELSE i.security_type
                            END::VARCHAR AS security_type,
                            TRUE::BOOLEAN AS identity_clear,
                            'SPLIT_ADJUSTED'::VARCHAR AS price_adjustment_mode,
                            {sql_string(lineage_id)}::VARCHAR AS raw_price_lineage_id,
                            a.provider::VARCHAR AS source_provider,
                            a.dataset::VARCHAR AS source_dataset,
                            a.source_id::VARCHAR AS adjusted_source_id
                        FROM {adjusted_sql} a
                        JOIN {raw_sql} r USING (symbol, session_date)
                        JOIN eligible_identity i ON i.symbol = a.symbol
                        JOIN v2_schedule s USING (session_date)
                        WHERE a.session_date BETWEEN DATE '{year_start}' AND DATE '{year_end}'
                        ORDER BY i.instrument_id, a.session_date
                    ) TO {sql_string(temp)}
                    (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)
                    """
                )
                rows = int(
                    con.execute(
                        f"SELECT count(*) FROM read_parquet({sql_string(temp)}, "
                        "hive_partitioning=false)"
                    ).fetchone()[0]
                )
                if rows == 0:
                    temp.unlink(missing_ok=True)
                    continue
                replace_with_retry(temp, target)
                total_rows += rows
                partitions.append(
                    {
                        "year": year,
                        "path": str(target),
                        "sha256": _sha256_file(target),
                        "bytes": target.stat().st_size,
                        "rows": rows,
                    }
                )
        finally:
            con.unregister("eligible_identity")
            con.unregister("v2_schedule")
            con.close()
        if total_rows == 0:
            raise AlpacaV2ValidationError("V2 research daily materialization produced no rows")

        report = {
            "contract": RESEARCH_DAILY_CONTRACT,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "status": "PASS",
            "source_fingerprint": source_fingerprint,
            "native_acceptance_fingerprint": native.report["acceptance_fingerprint"],
            "split_daily_fingerprint": split.report["source_fingerprint"],
            "start_date": start.isoformat(),
            "cutoff_session": cutoff.isoformat(),
            "source_cutoff_session": source_cutoff.isoformat(),
            "development_only": True,
            "protected_return_rows_materialized": 0,
            "eligible_symbols": len(eligible),
            "excluded_noncontiguous_symbols": int(
                (
                    identity.symbol_map["identity_clear"]
                    & identity.symbol_map["missing_sessions_between_bounds"].gt(0)
                ).sum()
            ),
            "excluded_split_source_symbols": sorted(split_excluded_symbols),
            "excluded_split_source_symbol_count": len(split_excluded_symbols),
            "research_rows": total_rows,
            "partitions": partitions,
            "checks": checks,
            "raw_execution_state_preserved_separately": True,
            "analytical_adjustment": "provider-native split adjustment only",
            "return_economics": (
                "SPLIT_ADJUSTED_PRICE_RETURN_WITHOUT_CASH_DISTRIBUTION_CREDIT"
            ),
            "cash_dividend_credits_materialized": False,
            "identity_policy": identity.report["continuity_policy"],
            "current_active_status_used_as_historical_filter": False,
            "master_protected_return_rows_read": 0,
            "historical_performance_opened": False,
            "strategy_authority_promoted": False,
            "production_promoted": False,
            "paper_authority": False,
            "live_authority": False,
            "v1_rows_read": 0,
            "v1_ancestry": "FORBIDDEN",
        }
        atomic_write_text(
            manifest_path,
            json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
            fsync=True,
        )
        return ResearchDailyResult(report=report)


class AlpacaV2SplitDailyAcquirer:
    """Capture provider-native split-adjusted daily bars as a separate V2 layer."""

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        client: AlpacaMarketDataClient | None = None,
    ) -> None:
        self.settings = settings
        self.layout = V2Layout.beneath((settings.project_root / "data").resolve())
        self.client = client
        self.base = AlpacaV2NativeAcquirer(settings)
        self.manifest_path = self.layout.manifests / "split_adjusted_daily.json"
        self.inventory_path = self.layout.validation / "split_adjusted_daily_inventory.parquet"
        self.rejection_path = self.layout.checkpoints / "split_adjusted_daily_rejections.json"

    def _client(self) -> AlpacaMarketDataClient:
        if self.client is None:
            self.client = AlpacaMarketDataClient(self.settings)
        return self.client

    @staticmethod
    def _policy(native: NativeAcceptanceResult) -> dict[str, object]:
        return {
            "contract": SPLIT_DAILY_CONTRACT,
            "native_acceptance_fingerprint": native.report["acceptance_fingerprint"],
            "provider": "alpaca",
            "feed": V2_FEED,
            "timeframe": "1Day",
            "adjustment": "split",
            "asof": V2_ASOF,
            "page_limit": V2_PAGE_LIMIT,
            "pagination": "opaque_next_page_token_until_null",
            "v1_ancestry": "FORBIDDEN",
        }

    def _paths(self, unit: NativeAcquisitionUnit) -> dict[str, Path]:
        partition = Path(f"year={unit.year:04d}") / f"batch={unit.batch_index:04d}"
        prefix = unit.unit_id[:20]
        return {
            "checkpoint": self.layout.checkpoints
            / "split_adjusted_daily_units"
            / partition
            / f"{prefix}.json",
            "work": self.layout.checkpoints / "split_adjusted_daily_work" / prefix,
            "raw_bundle": self.layout.source
            / "bars_split_adjusted"
            / "1d"
            / partition
            / f"{prefix}.concat.json.gz",
            "canonical": self.layout.derived
            / "analytical"
            / "stocks"
            / "1d_split"
            / partition
            / f"{prefix}.parquet",
            "quarantine": self.layout.validation
            / "split_adjusted_daily_quarantine"
            / partition
            / f"{prefix}.jsonl.gz",
        }

    def _load_rejections(self) -> dict[str, dict[str, object]]:
        if not self.rejection_path.is_file():
            return {}
        document = _read_json(self.rejection_path, "split-adjusted rejection registry")
        if document.get("contract") != SPLIT_DAILY_CONTRACT:
            raise AlpacaV2ValidationError("split-adjusted rejection contract drifted")
        result: dict[str, dict[str, object]] = {}
        for symbol, record in (document.get("symbols") or {}).items():
            if not isinstance(record, dict):
                raise AlpacaV2ValidationError("invalid split-adjusted rejection record")
            path = Path(str(record.get("path") or ""))
            _read_gzip_verified(path, str(record.get("sha256") or ""))
            result[str(symbol)] = dict(record)
        return result

    def _persist_rejection(
        self,
        registry: dict[str, dict[str, object]],
        exc: AlpacaInvalidSymbolError,
    ) -> None:
        symbol = exc.symbol
        if symbol in registry:
            return
        path = (
            self.layout.source
            / "quarantine"
            / "split_adjusted_provider_rejections"
            / f"{_sha256_bytes(exc.page.raw_body)}.json.gz"
        )
        record = self.base._persist_api_page(exc.page, path)
        record.update(
            {
                "symbol": symbol,
                "provider_message": exc.provider_message,
                "classification": "PROVIDER_REJECTED_SPLIT_DAILY_LITERAL_NO_SUBSTITUTION",
            }
        )
        registry[symbol] = record
        atomic_write_text(
            self.rejection_path,
            json.dumps(
                {
                    "contract": SPLIT_DAILY_CONTRACT,
                    "updated_at_utc": datetime.now(UTC).isoformat(),
                    "symbols": {key: registry[key] for key in sorted(registry)},
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            fsync=True,
        )

    def _canonicalize(
        self,
        unit: NativeAcquisitionUnit,
        native_paths: list[Path],
        target: Path,
    ) -> dict[str, object]:
        paths = list(native_paths)
        synthetic: Path | None = None
        if not paths:
            synthetic = target.parent / f".{unit.unit_id[:20]}.empty.parquet"
            self.base._write_native_page(synthetic, [])
            paths = [synthetic]
        source_sql = f"read_parquet({_sql_paths(paths)}, hive_partitioning=false)"
        schedule = self.base._session_frame(unit)
        source_id = f"alpaca:sip:1Day:split:asof=-:v2:unit={unit.unit_id}"
        con = connect_utc(":memory:")
        con.register("v2_sessions", schedule)
        try:
            base = f"""
                SELECT
                    p.provider_symbol AS symbol,
                    CAST(s.regular_open_utc AS TIMESTAMPTZ) AS timestamp_utc,
                    CAST(s.session_date AS DATE) AS session_date,
                    '1d'::VARCHAR AS timeframe,
                    'regular'::VARCHAR AS session_segment,
                    p.open::DOUBLE AS open,
                    p.high::DOUBLE AS high,
                    p.low::DOUBLE AS low,
                    p.close::DOUBLE AS close,
                    p.volume::DOUBLE AS volume,
                    p.vwap::DOUBLE AS vwap,
                    p.transaction_count::BIGINT AS transaction_count,
                    'alpaca'::VARCHAR AS provider,
                    'stock_daily_aggregates_split_adjusted'::VARCHAR AS dataset,
                    {sql_string(source_id)}::VARCHAR AS source_id,
                    TRUE::BOOLEAN AS is_adjusted,
                    p.provider_timestamp_utc::TIMESTAMPTZ AS provider_timestamp_utc
                FROM {source_sql} p
                JOIN v2_sessions s
                  ON CAST(p.provider_timestamp_utc AS DATE) = CAST(s.session_date AS DATE)
            """
            outside = int(
                con.execute(
                    f"""
                    SELECT count(*) FROM {source_sql} p
                    LEFT JOIN v2_sessions s
                      ON CAST(p.provider_timestamp_utc AS DATE) = CAST(s.session_date AS DATE)
                    WHERE s.session_date IS NULL
                    """
                ).fetchone()[0]
            )
            duplicates = int(
                con.execute(
                    f"""
                    SELECT coalesce(sum(n - 1), 0)
                    FROM (
                        SELECT symbol, timestamp_utc, count(*) AS n
                        FROM ({base}) GROUP BY symbol, timestamp_utc HAVING count(*) > 1
                    )
                    """
                ).fetchone()[0]
            )
            input_rows = int(con.execute(f"SELECT count(*) FROM {source_sql}").fetchone()[0])
            if duplicates or outside:
                return {
                    "status": "BLOCKED_VALIDATION",
                    "input_rows": input_rows,
                    "canonical_rows": 0,
                    "duplicate_rows": duplicates,
                    "outside_session_rows": outside,
                    "path": None,
                    "sha256": None,
                    "bytes": 0,
                }
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = unique_temp_path(target)
            con.execute(
                f"COPY (SELECT * FROM ({base}) ORDER BY symbol, timestamp_utc) "
                f"TO {sql_string(temp)} (FORMAT PARQUET, COMPRESSION ZSTD, "
                "ROW_GROUP_SIZE 100000)"
            )
            description = con.execute(
                f"DESCRIBE SELECT * FROM read_parquet({sql_string(temp)}, "
                "hive_partitioning=false)"
            ).fetchall()
            if not canonical_stock_daily_schema_matches(description):
                temp.unlink(missing_ok=True)
                raise AlpacaV2ValidationError(
                    "split-adjusted daily unit does not match canonical schema"
                )
            rows = int(
                con.execute(
                    f"SELECT count(*) FROM read_parquet({sql_string(temp)}, "
                    "hive_partitioning=false)"
                ).fetchone()[0]
            )
            replace_with_retry(temp, target)
        finally:
            con.unregister("v2_sessions")
            con.close()
            if synthetic is not None:
                synthetic.unlink(missing_ok=True)
        return {
            "status": "COMPLETE",
            "input_rows": input_rows,
            "canonical_rows": rows,
            "duplicate_rows": 0,
            "outside_session_rows": 0,
            "path": str(target),
            "sha256": _sha256_file(target),
            "bytes": target.stat().st_size,
        }

    def _validate_checkpoint(
        self,
        unit: NativeAcquisitionUnit,
        checkpoint: dict[str, Any],
        policy_sha256: str,
    ) -> bool:
        if (
            checkpoint.get("contract") != SPLIT_DAILY_UNIT_CONTRACT
            or checkpoint.get("unit_id") != unit.unit_id
            or checkpoint.get("policy_sha256") != policy_sha256
        ):
            raise AlpacaV2ValidationError(
                f"stale split-adjusted daily checkpoint: {unit.label}"
            )
        status = str(checkpoint.get("status") or "")
        if status in {"COMPLETE", "COMPLETE_WITH_QUARANTINE", "BLOCKED_VALIDATION"}:
            bundle = checkpoint.get("raw_bundle") or {}
            bundle_path = Path(str(bundle.get("path") or ""))
            if not bundle_path.is_file() or _sha256_file(bundle_path) != bundle.get("sha256"):
                raise AlpacaV2ValidationError(
                    f"split-adjusted raw bundle hash mismatch: {unit.label}"
                )
            canonical = checkpoint.get("canonical") or {}
            if status != "BLOCKED_VALIDATION":
                path = Path(str(canonical.get("path") or ""))
                if not path.is_file() or _sha256_file(path) != canonical.get("sha256"):
                    raise AlpacaV2ValidationError(
                        f"split-adjusted canonical hash mismatch: {unit.label}"
                    )
            quarantine = checkpoint.get("quarantine")
            if isinstance(quarantine, dict):
                path = Path(str(quarantine.get("path") or ""))
                if not path.is_file() or _sha256_file(path) != quarantine.get("sha256"):
                    raise AlpacaV2ValidationError(
                        f"split-adjusted quarantine hash mismatch: {unit.label}"
                    )
            return True
        if status != "IN_PROGRESS":
            raise AlpacaV2ValidationError(
                f"unknown split-adjusted checkpoint status {status}: {unit.label}"
            )
        for page in checkpoint.get("pages") or []:
            _read_gzip_verified(
                Path(str(page.get("raw_path") or "")),
                str(page.get("raw_sha256") or ""),
            )
            native = Path(str(page.get("native_path") or ""))
            if not native.is_file() or _sha256_file(native) != page.get("native_sha256"):
                raise AlpacaV2ValidationError(
                    f"split-adjusted in-progress page hash mismatch: {unit.label}"
                )
        return False

    def _acquire_unit(
        self,
        unit: NativeAcquisitionUnit,
        *,
        policy_sha256: str,
        registry: dict[str, dict[str, object]],
        excluded_symbols: frozenset[str],
        stop_requested: Callable[[], bool],
        progress: Callable[[dict[str, object]], None] | None,
    ) -> dict[str, Any]:
        paths = self._paths(unit)
        checkpoint_path = paths["checkpoint"]
        work = paths["work"]
        work.mkdir(parents=True, exist_ok=True)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        if checkpoint_path.is_file():
            checkpoint = _read_json(checkpoint_path, f"split daily checkpoint {unit.label}")
            if self._validate_checkpoint(unit, checkpoint, policy_sha256):
                return checkpoint
        else:
            request_symbols = [
                symbol
                for symbol in unit.symbols
                if symbol not in excluded_symbols and symbol not in registry
            ]
            checkpoint = {
                "contract": SPLIT_DAILY_UNIT_CONTRACT,
                "status": "IN_PROGRESS",
                "unit_id": unit.unit_id,
                "unit": asdict(unit),
                "policy_sha256": policy_sha256,
                "request_symbols": request_symbols,
                "provider_rejections": [],
                "pages": [],
                "next_page_token": None,
                "pagination_complete": not request_symbols,
                "started_at_utc": datetime.now(UTC).isoformat(),
            }
            atomic_write_text(
                checkpoint_path,
                json.dumps(checkpoint, indent=2, sort_keys=True) + "\n",
                fsync=True,
            )
        pages = list(checkpoint.get("pages") or [])
        request_symbols = [str(value) for value in checkpoint.get("request_symbols") or []]
        token = checkpoint.get("next_page_token")
        seen_tokens = {
            str(record["page_token_used"])
            for record in pages
            if record.get("page_token_used") is not None
        }
        request_start, request_end = self.base._request_bounds(unit)
        while not bool(checkpoint.get("pagination_complete")):
            self.base._require_disk()
            try:
                page = self._client().historical_bar_page(
                    symbols=request_symbols,
                    start=request_start,
                    end=request_end,
                    page_token=str(token) if token is not None else None,
                    timeframe="1Day",
                    feed=V2_FEED,
                    adjustment="split",
                    asof=V2_ASOF,
                    page_limit=V2_PAGE_LIMIT,
                )
            except AlpacaInvalidSymbolError as exc:
                if pages or exc.symbol not in request_symbols:
                    raise
                self._persist_rejection(registry, exc)
                request_symbols = [value for value in request_symbols if value != exc.symbol]
                checkpoint["request_symbols"] = request_symbols
                checkpoint["provider_rejections"] = [
                    {"symbol": symbol, **registry[symbol]}
                    for symbol in unit.symbols
                    if symbol in registry
                ]
                checkpoint["pagination_complete"] = not request_symbols
                atomic_write_text(
                    checkpoint_path,
                    json.dumps(checkpoint, indent=2, sort_keys=True) + "\n",
                    fsync=True,
                )
                continue
            page_index = len(pages)
            raw_path = work / f"page_{page_index:06d}.json.gz"
            raw_record = self.base._persist_api_page(page, raw_path)
            rows, anomalies, returned_rows = self.base._flatten_bar_page(
                page,
                requested_symbols=tuple(request_symbols),
                page_index=page_index,
                raw_sha256=str(raw_record["sha256"]),
            )
            native_path = work / f"page_{page_index:06d}.parquet"
            self.base._write_native_page(native_path, rows)
            quarantine = self.base._write_quarantine(
                work / f"page_{page_index:06d}.quarantine.jsonl.gz", anomalies
            )
            next_token = page.next_page_token
            if next_token is not None and (next_token in seen_tokens or next_token == token):
                raise AlpacaV2ValidationError(
                    "split-adjusted daily pagination repeated a token"
                )
            page_record = {
                "page_index": page_index,
                "page_token_used": token,
                "next_page_token": next_token,
                "request_url": page.url,
                "http_status": page.http_status,
                "raw_path": str(raw_path),
                "raw_sha256": raw_record["sha256"],
                "native_path": str(native_path),
                "native_sha256": _sha256_file(native_path),
                "native_bytes": native_path.stat().st_size,
                "returned_rows": returned_rows,
                "accepted_rows": len(rows),
                "quarantined_rows": len(anomalies),
                "quarantine": quarantine,
            }
            pages.append(page_record)
            if token is not None:
                seen_tokens.add(str(token))
            token = next_token
            checkpoint.update(
                {
                    "pages": pages,
                    "next_page_token": token,
                    "pagination_complete": token is None,
                    "updated_at_utc": datetime.now(UTC).isoformat(),
                }
            )
            atomic_write_text(
                checkpoint_path,
                json.dumps(checkpoint, indent=2, sort_keys=True) + "\n",
                fsync=True,
            )
            if progress is not None:
                progress(
                    {
                        "event": "split_page",
                        "unit": unit.label,
                        "page": page_index + 1,
                        "rows": len(rows),
                    }
                )
            if stop_requested():
                raise V2TimeLimitReached(
                    "split-adjusted daily time limit reached after a page checkpoint"
                )

        native_paths = [Path(str(record["native_path"])) for record in pages]
        canonical = self._canonicalize(unit, native_paths, paths["canonical"])
        raw_bundle = self.base._bundle_gzip_members(
            [Path(str(record["raw_path"])) for record in pages], paths["raw_bundle"]
        )
        quarantine_paths = [
            Path(str(record["quarantine"]["path"]))
            for record in pages
            if isinstance(record.get("quarantine"), dict)
        ]
        quarantine: dict[str, object] | None = None
        if quarantine_paths:
            quarantine = self.base._bundle_gzip_members(
                quarantine_paths, paths["quarantine"]
            )
            quarantine["records"] = sum(
                int(record.get("quarantined_rows", 0)) for record in pages
            )
        rejected = list(checkpoint.get("provider_rejections") or [])
        quarantined_rows = sum(int(record.get("quarantined_rows", 0)) for record in pages)
        if canonical["status"] == "BLOCKED_VALIDATION":
            status = "BLOCKED_VALIDATION"
        elif rejected or quarantined_rows:
            status = "COMPLETE_WITH_QUARANTINE"
        else:
            status = "COMPLETE"
        completed = {
            "contract": SPLIT_DAILY_UNIT_CONTRACT,
            "status": status,
            "unit_id": unit.unit_id,
            "unit": asdict(unit),
            "policy_sha256": policy_sha256,
            "request_symbols": request_symbols,
            "provider_rejections": rejected,
            "page_count": len(pages),
            "pages": [
                {
                    key: record.get(key)
                    for key in (
                        "page_index",
                        "page_token_used",
                        "next_page_token",
                        "request_url",
                        "http_status",
                        "raw_sha256",
                        "native_sha256",
                        "native_bytes",
                        "returned_rows",
                        "accepted_rows",
                        "quarantined_rows",
                    )
                }
                for record in pages
            ],
            "raw_bundle": raw_bundle,
            "canonical": canonical,
            "quarantine": quarantine,
            "quarantined_rows": quarantined_rows,
            "completed_at_utc": datetime.now(UTC).isoformat(),
            "v1_ancestry": "FORBIDDEN",
        }
        atomic_write_text(
            checkpoint_path,
            json.dumps(completed, indent=2, sort_keys=True) + "\n",
            fsync=True,
        )
        if status != "BLOCKED_VALIDATION":
            shutil.rmtree(work, ignore_errors=True)
        return completed

    def _report(
        self,
        units: tuple[NativeAcquisitionUnit, ...],
        policy: dict[str, object],
        *,
        stop_reason: str | None,
    ) -> SplitDailyResult:
        rows: list[dict[str, object]] = []
        status_counts: Counter[str] = Counter()
        quarantine_reason_counts: Counter[str] = Counter()
        rejection_registry = self._load_rejections()
        excluded_symbols: set[str] = set(rejection_registry)
        if rejection_registry:
            quarantine_reason_counts["PROVIDER_REJECTED_LITERAL"] = len(
                rejection_registry
            )
        unattributed_quarantine_rows = 0
        canonical_rows = 0
        for unit in units:
            checkpoint_path = self._paths(unit)["checkpoint"]
            if not checkpoint_path.is_file():
                continue
            checkpoint = _read_json(
                checkpoint_path, f"split-adjusted checkpoint {unit.label}"
            )
            status = str(checkpoint.get("status") or "UNKNOWN")
            if status not in {"COMPLETE", "COMPLETE_WITH_QUARANTINE", "BLOCKED_VALIDATION"}:
                continue
            status_counts[status] += 1
            for rejection in checkpoint.get("provider_rejections") or []:
                symbol = (
                    _clean_symbol(rejection.get("symbol"))
                    if isinstance(rejection, dict)
                    else None
                )
                if symbol is None:
                    unattributed_quarantine_rows += 1
                else:
                    excluded_symbols.add(symbol)
                    if symbol not in rejection_registry:
                        unattributed_quarantine_rows += 1
            quarantine = checkpoint.get("quarantine")
            if isinstance(quarantine, dict):
                quarantine_path = Path(str(quarantine.get("path") or ""))
                for record in _iter_gzip_json(quarantine_path):
                    reason = str(record.get("reason") or "UNKNOWN_ROW_ANOMALY")
                    quarantine_reason_counts[reason] += 1
                    symbol = _clean_symbol(record.get("symbol"))
                    if symbol is None:
                        unattributed_quarantine_rows += 1
                    else:
                        excluded_symbols.add(symbol)
            canonical = checkpoint.get("canonical") or {}
            canonical_rows += int(canonical.get("canonical_rows", 0))
            rows.append(
                {
                    "unit_id": unit.unit_id,
                    "year": unit.year,
                    "batch_index": unit.batch_index,
                    "status": status,
                    "checkpoint_path": str(checkpoint_path),
                    "checkpoint_sha256": _sha256_file(checkpoint_path),
                    "canonical_path": canonical.get("path"),
                    "canonical_sha256": canonical.get("sha256"),
                    "canonical_rows": int(canonical.get("canonical_rows", 0)),
                    "raw_bundle_path": (checkpoint.get("raw_bundle") or {}).get("path"),
                    "raw_bundle_sha256": (checkpoint.get("raw_bundle") or {}).get("sha256"),
                    "quarantined_rows": int(checkpoint.get("quarantined_rows", 0)),
                    "provider_rejections": len(checkpoint.get("provider_rejections") or []),
                }
            )
        inventory = pd.DataFrame(rows)
        if inventory.empty:
            inventory = pd.DataFrame(
                columns=[
                    "unit_id",
                    "year",
                    "batch_index",
                    "status",
                    "checkpoint_path",
                    "checkpoint_sha256",
                    "canonical_path",
                    "canonical_sha256",
                    "canonical_rows",
                    "raw_bundle_path",
                    "raw_bundle_sha256",
                    "quarantined_rows",
                    "provider_rejections",
                ]
            )
        inventory_record = _write_frame(
            self.inventory_path,
            inventory,
            order_by="year, batch_index, unit_id",
        )
        complete = len(inventory) == len(units)
        clean = (
            complete
            and status_counts.get("BLOCKED_VALIDATION", 0) == 0
            and unattributed_quarantine_rows == 0
        )
        source_fingerprint = _stable_hash(
            {
                "contract": SPLIT_DAILY_CONTRACT,
                "policy": policy,
                "inventory_sha256": inventory_record["sha256"],
                "status_counts": dict(sorted(status_counts.items())),
                "canonical_rows": canonical_rows,
                "excluded_symbols": sorted(excluded_symbols),
                "unattributed_quarantine_rows": unattributed_quarantine_rows,
            }
        )
        report = {
            "contract": SPLIT_DAILY_CONTRACT,
            "updated_at_utc": datetime.now(UTC).isoformat(),
            "status": "COMPLETE" if complete else (stop_reason or "IN_PROGRESS"),
            "clean_candidate": clean,
            "source_fingerprint": source_fingerprint,
            "policy": policy,
            "policy_sha256": _stable_hash(policy),
            "total_units": len(units),
            "completed_units": len(inventory),
            "missing_units": len(units) - len(inventory),
            "status_counts": dict(sorted(status_counts.items())),
            "canonical_rows": canonical_rows,
            "excluded_symbols": sorted(excluded_symbols),
            "excluded_symbol_count": len(excluded_symbols),
            "quarantine_reason_counts": dict(sorted(quarantine_reason_counts.items())),
            "unattributed_quarantine_rows": unattributed_quarantine_rows,
            "quarantine_policy": (
                "attributed symbol anomalies are globally excluded; any unattributed "
                "anomaly or unit-level validation block fails closed"
            ),
            "inventory": inventory_record,
            "v1_rows_read": 0,
            "v1_ancestry": "FORBIDDEN",
            "protected_return_rows_read": 0,
            "performance_opened": False,
            "production_promoted": False,
        }
        atomic_write_text(
            self.manifest_path,
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            fsync=True,
        )
        return SplitDailyResult(report=report, inventory=inventory)

    def run(
        self,
        native: NativeAcceptanceResult,
        *,
        max_units: int | None = None,
        max_hours: float | None = None,
        progress: Callable[[dict[str, object]], None] | None = None,
    ) -> SplitDailyResult:
        if max_units is not None and max_units < 1:
            raise ValueError("max_units must be positive")
        if max_hours is not None and max_hours <= 0:
            raise ValueError("max_hours must be positive")
        units = tuple(unit for unit in native.units if unit.canonical_timeframe == "1d")
        policy = self._policy(native)
        policy_sha = _stable_hash(policy)
        if self.manifest_path.is_file():
            existing = _read_json(self.manifest_path, "split-adjusted daily manifest")
            if existing.get("policy_sha256") != policy_sha:
                raise AlpacaV2ValidationError(
                    "existing split-adjusted daily source binds a different frozen policy"
                )
        registry = self._load_rejections()
        started = datetime.now(UTC)
        deadline = started + timedelta(hours=max_hours) if max_hours is not None else None
        executed = 0
        stop_reason: str | None = None

        def should_stop() -> bool:
            return deadline is not None and datetime.now(UTC) >= deadline

        try:
            for index, unit in enumerate(units, start=1):
                checkpoint_path = self._paths(unit)["checkpoint"]
                if checkpoint_path.is_file():
                    checkpoint = _read_json(
                        checkpoint_path, f"split-adjusted checkpoint {unit.label}"
                    )
                    if self._validate_checkpoint(unit, checkpoint, policy_sha):
                        if progress is not None and (index == len(units) or index % 250 == 0):
                            progress(
                                {
                                    "event": "split_skip",
                                    "completed": index,
                                    "total": len(units),
                                }
                            )
                        continue
                if max_units is not None and executed >= max_units:
                    stop_reason = "MAX_UNITS_REACHED"
                    break
                if should_stop():
                    stop_reason = "TIME_LIMIT_REACHED"
                    break
                if progress is not None:
                    progress(
                        {
                            "event": "split_unit_start",
                            "unit": unit.label,
                            "completed": index - 1,
                            "total": len(units),
                        }
                    )
                self._acquire_unit(
                    unit,
                    policy_sha256=policy_sha,
                    registry=registry,
                    excluded_symbols=native.excluded_symbols,
                    stop_requested=should_stop,
                    progress=progress,
                )
                executed += 1
        except V2TimeLimitReached:
            stop_reason = "TIME_LIMIT_REACHED"
        return self._report(units, policy, stop_reason=stop_reason)
