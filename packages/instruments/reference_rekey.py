from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import DataProvider, InstrumentIdentityQuality
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.schemas.instrument import InstrumentReferenceObservation

from .identity import IDENTITY_CONTRACT_VERSION, InstrumentIdentityResolver
from .registry import InstrumentRegistryStore


@dataclass(frozen=True, slots=True)
class ReferenceIdentityRekeyResult:
    as_of_date: date
    row_count: int
    old_instrument_count: int
    new_instrument_count: int
    changed_row_count: int
    old_duplicate_id_groups: int
    new_duplicate_id_groups: int
    old_multi_ticker_id_groups: int
    new_multi_ticker_id_groups: int
    strong_id_changes: int
    path: Path


def _safe(path: Path) -> str:
    return path.as_posix().replace("'", "''")


def _load_reference_rows(path: Path) -> list[dict[str, object]]:
    con = connect_utc(":memory:")
    try:
        safe = _safe(path)
        cursor = con.execute(
            f"""
            SELECT
                instrument_id,
                identity_key,
                identity_quality,
                provider,
                as_of_date,
                ticker,
                name,
                market,
                locale,
                currency_name,
                primary_exchange,
                security_type,
                active,
                composite_figi,
                share_class_figi,
                cik,
                delisted_utc,
                provider_last_updated_utc
            FROM read_parquet('{safe}')
            ORDER BY ticker, instrument_id
            """
        )
        columns = [item[0] for item in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    finally:
        con.close()


def _collision_counts(rows: list[dict[str, object]], id_field: str) -> tuple[int, int]:
    by_id: dict[str, list[str]] = {}
    for row in rows:
        key = str(row[id_field])
        by_id.setdefault(key, []).append(str(row["ticker"]))
    duplicate_groups = sum(len(tickers) > 1 for tickers in by_id.values())
    multi_ticker_groups = sum(len(set(tickers)) > 1 for tickers in by_id.values())
    return duplicate_groups, multi_ticker_groups


def rekey_reference_snapshot(settings: AtlasSettings, as_of_date: date) -> ReferenceIdentityRekeyResult:
    """Recompute ATLAS identity fields from an existing provider-fact snapshot.

    No provider call is made. The existing canonical reference rows are read,
    identity is resolved with the current identity contract, and the same provider
    metadata is rewritten atomically with corrected ``instrument_id`` / ``identity_key``
    values. Strong FIGI identities are required to remain unchanged.
    """

    paths = MarketDataPaths(settings)
    target = paths.reference_snapshot_file(as_of_date)
    if not target.exists():
        raise FileNotFoundError(f"Reference snapshot is not available: {target}")

    old_rows = _load_reference_rows(target)
    if not old_rows:
        raise ValueError(f"Reference snapshot contains no rows: {target}")

    resolver = InstrumentIdentityResolver()
    observations: list[InstrumentReferenceObservation] = []
    changed = 0
    strong_id_changes = 0
    audit_rows: list[dict[str, object]] = []

    for row in old_rows:
        row_date = row["as_of_date"]
        if isinstance(row_date, datetime):
            row_date = row_date.date()
        if row_date != as_of_date:
            raise ValueError(
                f"Reference row date {row_date} does not match requested snapshot {as_of_date}"
            )

        raw = {
            "ticker": row["ticker"],
            "composite_figi": row["composite_figi"],
            "share_class_figi": row["share_class_figi"],
            "cik": row["cik"],
            "primary_exchange": row["primary_exchange"],
            "type": row["security_type"],
        }
        new_id, new_key, new_quality = resolver.resolve(raw, as_of_date)
        old_id = str(row["instrument_id"])
        old_quality = InstrumentIdentityQuality(str(row["identity_quality"]))
        if new_id != old_id:
            changed += 1
            if old_quality == InstrumentIdentityQuality.STRONG:
                strong_id_changes += 1

        observations.append(
            InstrumentReferenceObservation(
                instrument_id=new_id,
                identity_key=new_key,
                identity_quality=new_quality,
                provider=DataProvider.MASSIVE,
                as_of_date=as_of_date,
                ticker=str(row["ticker"]),
                name=str(row["name"]) if row["name"] is not None else None,
                market=str(row["market"]) if row["market"] is not None else None,
                locale=str(row["locale"]) if row["locale"] is not None else None,
                currency_name=str(row["currency_name"]) if row["currency_name"] is not None else None,
                primary_exchange=str(row["primary_exchange"]) if row["primary_exchange"] is not None else None,
                security_type=str(row["security_type"]) if row["security_type"] is not None else None,
                active=bool(row["active"]),
                composite_figi=str(row["composite_figi"]) if row["composite_figi"] is not None else None,
                share_class_figi=str(row["share_class_figi"]) if row["share_class_figi"] is not None else None,
                cik=str(row["cik"]) if row["cik"] is not None else None,
                delisted_utc=row["delisted_utc"],
                provider_last_updated_utc=row["provider_last_updated_utc"],
            )
        )
        audit_rows.append({"instrument_id": new_id, "ticker": str(row["ticker"])})

    if strong_id_changes:
        raise ValueError(
            f"Identity rekey would change {strong_id_changes} strong FIGI identities; refusing rewrite"
        )

    old_duplicate_groups, old_multi_ticker_groups = _collision_counts(old_rows, "instrument_id")
    new_duplicate_groups, new_multi_ticker_groups = _collision_counts(audit_rows, "instrument_id")

    # This operation is intentionally offline-only. InstrumentRegistryStore's
    # provider is never used for a re-key, so pass a sentinel to avoid constructing
    # a REST client and resolving provider credentials.
    store = InstrumentRegistryStore(settings, provider=object())  # type: ignore[arg-type]
    store._write_snapshot(observations, target)  # noqa: SLF001 - controlled identity migration

    manifest_path = paths.reference_snapshot_manifest(as_of_date)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        manifest = {}
    manifest.update(
        {
            "as_of_date": as_of_date.isoformat(),
            "row_count": len(observations),
            "instrument_count": len({item.instrument_id for item in observations}),
            "identity_contract_version": IDENTITY_CONTRACT_VERSION,
            "identity_rekeyed_at_utc": datetime.now(UTC).isoformat(),
        }
    )
    atomic_write_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    store.rebuild_registry()

    return ReferenceIdentityRekeyResult(
        as_of_date=as_of_date,
        row_count=len(observations),
        old_instrument_count=len({str(row["instrument_id"]) for row in old_rows}),
        new_instrument_count=len({item.instrument_id for item in observations}),
        changed_row_count=changed,
        old_duplicate_id_groups=old_duplicate_groups,
        new_duplicate_id_groups=new_duplicate_groups,
        old_multi_ticker_id_groups=old_multi_ticker_groups,
        new_multi_ticker_id_groups=new_multi_ticker_groups,
        strong_id_changes=strong_id_changes,
        path=target,
    )
