from __future__ import annotations

import gzip
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Iterable, Iterator
from zoneinfo import ZoneInfo

import duckdb

from packages.core.market_calendar import MarketCalendar
from packages.data.alpaca_v2_rebuild import V2Layout


B34_CONTRACT = "atlas-b34-intraday-semantics-audit-v1"
B34_SAMPLE_CONTRACT = "atlas-b34-intraday-canonical-samples-v1"

# Deliberately stop at the last complete calendar month before the frozen
# DEVELOPMENT boundary. This means the audit never opens a monthly minute
# partition that overlaps the consumed master holdout beginning 2026-05-12.
B34_MAX_SAMPLE_DATE = date(2026, 4, 30)
B34_MASTER_PROTECTED_START = date(2026, 5, 12)
B34_MASTER_PROTECTED_END = date(2026, 8, 11)

MINUTE_DATASET = "stock_minute_aggregates"
MINUTE_TIMEFRAME = "1m"
ALPACA_V2_SOURCE_PREFIX = "alpaca:sip:1Min:raw:asof=-:v2:unit="

REQUIRED_SAMPLE_CLASSES = (
    "liquid_symbol_day",
    "sparse_or_no_trade_symbol_day",
    "split_day",
    "other_corporate_action_day",
    "dst_session_boundary_day",
)
COMPLETE_UNIT_STATUSES = {"COMPLETE", "COMPLETE_WITH_QUARANTINE"}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SPLIT_ACTION_TYPES = {"forward_splits", "reverse_splits", "unit_splits"}
_ACTION_DATE_KEYS = (
    "ex_date",
    "effective_date",
    "execution_date",
    "record_date",
    "payable_date",
    "declaration_date",
)


