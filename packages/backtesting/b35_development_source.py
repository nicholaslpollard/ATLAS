from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterator

import duckdb
import pandas as pd

from packages.core.settings import AtlasSettings
from packages.data.alpaca_v2_acquisition import ACQUISITION_CONTRACT
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.intraday_semantics_audit import (
    ALPACA_V2_SOURCE_PREFIX,
    B34_MASTER_PROTECTED_END,
    B34_MASTER_PROTECTED_START,
    MINUTE_DATASET,
    MINUTE_TIMEFRAME,
    MinuteUnit,
    discover_minute_units,
)
from packages.strategies.b35_conditional_evidence_contract import (
    B35_PREOUTCOME_FINGERPRINT,
    CONSUMED_MASTER_END,
    CONSUMED_MASTER_START,
    DEVELOPMENT_LAST_SCORING_SESSION,
    FUTURE_BLIND_START_ON_OR_AFTER,
)


B35_DEVELOPMENT_SOURCE_CONTRACT = (
    "atlas-b35-development-minute-source-v1-hash-bound-preprotected-lazy-unit"
)


class B35DevelopmentSourceError(RuntimeError):
    pass


class B35DevelopmentScopeError(B35DevelopmentSourceError):
    pass


@dataclass(frozen=True, slots=True)
class B35DevelopmentUnitBinding:
    unit_id: str
    year: int
    month: int
    symbols: tuple[str, ...]
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


def _month_key(value: date) -> tuple[int, int]:
    return value.year, value.month


def _binding(unit: MinuteUnit) -> B35DevelopmentUnitBinding:
    return B35DevelopmentUnitBinding(
        unit_id=unit.unit_id,
        year=unit.year,
        month=unit.month,
        symbols=unit.symbols,
        canonical_path=unit.canonical_path.resolve(),
        canonical_sha256=unit.canonical_sha256,
        checkpoint_path=unit.checkpoint_path.resolve(),
    )


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


def _expected_minute_units(
    layout: V2Layout,
    *,
    start_session: date,
    end_session: date,
) -> tuple[dict[str, dict[str, object]], str, str]:
    """Load the frozen native acquisition plan without touching market data."""

    manifest_path = layout.manifests / "native_acquisition_plan.json"
    plan_path = layout.manifests / "native_acquisition_plan.jsonl.gz"
    manifest = _read_json_object(manifest_path, "V2 native acquisition plan manifest")
    required = {
        "contract": ACQUISITION_CONTRACT,
        "status": "FROZEN",
        "v1_ancestry": "FORBIDDEN",
    }
    for field, expected in required.items():
        if manifest.get(field) != expected:
            raise B35DevelopmentSourceError(
                f"V2 native acquisition plan {field} is not {expected!r}"
            )
    recorded_path = Path(str(manifest.get("plan_path") or ""))
    try:
        if recorded_path.resolve() != plan_path.resolve():
            raise B35DevelopmentSourceError(
                "V2 native acquisition plan path does not resolve to the isolated V2 plan"
            )
    except OSError as exc:
        raise B35DevelopmentSourceError("invalid V2 native acquisition plan path") from exc
    if not plan_path.is_file():
        raise FileNotFoundError(f"missing frozen V2 native acquisition plan: {plan_path}")

    compressed_sha = _sha256_file(plan_path)
    expected_compressed_sha = str(manifest.get("plan_file_sha256") or "")
    if compressed_sha != expected_compressed_sha:
        raise B35DevelopmentSourceError("V2 native acquisition plan file SHA-256 drifted")
    try:
        raw = gzip.decompress(plan_path.read_bytes())
    except (OSError, EOFError) as exc:
        raise B35DevelopmentSourceError("V2 native acquisition plan gzip is unreadable") from exc
    raw_sha = _sha256_bytes(raw)
    expected_raw_sha = str(manifest.get("plan_sha256") or "")
    if raw_sha != expected_raw_sha:
        raise B35DevelopmentSourceError("V2 native acquisition plan content SHA-256 drifted")

    start_month = _month_key(start_session)
    end_month = _month_key(end_session)
    expected: dict[str, dict[str, object]] = {}
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
        if str(record.get("canonical_timeframe") or "") != MINUTE_TIMEFRAME:
            continue
        if str(record.get("provider_timeframe") or "") != "1Min":
            raise B35DevelopmentSourceError("minute native plan provider timeframe drifted")
        try:
            year = int(record["year"])
            month = int(record["month"])
        except (KeyError, TypeError, ValueError) as exc:
            raise B35DevelopmentSourceError("minute native plan year/month is invalid") from exc
        key = (year, month)
        if key < start_month or key > end_month:
            continue
        if year > 2026 or (year == 2026 and month >= 5):
            raise B35DevelopmentSourceError(
                "frozen native plan selection would enter a May-2026-or-later minute partition"
            )
        unit_id = str(record.get("unit_id") or "")
        symbols = tuple(str(value) for value in record.get("symbols") or [] if str(value))
        if not unit_id or not symbols:
            raise B35DevelopmentSourceError("minute native plan unit identity/symbols are incomplete")
        if unit_id in expected:
            raise B35DevelopmentSourceError("minute native plan contains duplicate unit identity")
        expected[unit_id] = {
            "unit_id": unit_id,
            "year": year,
            "month": month,
            "symbols": symbols,
        }
    if not expected:
        raise B35DevelopmentSourceError("frozen native plan selects no B35 DEVELOPMENT minute units")
    return expected, raw_sha, compressed_sha


