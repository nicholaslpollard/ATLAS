from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Callable, Iterator
from zoneinfo import ZoneInfo

import duckdb
import pandas as pd

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings
from packages.data.alpaca_v2_rebuild import MIN_FREE_RESERVE_BYTES, V2Layout, disk_guard
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.providers.alpaca import (
    AlpacaApiPage,
    AlpacaInvalidSymbolError,
    AlpacaMarketDataClient,
)
from packages.schemas.canonical_market import canonical_stock_daily_schema_matches


ACQUISITION_CONTRACT = "atlas-alpaca-sip-v2-native-acquisition-v1"
BOOTSTRAP_CONTRACT = "atlas-alpaca-sip-v2-bootstrap-v1"
SOURCE_SNAPSHOT_CONTRACT = "atlas-alpaca-sip-v2-source-snapshot-v1"
UNIT_CONTRACT = "atlas-alpaca-sip-v2-native-unit-v1"
RAW_BUNDLE_CONTRACT = "concatenated-deterministic-gzip-members-v1"

V2_FEED = "sip"
V2_ADJUSTMENT = "raw"
V2_ASOF = "-"
V2_PAGE_LIMIT = 10_000
V2_SYMBOL_BATCH_SIZE = 100
V2_DEFAULT_START = date(2016, 1, 4)
V2_TRANSIENT_WORK_BYTES = 2 * 1024**3

COMPLETE_UNIT_STATUSES = {
    "COMPLETE",
    "COMPLETE_WITH_QUARANTINE",
    "BLOCKED_VALIDATION",
}


class V2DiskFloorError(RuntimeError):
    pass


class V2TimeLimitReached(RuntimeError):
    pass


def _stable_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_bytes(path: Path, payload: bytes, *, fsync: bool = True) -> None:
    temp = unique_temp_path(path)
    try:
        with temp.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            if fsync:
                os.fsync(handle.fileno())
        replace_with_retry(temp, path)
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def _atomic_write_gzip(path: Path, payload: bytes) -> tuple[str, int, int]:
    compressed = gzip.compress(payload, compresslevel=6, mtime=0)
    _atomic_write_bytes(path, compressed)
    return _sha256_bytes(payload), len(payload), len(compressed)


def _read_gzip_verified(path: Path, expected_sha256: str) -> bytes:
    if not path.is_file():
        raise RuntimeError(f"missing immutable source payload: {path}")
    try:
        payload = gzip.decompress(path.read_bytes())
    except (OSError, EOFError) as exc:
        raise RuntimeError(f"unreadable immutable source payload: {path}") from exc
    if _sha256_bytes(payload) != expected_sha256:
        raise RuntimeError(f"immutable source payload hash mismatch: {path}")
    return payload


