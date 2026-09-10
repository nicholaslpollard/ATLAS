from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Iterator
from zoneinfo import ZoneInfo

import duckdb
import pandas as pd

from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings
from packages.data.alpaca_v2_acquisition import ACQUISITION_CONTRACT, UNIT_CONTRACT
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.intraday_semantics_audit import (
    ALPACA_V2_SOURCE_PREFIX,
    MINUTE_DATASET,
    MINUTE_TIMEFRAME,
)
from packages.strategies.b35_conditional_evidence_contract import (
    B35_PREOUTCOME_FINGERPRINT,
    CONSUMED_MASTER_END,
    CONSUMED_MASTER_START,
    DEVELOPMENT_LAST_SCORING_SESSION,
    FUTURE_BLIND_START_ON_OR_AFTER,
)


B35_DEVELOPMENT_SOURCE_CONTRACT = (
    "atlas-b35-development-minute-source-v2-native-plan-exact-path-physical"
)
_COMPLETE_STATUSES = {"COMPLETE", "COMPLETE_WITH_QUARANTINE"}


class B35DevelopmentSourceError(RuntimeError):
    pass


class B35DevelopmentScopeError(B35DevelopmentSourceError):
    pass


@dataclass(frozen=True, slots=True)
class B35DevelopmentUnitBinding:
    unit_id: str
    year: int
    month: int
    batch_index: int
    window_start: date
    window_end_exclusive: date
    symbols: tuple[str, ...]
    policy_sha256: str
    universe_sha256: str
    canonical_path: Path
    canonical_sha256: str
    checkpoint_path: Path


@dataclass(frozen=True, slots=True)
class B35DevelopmentSourcePlan:
    contract: str
    b35_preoutcome_fingerprint: str
    start_session: date
    end_session: date
    units: tuple[B35DevelopmentUnitBinding, ...]
    native_plan_sha256: str
    native_plan_file_sha256: str
    source_fingerprint: str


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(raw).hexdigest()


def _stable_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _month_key(value: date) -> tuple[int, int]:
    return value.year, value.month


_NATIVE_PLAN_KEYS = {
    "unit_id",
    "provider_timeframe",
    "canonical_timeframe",
    "window_start",
    "window_end_exclusive",
    "year",
    "month",
    "batch_index",
    "symbols",
    "universe_sha256",
    "policy_sha256",
}


def _exact_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_native_plan_record(record: dict[str, object], line_number: int) -> None:
    if set(record) != _NATIVE_PLAN_KEYS:
        raise B35DevelopmentSourceError(
            f"native acquisition plan line {line_number} schema drifted"
        )
    if not isinstance(record["unit_id"], str) or len(record["unit_id"]) != 64:
        raise B35DevelopmentSourceError("native acquisition unit id is malformed")
    if not isinstance(record["provider_timeframe"], str) or not isinstance(
        record["canonical_timeframe"], str
    ):
        raise B35DevelopmentSourceError("native acquisition timeframe schema drifted")
    if not isinstance(record["window_start"], str) or not isinstance(
        record["window_end_exclusive"], str
    ):
        raise B35DevelopmentSourceError("native acquisition window schema drifted")
    if not _exact_int(record["year"]) or not _exact_int(record["batch_index"]):
        raise B35DevelopmentSourceError("native acquisition integer schema drifted")
    if record["month"] is not None and not _exact_int(record["month"]):
        raise B35DevelopmentSourceError("native acquisition month schema drifted")
    symbols = record["symbols"]
    if (
        not isinstance(symbols, list)
        or not symbols
        or any(not isinstance(item, str) or not item for item in symbols)
        or symbols != sorted(set(symbols))
    ):
        raise B35DevelopmentSourceError("native acquisition symbol schema drifted")
    for field in ("universe_sha256", "policy_sha256"):
        if not isinstance(record[field], str) or len(str(record[field])) != 64:
            raise B35DevelopmentSourceError(f"native acquisition {field} is malformed")
    try:
        start = date.fromisoformat(record["window_start"])
        end = date.fromisoformat(record["window_end_exclusive"])
    except ValueError as exc:
        raise B35DevelopmentSourceError("native acquisition window is malformed") from exc
    expected_id = hashlib.sha256(
        _stable_json(
            {
                "contract": UNIT_CONTRACT,
                "provider_timeframe": record["provider_timeframe"],
                "window_start": start.isoformat(),
                "window_end_exclusive": end.isoformat(),
                "batch_index": record["batch_index"],
                "symbols": symbols,
                "universe_sha256": record["universe_sha256"],
                "policy_sha256": record["policy_sha256"],
            }
        ).encode("utf-8")
    ).hexdigest()
    if record["unit_id"] != expected_id:
        raise B35DevelopmentSourceError("native acquisition unit id does not match writer schema")