class IntradaySemanticsAuditError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MinuteUnit:
    checkpoint_path: Path
    canonical_path: Path
    raw_bundle_path: Path
    status: str
    year: int
    month: int
    symbols: tuple[str, ...]
    unit_id: str
    canonical_sha256: str
    raw_bundle_sha256: str


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _iso_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    text = value.strip()[:10]
    if not _DATE_RE.match(text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntradaySemanticsAuditError(f"unreadable JSON evidence: {path}") from exc
    if not isinstance(value, dict):
        raise IntradaySemanticsAuditError(f"JSON evidence is not an object: {path}")
    return value


def _path_from_checkpoint(value: object, checkpoint_path: Path) -> Path:
    path = Path(str(value or ""))
    if path.is_absolute():
        return path
    # Historical V2 checkpoints normally persist workstation-absolute paths.
    # Tests and relocations may use relative paths; resolve those against the
    # repository/project root inferred from the checkpoint tree.
    candidates = [checkpoint_path.parent / path, Path.cwd() / path]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return path.resolve()


def discover_minute_units(layout: V2Layout) -> tuple[MinuteUnit, ...]:
    root = layout.checkpoints / "native_units" / "1m"
    if not root.is_dir():
        raise IntradaySemanticsAuditError(f"missing V2 minute checkpoint root: {root}")

    units: list[MinuteUnit] = []
    for checkpoint_path in sorted(root.rglob("*.json")):
        document = _read_json(checkpoint_path)
        status = str(document.get("status") or "")
        if status not in COMPLETE_UNIT_STATUSES:
            continue
        unit = document.get("unit") or {}
        canonical = document.get("canonical") or {}
        raw_bundle = document.get("raw_bundle") or {}
        if not isinstance(unit, dict) or not isinstance(canonical, dict) or not isinstance(raw_bundle, dict):
            continue
        if str(unit.get("canonical_timeframe") or "") != MINUTE_TIMEFRAME:
            continue
        year = int(unit.get("year") or 0)
        month = int(unit.get("month") or 0)
        if year < 1900 or not 1 <= month <= 12:
            continue
        # Never select a monthly partition that could physically overlap the
        # consumed master holdout. May 2026 and later are excluded entirely.
        if date(year, month, 1) > date(B34_MAX_SAMPLE_DATE.year, B34_MAX_SAMPLE_DATE.month, 1):
            continue
        symbols = tuple(str(v) for v in unit.get("symbols") or [] if str(v))
        canonical_path = _path_from_checkpoint(canonical.get("path"), checkpoint_path)
        raw_bundle_path = _path_from_checkpoint(raw_bundle.get("path"), checkpoint_path)
        units.append(
            MinuteUnit(
                checkpoint_path=checkpoint_path,
                canonical_path=canonical_path,
                raw_bundle_path=raw_bundle_path,
                status=status,
                year=year,
                month=month,
                symbols=symbols,
                unit_id=str(document.get("unit_id") or ""),
                canonical_sha256=str(canonical.get("sha256") or ""),
                raw_bundle_sha256=str(raw_bundle.get("sha256") or ""),
            )
        )
    if not units:
        raise IntradaySemanticsAuditError(
            "no completed pre-protected V2 minute units were found"
        )
    return tuple(units)


def verify_unit_integrity(unit: MinuteUnit) -> dict[str, object]:
    errors: list[str] = []
    for label, path, expected in (
        ("canonical", unit.canonical_path, unit.canonical_sha256),
        ("raw_bundle", unit.raw_bundle_path, unit.raw_bundle_sha256),
    ):
        if not path.is_file():
            errors.append(f"{label} missing: {path}")
            continue
        actual = _sha256_file(path)
        if not expected:
            errors.append(f"{label} checkpoint has no sha256")
        elif actual != expected:
            errors.append(f"{label} sha256 mismatch")
    return {
        "checkpoint_path": str(unit.checkpoint_path),
        "unit_id": unit.unit_id,
        "status": unit.status,
        "canonical_path": str(unit.canonical_path),
        "raw_bundle_path": str(unit.raw_bundle_path),
        "accepted": not errors,
        "errors": errors,
    }


def _connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute("SET TimeZone='UTC'")
    con.execute("PRAGMA threads=2")
    return con


def _sample_rows(
    path: Path,
    *,
    symbol: str,
    session_date: date,
) -> list[dict[str, object]]:
    if session_date > B34_MAX_SAMPLE_DATE:
        raise IntradaySemanticsAuditError(
            f"B34 refuses sample date after {B34_MAX_SAMPLE_DATE.isoformat()}: {session_date}"
        )
    con = _connect()
    try:
        description = con.execute(
            "DESCRIBE SELECT * FROM read_parquet(?, hive_partitioning=false)",
            [str(path)],
        ).fetchall()
        columns = [str(row[0]) for row in description]
        rows = con.execute(
            """
            SELECT *
            FROM read_parquet(?, hive_partitioning=false)
            WHERE symbol = ? AND session_date = ?
            ORDER BY timestamp_utc, session_segment
            """,
            [str(path), symbol, session_date],
        ).fetchall()
        return [dict(zip(columns, row, strict=True)) for row in rows]
    finally:
        con.close()


def validate_minute_rows(
    rows: Iterable[dict[str, object]],
    *,
    sample_class: str,
    symbol: str,
    session_date: date,
    calendar: MarketCalendar | None = None,
    market_tz: ZoneInfo | None = None,
    allow_empty: bool = False,
) -> dict[str, object]:
    calendar = calendar or MarketCalendar()
    market_tz = market_tz or ZoneInfo("America/New_York")
    materialized = list(rows)
    errors: list[str] = []
    warnings: list[str] = []

    if session_date > B34_MAX_SAMPLE_DATE:
        errors.append("sample date exceeds B34 pre-protected audit cutoff")
    if B34_MASTER_PROTECTED_START <= session_date <= B34_MASTER_PROTECTED_END:
        errors.append("sample date intersects the consumed master holdout")
    if not materialized and not allow_empty:
        errors.append("sample contains no canonical minute rows")

    seen: set[tuple[object, ...]] = set()
    previous_timestamp: datetime | None = None
    gap_count = 0
    segments: dict[str, int] = {}
    utc_offsets: set[int] = set()

    for index, row in enumerate(materialized):
        row_symbol = str(row.get("symbol") or "")
        if row_symbol != symbol:
            errors.append(f"row {index}: symbol mismatch {row_symbol!r}")
        row_session = row.get("session_date")
        if isinstance(row_session, datetime):
            row_session = row_session.date()
        elif isinstance(row_session, str):
            row_session = _iso_date(row_session)
        if row_session != session_date:
            errors.append(f"row {index}: session_date mismatch {row_session!r}")

        timestamp = row.get("timestamp_utc")
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                timestamp = None
        if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
            errors.append(f"row {index}: invalid/naive timestamp_utc")
            continue
        timestamp = timestamp.astimezone(UTC)
        if timestamp.second != 0 or timestamp.microsecond != 0:
            errors.append(f"row {index}: timestamp is not aligned to a minute start")
        local = timestamp.astimezone(market_tz)
        if local.date() != session_date:
            errors.append(f"row {index}: New York local date does not equal session_date")
        offset = local.utcoffset()
        if offset is not None:
            utc_offsets.add(int(offset.total_seconds()))

        provider_timestamp = row.get("provider_timestamp_utc")
        if isinstance(provider_timestamp, str):
            try:
                provider_timestamp = datetime.fromisoformat(
                    provider_timestamp.replace("Z", "+00:00")
                )
            except ValueError:
                provider_timestamp = None
        if not isinstance(provider_timestamp, datetime) or provider_timestamp.tzinfo is None:
            errors.append(f"row {index}: missing provider_timestamp_utc")
        elif provider_timestamp.astimezone(UTC) != timestamp:
            errors.append(f"row {index}: canonical timestamp differs from provider timestamp")

        if str(row.get("timeframe") or "") != MINUTE_TIMEFRAME:
            errors.append(f"row {index}: timeframe is not {MINUTE_TIMEFRAME}")
        if str(row.get("dataset") or "") != MINUTE_DATASET:
            errors.append(f"row {index}: dataset is not {MINUTE_DATASET}")
        provider = str(row.get("provider") or "")
        if provider != "alpaca":
            errors.append(f"row {index}: V2 provider is not alpaca")
        if row.get("is_adjusted") is not False:
            errors.append(f"row {index}: V2 minute row is not explicitly raw/unadjusted")
        source_id = str(row.get("source_id") or "")
        if not source_id.startswith(ALPACA_V2_SOURCE_PREFIX):
            errors.append(f"row {index}: source_id does not lock SIP/1Min/raw/asof=- semantics")

        segment = str(row.get("session_segment") or "")
        expected_segment = calendar.classify(timestamp).value
        if segment != expected_segment:
            errors.append(
                f"row {index}: session segment {segment!r} != calendar {expected_segment!r}"
            )
        segments[segment] = segments.get(segment, 0) + 1

        key = (row_symbol, timestamp, row.get("timeframe"), segment)
        if key in seen:
            errors.append(f"row {index}: duplicate canonical bar key")
        seen.add(key)

        if previous_timestamp is not None:
            if timestamp < previous_timestamp:
                errors.append(f"row {index}: timestamps are not monotonic")
            delta = int((timestamp - previous_timestamp).total_seconds())
            if delta > 60:
                gap_count += 1
        previous_timestamp = timestamp

    if gap_count:
        warnings.append(
            "gaps are preserved as source facts; B34 does not synthesize missing minute bars"
        )

    return {
        "contract": B34_SAMPLE_CONTRACT,
        "sample_class": sample_class,
        "symbol": symbol,
        "session_date": session_date.isoformat(),
        "row_count": len(materialized),
        "allow_empty": allow_empty,
        "absence_evidence": bool(allow_empty and not materialized),
        "segment_counts": dict(sorted(segments.items())),
        "utc_offset_seconds": sorted(utc_offsets),
        "gap_count": gap_count,
        "accepted": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def _group_counts(path: Path, session_date: date) -> list[tuple[str, int]]:
    con = _connect()
    try:
        rows = con.execute(
            """
            SELECT symbol, count(*)::BIGINT AS n
            FROM read_parquet(?, hive_partitioning=false)
            WHERE session_date = ?
            GROUP BY symbol
            ORDER BY symbol
            """,
            [str(path), session_date],
        ).fetchall()
        return [(str(symbol), int(count)) for symbol, count in rows]
    finally:
        con.close()


def _has_rows(path: Path, symbol: str, session_date: date) -> bool:
    con = _connect()
    try:
        value = con.execute(
            """
            SELECT EXISTS(
                SELECT 1
                FROM read_parquet(?, hive_partitioning=false)
                WHERE symbol = ? AND session_date = ?
                LIMIT 1
            )
            """,
            [str(path), symbol, session_date],
        ).fetchone()
        return bool(value and value[0])
    finally:
        con.close()


def _session_dates(path: Path) -> tuple[date, ...]:
    con = _connect()
    try:
        rows = con.execute(
            """
            SELECT DISTINCT session_date
            FROM read_parquet(?, hive_partitioning=false)
            WHERE session_date <= ?
            ORDER BY session_date
            """,
            [str(path), B34_MAX_SAMPLE_DATE],
        ).fetchall()
        return tuple(row[0] for row in rows if isinstance(row[0], date))
    finally:
        con.close()


def select_liquid_and_sparse(units: tuple[MinuteUnit, ...]) -> tuple[dict[str, object], dict[str, object]]:
    # Newest fully pre-protected month first; path is a deterministic tiebreaker.
    candidates = sorted(
        units,
        key=lambda item: (item.year, item.month, str(item.checkpoint_path)),
        reverse=True,
    )
    for unit in candidates:
        if not unit.canonical_path.is_file():
            continue
        sessions = _session_dates(unit.canonical_path)
        if not sessions:
            continue
        session_date = sessions[-1]
        counts = _group_counts(unit.canonical_path, session_date)
        if not counts:
            continue
        by_symbol = dict(counts)
        liquid_symbol, liquid_count = sorted(
            counts, key=lambda item: (-item[1], item[0])
        )[0]
        missing_symbols = sorted(set(unit.symbols) - set(by_symbol))
        if missing_symbols:
            sparse_symbol = missing_symbols[0]
            sparse_count = 0
            sparse_empty = True
        else:
            sparse_symbol, sparse_count = sorted(counts, key=lambda item: (item[1], item[0]))[0]
            sparse_empty = False

        liquid = {
            "unit": unit,
            "symbol": liquid_symbol,
            "session_date": session_date,
            "row_count_hint": liquid_count,
            "allow_empty": False,
        }
        sparse = {
            "unit": unit,
            "symbol": sparse_symbol,
            "session_date": session_date,
            "row_count_hint": sparse_count,
            "allow_empty": sparse_empty,
        }
        return liquid, sparse
    raise IntradaySemanticsAuditError("could not select liquid/sparse deterministic minute samples")


def _walk_values(value: object) -> Iterator[tuple[str | None, object]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key), child
            yield from _walk_values(child)
    elif isinstance(value, list):
        for child in value:
            yield None, child
            yield from _walk_values(child)


def _action_symbols(payload: object) -> tuple[str, ...]:
    symbols: set[str] = set()
    if isinstance(payload, dict):
        for key, child in payload.items():
            normalized = str(key).lower().replace("-", "_")
            is_symbol = normalized == "symbol" or normalized.endswith("_symbol")
            if is_symbol and isinstance(child, str):
                symbol = child.strip()
                if symbol and "," not in symbol and not any(ch.isspace() for ch in symbol):
                    symbols.add(symbol)
            elif normalized in {"symbols", "new_symbols", "old_symbols"} and isinstance(child, list):
                for item in child:
                    if isinstance(item, str) and item.strip():
                        symbols.add(item.strip())
            if isinstance(child, (dict, list)):
                symbols.update(_action_symbols(child))
    elif isinstance(payload, list):
        for child in payload:
            symbols.update(_action_symbols(child))
    return tuple(sorted(symbols))


def _action_date(payload: object) -> date | None:
    if not isinstance(payload, dict):
        return None
    for key in _ACTION_DATE_KEYS:
        candidate = _iso_date(payload.get(key))
        if candidate is not None:
            return candidate
    for raw_key, value in _walk_values(payload):
        if raw_key is None:
            continue
        key = raw_key.lower().replace("-", "_")
        if key.endswith("_date") or key == "date":
            candidate = _iso_date(value)
            if candidate is not None:
                return candidate
    return None


def _corporate_action_records(layout: V2Layout) -> Iterator[dict[str, object]]:
    path = layout.corporate_actions / "native_actions.jsonl.gz"
    if not path.is_file():
        return
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                value = json.loads(line)
                if isinstance(value, dict):
                    yield value
    except (OSError, json.JSONDecodeError) as exc:
        raise IntradaySemanticsAuditError(
            f"unreadable V2 corporate-action evidence: {path}"
        ) from exc


def select_corporate_action(
    layout: V2Layout,
    units: tuple[MinuteUnit, ...],
    *,
    split: bool,
) -> dict[str, object] | None:
    candidates: list[tuple[date, str, str]] = []
    for record in _corporate_action_records(layout):
        action_type = str(record.get("action_type") or "")
        if (action_type in _SPLIT_ACTION_TYPES) != split:
            continue
        payload = record.get("payload")
        action_date = _action_date(payload)
        if action_date is None or action_date > B34_MAX_SAMPLE_DATE:
            continue
        for symbol in _action_symbols(payload):
            candidates.append((action_date, symbol, action_type))
    for action_date, symbol, action_type in sorted(candidates, reverse=True):
        for unit in units:
            if unit.year != action_date.year or unit.month != action_date.month:
                continue
            if symbol not in unit.symbols or not unit.canonical_path.is_file():
                continue
            if not _has_rows(unit.canonical_path, symbol, action_date):
                continue
            return {
                "unit": unit,
                "symbol": symbol,
                "session_date": action_date,
                "action_type": action_type,
                "allow_empty": False,
            }
    return None


def _dst_transition_sessions(calendar: MarketCalendar) -> tuple[date, ...]:
    sessions = calendar.sessions_in_range(date(2016, 1, 1), B34_MAX_SAMPLE_DATE)
    transitions: list[date] = []
    previous_offset: int | None = None
    for session in sessions:
        open_utc, _close_utc = calendar.regular_open_close(session)
        offset = open_utc.astimezone(ZoneInfo("America/New_York")).utcoffset()
        seconds = int(offset.total_seconds()) if offset is not None else 0
        if previous_offset is not None and seconds != previous_offset:
            transitions.append(session)
        previous_offset = seconds
    return tuple(transitions)


def select_dst_sample(
    units: tuple[MinuteUnit, ...],
    *,
    calendar: MarketCalendar | None = None,
) -> dict[str, object]:
    calendar = calendar or MarketCalendar()
    for session_date in reversed(_dst_transition_sessions(calendar)):
        for unit in units:
            if unit.year != session_date.year or unit.month != session_date.month:
                continue
            if not unit.canonical_path.is_file():
                continue
            counts = _group_counts(unit.canonical_path, session_date)
            if not counts:
                continue
            symbol = sorted(counts, key=lambda item: (-item[1], item[0]))[0][0]
            return {
                "unit": unit,
                "symbol": symbol,
                "session_date": session_date,
                "allow_empty": False,
            }
    raise IntradaySemanticsAuditError("could not select a DST-sensitive minute sample")


def _unavailable_sample(sample_class: str, reason: str) -> dict[str, object]:
    return {
        "contract": B34_SAMPLE_CONTRACT,
        "sample_class": sample_class,
        "status": "UNAVAILABLE_WITH_EVIDENCE",
        "accepted": True,
        "reason": reason,
        "row_count": 0,
    }


def _audit_selected(
    sample_class: str,
    selected: dict[str, object],
    *,
    calendar: MarketCalendar,
    market_tz: ZoneInfo,
) -> tuple[dict[str, object], dict[str, object]]:
    unit = selected["unit"]
    assert isinstance(unit, MinuteUnit)
    symbol = str(selected["symbol"])
    session_date = selected["session_date"]
    assert isinstance(session_date, date)
    integrity = verify_unit_integrity(unit)
    if not integrity["accepted"]:
        report = {
            "contract": B34_SAMPLE_CONTRACT,
            "sample_class": sample_class,
            "symbol": symbol,
            "session_date": session_date.isoformat(),
            "row_count": 0,
            "accepted": False,
            "errors": ["selected unit failed hash/path integrity"],
            "warnings": [],
        }
        return report, integrity
    rows = _sample_rows(unit.canonical_path, symbol=symbol, session_date=session_date)
    report = validate_minute_rows(
        rows,
        sample_class=sample_class,
        symbol=symbol,
        session_date=session_date,
        calendar=calendar,
        market_tz=market_tz,
        allow_empty=bool(selected.get("allow_empty", False)),
    )
    report["canonical_path"] = str(unit.canonical_path)
    report["unit_id"] = unit.unit_id
    if "action_type" in selected:
        report["action_type"] = str(selected["action_type"])
    if "row_count_hint" in selected:
        report["row_count_hint"] = int(selected["row_count_hint"])
    return report, integrity


def run_b34_audit(project_root: Path) -> dict[str, object]:
    project_root = project_root.resolve()
    data_root = project_root / "data"
    layout = V2Layout.beneath(data_root)
    units = discover_minute_units(layout)
    calendar = MarketCalendar()
    market_tz = ZoneInfo("America/New_York")

    liquid, sparse = select_liquid_and_sparse(units)
    split = select_corporate_action(layout, units, split=True)
    other = select_corporate_action(layout, units, split=False)
    dst = select_dst_sample(units, calendar=calendar)

    selections: list[tuple[str, dict[str, object] | None]] = [
        ("liquid_symbol_day", liquid),
        ("sparse_or_no_trade_symbol_day", sparse),
        ("split_day", split),
        ("other_corporate_action_day", other),
        ("dst_session_boundary_day", dst),
    ]

    samples: list[dict[str, object]] = []
    integrity_by_unit: dict[str, dict[str, object]] = {}
    for sample_class, selected in selections:
        if selected is None:
            kind = "split" if sample_class == "split_day" else "non-split corporate action"
            samples.append(
                _unavailable_sample(
                    sample_class,
                    f"no {kind} with a usable provider-literal symbol/date exists in a "
                    f"fully pre-protected V2 minute unit through {B34_MAX_SAMPLE_DATE.isoformat()}",
                )
            )
            continue
        report, integrity = _audit_selected(
            sample_class,
            selected,
            calendar=calendar,
            market_tz=market_tz,
        )
        samples.append(report)
        integrity_by_unit[str(integrity["unit_id"])] = integrity

    missing_classes = sorted(set(REQUIRED_SAMPLE_CLASSES) - {str(s["sample_class"]) for s in samples})
    if missing_classes:
        raise IntradaySemanticsAuditError(
            f"internal B34 sample coverage bug: missing {missing_classes}"
        )

    accepted = all(bool(sample.get("accepted")) for sample in samples) and all(
        bool(item.get("accepted")) for item in integrity_by_unit.values()
    )
    report = {
        "contract": B34_CONTRACT,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "status": "ACCEPTED" if accepted else "REJECTED",
        "accepted": accepted,
        "scope": "finite read-only V2 minute semantics audit",
        "max_sample_date": B34_MAX_SAMPLE_DATE.isoformat(),
        "protected_interval": {
            "start": B34_MASTER_PROTECTED_START.isoformat(),
            "end": B34_MASTER_PROTECTED_END.isoformat(),
            "overlapping_canonical_partitions_opened": 0,
            "note": "all selected monthly partitions end no later than April 2026",
        },
        "provider_contract": {
            "provider": "alpaca",
            "feed": "sip",
            "provider_timeframe": "1Min",
            "canonical_timeframe": MINUTE_TIMEFRAME,
            "adjustment": "raw",
            "asof": "-",
            "interval_timestamp": "left_edge_start",
            "session_timezone": "America/New_York",
            "missing_minutes": "preserve_absence_no_synthesis",
        },
        "sample_classes": samples,
        "unit_integrity": [
            integrity_by_unit[key] for key in sorted(integrity_by_unit)
        ],
        "provider_calls": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "paper_authority": False,
        "live_authority": False,
        "full_minute_materialization_authority": False,
    }
    report["evidence_sha256"] = hashlib.sha256(
        _stable_json({k: v for k, v in report.items() if k != "generated_at_utc"}).encode("utf-8")
    ).hexdigest()
    return report


def write_b34_report(project_root: Path, report: dict[str, object]) -> Path:
    project_root = project_root.resolve()
    layout = V2Layout.beneath(project_root / "data")
    target = layout.validation / "b34_intraday_semantics_audit.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".json.tmp")
    temp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(target)
    return target