def _validate_expected_coverage(
    expected: dict[str, dict[str, object]],
    discovered: tuple[MinuteUnit, ...],
    *,
    start_session: date,
    end_session: date,
) -> tuple[B35DevelopmentUnitBinding, ...]:
    start_month = _month_key(start_session)
    end_month = _month_key(end_session)
    actual: dict[str, MinuteUnit] = {}
    for unit in discovered:
        key = (unit.year, unit.month)
        if key < start_month or key > end_month:
            continue
        if unit.unit_id in actual:
            raise B35DevelopmentSourceError("completed minute-unit identity is duplicated")
        actual[unit.unit_id] = unit

    missing = sorted(set(expected) - set(actual))
    unexpected = sorted(set(actual) - set(expected))
    if missing or unexpected:
        detail = []
        if missing:
            detail.append(f"missing_expected={len(missing)} first={missing[:3]}")
        if unexpected:
            detail.append(f"unexpected_completed={len(unexpected)} first={unexpected[:3]}")
        raise B35DevelopmentSourceError(
            "B35 DEVELOPMENT minute coverage is not exact: " + "; ".join(detail)
        )

    selected: list[B35DevelopmentUnitBinding] = []
    for unit_id in sorted(expected):
        record = expected[unit_id]
        unit = actual[unit_id]
        if (
            unit.year != int(record["year"])
            or unit.month != int(record["month"])
            or unit.symbols != tuple(record["symbols"])
        ):
            raise B35DevelopmentSourceError(
                f"completed minute unit does not match its frozen plan: {unit_id}"
            )
        binding = _binding(unit)
        if len(binding.canonical_sha256) != 64:
            raise B35DevelopmentSourceError(
                f"minute unit has no canonical SHA-256 binding: {binding.unit_id}"
            )
        selected.append(binding)
    return tuple(
        sorted(selected, key=lambda item: (item.year, item.month, item.symbols, item.unit_id))
    )


