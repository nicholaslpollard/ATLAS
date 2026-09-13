from __future__ import annotations

import gzip
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from packages.backtesting.b35_development_source import (
    B35DevelopmentMinuteSource,
    _assert_native_path,
    _validate_native_plan_record,
)
from packages.backtesting.reference_v2_lake_adapter import ReferenceV2DailyLakeAdapter
from packages.backtesting.successor_development_outcomes import (
    ACCEPTED_SUCCESSOR_RUNNER_CONTRACT_FINGERPRINT,
    ACCEPTED_SUCCESSOR_SOURCE_VERIFICATION_RUN_FINGERPRINT,
    DEVELOPMENT_END,
    DEVELOPMENT_START,
    AcceptedSuccessorPreflight,
    validate_accepted_successor_preflight,
)
from packages.backtesting.successor_runner_contract import canonical_sha256
from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.settings import AtlasSettings
from packages.data.alpaca_v2_acquisition import ACQUISITION_CONTRACT, UNIT_CONTRACT
from packages.data.alpaca_v2_postbuild import (
    NATIVE_ACCEPTANCE_CONTRACT,
    RESEARCH_DAILY_CONTRACT,
)
from packages.data.alpaca_v2_rebuild import V2Layout


SPY_BENCHMARK_MAX_STALENESS_MINUTES = 5
SPY_DAILY_FALLBACK_LAST_YEAR = 2025
SPY_BENCHMARK_SOURCE_AUDIT_CONTRACT = (
    "atlas-successor-spy-benchmark-source-v3-minute-primary-pre2026-native-daily-fallback"
)
SPY_BENCHMARK_SOURCE_AUDIT_CONTRACT_FINGERPRINT = canonical_sha256(
    {
        "contract": SPY_BENCHMARK_SOURCE_AUDIT_CONTRACT,
        "symbol": "SPY",
        "scope": [DEVELOPMENT_START.isoformat(), DEVELOPMENT_END.isoformat()],
        "primary_source": "ACCEPTED_B35_EXACT_NATIVE_MINUTE_SOURCE",
        "primary_session_value": (
            "LAST_OBSERVED_SAME_SESSION_REGULAR_BAR_AT_OR_BEFORE_SCHEDULED_FINAL_MINUTE"
        ),
        "primary_maximum_staleness_minutes": SPY_BENCHMARK_MAX_STALENESS_MINUTES,
        "fallback_source": "ALPACA_V2_NATIVE_CANONICAL_RAW_DAILY_LINEAGED_BY_ACCEPTED_RESEARCH_DAILY_NATIVE_ACCEPTANCE",
        "fallback_scope": f"SESSION_YEAR_LE_{SPY_DAILY_FALLBACK_LAST_YEAR}",
        "fallback_trigger": "PRIMARY_MISSING_INVALID_OR_OVER_STALENESS",
        "fallback_exact_same_session_required": True,
        "fallback_2026_daily_partition_open_permitted": False,
        "cross_session_fill": False,
        "provider_fetch": False,
        "protected_master_rows_permitted": 0,
        "future_blind_rows_permitted": 0,
    }
)


class SuccessorSpyBenchmarkSourceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AcceptedSpyBenchmarkSource:
    benchmark_path: Path
    benchmark_sha256: str
    scientific_fingerprint: str
    scientific: dict[str, object]
    frame: pd.DataFrame


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SuccessorSpyBenchmarkSourceError(f"invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise SuccessorSpyBenchmarkSourceError(f"{label} must be an object: {path}")
    return payload


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _project_locator(project_root: Path, path: Path) -> str:
    root = project_root.resolve()
    resolved = path.resolve()
    if not _inside(resolved, root):
        raise SuccessorSpyBenchmarkSourceError(f"SPY source path escapes project root: {resolved}")
    return resolved.relative_to(root).as_posix()


def _resolve_locator(project_root: Path, locator: str) -> Path:
    relative = Path(locator)
    if not locator or relative.is_absolute():
        raise SuccessorSpyBenchmarkSourceError(f"SPY source locator must be project-relative: {locator!r}")
    resolved = (project_root.resolve() / relative).resolve()
    if not _inside(resolved, project_root):
        raise SuccessorSpyBenchmarkSourceError(f"SPY source locator escapes project root: {locator}")
    return resolved


def _audit_root(layout: V2Layout) -> Path:
    return (
        layout.derived
        / "strategy_lab"
        / "successor_spy_source_audit"
        / SPY_BENCHMARK_SOURCE_AUDIT_CONTRACT_FINGERPRINT[:16]
    ).resolve()


def _write_parquet_atomic(path: Path, frame: pd.DataFrame) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = unique_temp_path(path)
    try:
        frame.to_parquet(temp, index=False)
        replace_with_retry(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    return _sha256_file(path)


def _write_json(path: Path, payload: object) -> None:
    atomic_write_text(path, _canonical_json(payload) + "\n", fsync=True)


def source_audit_authority() -> dict[str, object]:
    return {
        "strategy_authority": "RESEARCH_SOURCE_VERIFICATION_ONLY",
        "strategy_outcomes_opened": False,
        "consumed_master_rows_read": 0,
        "future_blind_rows_read": 0,
        "provider_calls": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "paper_authority": False,
        "live_authority": False,
        "promotion_authority": False,
    }


def _minute_session_candidates(
    source: B35DevelopmentMinuteSource,
    minute_plan,
) -> tuple[pd.DataFrame, dict[str, object]]:
    spy_units = tuple(unit for unit in minute_plan.units if "SPY" in unit.symbols)
    if not spy_units:
        raise SuccessorSpyBenchmarkSourceError("accepted minute source contains no SPY units")
    pieces: list[pd.DataFrame] = []
    for binding in spy_units:
        frame = source.load_unit(
            binding,
            start_session=DEVELOPMENT_START,
            end_session=DEVELOPMENT_END,
        )
        if frame.empty:
            continue
        selected = frame.loc[
            (frame["symbol"].astype(str) == "SPY")
            & (frame["session_segment"].astype(str) == "regular"),
            ["session_date", "timestamp_utc", "close"],
        ].copy()
        if not selected.empty:
            pieces.append(selected)
    if not pieces:
        raise SuccessorSpyBenchmarkSourceError("accepted minute source emitted no SPY regular bars")

    bars = pd.concat(pieces, ignore_index=True)
    bars["session_date"] = pd.to_datetime(bars["session_date"], errors="raise").dt.date
    bars["timestamp_utc"] = pd.to_datetime(bars["timestamp_utc"], utc=True, errors="raise")
    if bars.duplicated(["session_date", "timestamp_utc"]).any():
        raise SuccessorSpyBenchmarkSourceError("SPY minute source contains duplicate minute keys")

    expected_rows: list[dict[str, object]] = []
    for session in source.calendar.sessions_in_range(DEVELOPMENT_START, DEVELOPMENT_END):
        _regular_open, regular_close = source.calendar.regular_open_close(session)
        expected_rows.append(
            {
                "session_date": session,
                "scheduled_final_timestamp_utc": pd.Timestamp(regular_close - timedelta(minutes=1)),
            }
        )
    expected = pd.DataFrame(expected_rows)
    if expected.empty:
        raise SuccessorSpyBenchmarkSourceError("SPY benchmark expected calendar is empty")

    candidates = bars.merge(expected, on="session_date", how="inner", validate="many_to_one")
    candidates = candidates.loc[
        candidates["timestamp_utc"] <= candidates["scheduled_final_timestamp_utc"]
    ].sort_values(["session_date", "timestamp_utc"], kind="stable")
    closing = candidates.groupby("session_date", sort=False, as_index=False).tail(1).copy()
    closing["staleness_minutes"] = (
        closing["scheduled_final_timestamp_utc"] - closing["timestamp_utc"]
    ).dt.total_seconds() / 60.0
    closing = expected.merge(
        closing[["session_date", "timestamp_utc", "close", "staleness_minutes"]],
        on="session_date",
        how="left",
        validate="one_to_one",
    )
    closing["close"] = pd.to_numeric(closing["close"], errors="coerce").astype("float64")
    valid = (
        closing["timestamp_utc"].notna()
        & closing["close"].notna()
        & (closing["close"] > 0.0)
        & closing["staleness_minutes"].notna()
        & (closing["staleness_minutes"] >= 0.0)
        & (closing["staleness_minutes"] <= float(SPY_BENCHMARK_MAX_STALENESS_MINUTES))
    )
    closing["minute_valid"] = valid
    stale = closing.loc[~valid, ["session_date", "timestamp_utc", "staleness_minutes"]]
    stale_records = [
        {
            "session_date": str(row.session_date),
            "last_observed_timestamp_utc": (
                None if pd.isna(row.timestamp_utc) else pd.Timestamp(row.timestamp_utc).isoformat()
            ),
            "staleness_minutes": (
                None if pd.isna(row.staleness_minutes) else float(row.staleness_minutes)
            ),
        }
        for row in stale.itertuples(index=False)
    ]
    report = {
        "minute_source_fingerprint": minute_plan.source_fingerprint,
        "spy_minute_unit_count": len(spy_units),
        "expected_session_count": len(expected),
        "minute_valid_session_count": int(valid.sum()),
        "minute_repair_needed_session_count": len(stale_records),
        "minute_repair_needed_sessions": stale_records,
        "maximum_primary_staleness_minutes": SPY_BENCHMARK_MAX_STALENESS_MINUTES,
    }
    return closing, report


def _load_plan_records_for_fallback(
    layout: V2Layout,
    *,
    years: set[int],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    if any(year > SPY_DAILY_FALLBACK_LAST_YEAR for year in years):
        raise SuccessorSpyBenchmarkSourceError("refusing 2026-or-later split-daily SPY fallback")
    manifest_path = layout.manifests / "native_acquisition_plan.json"
    plan_path = layout.manifests / "native_acquisition_plan.jsonl.gz"
    manifest = _read_json(manifest_path, "native acquisition plan manifest")
    if manifest.get("contract") != ACQUISITION_CONTRACT or manifest.get("status") != "FROZEN":
        raise SuccessorSpyBenchmarkSourceError("native acquisition plan is not the frozen V2 plan")
    if manifest.get("v1_ancestry") != "FORBIDDEN":
        raise SuccessorSpyBenchmarkSourceError("native acquisition plan V1 ancestry drifted")
    if not plan_path.is_file() or _sha256_file(plan_path) != str(manifest.get("plan_file_sha256") or ""):
        raise SuccessorSpyBenchmarkSourceError("native acquisition plan compressed hash drifted")
    try:
        raw = gzip.decompress(plan_path.read_bytes())
    except (OSError, EOFError) as exc:
        raise SuccessorSpyBenchmarkSourceError("native acquisition plan gzip is unreadable") from exc
    if hashlib.sha256(raw).hexdigest() != str(manifest.get("plan_sha256") or ""):
        raise SuccessorSpyBenchmarkSourceError("native acquisition plan content hash drifted")

    selected: list[dict[str, object]] = []
    for line_number, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SuccessorSpyBenchmarkSourceError(
                f"native acquisition plan line {line_number} is invalid"
            ) from exc
        if not isinstance(record, dict):
            raise SuccessorSpyBenchmarkSourceError("native acquisition plan record is not an object")
        if record.get("canonical_timeframe") != "1d":
            continue
        if int(record.get("year", -1)) not in years or "SPY" not in (record.get("symbols") or []):
            continue
        _validate_native_plan_record(record, line_number)
        if record.get("provider_timeframe") != "1Day" or record.get("month") is not None:
            raise SuccessorSpyBenchmarkSourceError("SPY daily native-plan identity drifted")
        selected.append(record)
    selected_years = [int(record["year"]) for record in selected]
    if sorted(selected_years) != sorted(years) or len(selected_years) != len(set(selected_years)):
        raise SuccessorSpyBenchmarkSourceError(
            f"SPY split-daily fallback units do not map one-to-one to requested years: {sorted(years)}"
        )
    return selected, {
        "native_plan_sha256": str(manifest["plan_sha256"]),
        "native_plan_file_sha256": str(manifest["plan_file_sha256"]),
    }


def _daily_fallback_rows(
    settings: AtlasSettings,
    *,
    requested_sessions: tuple[date, ...],
) -> tuple[pd.DataFrame, dict[str, object]]:
    if not requested_sessions:
        return pd.DataFrame(columns=["session_date", "close"]), {
            "native_acceptance_fingerprint": None,
            "unit_count": 0,
            "unit_bindings": [],
            "protected_or_future_daily_partition_opened": False,
        }
    if any(session.year > SPY_DAILY_FALLBACK_LAST_YEAR for session in requested_sessions):
        raise SuccessorSpyBenchmarkSourceError("native daily fallback requested inside 2026")

    project_root = settings.project_root.resolve()
    layout = V2Layout.beneath((project_root / "data").resolve())
    adapter = ReferenceV2DailyLakeAdapter(settings)
    _research_manifest_path, research_manifest = adapter._manifest(None)
    if research_manifest.get("contract") != RESEARCH_DAILY_CONTRACT:
        raise SuccessorSpyBenchmarkSourceError("accepted research-daily contract drifted")
    expected_native_fingerprint = str(
        research_manifest.get("native_acceptance_fingerprint") or ""
    )
    if len(expected_native_fingerprint) != 64:
        raise SuccessorSpyBenchmarkSourceError(
            "research-daily native acceptance lineage fingerprint is missing"
        )

    native_report_path = (layout.validation / "native_acceptance.json").absolute()
    _assert_native_path(
        native_report_path,
        expected=native_report_path,
        root=layout.root,
        label="native acceptance report",
    )
    native_report = _read_json(native_report_path, "native acceptance report")
    required = {
        "contract": NATIVE_ACCEPTANCE_CONTRACT,
        "status": "PASS",
        "v1_ancestry": "FORBIDDEN",
        "protected_return_rows_read": 0,
        "production_promoted": False,
    }
    for field, expected in required.items():
        if native_report.get(field) != expected:
            raise SuccessorSpyBenchmarkSourceError(
                f"native acceptance report {field} is not {expected!r}"
            )
    if str(native_report.get("acceptance_fingerprint") or "") != expected_native_fingerprint:
        raise SuccessorSpyBenchmarkSourceError(
            "native daily lineage differs from accepted research daily"
        )
    if "SPY" in {str(value) for value in native_report.get("excluded_symbols") or []}:
        raise SuccessorSpyBenchmarkSourceError("SPY is excluded from accepted native V2 source")
    inventory = native_report.get("unit_inventory")
    if not isinstance(inventory, dict):
        raise SuccessorSpyBenchmarkSourceError("native acceptance unit inventory binding is missing")
    inventory_path = Path(str(inventory.get("path") or "")).absolute()
    _assert_native_path(
        inventory_path,
        expected=(layout.validation / "native_unit_inventory.parquet").absolute(),
        root=layout.root,
        label="native unit inventory",
    )
    if not inventory_path.is_file() or _sha256_file(inventory_path) != str(
        inventory.get("sha256") or ""
    ):
        raise SuccessorSpyBenchmarkSourceError("native acceptance unit inventory hash drifted")

    years = {session.year for session in requested_sessions}
    records, plan_report = _load_plan_records_for_fallback(layout, years=years)
    requested = set(requested_sessions)
    pieces: list[pd.DataFrame] = []
    unit_bindings: list[dict[str, object]] = []
    for record in sorted(records, key=lambda item: int(item["year"])):
        year = int(record["year"])
        batch = int(record["batch_index"])
        unit_id = str(record["unit_id"])
        prefix = unit_id[:20]
        partition = Path(f"year={year:04d}") / f"batch={batch:04d}"
        checkpoint_path = (
            layout.checkpoints
            / "native_units"
            / "1d"
            / partition
            / f"{prefix}.json"
        ).absolute()
        canonical_path = (layout.canonical_daily / partition / f"{prefix}.parquet").absolute()
        if year > SPY_DAILY_FALLBACK_LAST_YEAR:
            raise SuccessorSpyBenchmarkSourceError("refusing to open 2026 native daily partition")
        _assert_native_path(
            checkpoint_path,
            expected=checkpoint_path,
            root=layout.root,
            label=f"native SPY daily checkpoint {year}",
        )
        _assert_native_path(
            canonical_path,
            expected=canonical_path,
            root=layout.root,
            label=f"native SPY daily canonical {year}",
        )
        checkpoint = _read_json(checkpoint_path, f"native SPY daily checkpoint {year}")
        if checkpoint.get("contract") != UNIT_CONTRACT:
            raise SuccessorSpyBenchmarkSourceError(
                f"native SPY daily checkpoint contract drifted: {year}"
            )
        if str(checkpoint.get("status") or "") not in {
            "COMPLETE",
            "COMPLETE_WITH_QUARANTINE",
        }:
            raise SuccessorSpyBenchmarkSourceError(
                f"native SPY daily checkpoint is not accepted complete: {year}"
            )
        if (
            checkpoint.get("unit_id") != unit_id
            or checkpoint.get("policy_sha256") != record.get("policy_sha256")
            or checkpoint.get("universe_sha256") != record.get("universe_sha256")
            or canonical_sha256(checkpoint.get("unit")) != canonical_sha256(record)
        ):
            raise SuccessorSpyBenchmarkSourceError(
                f"native SPY daily checkpoint identity drifted: {year}"
            )
        canonical = checkpoint.get("canonical")
        if not isinstance(canonical, dict):
            raise SuccessorSpyBenchmarkSourceError(
                f"native SPY daily canonical binding missing: {year}"
            )
        recorded_path = Path(str(canonical.get("path") or "")).absolute()
        _assert_native_path(
            recorded_path,
            expected=canonical_path,
            root=layout.root,
            label=f"native SPY daily recorded canonical {year}",
        )
        expected_sha = str(canonical.get("sha256") or "")
        if len(expected_sha) != 64 or not canonical_path.is_file():
            raise SuccessorSpyBenchmarkSourceError(
                f"native SPY daily canonical binding incomplete: {year}"
            )
        if _sha256_file(canonical_path) != expected_sha:
            raise SuccessorSpyBenchmarkSourceError(
                f"native SPY daily canonical hash drifted: {year}"
            )
        rejected = {
            str(item.get("symbol") or "")
            for item in checkpoint.get("provider_rejections") or []
            if isinstance(item, dict)
        }
        if "SPY" in rejected:
            raise SuccessorSpyBenchmarkSourceError(
                f"SPY was provider-rejected in native daily source: {year}"
            )

        frame = pd.read_parquet(
            canonical_path,
            columns=[
                "symbol",
                "session_date",
                "close",
                "provider",
                "dataset",
                "timeframe",
                "session_segment",
                "is_adjusted",
                "source_id",
            ],
        )
        frame["session_date"] = pd.to_datetime(
            frame["session_date"], errors="raise"
        ).dt.date
        frame = frame.loc[
            (frame["symbol"].astype(str) == "SPY")
            & frame["session_date"].isin(requested)
        ].copy()
        if not frame.empty:
            expected_source_id = (
                f"alpaca:sip:1Day:raw:asof=-:v2:unit={unit_id}"
            )
            provenance_bad = (
                (frame["provider"].astype(str) != "alpaca")
                | (frame["dataset"].astype(str) != "stock_daily_aggregates")
                | (frame["timeframe"].astype(str) != "1d")
                | (frame["session_segment"].astype(str) != "regular")
                | frame["is_adjusted"].astype(bool)
                | (frame["source_id"].astype(str) != expected_source_id)
            )
            if provenance_bad.any():
                raise SuccessorSpyBenchmarkSourceError(
                    f"native SPY daily provenance drifted: {year}"
                )
            pieces.append(frame[["session_date", "close"]])
        unit_bindings.append(
            {
                "year": year,
                "unit_id": unit_id,
                "canonical_locator": _project_locator(project_root, canonical_path),
                "canonical_sha256": expected_sha,
            }
        )

    fallback = (
        pd.concat(pieces, ignore_index=True)
        if pieces
        else pd.DataFrame(columns=["session_date", "close"])
    )
    if fallback.duplicated(["session_date"]).any():
        raise SuccessorSpyBenchmarkSourceError("native SPY daily fallback has duplicate sessions")
    fallback["close"] = pd.to_numeric(
        fallback["close"], errors="coerce"
    ).astype("float64")
    bad_close = (
        fallback["close"].isna()
        | (fallback["close"] <= 0.0)
        | ~fallback["close"].map(math.isfinite)
    )
    if bad_close.any():
        raise SuccessorSpyBenchmarkSourceError(
            "native SPY daily fallback contains invalid closes"
        )
    return fallback, {
        "research_daily_source_fingerprint": str(
            research_manifest["source_fingerprint"]
        ),
        "native_acceptance_fingerprint": expected_native_fingerprint,
        **plan_report,
        "unit_count": len(unit_bindings),
        "unit_bindings": unit_bindings,
        "unit_bindings_fingerprint": canonical_sha256(unit_bindings),
        "protected_or_future_daily_partition_opened": False,
    }


def resolve_spy_benchmark_source(
    minute_closing: pd.DataFrame,
    daily_fallback: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, object]]:
    required = {
        "session_date",
        "timestamp_utc",
        "close",
        "staleness_minutes",
        "minute_valid",
    }
    if not required.issubset(minute_closing.columns):
        raise SuccessorSpyBenchmarkSourceError("minute closing table is missing required columns")
    closing = minute_closing.copy()
    closing["session_date"] = pd.to_datetime(closing["session_date"], errors="raise").dt.date
    if closing["session_date"].duplicated().any():
        raise SuccessorSpyBenchmarkSourceError("minute closing table contains duplicate sessions")
    fallback = daily_fallback.copy()
    if not fallback.empty:
        fallback["session_date"] = pd.to_datetime(fallback["session_date"], errors="raise").dt.date
        fallback["close"] = pd.to_numeric(fallback["close"], errors="coerce").astype("float64")
        if fallback["session_date"].duplicated().any():
            raise SuccessorSpyBenchmarkSourceError("daily fallback table contains duplicate sessions")
    fallback_by_date = {
        row.session_date: float(row.close) for row in fallback.itertuples(index=False)
    }

    benchmark_rows: list[dict[str, object]] = []
    fallback_records: list[dict[str, object]] = []
    unresolved: list[dict[str, object]] = []
    for row in closing.sort_values("session_date", kind="stable").itertuples(index=False):
        session = row.session_date
        if bool(row.minute_valid):
            benchmark_rows.append({"session_date": session, "close": float(row.close)})
            continue
        if session.year <= SPY_DAILY_FALLBACK_LAST_YEAR and session in fallback_by_date:
            benchmark_rows.append({"session_date": session, "close": fallback_by_date[session]})
            fallback_records.append(
                {
                    "session_date": session.isoformat(),
                    "minute_last_timestamp_utc": (
                        None if pd.isna(row.timestamp_utc) else pd.Timestamp(row.timestamp_utc).isoformat()
                    ),
                    "minute_staleness_minutes": (
                        None if pd.isna(row.staleness_minutes) else float(row.staleness_minutes)
                    ),
                    "replacement_source": "NATIVE_RAW_DAILY",
                }
            )
            continue
        unresolved.append(
            {
                "session_date": session.isoformat(),
                "minute_last_timestamp_utc": (
                    None if pd.isna(row.timestamp_utc) else pd.Timestamp(row.timestamp_utc).isoformat()
                ),
                "minute_staleness_minutes": (
                    None if pd.isna(row.staleness_minutes) else float(row.staleness_minutes)
                ),
                "daily_fallback_permitted": session.year <= SPY_DAILY_FALLBACK_LAST_YEAR,
                "daily_fallback_available": session in fallback_by_date,
            }
        )
    if unresolved:
        raise SuccessorSpyBenchmarkSourceError(
            "SPY benchmark source audit has unresolved session(s): " + _canonical_json(unresolved)
        )
    benchmark = pd.DataFrame(benchmark_rows)
    benchmark["session_date"] = pd.to_datetime(benchmark["session_date"], errors="raise").dt.date
    benchmark["close"] = pd.to_numeric(benchmark["close"], errors="raise").astype("float64")
    if benchmark["session_date"].duplicated().any() or len(benchmark) != len(closing):
        raise SuccessorSpyBenchmarkSourceError("resolved SPY benchmark session accounting drifted")
    return benchmark, {
        "session_count": len(benchmark),
        "minute_primary_session_count": len(benchmark) - len(fallback_records),
        "daily_fallback_session_count": len(fallback_records),
        "daily_fallback_sessions": fallback_records,
        "unresolved_session_count": 0,
        "cross_session_fill": False,
    }


def audit_successor_spy_benchmark_source(
    settings: AtlasSettings,
    *,
    preflight: AcceptedSuccessorPreflight | None = None,
) -> dict[str, object]:
    project_root = settings.project_root.resolve()
    accepted = preflight or validate_accepted_successor_preflight(project_root)
    minute_source = B35DevelopmentMinuteSource(settings)
    minute_plan = minute_source.plan(DEVELOPMENT_START, DEVELOPMENT_END)
    minute_closing, minute_report = _minute_session_candidates(minute_source, minute_plan)
    repair_sessions = tuple(
        row.session_date
        for row in minute_closing.loc[~minute_closing["minute_valid"]].itertuples(index=False)
        if row.session_date.year <= SPY_DAILY_FALLBACK_LAST_YEAR
    )
    daily_fallback, daily_report = _daily_fallback_rows(
        settings,
        requested_sessions=repair_sessions,
    )
    benchmark, resolution = resolve_spy_benchmark_source(minute_closing, daily_fallback)

    expected_sessions = list(minute_source.calendar.sessions_in_range(DEVELOPMENT_START, DEVELOPMENT_END))
    if benchmark["session_date"].tolist() != expected_sessions:
        raise SuccessorSpyBenchmarkSourceError("SPY benchmark does not exactly match DEVELOPMENT XNYS sessions")
    if benchmark["close"].isna().any() or (benchmark["close"] <= 0.0).any():
        raise SuccessorSpyBenchmarkSourceError("SPY benchmark contains invalid closes")

    layout = V2Layout.beneath((project_root / "data").resolve())
    root = _audit_root(layout)
    root.mkdir(parents=True, exist_ok=True)
    benchmark_path = root / "benchmark_spy.parquet"
    benchmark_sha = _write_parquet_atomic(benchmark_path, benchmark)
    scientific = {
        "contract": SPY_BENCHMARK_SOURCE_AUDIT_CONTRACT,
        "contract_fingerprint": SPY_BENCHMARK_SOURCE_AUDIT_CONTRACT_FINGERPRINT,
        "status": "ACCEPTED_SOURCE_ONLY",
        "scope": [DEVELOPMENT_START.isoformat(), DEVELOPMENT_END.isoformat()],
        "accepted_runner_contract_fingerprint": ACCEPTED_SUCCESSOR_RUNNER_CONTRACT_FINGERPRINT,
        "accepted_source_verification_run_fingerprint": ACCEPTED_SUCCESSOR_SOURCE_VERIFICATION_RUN_FINGERPRINT,
        "accepted_source_manifest_fingerprint": accepted.source_manifest_fingerprint,
        "minute": minute_report,
        "daily_fallback": daily_report,
        "resolution": resolution,
        "benchmark_sha256": benchmark_sha,
        "benchmark_rows": len(benchmark),
        "authority": source_audit_authority(),
    }
    scientific_fingerprint = canonical_sha256(scientific)
    receipt = {
        "scientific": scientific,
        "scientific_fingerprint": scientific_fingerprint,
        "operational": {
            "benchmark_locator": _project_locator(project_root, benchmark_path),
            "benchmark_sha256": benchmark_sha,
        },
        "generated_at_utc": datetime.now(UTC).isoformat(),
    }
    _write_json(root / "receipt.json", receipt)
    return receipt


def load_accepted_spy_benchmark_source(
    settings: AtlasSettings,
    *,
    preflight: AcceptedSuccessorPreflight,
) -> AcceptedSpyBenchmarkSource:
    project_root = settings.project_root.resolve()
    layout = V2Layout.beneath((project_root / "data").resolve())
    root = _audit_root(layout)
    receipt_path = root / "receipt.json"
    if not receipt_path.is_file():
        raise SuccessorSpyBenchmarkSourceError(
            "accepted SPY benchmark source audit is missing; run the bounded SPY source audit before DEVELOPMENT outcomes"
        )
    receipt = _read_json(receipt_path, "SPY benchmark source audit receipt")
    scientific = receipt.get("scientific")
    operational = receipt.get("operational")
    if not isinstance(scientific, dict) or not isinstance(operational, dict):
        raise SuccessorSpyBenchmarkSourceError("SPY benchmark source audit receipt is malformed")
    scientific_fingerprint = str(receipt.get("scientific_fingerprint") or "")
    if canonical_sha256(scientific) != scientific_fingerprint:
        raise SuccessorSpyBenchmarkSourceError("SPY benchmark source audit scientific fingerprint drifted")
    required = {
        "contract": SPY_BENCHMARK_SOURCE_AUDIT_CONTRACT,
        "contract_fingerprint": SPY_BENCHMARK_SOURCE_AUDIT_CONTRACT_FINGERPRINT,
        "status": "ACCEPTED_SOURCE_ONLY",
        "scope": [DEVELOPMENT_START.isoformat(), DEVELOPMENT_END.isoformat()],
        "accepted_runner_contract_fingerprint": ACCEPTED_SUCCESSOR_RUNNER_CONTRACT_FINGERPRINT,
        "accepted_source_verification_run_fingerprint": ACCEPTED_SUCCESSOR_SOURCE_VERIFICATION_RUN_FINGERPRINT,
        "accepted_source_manifest_fingerprint": preflight.source_manifest_fingerprint,
        "benchmark_rows": len(B35DevelopmentMinuteSource(settings).calendar.sessions_in_range(DEVELOPMENT_START, DEVELOPMENT_END)),
        "authority": source_audit_authority(),
    }
    for field, expected in required.items():
        if scientific.get(field) != expected:
            raise SuccessorSpyBenchmarkSourceError(
                f"SPY benchmark source audit {field} is not {expected!r}"
            )
    resolution = scientific.get("resolution")
    if not isinstance(resolution, dict) or int(resolution.get("unresolved_session_count", -1)) != 0:
        raise SuccessorSpyBenchmarkSourceError("SPY benchmark source audit has unresolved sessions")
    daily = scientific.get("daily_fallback")
    if not isinstance(daily, dict) or daily.get("protected_or_future_daily_partition_opened") is not False:
        raise SuccessorSpyBenchmarkSourceError("SPY benchmark source audit daily boundary drifted")

    benchmark_path = _resolve_locator(project_root, str(operational.get("benchmark_locator") or ""))
    expected_path = (root / "benchmark_spy.parquet").resolve()
    if benchmark_path != expected_path:
        raise SuccessorSpyBenchmarkSourceError("SPY benchmark source artifact path drifted")
    expected_sha = str(scientific.get("benchmark_sha256") or "")
    if operational.get("benchmark_sha256") != expected_sha or not benchmark_path.is_file():
        raise SuccessorSpyBenchmarkSourceError("SPY benchmark source artifact binding drifted")
    actual_sha = _sha256_file(benchmark_path)
    if actual_sha != expected_sha:
        raise SuccessorSpyBenchmarkSourceError("SPY benchmark source artifact SHA-256 drifted")
    frame = pd.read_parquet(benchmark_path)
    if list(frame.columns) != ["session_date", "close"]:
        raise SuccessorSpyBenchmarkSourceError("SPY benchmark source artifact schema drifted")
    frame["session_date"] = pd.to_datetime(frame["session_date"], errors="raise").dt.date
    frame["close"] = pd.to_numeric(frame["close"], errors="raise").astype("float64")
    expected_sessions = list(B35DevelopmentMinuteSource(settings).calendar.sessions_in_range(DEVELOPMENT_START, DEVELOPMENT_END))
    if frame["session_date"].tolist() != expected_sessions:
        raise SuccessorSpyBenchmarkSourceError("SPY benchmark source artifact session coverage drifted")
    if frame["session_date"].duplicated().any() or frame["close"].isna().any() or (frame["close"] <= 0).any():
        raise SuccessorSpyBenchmarkSourceError("SPY benchmark source artifact values drifted")
    return AcceptedSpyBenchmarkSource(
        benchmark_path=benchmark_path,
        benchmark_sha256=actual_sha,
        scientific_fingerprint=scientific_fingerprint,
        scientific=scientific,
        frame=frame,
    )