def _read_json_object(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(f"missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise B35DevelopmentSourceError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise B35DevelopmentSourceError(f"{label} is not a JSON object: {path}")
    return value


def _assert_native_path(path: Path, *, expected: Path, root: Path, label: str) -> Path:
    """Require the exact writer path and reject symlink/root escapes."""

    expected = expected.absolute()
    root = root.absolute()
    path = path.absolute()
    if path != expected:
        raise B35DevelopmentSourceError(f"{label} is not the exact frozen native-unit path")
    try:
        relative = expected.relative_to(root)
    except ValueError as exc:
        raise B35DevelopmentSourceError(f"{label} escapes the isolated V2 root") from exc
    cursor = root
    if cursor.is_symlink():
        raise B35DevelopmentSourceError(f"{label} V2 root is a symlink")
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise B35DevelopmentSourceError(f"{label} path contains a symlink: {cursor}")
    resolved_root = root.resolve(strict=False)
    resolved = expected.resolve(strict=False)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise B35DevelopmentSourceError(f"{label} resolves outside isolated V2 root") from exc
    if resolved != expected.resolve(strict=False):
        raise B35DevelopmentSourceError(f"{label} resolution drifted")
    return expected


def _load_frozen_minute_plan(
    layout: V2Layout,
    *,
    start_session: date,
    end_session: date,
) -> tuple[list[dict[str, object]], str, str]:
    manifest_path = layout.manifests / "native_acquisition_plan.json"
    plan_path = layout.manifests / "native_acquisition_plan.jsonl.gz"
    _assert_native_path(
        manifest_path,
        expected=manifest_path,
        root=layout.root,
        label="native acquisition plan manifest",
    )
    manifest = _read_json_object(manifest_path, "V2 native acquisition plan manifest")
    for field, expected in {
        "contract": ACQUISITION_CONTRACT,
        "status": "FROZEN",
        "v1_ancestry": "FORBIDDEN",
    }.items():
        if manifest.get(field) != expected:
            raise B35DevelopmentSourceError(
                f"V2 native acquisition plan {field} is not {expected!r}"
            )
    recorded_plan_path = Path(str(manifest.get("plan_path") or "")).absolute()
    _assert_native_path(
        recorded_plan_path,
        expected=plan_path,
        root=layout.root,
        label="native acquisition plan",
    )
    if not plan_path.is_file():
        raise FileNotFoundError(f"missing frozen V2 native acquisition plan: {plan_path}")
    compressed_sha = _sha256_file(plan_path)
    if compressed_sha != str(manifest.get("plan_file_sha256") or ""):
        raise B35DevelopmentSourceError("V2 native acquisition plan file SHA-256 drifted")
    try:
        raw = gzip.decompress(plan_path.read_bytes())
    except (OSError, EOFError) as exc:
        raise B35DevelopmentSourceError("V2 native acquisition plan gzip is unreadable") from exc
    raw_sha = _sha256_bytes(raw)
    if raw_sha != str(manifest.get("plan_sha256") or ""):
        raise B35DevelopmentSourceError("V2 native acquisition plan content SHA-256 drifted")

    start_month = _month_key(start_session)
    end_month = _month_key(end_session)
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    for line_number, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise B35DevelopmentSourceError(
                f"invalid native acquisition plan line {line_number}"
            ) from exc
        if not isinstance(record, dict):
            raise B35DevelopmentSourceError(
                f"native acquisition plan line {line_number} is not an object"
            )
        _validate_native_plan_record(record, line_number)
        if record["canonical_timeframe"] != MINUTE_TIMEFRAME:
            continue
        if record["provider_timeframe"] != "1Min":
            raise B35DevelopmentSourceError("minute native plan provider timeframe drifted")
        try:
            year = int(record["year"])
            month = int(record["month"])
            batch_index = int(record["batch_index"])
            window_start = date.fromisoformat(str(record["window_start"]))
            window_end = date.fromisoformat(str(record["window_end_exclusive"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise B35DevelopmentSourceError("minute native plan identity is malformed") from exc
        if (year, month) < start_month or (year, month) > end_month:
            continue
        if year > 2026 or (year == 2026 and month >= 5):
            raise B35DevelopmentSourceError(
                "frozen native plan selection would enter a May-2026-or-later minute partition"
            )
        unit_id = str(record.get("unit_id") or "")
        symbols = tuple(str(value) for value in record.get("symbols") or [] if str(value))
        policy_sha = str(record.get("policy_sha256") or "")
        universe_sha = str(record.get("universe_sha256") or "")
        if (
            len(unit_id) != 64
            or not symbols
            or batch_index < 0
            or len(policy_sha) != 64
            or len(universe_sha) != 64
            or window_start.year != year
            or window_start.month != month
            or window_end <= window_start
        ):
            raise B35DevelopmentSourceError("minute native plan unit binding is incomplete")
        if unit_id in seen:
            raise B35DevelopmentSourceError("minute native plan contains duplicate unit identity")
        seen.add(unit_id)
        records.append(record)
    if not records:
        raise B35DevelopmentSourceError("frozen native plan selects no B35 DEVELOPMENT minute units")
    return records, raw_sha, compressed_sha


def _binding_from_plan(layout: V2Layout, record: dict[str, object]) -> B35DevelopmentUnitBinding:
    unit_id = str(record["unit_id"])
    year = int(record["year"])
    month = int(record["month"])
    batch = int(record["batch_index"])
    prefix = unit_id[:20]
    partition = (
        Path(f"year={year:04d}") / f"month={month:02d}" / f"batch={batch:04d}"
    )
    expected_checkpoint = (
        layout.checkpoints / "native_units" / "1m" / partition / f"{prefix}.json"
    ).absolute()
    expected_canonical = (layout.canonical_minute / partition / f"{prefix}.parquet").absolute()
    _assert_native_path(
        expected_checkpoint,
        expected=expected_checkpoint,
        root=layout.root,
        label="minute checkpoint",
    )
    _assert_native_path(
        expected_canonical,
        expected=expected_canonical,
        root=layout.root,
        label="canonical minute parquet",
    )
    checkpoint = _read_json_object(expected_checkpoint, "B35 minute checkpoint")
    if checkpoint.get("contract") != UNIT_CONTRACT:
        raise B35DevelopmentSourceError(f"minute checkpoint contract drifted: {unit_id}")
    if str(checkpoint.get("status") or "") not in _COMPLETE_STATUSES:
        raise B35DevelopmentSourceError(f"minute checkpoint is not accepted complete: {unit_id}")
    if checkpoint.get("unit_id") != unit_id:
        raise B35DevelopmentSourceError(f"minute checkpoint unit id drifted: {unit_id}")
    if checkpoint.get("policy_sha256") != record.get("policy_sha256"):
        raise B35DevelopmentSourceError(f"minute checkpoint policy binding drifted: {unit_id}")
    if checkpoint.get("universe_sha256") != record.get("universe_sha256"):
        raise B35DevelopmentSourceError(f"minute checkpoint universe binding drifted: {unit_id}")
    if _stable_json(checkpoint.get("unit")) != _stable_json(record):
        raise B35DevelopmentSourceError(f"minute checkpoint frozen unit body drifted: {unit_id}")
    canonical = checkpoint.get("canonical")
    if not isinstance(canonical, dict):
        raise B35DevelopmentSourceError(f"minute checkpoint has no canonical binding: {unit_id}")
    recorded_canonical = Path(str(canonical.get("path") or "")).absolute()
    _assert_native_path(
        recorded_canonical,
        expected=expected_canonical,
        root=layout.root,
        label="canonical minute parquet",
    )
    canonical_sha = str(canonical.get("sha256") or "")
    if len(canonical_sha) != 64:
        raise B35DevelopmentSourceError(f"minute checkpoint has no canonical SHA-256: {unit_id}")
    return B35DevelopmentUnitBinding(
        unit_id=unit_id,
        year=year,
        month=month,
        batch_index=batch,
        window_start=date.fromisoformat(str(record["window_start"])),
        window_end_exclusive=date.fromisoformat(str(record["window_end_exclusive"])),
        symbols=tuple(str(value) for value in record.get("symbols") or []),
        policy_sha256=str(record["policy_sha256"]),
        universe_sha256=str(record["universe_sha256"]),
        canonical_path=expected_canonical,
        canonical_sha256=canonical_sha,
        checkpoint_path=expected_checkpoint,
    )


class B35DevelopmentMinuteSource:
    """Hash-bound, exact-path, pre-protected V2 minute reader for B35 DEVELOPMENT."""

    def __init__(self, settings: AtlasSettings, *, duckdb_threads: int = 2) -> None:
        self.settings = settings
        self.duckdb_threads = max(1, int(duckdb_threads))
        self.layout = V2Layout.beneath((settings.project_root / "data").resolve())
        self.calendar = MarketCalendar(
            exchange=settings.data.calendar.exchange,
            market_tz=ZoneInfo(settings.data.calendar.market_timezone),
        )
        self.market_tz = ZoneInfo(settings.data.calendar.market_timezone)
        # A B35 source reader is process-local. Parallel replay workers persist
        # across group tasks, so cache purely operational resources per worker.
        # This does not cache source bytes, checkpoints, hashes, or validation
        # results: every canonical unit is still re-bound and SHA-verified.
        self._calendar_frame_cache: dict[tuple[date, date], pd.DataFrame] = {}
        self._duckdb_connection: duckdb.DuckDBPyConnection | None = None
        self._registered_calendar_views: set[str] = set()

    def _connection(self) -> duckdb.DuckDBPyConnection:
        con = self._duckdb_connection
        if con is None:
            con = duckdb.connect(":memory:")
            con.execute("SET TimeZone='UTC'")
            con.execute(f"PRAGMA threads={self.duckdb_threads}")
            con.execute("PRAGMA disable_progress_bar")
            self._duckdb_connection = con
        return con

    def close(self) -> None:
        con = self._duckdb_connection
        self._duckdb_connection = None
        self._registered_calendar_views.clear()
        if con is not None:
            con.close()

    @staticmethod
    def validate_scope(start_session: date, end_session: date) -> None:
        if end_session < start_session:
            raise B35DevelopmentScopeError("B35 DEVELOPMENT end precedes start")
        if end_session > DEVELOPMENT_LAST_SCORING_SESSION:
            raise B35DevelopmentScopeError(
                "B35 DEVELOPMENT scored source cannot pass 2026-04-30"
            )
        if start_session >= CONSUMED_MASTER_START or end_session >= CONSUMED_MASTER_START:
            raise B35DevelopmentScopeError(
                "B35 DEVELOPMENT cannot approach or enter the consumed master interval"
            )
        if start_session >= FUTURE_BLIND_START_ON_OR_AFTER:
            raise B35DevelopmentScopeError("B35 DEVELOPMENT cannot enter the future blind")

    def plan(
        self,
        start_session: date,
        end_session: date = DEVELOPMENT_LAST_SCORING_SESSION,
    ) -> B35DevelopmentSourcePlan:
        self.validate_scope(start_session, end_session)
        records, native_plan_sha, native_plan_file_sha = _load_frozen_minute_plan(
            self.layout,
            start_session=start_session,
            end_session=end_session,
        )
        bindings = tuple(
            sorted(
                (_binding_from_plan(self.layout, record) for record in records),
                key=lambda item: (item.year, item.month, item.batch_index, item.unit_id),
            )
        )
        if len(bindings) != len(records):
            raise B35DevelopmentSourceError("B35 exact native-plan coverage accounting drifted")
        payload = {
            "contract": B35_DEVELOPMENT_SOURCE_CONTRACT,
            "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
            "start_session": start_session.isoformat(),
            "end_session": end_session.isoformat(),
            "native_plan_sha256": native_plan_sha,
            "native_plan_file_sha256": native_plan_file_sha,
            "units": [
                {
                    "unit_id": item.unit_id,
                    "year": item.year,
                    "month": item.month,
                    "batch_index": item.batch_index,
                    "window_start": item.window_start.isoformat(),
                    "window_end_exclusive": item.window_end_exclusive.isoformat(),
                    "symbols": item.symbols,
                    "policy_sha256": item.policy_sha256,
                    "universe_sha256": item.universe_sha256,
                    "canonical_path": str(item.canonical_path),
                    "canonical_sha256": item.canonical_sha256,
                    "checkpoint_path": str(item.checkpoint_path),
                }
                for item in bindings
            ],
            "exact_native_path_confinement": True,
            "consumed_master_rows_permitted": 0,
            "future_blind_rows_permitted": 0,
            "provider_calls": 0,
            "broker_reads": 0,
            "broker_writes": 0,
        }
        return B35DevelopmentSourcePlan(
            contract=B35_DEVELOPMENT_SOURCE_CONTRACT,
            b35_preoutcome_fingerprint=B35_PREOUTCOME_FINGERPRINT,
            start_session=start_session,
            end_session=end_session,
            units=bindings,
            native_plan_sha256=native_plan_sha,
            native_plan_file_sha256=native_plan_file_sha,
            source_fingerprint=_stable_hash(payload),
        )

    def verify_unit(self, binding: B35DevelopmentUnitBinding) -> str:
        if binding.year > 2026 or (binding.year == 2026 and binding.month >= 5):
            raise B35DevelopmentSourceError(
                "refusing to hash/open a minute unit in or after May 2026"
            )
        prefix = binding.unit_id[:20]
        partition = (
            Path(f"year={binding.year:04d}")
            / f"month={binding.month:02d}"
            / f"batch={binding.batch_index:04d}"
        )
        expected_checkpoint = (
            self.layout.checkpoints / "native_units" / "1m" / partition / f"{prefix}.json"
        ).absolute()
        expected_canonical = (
            self.layout.canonical_minute / partition / f"{prefix}.parquet"
        ).absolute()
        _assert_native_path(
            binding.checkpoint_path,
            expected=expected_checkpoint,
            root=self.layout.root,
            label="minute checkpoint",
        )
        _assert_native_path(
            binding.canonical_path,
            expected=expected_canonical,
            root=self.layout.root,
            label="canonical minute parquet",
        )
        # Revalidate the checkpoint identity before every canonical open so a
        # post-plan metadata replacement cannot redirect or rebind the unit.
        checkpoint = _read_json_object(binding.checkpoint_path, "B35 minute checkpoint")
        if (
            checkpoint.get("contract") != UNIT_CONTRACT
            or checkpoint.get("unit_id") != binding.unit_id
            or str(checkpoint.get("status") or "") not in _COMPLETE_STATUSES
            or checkpoint.get("policy_sha256") != binding.policy_sha256
            or checkpoint.get("universe_sha256") != binding.universe_sha256
        ):
            raise B35DevelopmentSourceError(
                f"minute checkpoint identity changed after planning: {binding.unit_id}"
            )
        canonical = checkpoint.get("canonical")
        if not isinstance(canonical, dict):
            raise B35DevelopmentSourceError("minute checkpoint canonical binding disappeared")
        recorded_path = Path(str(canonical.get("path") or "")).absolute()
        _assert_native_path(
            recorded_path,
            expected=expected_canonical,
            root=self.layout.root,
            label="canonical minute parquet",
        )
        if canonical.get("sha256") != binding.canonical_sha256:
            raise B35DevelopmentSourceError("minute checkpoint canonical hash binding changed")
        if not binding.canonical_path.is_file():
            raise FileNotFoundError(
                f"missing B35 canonical minute unit: {binding.canonical_path}"
            )
        actual = _sha256_file(binding.canonical_path)
        if actual != binding.canonical_sha256:
            raise B35DevelopmentSourceError(
                f"canonical minute unit SHA-256 drifted: {binding.unit_id}"
            )
        return actual

    def _calendar_frame(self, binding: B35DevelopmentUnitBinding) -> pd.DataFrame:
        key = (binding.window_start, binding.window_end_exclusive)
        cached = self._calendar_frame_cache.get(key)
        if cached is not None:
            return cached
        rows: list[dict[str, object]] = []
        end = binding.window_end_exclusive - timedelta(days=1)
        for session in self.calendar.sessions_in_range(binding.window_start, end):
            regular_open, regular_close = self.calendar.regular_open_close(session)
            pre_start = datetime.combine(session, time(4, 0), self.market_tz).astimezone(
                regular_open.tzinfo
            )
            after_end = datetime.combine(session, time(20, 0), self.market_tz).astimezone(
                regular_open.tzinfo
            )
            rows.append(
                {
                    "session_date": session,
                    "premarket_start_utc": pre_start,
                    "regular_open_utc": regular_open,
                    "regular_close_utc": regular_close,
                    "after_hours_end_utc": after_end,
                }
            )
        frame = pd.DataFrame(rows)
        self._calendar_frame_cache[key] = frame
        return frame

    def load_unit(
        self,
        binding: B35DevelopmentUnitBinding,
        *,
        start_session: date,
        end_session: date,
    ) -> pd.DataFrame:
        self.validate_scope(start_session, end_session)
        if (binding.year, binding.month) < _month_key(start_session) or (
            binding.year,
            binding.month,
        ) > _month_key(end_session):
            raise B35DevelopmentSourceError("unit lies outside the requested B35 scope")
        self.verify_unit(binding)
        calendar_frame = self._calendar_frame(binding)
        if calendar_frame.empty:
            raise B35DevelopmentSourceError("minute unit month contains no accepted exchange sessions")

        con = self._connection()
        calendar_view = f"b35_calendar_{binding.year:04d}_{binding.month:02d}"
        if calendar_view not in self._registered_calendar_views:
            con.register(calendar_view, calendar_frame)
            self._registered_calendar_views.add(calendar_view)
        symbol_placeholders = ",".join("?" for _ in binding.symbols)
        exact_source_id = ALPACA_V2_SOURCE_PREFIX + binding.unit_id
        try:
            validation_sql = f"""
                WITH source_rows AS (
                    SELECT
                        p.*,
                        c.session_date AS calendar_session_date,
                        c.premarket_start_utc,
                        c.regular_open_utc,
                        c.regular_close_utc,
                        c.after_hours_end_utc,
                        count(*) OVER (
                            PARTITION BY p.symbol, p.timestamp_utc, p.timeframe, p.session_segment
                        ) AS duplicate_count
                    FROM read_parquet(?, hive_partitioning=false) p
                    LEFT JOIN {calendar_view} c
                      ON p.session_date = c.session_date
                ), checked AS (
                    SELECT
                        *,
                        CASE
                            WHEN calendar_session_date IS NULL
                                THEN session_segment = 'closed'
                            WHEN timestamp_utc >= premarket_start_utc
                             AND timestamp_utc < regular_open_utc
                                THEN session_segment = 'premarket'
                            WHEN timestamp_utc >= regular_open_utc
                             AND timestamp_utc < regular_close_utc
                                THEN session_segment = 'regular'
                            WHEN timestamp_utc >= regular_close_utc
                             AND timestamp_utc < after_hours_end_utc
                                THEN session_segment = 'after_hours'
                            ELSE session_segment = 'closed'
                        END AS segment_ok
                    FROM source_rows
                )
                SELECT
                    count(*)::BIGINT AS rows,
                    count(*) FILTER (
                        WHERE session_date IS NULL
                           OR session_date < ? OR session_date >= ?
                           OR symbol IS NULL OR symbol NOT IN ({symbol_placeholders})
                           OR provider IS DISTINCT FROM 'alpaca'
                           OR dataset IS DISTINCT FROM ?
                           OR timeframe IS DISTINCT FROM ?
                           OR is_adjusted IS DISTINCT FROM FALSE
                           OR source_id IS DISTINCT FROM ?
                           OR timestamp_utc IS NULL OR provider_timestamp_utc IS NULL
                           OR timestamp_utc IS DISTINCT FROM provider_timestamp_utc
                           OR date_trunc('minute', timestamp_utc) IS DISTINCT FROM timestamp_utc
                           OR open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL
                           OR volume IS NULL
                           OR NOT isfinite(CAST(open AS DOUBLE))
                           OR NOT isfinite(CAST(high AS DOUBLE))
                           OR NOT isfinite(CAST(low AS DOUBLE))
                           OR NOT isfinite(CAST(close AS DOUBLE))
                           OR NOT isfinite(CAST(volume AS DOUBLE))
                           OR open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
                           OR volume < 0
                           OR high < greatest(open, close)
                           OR low > least(open, close)
                           OR high < low
                           OR (vwap IS NOT NULL AND (
                                  NOT isfinite(CAST(vwap AS DOUBLE)) OR vwap <= 0
                              ))
                           OR (transaction_count IS NOT NULL AND transaction_count < 0)
                    )::BIGINT AS invalid_physical_rows,
                    count(*) FILTER (WHERE duplicate_count > 1)::BIGINT AS duplicate_member_rows,
                    count(*) FILTER (WHERE segment_ok IS DISTINCT FROM TRUE)::BIGINT AS incorrect_session_rows
                FROM checked
            """
            params: list[object] = [
                str(binding.canonical_path),
                binding.window_start,
                binding.window_end_exclusive,
                *binding.symbols,
                MINUTE_DATASET,
                MINUTE_TIMEFRAME,
                exact_source_id,
            ]
            validation = con.execute(validation_sql, params).fetchone()
            frame = con.execute(
                """
                SELECT *
                FROM read_parquet(?, hive_partitioning=false)
                WHERE session_date BETWEEN ? AND ?
                  AND session_segment IN ('premarket', 'regular')
                ORDER BY symbol, session_date, timestamp_utc, session_segment
                """,
                [str(binding.canonical_path), start_session, end_session],
            ).fetchdf()
        except duckdb.Error as exc:
            raise B35DevelopmentSourceError(
                f"canonical minute unit violates B35 physical contract: {binding.unit_id}"
            ) from exc

        if "is_adjusted" not in frame.columns or str(frame["is_adjusted"].dtype).lower() not in {
            "bool",
            "boolean",
        }:
            raise B35DevelopmentSourceError(
                "B35 canonical schema is_adjusted must be BOOLEAN"
            )
        if validation is None or int(validation[1]) != 0:
            raise B35DevelopmentSourceError("B35 canonical unit contains invalid physical rows")
        if int(validation[2]) != 0:
            raise B35DevelopmentSourceError("B35 canonical unit contains duplicate minute keys")
        if int(validation[3]) != 0:
            raise B35DevelopmentSourceError("B35 canonical unit contains incorrect session labels")
        return frame

    def iter_unit_frames(
        self, plan: B35DevelopmentSourcePlan
    ) -> Iterator[tuple[B35DevelopmentUnitBinding, pd.DataFrame]]:
        validate_source_plan(plan)
        self.validate_scope(plan.start_session, plan.end_session)
        for binding in plan.units:
            yield binding, self.load_unit(
                binding,
                start_session=plan.start_session,
                end_session=plan.end_session,
            )

    @staticmethod
    def report(plan: B35DevelopmentSourcePlan) -> dict[str, object]:
        validate_source_plan(plan)
        months = sorted({f"{item.year:04d}-{item.month:02d}" for item in plan.units})
        return {
            "contract": B35_DEVELOPMENT_SOURCE_CONTRACT,
            "status": "PLANNED_PROTECTED_SAFE",
            "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
            "source_fingerprint": plan.source_fingerprint,
            "native_plan_sha256": plan.native_plan_sha256,
            "native_plan_file_sha256": plan.native_plan_file_sha256,
            "start_session": plan.start_session.isoformat(),
            "end_session": plan.end_session.isoformat(),
            "unit_count": len(plan.units),
            "month_count": len(months),
            "months": months,
            "exact_native_path_confinement": True,
            "lazy_hash_verification": True,
            "physical_row_validation": True,
            "raw_bundles_opened": 0,
            "consumed_master_interval": [
                CONSUMED_MASTER_START.isoformat(),
                CONSUMED_MASTER_END.isoformat(),
            ],
            "consumed_master_rows_permitted": 0,
            "consumed_master_rows_read": 0,
            "future_blind_start_on_or_after": FUTURE_BLIND_START_ON_OR_AFTER.isoformat(),
            "future_blind_rows_permitted": 0,
            "future_blind_rows_read": 0,
            "provider_calls": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "paper_authority": False,
            "live_authority": False,
            "broad_minute_materialization_authority": False,
        }



def _source_plan_payload(plan: B35DevelopmentSourcePlan) -> dict[str, object]:
    return {
        "contract": plan.contract,
        "b35_preoutcome_fingerprint": plan.b35_preoutcome_fingerprint,
        "start_session": plan.start_session.isoformat(),
        "end_session": plan.end_session.isoformat(),
        "native_plan_sha256": plan.native_plan_sha256,
        "native_plan_file_sha256": plan.native_plan_file_sha256,
        "units": [
            {
                "unit_id": item.unit_id,
                "year": item.year,
                "month": item.month,
                "batch_index": item.batch_index,
                "window_start": item.window_start.isoformat(),
                "window_end_exclusive": item.window_end_exclusive.isoformat(),
                "symbols": item.symbols,
                "policy_sha256": item.policy_sha256,
                "universe_sha256": item.universe_sha256,
                "canonical_path": str(item.canonical_path),
                "canonical_sha256": item.canonical_sha256,
                "checkpoint_path": str(item.checkpoint_path),
            }
            for item in plan.units
        ],
        "exact_native_path_confinement": True,
        "consumed_master_rows_permitted": 0,
        "future_blind_rows_permitted": 0,
        "provider_calls": 0,
        "broker_reads": 0,
        "broker_writes": 0,
    }


def validate_source_plan(plan: B35DevelopmentSourcePlan) -> str:
    if plan.contract != B35_DEVELOPMENT_SOURCE_CONTRACT:
        raise B35DevelopmentSourceError("B35 source-plan contract mismatch")
    if plan.b35_preoutcome_fingerprint != B35_PREOUTCOME_FINGERPRINT:
        raise B35DevelopmentSourceError("B35 source-plan pre-outcome fingerprint drifted")
    B35DevelopmentMinuteSource.validate_scope(plan.start_session, plan.end_session)
    if not plan.units:
        raise B35DevelopmentSourceError("B35 source plan contains no units")
    actual = _stable_hash(_source_plan_payload(plan))
    if actual != plan.source_fingerprint:
        raise B35DevelopmentSourceError("B35 source-plan fingerprint does not match its contents")
    return actual