class B35DevelopmentMinuteSource:
    """Read only accepted pre-protected V2 minute units for B35 DEVELOPMENT.

    Planning verifies exact coverage against the immutable native acquisition plan
    while reading metadata only. A canonical parquet is hash verified immediately
    before that one unit is opened. No raw bundle, May-2026 partition, consumed
    master, future blind, provider, or broker source is opened here.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.layout = V2Layout.beneath((settings.project_root / "data").resolve())

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
        expected, native_plan_sha, native_plan_file_sha = _expected_minute_units(
            self.layout,
            start_session=start_session,
            end_session=end_session,
        )
        discovered = discover_minute_units(self.layout)
        selected = _validate_expected_coverage(
            expected,
            discovered,
            start_session=start_session,
            end_session=end_session,
        )
        payload = {
            "contract": B35_DEVELOPMENT_SOURCE_CONTRACT,
            "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
            "start_session": start_session.isoformat(),
            "end_session": end_session.isoformat(),
            "native_plan_sha256": native_plan_sha,
            "native_plan_file_sha256": native_plan_file_sha,
            "expected_unit_count": len(expected),
            "units": [
                {
                    "unit_id": item.unit_id,
                    "year": item.year,
                    "month": item.month,
                    "symbols": item.symbols,
                    "canonical_path": str(item.canonical_path),
                    "canonical_sha256": item.canonical_sha256,
                    "checkpoint_path": str(item.checkpoint_path),
                }
                for item in selected
            ],
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
            units=selected,
            native_plan_sha256=native_plan_sha,
            native_plan_file_sha256=native_plan_file_sha,
            source_fingerprint=_stable_hash(payload),
        )

    @staticmethod
    def verify_unit(binding: B35DevelopmentUnitBinding) -> str:
        if binding.year > 2026 or (binding.year == 2026 and binding.month >= 5):
            raise B35DevelopmentSourceError(
                "refusing to hash/open a minute unit in or after May 2026"
            )
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

    @staticmethod
    def load_unit(
        binding: B35DevelopmentUnitBinding,
        *,
        start_session: date,
        end_session: date,
    ) -> pd.DataFrame:
        B35DevelopmentMinuteSource.validate_scope(start_session, end_session)
        if (binding.year, binding.month) < _month_key(start_session) or (
            binding.year,
            binding.month,
        ) > _month_key(end_session):
            raise B35DevelopmentSourceError("unit lies outside the requested B35 scope")
        B35DevelopmentMinuteSource.verify_unit(binding)
        con = duckdb.connect(":memory:")
        con.execute("SET TimeZone='UTC'")
        try:
            stats = con.execute(
                """
                SELECT
                    count(*) AS rows,
                    count(*) FILTER (
                        WHERE session_date > ?
                           OR session_date BETWEEN ? AND ?
                           OR session_date >= ?
                    ) AS forbidden_rows,
                    count(*) FILTER (
                        WHERE provider <> 'alpaca'
                           OR dataset <> ?
                           OR timeframe <> ?
                           OR is_adjusted <> FALSE
                           OR source_id NOT LIKE ?
                           OR timestamp_utc <> provider_timestamp_utc
                           OR open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
                           OR volume < 0
                           OR high < greatest(open, close)
                           OR low > least(open, close)
                           OR high < low
                    ) AS invalid_rows
                FROM read_parquet(?, hive_partitioning=false)
                WHERE session_date BETWEEN ? AND ?
                """,
                [
                    DEVELOPMENT_LAST_SCORING_SESSION,
                    B34_MASTER_PROTECTED_START,
                    B34_MASTER_PROTECTED_END,
                    FUTURE_BLIND_START_ON_OR_AFTER,
                    MINUTE_DATASET,
                    MINUTE_TIMEFRAME,
                    ALPACA_V2_SOURCE_PREFIX + "%",
                    str(binding.canonical_path),
                    start_session,
                    end_session,
                ],
            ).fetchone()
            frame = con.execute(
                """
                SELECT *
                FROM read_parquet(?, hive_partitioning=false)
                WHERE session_date BETWEEN ? AND ?
                ORDER BY symbol, session_date, timestamp_utc, session_segment
                """,
                [str(binding.canonical_path), start_session, end_session],
            ).fetchdf()
        except duckdb.Error as exc:
            raise B35DevelopmentSourceError(
                f"canonical minute unit violates B35 physical contract: {binding.unit_id}"
            ) from exc
        finally:
            con.close()
        assert stats is not None
        if int(stats[1]) != 0:
            raise B35DevelopmentSourceError("B35 unit query exposed forbidden-date rows")
        if int(stats[2]) != 0:
            raise B35DevelopmentSourceError("B35 unit contains invalid canonical minute rows")
        if int(stats[0]) != len(frame):
            raise B35DevelopmentSourceError("B35 unit row accounting mismatch")
        return frame

    def iter_unit_frames(
        self,
        plan: B35DevelopmentSourcePlan,
    ) -> Iterator[tuple[B35DevelopmentUnitBinding, pd.DataFrame]]:
        if plan.contract != B35_DEVELOPMENT_SOURCE_CONTRACT:
            raise B35DevelopmentSourceError("B35 source-plan contract mismatch")
        if plan.b35_preoutcome_fingerprint != B35_PREOUTCOME_FINGERPRINT:
            raise B35DevelopmentSourceError("B35 source-plan pre-outcome fingerprint drifted")
        self.validate_scope(plan.start_session, plan.end_session)
        for binding in plan.units:
            yield binding, self.load_unit(
                binding,
                start_session=plan.start_session,
                end_session=plan.end_session,
            )

    @staticmethod
    def report(plan: B35DevelopmentSourcePlan) -> dict[str, object]:
        months = sorted({f"{item.year:04d}-{item.month:02d}" for item in plan.units})
        return {
            "contract": B35_DEVELOPMENT_SOURCE_CONTRACT,
            "status": "PLANNED_PROTECTED_SAFE",
            "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
            "source_fingerprint": plan.source_fingerprint,
            "start_session": plan.start_session.isoformat(),
            "end_session": plan.end_session.isoformat(),
            "unit_count": len(plan.units),
            "month_count": len(months),
            "months": months,
            "native_plan_sha256": plan.native_plan_sha256,
            "native_plan_file_sha256": plan.native_plan_file_sha256,
            "expected_unit_coverage_exact": True,
            "lazy_hash_verification": True,
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