def _clean_symbol(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    symbol = value.strip()
    if not symbol or len(symbol) > 64 or "," in symbol or any(ch.isspace() for ch in symbol):
        return None
    return symbol


def _chunks(values: list[str], size: int) -> Iterator[tuple[str, ...]]:
    for index in range(0, len(values), size):
        yield tuple(values[index : index + size])


def _exclusive_windows(start: date, cutoff: date, timeframe: str) -> list[tuple[date, date]]:
    """Return adjacent [start, end) API windows through the frozen cutoff."""

    if start > cutoff:
        raise ValueError("V2 start date is after the frozen cutoff")
    final_end = cutoff + timedelta(days=1)
    result: list[tuple[date, date]] = []
    cursor = start
    while cursor < final_end:
        if timeframe == "1Day":
            boundary = date(cursor.year + 1, 1, 1)
        elif timeframe == "1Min":
            boundary = (
                date(cursor.year + 1, 1, 1)
                if cursor.month == 12
                else date(cursor.year, cursor.month + 1, 1)
            )
        else:
            raise ValueError(f"unsupported native timeframe: {timeframe}")
        end = min(boundary, final_end)
        result.append((cursor, end))
        cursor = end
    return result


def last_completed_session(
    calendar: MarketCalendar,
    *,
    now_utc: datetime | None = None,
) -> date:
    now = now_utc or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")
    now = now.astimezone(UTC)
    candidate = now.date()
    for _ in range(370):
        if calendar.is_session(candidate):
            _open, close = calendar.regular_open_close(candidate)
            if close <= now:
                return candidate
        candidate -= timedelta(days=1)
    raise RuntimeError("could not resolve the most recent completed exchange session")


@dataclass(frozen=True, slots=True)
class NativeAcquisitionUnit:
    unit_id: str
    provider_timeframe: str
    canonical_timeframe: str
    window_start: str
    window_end_exclusive: str
    year: int
    month: int | None
    batch_index: int
    symbols: tuple[str, ...]
    universe_sha256: str
    policy_sha256: str

    @property
    def label(self) -> str:
        window = f"{self.year:04d}" if self.month is None else f"{self.year:04d}-{self.month:02d}"
        return f"{self.canonical_timeframe} {window} batch {self.batch_index:04d}"


def _unit_id(
    *,
    provider_timeframe: str,
    window_start: date,
    window_end: date,
    batch_index: int,
    symbols: tuple[str, ...],
    universe_sha256: str,
    policy_sha256: str,
) -> str:
    return hashlib.sha256(
        _stable_json(
            {
                "contract": UNIT_CONTRACT,
                "provider_timeframe": provider_timeframe,
                "window_start": window_start.isoformat(),
                "window_end_exclusive": window_end.isoformat(),
                "batch_index": batch_index,
                "symbols": list(symbols),
                "universe_sha256": universe_sha256,
                "policy_sha256": policy_sha256,
            }
        )
    ).hexdigest()


def build_native_plan(
    *,
    symbols: list[str],
    start: date,
    cutoff: date,
    universe_sha256: str,
    policy_sha256: str,
    batch_size: int = V2_SYMBOL_BATCH_SIZE,
) -> list[NativeAcquisitionUnit]:
    if symbols != sorted(set(symbols)):
        raise ValueError("V2 acquisition symbols must be sorted and exact-unique")
    batches = list(_chunks(symbols, batch_size))
    units: list[NativeAcquisitionUnit] = []
    for provider_timeframe, canonical_timeframe in (("1Day", "1d"), ("1Min", "1m")):
        for window_start, window_end in _exclusive_windows(start, cutoff, provider_timeframe):
            for batch_index, batch in enumerate(batches):
                units.append(
                    NativeAcquisitionUnit(
                        unit_id=_unit_id(
                            provider_timeframe=provider_timeframe,
                            window_start=window_start,
                            window_end=window_end,
                            batch_index=batch_index,
                            symbols=batch,
                            universe_sha256=universe_sha256,
                            policy_sha256=policy_sha256,
                        ),
                        provider_timeframe=provider_timeframe,
                        canonical_timeframe=canonical_timeframe,
                        window_start=window_start.isoformat(),
                        window_end_exclusive=window_end.isoformat(),
                        year=window_start.year,
                        month=window_start.month if provider_timeframe == "1Min" else None,
                        batch_index=batch_index,
                        symbols=batch,
                        universe_sha256=universe_sha256,
                        policy_sha256=policy_sha256,
                    )
                )
    return units


def _extract_action_records(payload: object, page_index: int) -> list[dict[str, object]]:
    if not isinstance(payload, dict):
        return []
    root = payload.get("corporate_actions")
    if isinstance(root, dict):
        containers = root.items()
    elif isinstance(root, list):
        containers = (("unspecified", root),)
    else:
        containers = (
            (str(key), value)
            for key, value in payload.items()
            if key != "next_page_token" and isinstance(value, list)
        )
    records: list[dict[str, object]] = []
    for action_type, values in containers:
        if not isinstance(values, list):
            continue
        for record_index, value in enumerate(values):
            if isinstance(value, dict):
                records.append(
                    {
                        "action_type": str(action_type),
                        "source_page_index": page_index,
                        "source_record_index": record_index,
                        "payload": value,
                    }
                )
    return records


def _action_symbols(value: object) -> set[str]:
    result: set[str] = set()

    def visit(item: object, key: str | None = None) -> None:
        normalized = (key or "").lower().replace("-", "_")
        symbol_field = normalized == "symbol" or normalized == "symbols" or normalized.endswith(
            "_symbol"
        ) or normalized.endswith("_symbols")
        if symbol_field and isinstance(item, str):
            symbol = _clean_symbol(item)
            if symbol is not None:
                result.add(symbol)
        elif symbol_field and isinstance(item, list):
            for child in item:
                if isinstance(child, str):
                    symbol = _clean_symbol(child)
                    if symbol is not None:
                        result.add(symbol)
        if isinstance(item, dict):
            for child_key, child in item.items():
                visit(child, str(child_key))
        elif isinstance(item, list) and not symbol_field:
            for child in item:
                visit(child, key)

    visit(value)
    return result


class AlpacaV2NativeAcquirer:
    """Build a fresh, generation-isolated Alpaca SIP native base.

    The class never reads legacy provider, canonical, derived, manifest, or
    checkpoint paths.  Its only persisted inputs on resume live below the V2
    generation root.  Provider ticker literals are retained exactly; identity
    continuity is deliberately deferred to the separately gated lifecycle layer.
    """

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        start_date: date = V2_DEFAULT_START,
        now_utc: datetime | None = None,
        client: AlpacaMarketDataClient | None = None,
    ) -> None:
        self.settings = settings
        self.data_root = (settings.project_root / "data").resolve()
        self.layout = V2Layout.beneath(self.data_root)
        self.calendar = MarketCalendar(exchange=settings.data.calendar.exchange)
        self.market_tz = ZoneInfo(settings.data.calendar.market_timezone)
        self.start_date = start_date
        self.now_utc = now_utc
        self.client = client
        self.bootstrap_path = self.layout.checkpoints / "bootstrap.json"
        self.source_manifest_path = self.layout.manifests / "source_snapshot.json"
        self.plan_path = self.layout.manifests / "native_acquisition_plan.jsonl.gz"
        self.plan_manifest_path = self.layout.manifests / "native_acquisition_plan.json"
        self.report_path = self.layout.manifests / "native_acquisition_report.json"
        self.rejection_registry_path = self.layout.checkpoints / "provider_rejected_symbols.json"

    def _client(self) -> AlpacaMarketDataClient:
        if self.client is None:
            self.client = AlpacaMarketDataClient(self.settings)
        return self.client

    def _request_policy(self) -> dict[str, object]:
        rpm = int(self.settings.alpaca.market_data.requests_per_minute)
        if rpm > 180:
            raise RuntimeError("V2 requires Alpaca request pacing at or below 180 requests/minute")
        return {
            "provider": "alpaca",
            "feed": V2_FEED,
            "adjustment": V2_ADJUSTMENT,
            "asof": V2_ASOF,
            "page_limit": V2_PAGE_LIMIT,
            "symbol_batch_size": V2_SYMBOL_BATCH_SIZE,
            "requests_per_minute": rpm,
            "daily_source": "native_1Day",
            "minute_source": "native_1Min",
            "pagination": "opaque_next_page_token_until_null",
            "window_boundaries": (
                "America/New_York local-midnight start inclusive; next local midnight minus "
                "one microsecond inclusive end"
            ),
            "universe": "fresh_active_plus_inactive_assets_plus_corporate_action_literals",
            "identity": "provider_literal_only_unresolved_until_lifecycle_gate",
            "v1_ancestry": "FORBIDDEN",
        }

    def _request_bounds(self, unit: NativeAcquisitionUnit) -> tuple[str, str]:
        start_local = datetime.combine(
            date.fromisoformat(unit.window_start),
            time.min,
            self.market_tz,
        )
        exclusive_end_local = datetime.combine(
            date.fromisoformat(unit.window_end_exclusive),
            time.min,
            self.market_tz,
        )
        inclusive_end = exclusive_end_local.astimezone(UTC) - timedelta(microseconds=1)

        def render(value: datetime) -> str:
            return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")

        return render(start_local), render(inclusive_end)

    def freeze_bootstrap(self) -> dict[str, Any]:
        self.layout.create()
        policy = self._request_policy()
        policy_sha = _sha256_bytes(_stable_json(policy))
        if self.bootstrap_path.is_file():
            document = json.loads(self.bootstrap_path.read_text(encoding="utf-8"))
            locked = (
                document.get("contract") == BOOTSTRAP_CONTRACT
                and document.get("start_date") == self.start_date.isoformat()
                and document.get("request_policy") == policy
                and document.get("request_policy_sha256") == policy_sha
                and document.get("v1_ancestry") == "FORBIDDEN"
            )
            if not locked:
                raise RuntimeError(
                    "existing V2 bootstrap conflicts with requested semantics; preserve it and start a new generation"
                )
            return document

        cutoff = last_completed_session(self.calendar, now_utc=self.now_utc)
        if self.start_date > cutoff:
            raise RuntimeError("V2 start date is after the last completed exchange session")
        created = datetime.now(UTC).isoformat()
        run_id = _sha256_bytes(
            _stable_json(
                {
                    "contract": BOOTSTRAP_CONTRACT,
                    "created_at_utc": created,
                    "start_date": self.start_date.isoformat(),
                    "cutoff_session": cutoff.isoformat(),
                    "request_policy_sha256": policy_sha,
                }
            )
        )
        document = {
            "contract": BOOTSTRAP_CONTRACT,
            "created_at_utc": created,
            "run_id": run_id,
            "start_date": self.start_date.isoformat(),
            "cutoff_session": cutoff.isoformat(),
            "request_policy": policy,
            "request_policy_sha256": policy_sha,
            "v1_ancestry": "FORBIDDEN",
            "production_authority": False,
        }
        atomic_write_text(
            self.bootstrap_path,
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            fsync=True,
        )
        return document

    def _persist_api_page(self, page: AlpacaApiPage, path: Path) -> dict[str, object]:
        sha, raw_bytes, compressed_bytes = _atomic_write_gzip(path, page.raw_body)
        return {
            "request_name": page.request_name,
            "request_url": page.url,
            "http_status": int(page.http_status),
            "sha256": sha,
            "uncompressed_bytes": raw_bytes,
            "compressed_bytes": compressed_bytes,
            "path": str(path),
            "page_token_used": page.page_token_used,
            "next_page_token": page.next_page_token,
            "captured_at_utc": datetime.now(UTC).isoformat(),
        }

    def _load_source_manifest(self) -> tuple[dict[str, Any], list[str]] | None:
        if not self.source_manifest_path.is_file():
            return None
        document = json.loads(self.source_manifest_path.read_text(encoding="utf-8"))
        if document.get("contract") != SOURCE_SNAPSHOT_CONTRACT:
            raise RuntimeError("incompatible V2 source snapshot manifest")
        for key in ("assets_parquet", "corporate_actions_native", "universe_parquet"):
            record = document.get(key) or {}
            path = Path(str(record.get("path") or ""))
            if not path.is_file() or _sha256_file(path) != record.get("sha256"):
                raise RuntimeError(f"V2 source snapshot hash mismatch: {key}")
        for record in document.get("asset_pages") or []:
            _read_gzip_verified(
                Path(str(record.get("path") or "")),
                str(record.get("sha256") or ""),
            )
        action_bundle = document.get("corporate_actions_raw_bundle") or {}
        action_bundle_path = Path(str(action_bundle.get("path") or ""))
        if not action_bundle_path.is_file() or _sha256_file(action_bundle_path) != action_bundle.get(
            "sha256"
        ):
            raise RuntimeError("V2 corporate-action raw bundle hash mismatch")
        symbols = [str(value) for value in document.get("symbols") or []]
        if symbols != sorted(set(symbols)):
            raise RuntimeError("V2 source snapshot contains a non-deterministic universe")
        if _sha256_bytes("\n".join(symbols).encode("utf-8")) != document.get(
            "universe_sha256"
        ):
            raise RuntimeError("V2 source snapshot universe fingerprint mismatch")
        return document, symbols

    def _ensure_asset_snapshot(self) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        raw_root = self.layout.source / "assets"
        raw_root.mkdir(parents=True, exist_ok=True)
        page_records: list[dict[str, object]] = []
        rows: list[dict[str, object]] = []
        for requested_status in ("active", "inactive"):
            path = raw_root / f"{requested_status}.json.gz"
            metadata_path = raw_root / f"{requested_status}.meta.json"
            if path.is_file() and metadata_path.is_file():
                record = json.loads(metadata_path.read_text(encoding="utf-8"))
                body = _read_gzip_verified(path, str(record.get("sha256") or ""))
            else:
                page = self._client().get_assets(status=requested_status)
                record = self._persist_api_page(page, path)
                atomic_write_text(
                    metadata_path,
                    json.dumps(record, indent=2, sort_keys=True) + "\n",
                    fsync=True,
                )
                body = page.raw_body
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, list):
                raise RuntimeError(f"Alpaca {requested_status} assets response is not a list")
            page_records.append(record)
            for index, item in enumerate(payload):
                if not isinstance(item, dict):
                    continue
                symbol = _clean_symbol(item.get("symbol"))
                if symbol is None:
                    continue
                rows.append(
                    {
                        "provider_asset_id": str(item.get("id") or ""),
                        "symbol": symbol,
                        "requested_status": requested_status,
                        "provider_status": str(item.get("status") or ""),
                        "asset_class": str(item.get("class") or ""),
                        "exchange": str(item.get("exchange") or ""),
                        "name": str(item.get("name") or ""),
                        "tradable": bool(item.get("tradable", False)),
                        "marginable": bool(item.get("marginable", False)),
                        "shortable": bool(item.get("shortable", False)),
                        "easy_to_borrow": bool(item.get("easy_to_borrow", False)),
                        "fractionable": bool(item.get("fractionable", False)),
                        "source_record_index": index,
                        "payload_json": _stable_json(item).decode("utf-8"),
                    }
                )
        return rows, page_records

    @staticmethod
    def _write_assets_parquet(path: Path, rows: list[dict[str, object]]) -> None:
        columns = [
            "provider_asset_id",
            "symbol",
            "requested_status",
            "provider_status",
            "asset_class",
            "exchange",
            "name",
            "tradable",
            "marginable",
            "shortable",
            "easy_to_borrow",
            "fractionable",
            "source_record_index",
            "payload_json",
        ]
        frame = pd.DataFrame(rows, columns=columns)
        temp = unique_temp_path(path)
        con = connect_utc(":memory:")
        try:
            con.register("assets_df", frame)
            con.execute(
                "COPY (SELECT * FROM assets_df ORDER BY symbol, requested_status, provider_asset_id) "
                "TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
                [str(temp)],
            )
        finally:
            con.close()
        replace_with_retry(temp, path)

    def _ensure_corporate_actions(
        self,
        *,
        start: str,
        cutoff: str,
    ) -> tuple[list[dict[str, object]], dict[str, object]]:
        root = self.layout.source / "corporate_actions"
        page_root = root / ".pages"
        checkpoint_path = self.layout.checkpoints / "corporate_actions.json"
        native_path = self.layout.corporate_actions / "native_actions.jsonl.gz"
        bundle_path = root / "complete_pages.concat.json.gz"
        complete_path = self.layout.manifests / "corporate_actions.json"
        for path in (root, page_root, native_path.parent, complete_path.parent):
            path.mkdir(parents=True, exist_ok=True)

        if complete_path.is_file():
            manifest = json.loads(complete_path.read_text(encoding="utf-8"))
            if (
                manifest.get("contract") != SOURCE_SNAPSHOT_CONTRACT
                or manifest.get("start") != start
                or manifest.get("cutoff") != cutoff
            ):
                raise RuntimeError("incompatible completed V2 corporate-action snapshot")
            for record in (manifest.get("raw_bundle") or {}, manifest.get("native_actions") or {}):
                path = Path(str(record.get("path") or ""))
                if not path.is_file() or _sha256_file(path) != record.get("sha256"):
                    raise RuntimeError("completed V2 corporate-action snapshot hash mismatch")
            actions: list[dict[str, object]] = []
            with gzip.open(native_path, "rt", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        value = json.loads(line)
                        if isinstance(value, dict):
                            actions.append(value)
            return actions, manifest

        if checkpoint_path.is_file():
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            if (
                checkpoint.get("contract") != SOURCE_SNAPSHOT_CONTRACT
                or checkpoint.get("start") != start
                or checkpoint.get("cutoff") != cutoff
            ):
                raise RuntimeError("incompatible V2 corporate-action checkpoint")
        else:
            checkpoint = {
                "contract": SOURCE_SNAPSHOT_CONTRACT,
                "status": "IN_PROGRESS",
                "start": start,
                "cutoff": cutoff,
                "pages": [],
                "next_page_token": None,
                "pagination_complete": False,
            }
            atomic_write_text(
                checkpoint_path,
                json.dumps(checkpoint, indent=2, sort_keys=True) + "\n",
                fsync=True,
            )

        pages = list(checkpoint.get("pages") or [])
        for record in pages:
            _read_gzip_verified(
                Path(str(record.get("path") or "")),
                str(record.get("sha256") or ""),
            )
        token = checkpoint.get("next_page_token")
        seen_tokens = {
            str(record["page_token_used"])
            for record in pages
            if record.get("page_token_used") is not None
        }
        while not bool(checkpoint.get("pagination_complete")):
            page = self._client().corporate_action_page(
                start=start,
                end=cutoff,
                page_token=str(token) if token is not None else None,
            )
            page_index = len(pages)
            record = self._persist_api_page(page, page_root / f"page_{page_index:06d}.json.gz")
            next_token = page.next_page_token
            if next_token is not None and (next_token in seen_tokens or next_token == token):
                raise RuntimeError("Alpaca corporate-action pagination repeated a page token")
            pages.append(record)
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

        actions: list[dict[str, object]] = []
        for page_index, record in enumerate(pages):
            body = _read_gzip_verified(
                Path(str(record["path"])),
                str(record["sha256"]),
            )
            actions.extend(_extract_action_records(json.loads(body.decode("utf-8")), page_index))

        native_lines = b"".join(_stable_json(item) + b"\n" for item in actions)
        _atomic_write_gzip(native_path, native_lines)

        bundle_temp = unique_temp_path(bundle_path)
        bundle_temp.parent.mkdir(parents=True, exist_ok=True)
        try:
            with bundle_temp.open("wb") as target:
                if pages:
                    for record in pages:
                        target.write(Path(str(record["path"])).read_bytes())
                else:
                    target.write(gzip.compress(b"", compresslevel=6, mtime=0))
                target.flush()
                os.fsync(target.fileno())
            replace_with_retry(bundle_temp, bundle_path)
        except Exception:
            bundle_temp.unlink(missing_ok=True)
            raise

        compact_pages = [
            {
                key: record.get(key)
                for key in (
                    "request_name",
                    "request_url",
                    "http_status",
                    "sha256",
                    "uncompressed_bytes",
                    "compressed_bytes",
                    "page_token_used",
                    "next_page_token",
                    "captured_at_utc",
                )
            }
            for record in pages
        ]
        manifest = {
            "contract": SOURCE_SNAPSHOT_CONTRACT,
            "status": "COMPLETE",
            "start": start,
            "cutoff": cutoff,
            "data_quality": "complete",
            "page_count": len(pages),
            "action_record_count": len(actions),
            "pages": compact_pages,
            "raw_bundle": {
                "contract": RAW_BUNDLE_CONTRACT,
                "path": str(bundle_path),
                "sha256": _sha256_file(bundle_path),
                "bytes": bundle_path.stat().st_size,
                "member_count": max(1, len(pages)),
            },
            "native_actions": {
                "path": str(native_path),
                "sha256": _sha256_file(native_path),
                "bytes": native_path.stat().st_size,
            },
            "completed_at_utc": datetime.now(UTC).isoformat(),
            "identity_authority": False,
        }
        atomic_write_text(
            complete_path,
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            fsync=True,
        )
        for record in pages:
            Path(str(record["path"])).unlink(missing_ok=True)
        shutil.rmtree(page_root, ignore_errors=True)
        return actions, manifest

    @staticmethod
    def _write_universe_parquet(path: Path, rows: list[dict[str, object]]) -> None:
        frame = pd.DataFrame(
            rows,
            columns=[
                "symbol",
                "from_active_assets",
                "from_inactive_assets",
                "from_corporate_actions",
                "provider_asset_ids",
                "source_count",
                "identity_status",
            ],
        )
        temp = unique_temp_path(path)
        con = connect_utc(":memory:")
        try:
            con.register("universe_df", frame)
            con.execute(
                "COPY (SELECT * FROM universe_df ORDER BY symbol) TO ? "
                "(FORMAT PARQUET, COMPRESSION ZSTD)",
                [str(temp)],
            )
        finally:
            con.close()
        replace_with_retry(temp, path)

    def ensure_source_snapshot(self, bootstrap: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        existing = self._load_source_manifest()
        if existing is not None:
            manifest, symbols = existing
            if manifest.get("run_id") != bootstrap.get("run_id"):
                raise RuntimeError("V2 source snapshot belongs to a different frozen bootstrap")
            return manifest, symbols

        asset_rows, asset_pages = self._ensure_asset_snapshot()
        actions, action_manifest = self._ensure_corporate_actions(
            start=str(bootstrap["start_date"]),
            cutoff=str(bootstrap["cutoff_session"]),
        )
        assets_path = self.layout.identity / "assets_snapshot.parquet"
        self._write_assets_parquet(assets_path, asset_rows)

        provenance: dict[str, dict[str, object]] = {}
        for row in asset_rows:
            symbol = str(row["symbol"])
            item = provenance.setdefault(
                symbol,
                {
                    "symbol": symbol,
                    "from_active_assets": False,
                    "from_inactive_assets": False,
                    "from_corporate_actions": False,
                    "provider_asset_ids": set(),
                },
            )
            if row["requested_status"] == "active":
                item["from_active_assets"] = True
            if row["requested_status"] == "inactive":
                item["from_inactive_assets"] = True
            asset_id = str(row.get("provider_asset_id") or "")
            if asset_id:
                cast_ids = item["provider_asset_ids"]
                assert isinstance(cast_ids, set)
                cast_ids.add(asset_id)
        for action in actions:
            for symbol in _action_symbols(action.get("payload")):
                item = provenance.setdefault(
                    symbol,
                    {
                        "symbol": symbol,
                        "from_active_assets": False,
                        "from_inactive_assets": False,
                        "from_corporate_actions": False,
                        "provider_asset_ids": set(),
                    },
                )
                item["from_corporate_actions"] = True

        symbols = sorted(provenance)
        if not symbols:
            raise RuntimeError("fresh Alpaca source snapshots produced an empty acquisition universe")
        universe_rows: list[dict[str, object]] = []
        for symbol in symbols:
            item = provenance[symbol]
            ids = item.pop("provider_asset_ids")
            assert isinstance(ids, set)
            source_count = sum(
                int(bool(item[key]))
                for key in (
                    "from_active_assets",
                    "from_inactive_assets",
                    "from_corporate_actions",
                )
            )
            universe_rows.append(
                {
                    **item,
                    "provider_asset_ids": ",".join(sorted(ids)),
                    "source_count": source_count,
                    "identity_status": "PROVIDER_LITERAL_UNRESOLVED",
                }
            )
        universe_path = self.layout.identity / "acquisition_universe.parquet"
        self._write_universe_parquet(universe_path, universe_rows)
        universe_sha = _sha256_bytes("\n".join(symbols).encode("utf-8"))
        native_actions = action_manifest["native_actions"]
        assert isinstance(native_actions, dict)
        manifest = {
            "contract": SOURCE_SNAPSHOT_CONTRACT,
            "status": "COMPLETE",
            "run_id": bootstrap["run_id"],
            "captured_at_utc": datetime.now(UTC).isoformat(),
            "asset_pages": asset_pages,
            "asset_record_count": len(asset_rows),
            "corporate_action_page_count": action_manifest["page_count"],
            "corporate_action_record_count": action_manifest["action_record_count"],
            "corporate_actions_raw_bundle": action_manifest["raw_bundle"],
            "assets_parquet": {
                "path": str(assets_path),
                "sha256": _sha256_file(assets_path),
                "bytes": assets_path.stat().st_size,
            },
            "corporate_actions_native": native_actions,
            "universe_parquet": {
                "path": str(universe_path),
                "sha256": _sha256_file(universe_path),
                "bytes": universe_path.stat().st_size,
            },
            "symbols": symbols,
            "symbol_count": len(symbols),
            "universe_sha256": universe_sha,
            "identity_status": "PROVIDER_LITERAL_UNRESOLVED",
            "v1_ancestry": "FORBIDDEN",
        }
        atomic_write_text(
            self.source_manifest_path,
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            fsync=True,
        )
        return manifest, symbols

    def ensure_plan(
        self,
        bootstrap: dict[str, Any],
        source_manifest: dict[str, Any],
        symbols: list[str],
    ) -> tuple[list[NativeAcquisitionUnit], dict[str, Any]]:
        units = build_native_plan(
            symbols=symbols,
            start=date.fromisoformat(str(bootstrap["start_date"])),
            cutoff=date.fromisoformat(str(bootstrap["cutoff_session"])),
            universe_sha256=str(source_manifest["universe_sha256"]),
            policy_sha256=str(bootstrap["request_policy_sha256"]),
        )
        lines = b"".join(_stable_json(asdict(unit)) + b"\n" for unit in units)
        plan_fingerprint = _sha256_bytes(lines)
        if self.plan_manifest_path.is_file():
            manifest = json.loads(self.plan_manifest_path.read_text(encoding="utf-8"))
            if (
                manifest.get("contract") != ACQUISITION_CONTRACT
                or manifest.get("plan_sha256") != plan_fingerprint
                or manifest.get("universe_sha256") != source_manifest.get("universe_sha256")
                or manifest.get("policy_sha256") != bootstrap.get("request_policy_sha256")
            ):
                raise RuntimeError("existing V2 native plan conflicts with the frozen source snapshot")
            if not self.plan_path.is_file() or _sha256_file(self.plan_path) != manifest.get(
                "plan_file_sha256"
            ):
                raise RuntimeError("V2 native acquisition plan file hash mismatch")
            return units, manifest

        _atomic_write_gzip(self.plan_path, lines)
        daily_units = sum(unit.provider_timeframe == "1Day" for unit in units)
        minute_units = len(units) - daily_units
        manifest = {
            "contract": ACQUISITION_CONTRACT,
            "status": "FROZEN",
            "run_id": bootstrap["run_id"],
            "start_date": bootstrap["start_date"],
            "cutoff_session": bootstrap["cutoff_session"],
            "universe_sha256": source_manifest["universe_sha256"],
            "policy_sha256": bootstrap["request_policy_sha256"],
            "plan_sha256": plan_fingerprint,
            "plan_path": str(self.plan_path),
            "plan_file_sha256": _sha256_file(self.plan_path),
            "symbol_count": len(symbols),
            "daily_units": daily_units,
            "minute_units": minute_units,
            "total_units": len(units),
            "execution_order": ["native_1Day", "native_1Min"],
            "v1_ancestry": "FORBIDDEN",
            "frozen_at_utc": datetime.now(UTC).isoformat(),
        }
        atomic_write_text(
            self.plan_manifest_path,
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            fsync=True,
        )
        return units, manifest

    def _unit_paths(self, unit: NativeAcquisitionUnit) -> dict[str, Path]:
        if unit.canonical_timeframe == "1d":
            partition = Path(f"year={unit.year:04d}") / f"batch={unit.batch_index:04d}"
            canonical_root = self.layout.canonical_daily
        else:
            assert unit.month is not None
            partition = (
                Path(f"year={unit.year:04d}")
                / f"month={unit.month:02d}"
                / f"batch={unit.batch_index:04d}"
            )
            canonical_root = self.layout.canonical_minute
        prefix = unit.unit_id[:20]
        return {
            "checkpoint": self.layout.checkpoints
            / "native_units"
            / unit.canonical_timeframe
            / partition
            / f"{prefix}.json",
            "work": self.layout.checkpoints
            / "native_unit_work"
            / unit.canonical_timeframe
            / prefix,
            "raw_bundle": self.layout.source
            / "bars"
            / unit.canonical_timeframe
            / partition
            / f"{prefix}.concat.json.gz",
            "canonical": canonical_root / partition / f"{prefix}.parquet",
            "quarantine": self.layout.validation
            / "bar_quarantine"
            / unit.canonical_timeframe
            / partition
            / f"{prefix}.jsonl.gz",
        }

    def _load_rejections(self) -> dict[str, dict[str, object]]:
        if not self.rejection_registry_path.is_file():
            return {}
        document = json.loads(self.rejection_registry_path.read_text(encoding="utf-8"))
        if document.get("contract") != ACQUISITION_CONTRACT:
            raise RuntimeError("incompatible V2 provider-rejection registry")
        records = document.get("symbols") or {}
        if not isinstance(records, dict):
            raise RuntimeError("invalid V2 provider-rejection registry")
        result: dict[str, dict[str, object]] = {}
        for symbol, record in records.items():
            exact = _clean_symbol(symbol)
            if exact is None or not isinstance(record, dict):
                raise RuntimeError("invalid V2 provider-rejection record")
            path = Path(str(record.get("path") or ""))
            _read_gzip_verified(path, str(record.get("sha256") or ""))
            result[exact] = dict(record)
        return result

    def _persist_rejection(
        self,
        registry: dict[str, dict[str, object]],
        exc: AlpacaInvalidSymbolError,
    ) -> None:
        symbol = exc.symbol
        if symbol in registry:
            return
        digest = _sha256_bytes(exc.page.raw_body)
        path = self.layout.source / "quarantine" / "provider_rejections" / f"{digest}.json.gz"
        record = self._persist_api_page(exc.page, path)
        record.update(
            {
                "symbol": symbol,
                "provider_message": exc.provider_message,
                "classification": "PROVIDER_REJECTED_LITERAL_NO_SUBSTITUTION",
            }
        )
        registry[symbol] = record
        document = {
            "contract": ACQUISITION_CONTRACT,
            "updated_at_utc": datetime.now(UTC).isoformat(),
            "symbols": {key: registry[key] for key in sorted(registry)},
        }
        atomic_write_text(
            self.rejection_registry_path,
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            fsync=True,
        )

    @staticmethod
    def _valid_number(value: object, *, positive: bool = False) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number):
            return None
        if positive and number <= 0:
            return None
        return number

    @classmethod
    def _flatten_bar_page(
        cls,
        page: AlpacaApiPage,
        *,
        requested_symbols: tuple[str, ...],
        page_index: int,
        raw_sha256: str,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]], int]:
        payload = page.payload
        if not isinstance(payload, dict):
            raise RuntimeError("Alpaca historical-bars response is not a JSON object")
        bars = payload.get("bars")
        if bars is None:
            bars = {}
        if not isinstance(bars, dict):
            raise RuntimeError("Alpaca historical-bars response has a non-object bars field")
        allowed = set(requested_symbols)
        rows: list[dict[str, object]] = []
        anomalies: list[dict[str, object]] = []
        returned_rows = 0
        for raw_symbol, values in bars.items():
            symbol = _clean_symbol(raw_symbol)
            if not isinstance(values, list):
                anomalies.append(
                    {
                        "page_index": page_index,
                        "symbol": str(raw_symbol),
                        "record_index": None,
                        "reason": "NON_LIST_SYMBOL_BARS",
                        "raw_page_sha256": raw_sha256,
                    }
                )
                continue
            for record_index, item in enumerate(values):
                returned_rows += 1
                reason: str | None = None
                if symbol is None or symbol not in allowed:
                    reason = "UNREQUESTED_OR_INVALID_RESPONSE_SYMBOL"
                elif not isinstance(item, dict):
                    reason = "NON_OBJECT_BAR"
                if reason is not None:
                    anomalies.append(
                        {
                            "page_index": page_index,
                            "symbol": str(raw_symbol),
                            "record_index": record_index,
                            "reason": reason,
                            "raw_page_sha256": raw_sha256,
                        }
                    )
                    continue
                assert symbol is not None and isinstance(item, dict)
                timestamp_text = item.get("t")
                parsed_timestamp: datetime | None = None
                if isinstance(timestamp_text, str):
                    try:
                        parsed_timestamp = datetime.fromisoformat(
                            timestamp_text.replace("Z", "+00:00")
                        )
                    except ValueError:
                        parsed_timestamp = None
                if parsed_timestamp is None or parsed_timestamp.tzinfo is None:
                    reason = "INVALID_TIMESTAMP"
                open_value = cls._valid_number(item.get("o"), positive=True)
                high_value = cls._valid_number(item.get("h"), positive=True)
                low_value = cls._valid_number(item.get("l"), positive=True)
                close_value = cls._valid_number(item.get("c"), positive=True)
                volume_value = cls._valid_number(item.get("v"))
                if reason is None and None in (open_value, high_value, low_value, close_value):
                    reason = "INVALID_OHLC_NUMBER"
                if (
                    reason is None
                    and None not in (open_value, high_value, low_value, close_value)
                    and (
                        high_value < low_value
                        or high_value < open_value
                        or high_value < close_value
                        or low_value > open_value
                        or low_value > close_value
                    )
                ):
                    reason = "INVALID_OHLC_GEOMETRY"
                if reason is None and (volume_value is None or volume_value < 0):
                    reason = "INVALID_VOLUME"
                raw_vwap = item.get("vw")
                vwap_value = None if raw_vwap is None else cls._valid_number(raw_vwap, positive=True)
                if reason is None and raw_vwap is not None and vwap_value is None:
                    reason = "INVALID_VWAP"
                raw_trades = item.get("n")
                trade_count: int | None = None
                if raw_trades is not None:
                    try:
                        numeric_trades = float(raw_trades)
                        if (
                            not math.isfinite(numeric_trades)
                            or numeric_trades < 0
                            or numeric_trades != math.floor(numeric_trades)
                        ):
                            raise ValueError
                        trade_count = int(numeric_trades)
                    except (TypeError, ValueError, OverflowError):
                        reason = reason or "INVALID_TRANSACTION_COUNT"
                if reason is not None:
                    anomalies.append(
                        {
                            "page_index": page_index,
                            "symbol": symbol,
                            "record_index": record_index,
                            "reason": reason,
                            "timestamp": timestamp_text,
                            "raw_page_sha256": raw_sha256,
                        }
                    )
                    continue
                rows.append(
                    {
                        "provider_symbol": symbol,
                        "provider_timestamp_utc": parsed_timestamp.astimezone(UTC),
                        "open": open_value,
                        "high": high_value,
                        "low": low_value,
                        "close": close_value,
                        "volume": volume_value,
                        "vwap": vwap_value,
                        "transaction_count": trade_count,
                        "source_page_sha256": raw_sha256,
                        "source_page_index": page_index,
                        "source_record_index": record_index,
                    }
                )
        return rows, anomalies, returned_rows

    @staticmethod
    def _write_native_page(path: Path, rows: list[dict[str, object]]) -> int:
        columns = [
            "provider_symbol",
            "provider_timestamp_utc",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "vwap",
            "transaction_count",
            "source_page_sha256",
            "source_page_index",
            "source_record_index",
        ]
        frame = pd.DataFrame(rows, columns=columns)
        temp = unique_temp_path(path)
        con = connect_utc(":memory:")
        try:
            if rows:
                con.register("page_df", frame)
                source = "page_df"
            else:
                con.execute(
                    "CREATE TABLE empty_page("
                    "provider_symbol VARCHAR, provider_timestamp_utc TIMESTAMPTZ, "
                    "open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE, "
                    "vwap DOUBLE, transaction_count BIGINT, source_page_sha256 VARCHAR, "
                    "source_page_index BIGINT, source_record_index BIGINT)"
                )
                source = "empty_page"
            con.execute(
                f"""
                COPY (
                    SELECT
                        provider_symbol::VARCHAR AS provider_symbol,
                        provider_timestamp_utc::TIMESTAMPTZ AS provider_timestamp_utc,
                        open::DOUBLE AS open,
                        high::DOUBLE AS high,
                        low::DOUBLE AS low,
                        close::DOUBLE AS close,
                        volume::DOUBLE AS volume,
                        vwap::DOUBLE AS vwap,
                        transaction_count::BIGINT AS transaction_count,
                        source_page_sha256::VARCHAR AS source_page_sha256,
                        source_page_index::BIGINT AS source_page_index,
                        source_record_index::BIGINT AS source_record_index
                    FROM {source}
                    ORDER BY provider_symbol, provider_timestamp_utc, source_record_index
                ) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)
                """,
                [str(temp)],
            )
        finally:
            con.close()
        replace_with_retry(temp, path)
        return len(rows)

    @staticmethod
    def _write_quarantine(path: Path, records: list[dict[str, object]]) -> dict[str, object] | None:
        if not records:
            return None
        payload = b"".join(_stable_json(item) + b"\n" for item in records)
        _atomic_write_gzip(path, payload)
        return {
            "path": str(path),
            "sha256": _sha256_file(path),
            "bytes": path.stat().st_size,
            "records": len(records),
        }

    def _session_frame(self, unit: NativeAcquisitionUnit) -> pd.DataFrame:
        start = date.fromisoformat(unit.window_start)
        end = date.fromisoformat(unit.window_end_exclusive) - timedelta(days=1)
        rows: list[dict[str, object]] = []
        for session_date in self.calendar.sessions_in_range(start, end):
            regular_open, regular_close = self.calendar.regular_open_close(session_date)
            rows.append(
                {
                    "session_date": session_date,
                    "premarket_start_utc": datetime.combine(
                        session_date,
                        self.calendar.premarket_start,
                        self.market_tz,
                    ).astimezone(UTC),
                    "regular_open_utc": regular_open,
                    "regular_close_utc": regular_close,
                    "after_hours_end_utc": datetime.combine(
                        session_date,
                        self.calendar.after_hours_end,
                        self.market_tz,
                    ).astimezone(UTC),
                }
            )
        return pd.DataFrame(
            rows,
            columns=[
                "session_date",
                "premarket_start_utc",
                "regular_open_utc",
                "regular_close_utc",
                "after_hours_end_utc",
            ],
        )

    def _canonicalize_unit(
        self,
        unit: NativeAcquisitionUnit,
        *,
        native_page_paths: list[Path],
        target: Path,
    ) -> dict[str, object]:
        paths = list(native_page_paths)
        synthetic_empty: Path | None = None
        if not paths:
            synthetic_empty = target.parent / f".{unit.unit_id[:20]}.empty-native.parquet"
            self._write_native_page(synthetic_empty, [])
            paths = [synthetic_empty]
        input_sql = "read_parquet([" + ",".join(sql_string(path) for path in paths) + "])"
        schedule = self._session_frame(unit)
        source_id = (
            f"alpaca:sip:{unit.provider_timeframe}:raw:asof=-:v2:unit={unit.unit_id}"
        )
        dataset = (
            "stock_daily_aggregates"
            if unit.canonical_timeframe == "1d"
            else "stock_minute_aggregates"
        )
        source_literal = sql_string(source_id)
        dataset_literal = sql_string(dataset)
        timeframe_literal = sql_string(unit.canonical_timeframe)
        market_tz_literal = sql_string(str(self.market_tz))
        con = connect_utc(":memory:")
        con.execute("PRAGMA threads=2")
        con.register("v2_sessions", schedule)
        try:
            if unit.canonical_timeframe == "1d":
                base = f"""
                    SELECT
                        p.provider_symbol AS symbol,
                        CAST(s.regular_open_utc AS TIMESTAMPTZ) AS timestamp_utc,
                        CAST(s.session_date AS DATE) AS session_date,
                        {timeframe_literal} AS timeframe,
                        'regular'::VARCHAR AS session_segment,
                        p.open::DOUBLE AS open,
                        p.high::DOUBLE AS high,
                        p.low::DOUBLE AS low,
                        p.close::DOUBLE AS close,
                        p.volume::DOUBLE AS volume,
                        p.vwap::DOUBLE AS vwap,
                        p.transaction_count::BIGINT AS transaction_count,
                        'alpaca'::VARCHAR AS provider,
                        {dataset_literal} AS dataset,
                        {source_literal} AS source_id,
                        FALSE::BOOLEAN AS is_adjusted,
                        p.provider_timestamp_utc::TIMESTAMPTZ AS provider_timestamp_utc
                    FROM {input_sql} p
                    JOIN v2_sessions s
                      ON CAST(p.provider_timestamp_utc AS DATE) = CAST(s.session_date AS DATE)
                """
                unmatched = int(
                    con.execute(
                        f"""
                        SELECT count(*)
                        FROM {input_sql} p
                        LEFT JOIN v2_sessions s
                          ON CAST(p.provider_timestamp_utc AS DATE) = CAST(s.session_date AS DATE)
                        WHERE s.session_date IS NULL
                        """
                    ).fetchone()[0]
                )
            else:
                local_date = (
                    f"CAST(timezone({market_tz_literal}, p.provider_timestamp_utc) AS DATE)"
                )
                base = f"""
                    SELECT
                        p.provider_symbol AS symbol,
                        p.provider_timestamp_utc::TIMESTAMPTZ AS timestamp_utc,
                        {local_date} AS session_date,
                        {timeframe_literal} AS timeframe,
                        CASE
                            WHEN s.session_date IS NULL THEN 'closed'
                            WHEN p.provider_timestamp_utc >= s.premarket_start_utc
                             AND p.provider_timestamp_utc < s.regular_open_utc THEN 'premarket'
                            WHEN p.provider_timestamp_utc >= s.regular_open_utc
                             AND p.provider_timestamp_utc < s.regular_close_utc THEN 'regular'
                            WHEN p.provider_timestamp_utc >= s.regular_close_utc
                             AND p.provider_timestamp_utc < s.after_hours_end_utc THEN 'after_hours'
                            ELSE 'closed'
                        END::VARCHAR AS session_segment,
                        p.open::DOUBLE AS open,
                        p.high::DOUBLE AS high,
                        p.low::DOUBLE AS low,
                        p.close::DOUBLE AS close,
                        p.volume::DOUBLE AS volume,
                        p.vwap::DOUBLE AS vwap,
                        p.transaction_count::BIGINT AS transaction_count,
                        'alpaca'::VARCHAR AS provider,
                        {dataset_literal} AS dataset,
                        {source_literal} AS source_id,
                        FALSE::BOOLEAN AS is_adjusted,
                        p.provider_timestamp_utc::TIMESTAMPTZ AS provider_timestamp_utc
                    FROM {input_sql} p
                    LEFT JOIN v2_sessions s
                      ON {local_date} = CAST(s.session_date AS DATE)
                """
                unmatched = int(
                    con.execute(f"SELECT count(*) FROM ({base}) WHERE session_segment = 'closed'")
                    .fetchone()[0]
                )

            duplicate_rows = int(
                con.execute(
                    f"""
                    SELECT coalesce(sum(n - 1), 0)
                    FROM (
                        SELECT symbol, timestamp_utc, timeframe, session_segment, count(*) AS n
                        FROM ({base})
                        GROUP BY ALL
                        HAVING count(*) > 1
                    )
                    """
                ).fetchone()[0]
            )
            input_rows = int(con.execute(f"SELECT count(*) FROM {input_sql}").fetchone()[0])
            if duplicate_rows:
                return {
                    "status": "BLOCKED_VALIDATION",
                    "input_rows": input_rows,
                    "canonical_rows": 0,
                    "duplicate_rows": duplicate_rows,
                    "outside_session_rows": unmatched,
                    "path": None,
                    "sha256": None,
                    "bytes": 0,
                }

            target.parent.mkdir(parents=True, exist_ok=True)
            temp = unique_temp_path(target)
            compression = str(self.settings.data.parquet.compression).upper()
            row_group_size = int(self.settings.data.parquet.row_group_size)
            con.execute(
                f"""
                COPY (
                    SELECT * FROM ({base})
                    ORDER BY symbol, timestamp_utc, session_segment
                ) TO {sql_string(temp)}
                (FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size})
                """
            )
            description = con.execute(
                f"DESCRIBE SELECT * FROM read_parquet({sql_string(temp)}, hive_partitioning=false)"
            ).fetchall()
            if not canonical_stock_daily_schema_matches(description):
                temp.unlink(missing_ok=True)
                raise RuntimeError(
                    "V2 native unit does not match the canonical market schema: "
                    f"{[(row[0], row[1]) for row in description]}"
                )
            canonical_rows = int(
                con.execute(
                    f"SELECT count(*) FROM read_parquet({sql_string(temp)}, hive_partitioning=false)"
                ).fetchone()[0]
            )
            replace_with_retry(temp, target)
        finally:
            con.unregister("v2_sessions")
            con.close()
            if synthetic_empty is not None:
                synthetic_empty.unlink(missing_ok=True)
        return {
            "status": "COMPLETE",
            "input_rows": input_rows,
            "canonical_rows": canonical_rows,
            "duplicate_rows": duplicate_rows,
            "outside_session_rows": unmatched,
            "path": str(target),
            "sha256": _sha256_file(target),
            "bytes": target.stat().st_size,
        }

    @staticmethod
    def _bundle_gzip_members(paths: list[Path], target: Path) -> dict[str, object]:
        temp = unique_temp_path(target)
        try:
            with temp.open("wb") as handle:
                if paths:
                    for path in paths:
                        handle.write(path.read_bytes())
                else:
                    handle.write(gzip.compress(b"", compresslevel=6, mtime=0))
                handle.flush()
                os.fsync(handle.fileno())
            replace_with_retry(temp, target)
        except Exception:
            temp.unlink(missing_ok=True)
            raise
        return {
            "contract": RAW_BUNDLE_CONTRACT,
            "path": str(target),
            "sha256": _sha256_file(target),
            "bytes": target.stat().st_size,
            "member_count": max(1, len(paths)),
        }

    def _validate_unit_checkpoint(
        self,
        unit: NativeAcquisitionUnit,
        checkpoint: dict[str, Any],
    ) -> bool:
        if (
            checkpoint.get("contract") != UNIT_CONTRACT
            or checkpoint.get("unit_id") != unit.unit_id
            or checkpoint.get("policy_sha256") != unit.policy_sha256
            or checkpoint.get("universe_sha256") != unit.universe_sha256
            or _stable_json(checkpoint.get("unit")) != _stable_json(asdict(unit))
        ):
            raise RuntimeError(f"stale or incompatible V2 unit checkpoint: {unit.label}")
        status = str(checkpoint.get("status") or "")
        if status in COMPLETE_UNIT_STATUSES:
            bundle = checkpoint.get("raw_bundle") or {}
            bundle_path = Path(str(bundle.get("path") or ""))
            if not bundle_path.is_file() or _sha256_file(bundle_path) != bundle.get("sha256"):
                raise RuntimeError(f"completed V2 unit raw bundle hash mismatch: {unit.label}")
            canonical = checkpoint.get("canonical") or {}
            if status != "BLOCKED_VALIDATION":
                canonical_path = Path(str(canonical.get("path") or ""))
                if not canonical_path.is_file() or _sha256_file(canonical_path) != canonical.get(
                    "sha256"
                ):
                    raise RuntimeError(f"completed V2 unit canonical hash mismatch: {unit.label}")
            quarantine = checkpoint.get("quarantine")
            if isinstance(quarantine, dict):
                quarantine_path = Path(str(quarantine.get("path") or ""))
                if not quarantine_path.is_file() or _sha256_file(
                    quarantine_path
                ) != quarantine.get("sha256"):
                    raise RuntimeError(f"completed V2 unit quarantine hash mismatch: {unit.label}")
            return True
        if status != "IN_PROGRESS":
            raise RuntimeError(f"unknown V2 unit checkpoint status {status!r}: {unit.label}")
        for page in checkpoint.get("pages") or []:
            _read_gzip_verified(
                Path(str(page.get("raw_path") or "")),
                str(page.get("raw_sha256") or ""),
            )
            native_path = Path(str(page.get("native_path") or ""))
            if not native_path.is_file() or _sha256_file(native_path) != page.get("native_sha256"):
                raise RuntimeError(f"in-progress V2 native page hash mismatch: {unit.label}")
            quarantine = page.get("quarantine")
            if isinstance(quarantine, dict):
                path = Path(str(quarantine.get("path") or ""))
                if not path.is_file() or _sha256_file(path) != quarantine.get("sha256"):
                    raise RuntimeError(f"in-progress V2 quarantine page hash mismatch: {unit.label}")
        return False

    def _require_disk(self, *, required_bytes: int = V2_TRANSIENT_WORK_BYTES) -> None:
        self.data_root.mkdir(parents=True, exist_ok=True)
        guard_path = self.layout.root if self.layout.root.exists() else self.data_root
        check = disk_guard(
            guard_path,
            required_bytes=required_bytes,
            reserve_bytes=MIN_FREE_RESERVE_BYTES,
        )
        if not check["accepted"]:
            raise V2DiskFloorError(
                "V2 paused before a write because the 30 GiB reserve plus transient-work floor is unavailable"
            )

    def _acquire_unit(
        self,
        unit: NativeAcquisitionUnit,
        *,
        registry: dict[str, dict[str, object]],
        stop_requested: Callable[[], bool] | None = None,
        progress: Callable[[dict[str, object]], None] | None = None,
    ) -> dict[str, Any]:
        paths = self._unit_paths(unit)
        checkpoint_path = paths["checkpoint"]
        work = paths["work"]
        work.mkdir(parents=True, exist_ok=True)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        if checkpoint_path.is_file():
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            if self._validate_unit_checkpoint(unit, checkpoint):
                return checkpoint
        else:
            request_symbols = [symbol for symbol in unit.symbols if symbol not in registry]
            checkpoint = {
                "contract": UNIT_CONTRACT,
                "status": "IN_PROGRESS",
                "unit_id": unit.unit_id,
                "unit": asdict(unit),
                "policy_sha256": unit.policy_sha256,
                "universe_sha256": unit.universe_sha256,
                "request_symbols": request_symbols,
                "provider_rejections": [
                    {"symbol": symbol, **registry[symbol]}
                    for symbol in unit.symbols
                    if symbol in registry
                ],
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

        pages: list[dict[str, Any]] = list(checkpoint.get("pages") or [])
        request_symbols = [str(value) for value in checkpoint.get("request_symbols") or []]
        token = checkpoint.get("next_page_token")
        seen_tokens = {
            str(record["page_token_used"])
            for record in pages
            if record.get("page_token_used") is not None
        }
        request_start, request_end = self._request_bounds(unit)
        while not bool(checkpoint.get("pagination_complete")):
            self._require_disk()
            try:
                page = self._client().historical_bar_page(
                    symbols=request_symbols,
                    start=request_start,
                    end=request_end,
                    page_token=str(token) if token is not None else None,
                    timeframe=unit.provider_timeframe,
                    feed=V2_FEED,
                    adjustment=V2_ADJUSTMENT,
                    asof=V2_ASOF,
                    page_limit=V2_PAGE_LIMIT,
                )
            except AlpacaInvalidSymbolError as exc:
                if pages:
                    raise RuntimeError(
                        "Alpaca rejected a literal after pagination began; preserving the partial unit for review"
                    ) from exc
                if exc.symbol not in request_symbols:
                    raise RuntimeError(
                        "Alpaca rejected a symbol outside the exact submitted V2 unit"
                    ) from exc
                self._persist_rejection(registry, exc)
                request_symbols = [symbol for symbol in request_symbols if symbol != exc.symbol]
                checkpoint["request_symbols"] = request_symbols
                checkpoint["provider_rejections"] = [
                    {"symbol": symbol, **registry[symbol]}
                    for symbol in unit.symbols
                    if symbol in registry
                ]
                checkpoint["pagination_complete"] = not request_symbols
                checkpoint["updated_at_utc"] = datetime.now(UTC).isoformat()
                atomic_write_text(
                    checkpoint_path,
                    json.dumps(checkpoint, indent=2, sort_keys=True) + "\n",
                    fsync=True,
                )
                if progress is not None:
                    progress(
                        {
                            "event": "provider_rejection",
                            "unit": unit.label,
                            "symbol": exc.symbol,
                        }
                    )
                continue

            page_index = len(pages)
            raw_path = work / f"page_{page_index:06d}.json.gz"
            raw_record = self._persist_api_page(page, raw_path)
            rows, anomalies, returned_rows = self._flatten_bar_page(
                page,
                requested_symbols=tuple(request_symbols),
                page_index=page_index,
                raw_sha256=str(raw_record["sha256"]),
            )
            native_path = work / f"page_{page_index:06d}.parquet"
            self._write_native_page(native_path, rows)
            quarantine = self._write_quarantine(
                work / f"page_{page_index:06d}.quarantine.jsonl.gz",
                anomalies,
            )
            next_token = page.next_page_token
            if next_token is not None and (next_token in seen_tokens or next_token == token):
                raise RuntimeError("Alpaca historical-bar pagination repeated a page token")
            page_record = {
                "page_index": page_index,
                "page_token_used": token,
                "next_page_token": next_token,
                "request_url": page.url,
                "http_status": int(page.http_status),
                "raw_path": str(raw_path),
                "raw_sha256": raw_record["sha256"],
                "raw_uncompressed_bytes": raw_record["uncompressed_bytes"],
                "raw_compressed_bytes": raw_record["compressed_bytes"],
                "native_path": str(native_path),
                "native_sha256": _sha256_file(native_path),
                "native_bytes": native_path.stat().st_size,
                "returned_rows": returned_rows,
                "accepted_rows": len(rows),
                "quarantined_rows": len(anomalies),
                "quarantine": quarantine,
                "captured_at_utc": raw_record["captured_at_utc"],
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
                        "event": "page",
                        "unit": unit.label,
                        "page": page_index + 1,
                        "accepted_rows": len(rows),
                        "quarantined_rows": len(anomalies),
                        "next_page": token is not None,
                    }
                )
            if stop_requested is not None and stop_requested():
                raise V2TimeLimitReached("V2 time limit reached after an atomic page checkpoint")

        native_paths = [Path(str(record["native_path"])) for record in pages]
        transient = max(
            V2_TRANSIENT_WORK_BYTES,
            2 * sum(int(record.get("native_bytes", 0)) for record in pages),
        )
        self._require_disk(required_bytes=transient)
        canonical = self._canonicalize_unit(
            unit,
            native_page_paths=native_paths,
            target=paths["canonical"],
        )
        raw_bundle = self._bundle_gzip_members(
            [Path(str(record["raw_path"])) for record in pages],
            paths["raw_bundle"],
        )
        quarantine_paths = [
            Path(str(record["quarantine"]["path"]))
            for record in pages
            if isinstance(record.get("quarantine"), dict)
        ]
        quarantine: dict[str, object] | None = None
        if quarantine_paths:
            quarantine = self._bundle_gzip_members(quarantine_paths, paths["quarantine"])
            quarantine["records"] = sum(int(record.get("quarantined_rows", 0)) for record in pages)

        provider_rejections = list(checkpoint.get("provider_rejections") or [])
        quarantined_rows = sum(int(record.get("quarantined_rows", 0)) for record in pages)
        if canonical["status"] == "BLOCKED_VALIDATION":
            status = "BLOCKED_VALIDATION"
        elif quarantined_rows or provider_rejections or int(canonical["outside_session_rows"]):
            status = "COMPLETE_WITH_QUARANTINE"
        else:
            status = "COMPLETE"
        compact_pages = [
            {
                key: record.get(key)
                for key in (
                    "page_index",
                    "page_token_used",
                    "next_page_token",
                    "request_url",
                    "http_status",
                    "raw_sha256",
                    "raw_uncompressed_bytes",
                    "raw_compressed_bytes",
                    "native_sha256",
                    "native_bytes",
                    "returned_rows",
                    "accepted_rows",
                    "quarantined_rows",
                    "captured_at_utc",
                )
            }
            for record in pages
        ]
        completed = {
            "contract": UNIT_CONTRACT,
            "status": status,
            "unit_id": unit.unit_id,
            "unit": asdict(unit),
            "policy_sha256": unit.policy_sha256,
            "universe_sha256": unit.universe_sha256,
            "request_symbols": request_symbols,
            "provider_rejections": provider_rejections,
            "page_count": len(pages),
            "pages": compact_pages,
            "raw_bundle": raw_bundle,
            "canonical": canonical,
            "quarantine": quarantine,
            "returned_rows": sum(int(record.get("returned_rows", 0)) for record in pages),
            "accepted_native_rows": sum(
                int(record.get("accepted_rows", 0)) for record in pages
            ),
            "quarantined_rows": quarantined_rows,
            "identity_status": "PROVIDER_LITERAL_UNRESOLVED",
            "v1_ancestry": "FORBIDDEN",
            "completed_at_utc": datetime.now(UTC).isoformat(),
        }
        atomic_write_text(
            checkpoint_path,
            json.dumps(completed, indent=2, sort_keys=True) + "\n",
            fsync=True,
        )
        if status != "BLOCKED_VALIDATION":
            shutil.rmtree(work, ignore_errors=True)
        if progress is not None:
            progress(
                {
                    "event": "unit",
                    "unit": unit.label,
                    "status": status,
                    "pages": len(pages),
                    "canonical_rows": canonical["canonical_rows"],
                    "quarantined_rows": quarantined_rows,
                }
            )
        return completed

    def _completed_unit(self, unit: NativeAcquisitionUnit) -> dict[str, Any] | None:
        path = self._unit_paths(unit)["checkpoint"]
        if not path.is_file():
            return None
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
        return checkpoint if self._validate_unit_checkpoint(unit, checkpoint) else None

    def _write_report(
        self,
        *,
        bootstrap: dict[str, Any],
        source_manifest: dict[str, Any],
        plan_manifest: dict[str, Any],
        units: list[NativeAcquisitionUnit],
        executed_this_run: int,
        skipped_this_run: int,
        stop_reason: str | None,
    ) -> dict[str, Any]:
        status_counts: dict[str, int] = {}
        total_pages = 0
        canonical_rows = 0
        quarantined_rows = 0
        completed = 0
        daily_completed = 0
        minute_completed = 0
        for unit in units:
            path = self._unit_paths(unit)["checkpoint"]
            if not path.is_file():
                continue
            document = json.loads(path.read_text(encoding="utf-8"))
            status = str(document.get("status") or "UNKNOWN")
            status_counts[status] = status_counts.get(status, 0) + 1
            if status in COMPLETE_UNIT_STATUSES:
                completed += 1
                if unit.canonical_timeframe == "1d":
                    daily_completed += 1
                else:
                    minute_completed += 1
                total_pages += int(document.get("page_count", 0))
                canonical_rows += int((document.get("canonical") or {}).get("canonical_rows", 0))
                quarantined_rows += int(document.get("quarantined_rows", 0))
        complete = completed == len(units)
        trusted_candidate = (
            complete
            and status_counts.get("BLOCKED_VALIDATION", 0) == 0
            and status_counts.get("COMPLETE_WITH_QUARANTINE", 0) == 0
        )
        report = {
            "contract": ACQUISITION_CONTRACT,
            "updated_at_utc": datetime.now(UTC).isoformat(),
            "status": "COMPLETE" if complete else (stop_reason or "IN_PROGRESS"),
            "run_id": bootstrap["run_id"],
            "start_date": bootstrap["start_date"],
            "cutoff_session": bootstrap["cutoff_session"],
            "source_snapshot_sha256": _sha256_file(self.source_manifest_path),
            "plan_sha256": plan_manifest["plan_sha256"],
            "universe_sha256": source_manifest["universe_sha256"],
            "symbol_count": source_manifest["symbol_count"],
            "total_units": len(units),
            "completed_units": completed,
            "missing_units": len(units) - completed,
            "daily_units": plan_manifest["daily_units"],
            "daily_completed": daily_completed,
            "minute_units": plan_manifest["minute_units"],
            "minute_completed": minute_completed,
            "status_counts": status_counts,
            "raw_pages": total_pages,
            "canonical_rows": canonical_rows,
            "quarantined_rows": quarantined_rows,
            "executed_units_this_run": executed_this_run,
            "skipped_units_this_run": skipped_this_run,
            "native_base_complete": complete,
            "native_base_clean_candidate": trusted_candidate,
            "identity_lifecycle_validated": False,
            "production_promoted": False,
            "historical_strategy_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "protected_reads": 0,
            "v1_ancestry": "FORBIDDEN",
        }
        atomic_write_text(
            self.report_path,
            json.dumps(report, indent=2, sort_keys=True) + "\n",
        )
        return report

    def run(
        self,
        *,
        max_units: int | None = None,
        max_hours: float | None = None,
        timeframes: tuple[str, ...] = ("1d", "1m"),
        progress: Callable[[dict[str, object]], None] | None = None,
    ) -> dict[str, Any]:
        unknown = set(timeframes) - {"1d", "1m"}
        if unknown:
            raise ValueError(f"unsupported V2 canonical timeframes: {sorted(unknown)}")
        if max_units is not None and max_units < 1:
            raise ValueError("max_units must be positive")
        if max_hours is not None and max_hours <= 0:
            raise ValueError("max_hours must be positive")
        self._require_disk()
        bootstrap = self.freeze_bootstrap()
        source_manifest, symbols = self.ensure_source_snapshot(bootstrap)
        units, plan_manifest = self.ensure_plan(bootstrap, source_manifest, symbols)
        selected = [unit for unit in units if unit.canonical_timeframe in timeframes]
        registry = self._load_rejections()
        started = datetime.now(UTC)
        deadline = started + timedelta(hours=max_hours) if max_hours is not None else None
        executed = 0
        skipped = 0
        stop_reason: str | None = None

        def should_stop() -> bool:
            return deadline is not None and datetime.now(UTC) >= deadline

        try:
            for unit_index, unit in enumerate(selected, start=1):
                existing = self._completed_unit(unit)
                if existing is not None:
                    skipped += 1
                    if progress is not None:
                        progress(
                            {
                                "event": "skip",
                                "unit": unit.label,
                                "unit_index": unit_index,
                                "selected_units": len(selected),
                                "status": existing["status"],
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
                            "event": "unit_start",
                            "unit": unit.label,
                            "unit_index": unit_index,
                            "selected_units": len(selected),
                        }
                    )
                self._acquire_unit(
                    unit,
                    registry=registry,
                    stop_requested=should_stop,
                    progress=progress,
                )
                executed += 1
        except V2TimeLimitReached:
            stop_reason = "TIME_LIMIT_REACHED"
        except V2DiskFloorError:
            stop_reason = "PAUSED_DISK_FLOOR"
            self._write_report(
                bootstrap=bootstrap,
                source_manifest=source_manifest,
                plan_manifest=plan_manifest,
                units=units,
                executed_this_run=executed,
                skipped_this_run=skipped,
                stop_reason=stop_reason,
            )
            raise

        return self._write_report(
            bootstrap=bootstrap,
            source_manifest=source_manifest,
            plan_manifest=plan_manifest,
            units=units,
            executed_this_run=executed,
            skipped_this_run=skipped,
            stop_reason=stop_reason,
        )
