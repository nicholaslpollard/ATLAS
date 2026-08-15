from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Iterable

from packages.core.enums import DataProvider, InstrumentIdentityQuality
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.providers.massive.reference_data import MassiveReferenceProvider
from packages.schemas.instrument import InstrumentReferenceObservation, ReferenceSnapshotResult

from .identity import InstrumentIdentityResolver

try:
    import duckdb  # noqa: F401
except ImportError:  # pragma: no cover
    duckdb = None


REFERENCE_CONTRACT_VERSION = "reference-v3-provider-native-ticker-case"


def _parse_optional_datetime(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


class InstrumentRegistryStore:
    """Persist point-in-time Massive reference snapshots and derived identity views."""

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        provider: MassiveReferenceProvider | None = None,
    ) -> None:
        if duckdb is None:
            raise RuntimeError("duckdb is required for instrument reference storage")
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.provider = provider or MassiveReferenceProvider(settings)
        self.identity = InstrumentIdentityResolver()

    def _observation(self, row: dict[str, object], as_of_date: date) -> InstrumentReferenceObservation:
        instrument_id, identity_key, quality = self.identity.resolve(row, as_of_date)
        return InstrumentReferenceObservation(
            instrument_id=instrument_id,
            identity_key=identity_key,
            identity_quality=quality,
            provider=DataProvider.MASSIVE,
            as_of_date=as_of_date,
            ticker=str(row.get("ticker") or ""),
            name=str(row["name"]) if row.get("name") is not None else None,
            market=str(row["market"]) if row.get("market") is not None else None,
            locale=str(row["locale"]) if row.get("locale") is not None else None,
            currency_name=str(row["currency_name"]) if row.get("currency_name") is not None else None,
            primary_exchange=str(row["primary_exchange"]) if row.get("primary_exchange") is not None else None,
            security_type=str(row["type"]) if row.get("type") is not None else None,
            active=bool(row.get("active", True)),
            composite_figi=str(row["composite_figi"]) if row.get("composite_figi") is not None else None,
            share_class_figi=str(row["share_class_figi"]) if row.get("share_class_figi") is not None else None,
            cik=str(row["cik"]) if row.get("cik") is not None else None,
            delisted_utc=_parse_optional_datetime(row.get("delisted_utc")),
            provider_last_updated_utc=_parse_optional_datetime(row.get("last_updated_utc")),
        )

    @staticmethod
    def _safe(path: Path | str) -> str:
        return str(path).replace("\\", "/").replace("'", "''")

    def _write_snapshot(self, observations: Iterable[InstrumentReferenceObservation], target: Path) -> int:
        target.parent.mkdir(parents=True, exist_ok=True)
        staging_json = target.with_name(f".{target.name}.{os.getpid()}.jsonl")
        count = 0
        with staging_json.open("w", encoding="utf-8") as handle:
            for obs in observations:
                handle.write(obs.model_dump_json() + "\n")
                count += 1
        if count == 0:
            staging_json.unlink(missing_ok=True)
            raise ValueError("Massive reference snapshot returned zero usable stock rows")

        temp = atomic_target(target)
        temp.unlink(missing_ok=True)
        con = connect_utc(":memory:")
        try:
            source = self._safe(staging_json)
            dest = self._safe(temp)
            compression = self.settings.data.parquet.compression.upper()
            con.execute(
                f"""
                COPY (
                    SELECT
                        instrument_id,
                        identity_key,
                        identity_quality,
                        provider,
                        CAST(as_of_date AS DATE) AS as_of_date,
                        trim(ticker) AS ticker,
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
                        CAST(delisted_utc AS TIMESTAMPTZ) AS delisted_utc,
                        CAST(provider_last_updated_utc AS TIMESTAMPTZ) AS provider_last_updated_utc
                    FROM read_json_auto('{source}', format='newline_delimited')
                    ORDER BY ticker, instrument_id
                ) TO '{dest}' (FORMAT PARQUET, COMPRESSION {compression})
                """
            )
        finally:
            con.close()
            staging_json.unlink(missing_ok=True)
        promote(temp, target)
        return count

    def _snapshot_counts(self, path: Path) -> tuple[int, int, dict[str, int]]:
        con = connect_utc(":memory:")
        try:
            safe = self._safe(path)
            row = con.execute(
                f"""
                SELECT
                    count(*),
                    count(DISTINCT instrument_id),
                    count(*) FILTER (WHERE identity_quality='strong'),
                    count(*) FILTER (WHERE identity_quality='medium'),
                    count(*) FILTER (WHERE identity_quality='fallback')
                FROM read_parquet('{safe}')
                """
            ).fetchone()
            return int(row[0]), int(row[1]), {"strong": int(row[2]), "medium": int(row[3]), "fallback": int(row[4])}
        finally:
            con.close()

    def sync_snapshot(
        self,
        as_of_date: date,
        *,
        include_inactive: bool = True,
        force: bool = False,
    ) -> ReferenceSnapshotResult:
        target = self.paths.reference_snapshot_file(as_of_date)
        manifest = self.paths.reference_snapshot_manifest(as_of_date)
        if target.exists() and manifest.exists() and not force:
            try:
                meta = json.loads(manifest.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                meta = {}
            if (
                bool(meta.get("include_inactive")) == include_inactive
                and meta.get("contract_version") == REFERENCE_CONTRACT_VERSION
            ):
                rows, instruments, quality = self._snapshot_counts(target)
                self.rebuild_registry()
                return ReferenceSnapshotResult(
                    as_of_date=as_of_date,
                    row_count=rows,
                    instrument_count=instruments,
                    path=str(target),
                    skipped=True,
                    strong_identity_count=quality["strong"],
                    medium_identity_count=quality["medium"],
                    fallback_identity_count=quality["fallback"],
                )

        raw_rows = self.provider.stock_snapshot(as_of_date, include_inactive=include_inactive)
        observations = [self._observation(row, as_of_date) for row in raw_rows]
        row_count = self._write_snapshot(observations, target)
        instrument_count = len({obs.instrument_id for obs in observations})
        quality = {
            "strong": sum(obs.identity_quality == InstrumentIdentityQuality.STRONG for obs in observations),
            "medium": sum(obs.identity_quality == InstrumentIdentityQuality.MEDIUM for obs in observations),
            "fallback": sum(obs.identity_quality == InstrumentIdentityQuality.FALLBACK for obs in observations),
        }
        manifest.parent.mkdir(parents=True, exist_ok=True)
        temp_manifest = manifest.with_suffix(manifest.suffix + f".{os.getpid()}.tmp")
        temp_manifest.write_text(
            json.dumps(
                {
                    "as_of_date": as_of_date.isoformat(),
                    "include_inactive": include_inactive,
                    "contract_version": REFERENCE_CONTRACT_VERSION,
                    "row_count": row_count,
                    "instrument_count": instrument_count,
                    "fetched_at_utc": datetime.now(UTC).isoformat(),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        os.replace(temp_manifest, manifest)
        self.rebuild_registry()
        return ReferenceSnapshotResult(
            as_of_date=as_of_date,
            row_count=row_count,
            instrument_count=instrument_count,
            path=str(target),
            skipped=False,
            strong_identity_count=quality["strong"],
            medium_identity_count=quality["medium"],
            fallback_identity_count=quality["fallback"],
        )

    def rebuild_registry(self) -> None:
        glob = self.paths.reference_snapshot_glob()
        snapshot_root = self.settings.resolved_path(self.settings.data.paths.canonical) / "reference" / "massive" / "tickers"
        if not any(snapshot_root.glob("date=*/*.parquet")):
            return

        registry = self.paths.instrument_registry_file()
        aliases = self.paths.ticker_observations_file()
        reg_temp = atomic_target(registry)
        alias_temp = atomic_target(aliases)
        reg_temp.unlink(missing_ok=True)
        alias_temp.unlink(missing_ok=True)
        con = connect_utc(":memory:")
        try:
            source = self._safe(glob)
            reg_dest = self._safe(reg_temp)
            alias_dest = self._safe(alias_temp)
            compression = self.settings.data.parquet.compression.upper()
            con.execute(
                f"""
                COPY (
                    SELECT
                        instrument_id,
                        any_value(identity_key) AS identity_key,
                        any_value(identity_quality) AS identity_quality,
                        arg_max(ticker, as_of_date) AS latest_ticker,
                        arg_max(name, as_of_date) AS latest_name,
                        max(composite_figi) AS composite_figi,
                        max(share_class_figi) AS share_class_figi,
                        max(cik) AS cik,
                        arg_max(primary_exchange, as_of_date) AS primary_exchange,
                        arg_max(security_type, as_of_date) AS security_type,
                        min(as_of_date) AS first_observed_date,
                        max(as_of_date) AS last_observed_date,
                        arg_max(active, as_of_date) AS active_latest
                    FROM read_parquet('{source}', union_by_name=true)
                    GROUP BY instrument_id
                    ORDER BY latest_ticker, instrument_id
                ) TO '{reg_dest}' (FORMAT PARQUET, COMPRESSION {compression})
                """
            )
            con.execute(
                f"""
                COPY (
                    SELECT
                        instrument_id,
                        ticker,
                        min(as_of_date) AS first_observed_date,
                        max(as_of_date) AS last_observed_date,
                        count(*) AS observation_count
                    FROM read_parquet('{source}', union_by_name=true)
                    GROUP BY instrument_id, ticker
                    ORDER BY ticker, instrument_id
                ) TO '{alias_dest}' (FORMAT PARQUET, COMPRESSION {compression})
                """
            )
        finally:
            con.close()
        promote(reg_temp, registry)
        promote(alias_temp, aliases)

    def resolve_ticker(self, ticker: str, as_of_date: date) -> list[dict[str, object]]:
        snapshot = self.paths.reference_snapshot_file(as_of_date)
        if not snapshot.exists():
            return []
        con = connect_utc(":memory:")
        try:
            safe = self._safe(snapshot)
            rows = con.execute(
                f"""SELECT instrument_id, ticker, name, composite_figi, share_class_figi, cik,
                           primary_exchange, security_type, active
                    FROM read_parquet('{safe}') WHERE ticker=? ORDER BY instrument_id""",
                [ticker.strip()],
            ).fetchall()
            columns = ["instrument_id", "ticker", "name", "composite_figi", "share_class_figi", "cik", "primary_exchange", "security_type", "active"]
            return [dict(zip(columns, row)) for row in rows]
        finally:
            con.close()
