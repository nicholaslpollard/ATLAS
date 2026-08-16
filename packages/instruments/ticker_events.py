from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from packages.core.atomic_io import atomic_write_text, unique_temp_path
from packages.core.enums import DataProvider
from packages.core.identifiers import stable_id
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.providers.massive.reference_data import MassiveReferenceProvider
from packages.schemas.instrument import TickerChangeEvent, TickerEventSyncResult

try:
    import duckdb  # noqa: F401
except ImportError:  # pragma: no cover
    duckdb = None


TICKER_EVENT_CONTRACT_VERSION = "ticker-events-v1"


class TickerEventStore:
    """Persist explicit provider ticker-change evidence for stable instruments.

    Composite FIGI is the preferred provider query identifier because Massive's
    ticker-events endpoint documents it as a stable way to retrieve continuity
    across ticker changes. If no Composite FIGI exists, ATLAS may query by the exact
    current ticker, but those rows are marked ``continuity_authority=False`` and are
    never sufficient by themselves to merge instrument identities.
    """

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        provider: MassiveReferenceProvider | None = None,
    ) -> None:
        if duckdb is None:
            raise RuntimeError("duckdb is required for ticker-event persistence")
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.provider = provider or MassiveReferenceProvider(settings)

    @staticmethod
    def _safe(path: Path | str) -> str:
        return str(path).replace("\\", "/").replace("'", "''")

    def _resolve_snapshot_target(self, ticker: str, as_of_date: date) -> dict[str, object]:
        ticker = ticker.strip()
        if not ticker:
            raise ValueError("ticker cannot be blank")
        snapshot = self.paths.reference_snapshot_file(as_of_date)
        if not snapshot.is_file():
            raise FileNotFoundError(
                f"Reference snapshot is missing for {as_of_date}; run sync_instrument_reference.py first"
            )

        con = connect_utc(":memory:")
        try:
            row = con.execute(
                f"""
                SELECT instrument_id, ticker, name, composite_figi, share_class_figi, cik,
                       primary_exchange, security_type
                FROM read_parquet({sql_string(snapshot)})
                WHERE ticker = ?
                ORDER BY instrument_id
                """,
                [ticker],
            ).fetchall()
        finally:
            con.close()

        if not row:
            raise LookupError(f"No exact provider ticker {ticker!r} in reference snapshot {as_of_date}")
        if len(row) != 1:
            ids = ", ".join(str(item[0]) for item in row)
            raise LookupError(
                f"Ticker {ticker!r} resolves to {len(row)} instruments on {as_of_date}; "
                f"select an instrument explicitly before syncing events. Candidates: {ids}"
            )

        values = row[0]
        columns = (
            "instrument_id",
            "ticker",
            "name",
            "composite_figi",
            "share_class_figi",
            "cik",
            "primary_exchange",
            "security_type",
        )
        return dict(zip(columns, values))

    @staticmethod
    def _query_identity(target: dict[str, object]) -> tuple[str, str, bool]:
        composite_figi = str(target.get("composite_figi") or "").strip().upper()
        if composite_figi:
            return composite_figi, "composite_figi", True
        ticker = str(target.get("ticker") or "").strip()
        if not ticker:
            raise ValueError("resolved instrument has no provider ticker")
        return ticker, "ticker", False

    @staticmethod
    def _normalize_events(
        raw_events: list[dict[str, object]],
        *,
        instrument_id: str,
        query_identifier: str,
        query_identifier_type: str,
        continuity_authority: bool,
        fetched_at_utc: datetime,
    ) -> list[TickerChangeEvent]:
        events: list[TickerChangeEvent] = []
        seen: set[tuple[date, str]] = set()
        for raw in raw_events:
            event_type = str(raw.get("type") or "").strip().lower()
            if event_type != "ticker_change":
                continue
            raw_date = raw.get("date")
            change = raw.get("ticker_change")
            if not raw_date or not isinstance(change, dict):
                continue
            ticker = str(change.get("ticker") or "").strip()
            if not ticker:
                continue
            try:
                event_date = date.fromisoformat(str(raw_date))
            except ValueError:
                continue
            key = (event_date, ticker)
            if key in seen:
                continue
            seen.add(key)
            events.append(
                TickerChangeEvent(
                    event_id=stable_id(
                        DataProvider.MASSIVE,
                        instrument_id,
                        event_type,
                        event_date,
                        ticker,
                        prefix="tevt",
                    ),
                    instrument_id=instrument_id,
                    event_type=event_type,
                    event_date=event_date,
                    ticker=ticker,
                    query_identifier=query_identifier,
                    query_identifier_type=query_identifier_type,
                    continuity_authority=continuity_authority,
                    fetched_at_utc=fetched_at_utc,
                )
            )
        events.sort(key=lambda item: (item.event_date, item.ticker))
        return events

    def _write_events(self, events: list[TickerChangeEvent], target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(target)
        temp.unlink(missing_ok=True)
        compression = self.settings.data.parquet.compression.upper()

        con = connect_utc(":memory:")
        staging_json: Path | None = None
        try:
            if events:
                staging_json = unique_temp_path(target.with_suffix(".jsonl"))
                with staging_json.open("w", encoding="utf-8") as handle:
                    for event in events:
                        handle.write(event.model_dump_json() + "\n")
                con.execute(
                    f"""
                    COPY (
                        SELECT
                            event_id,
                            instrument_id,
                            provider,
                            event_type,
                            CAST(event_date AS DATE) AS event_date,
                            ticker,
                            query_identifier,
                            query_identifier_type,
                            continuity_authority,
                            provider_name,
                            CAST(fetched_at_utc AS TIMESTAMPTZ) AS fetched_at_utc
                        FROM read_json_auto({sql_string(staging_json)}, format='newline_delimited')
                        ORDER BY event_date, ticker
                    ) TO {sql_string(temp)} (FORMAT PARQUET, COMPRESSION {compression})
                    """
                )
            else:
                con.execute(
                    f"""
                    COPY (
                        SELECT
                            CAST(NULL AS VARCHAR) AS event_id,
                            CAST(NULL AS VARCHAR) AS instrument_id,
                            CAST(NULL AS VARCHAR) AS provider,
                            CAST(NULL AS VARCHAR) AS event_type,
                            CAST(NULL AS DATE) AS event_date,
                            CAST(NULL AS VARCHAR) AS ticker,
                            CAST(NULL AS VARCHAR) AS query_identifier,
                            CAST(NULL AS VARCHAR) AS query_identifier_type,
                            CAST(NULL AS BOOLEAN) AS continuity_authority,
                            CAST(NULL AS VARCHAR) AS provider_name,
                            CAST(NULL AS TIMESTAMPTZ) AS fetched_at_utc
                        WHERE FALSE
                    ) TO {sql_string(temp)} (FORMAT PARQUET, COMPRESSION {compression})
                    """
                )
        finally:
            con.close()
            if staging_json is not None:
                try:
                    staging_json.unlink(missing_ok=True)
                except OSError:
                    pass
        promote(temp, target)

    def _rebuild_authoritative_intervals(self, *, files_exist: bool) -> None:
        """Build half-open ticker validity intervals from authoritative event facts.

        Only Composite-FIGI-backed rows (``continuity_authority=true``) are eligible.
        If an instrument has more than one ticker on any one provider event date,
        ATLAS suppresses that instrument's entire interval map. It is safer to have
        no mapping than to bridge across ambiguous provider evidence.
        """

        target = self.paths.authoritative_ticker_intervals_file()
        if not files_exist:
            target.unlink(missing_ok=True)
            return

        target.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(target)
        temp.unlink(missing_ok=True)
        compression = self.settings.data.parquet.compression.upper()
        con = connect_utc(":memory:")
        try:
            con.execute(
                f"""
                COPY (
                    WITH authoritative AS (
                        SELECT
                            instrument_id,
                            ticker,
                            event_date,
                            query_identifier,
                            query_identifier_type,
                            fetched_at_utc
                        FROM read_parquet(
                            '{self._safe(self.paths.ticker_events_glob())}',
                            union_by_name=true,
                            hive_partitioning=false
                        )
                        WHERE continuity_authority = true
                    ), conflicted AS (
                        SELECT DISTINCT instrument_id
                        FROM authoritative
                        GROUP BY instrument_id, event_date
                        HAVING count(DISTINCT ticker) > 1
                    ), clean AS (
                        SELECT a.*
                        FROM authoritative a
                        LEFT JOIN conflicted c USING (instrument_id)
                        WHERE c.instrument_id IS NULL
                    )
                    SELECT
                        instrument_id,
                        ticker,
                        event_date AS valid_from_date,
                        lead(event_date) OVER (
                            PARTITION BY instrument_id ORDER BY event_date, ticker
                        ) AS valid_to_date_exclusive,
                        query_identifier,
                        query_identifier_type,
                        true AS continuity_authority,
                        'massive_ticker_events' AS evidence_source,
                        fetched_at_utc
                    FROM clean
                    ORDER BY instrument_id, valid_from_date, ticker
                ) TO {sql_string(temp)} (FORMAT PARQUET, COMPRESSION {compression})
                """
            )
        finally:
            con.close()
        promote(temp, target)

    def _rebuild_event_view(self) -> None:
        root = self.settings.resolved_path(self.settings.data.paths.canonical) / "corporate_actions" / "massive" / "ticker_events"
        files = list(root.glob("instrument_id=*/*.parquet")) if root.exists() else []
        target = self.paths.ticker_event_observations_file()
        if not files:
            target.unlink(missing_ok=True)
            self._rebuild_authoritative_intervals(files_exist=False)
            return

        target.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(target)
        temp.unlink(missing_ok=True)
        compression = self.settings.data.parquet.compression.upper()
        con = connect_utc(":memory:")
        try:
            con.execute(
                f"""
                COPY (
                    SELECT *
                    FROM read_parquet(
                        '{self._safe(self.paths.ticker_events_glob())}',
                        union_by_name=true,
                        hive_partitioning=false
                    )
                    ORDER BY instrument_id, event_date, ticker
                ) TO {sql_string(temp)} (FORMAT PARQUET, COMPRESSION {compression})
                """
            )
        finally:
            con.close()
        promote(temp, target)
        self._rebuild_authoritative_intervals(files_exist=True)

    def rebuild_derived_views(self) -> None:
        """Rebuild combined ticker-event and authoritative interval artifacts."""
        self._rebuild_event_view()

    def sync_for_ticker(self, ticker: str, as_of_date: date, *, force: bool = False) -> TickerEventSyncResult:
        target_obs = self._resolve_snapshot_target(ticker, as_of_date)
        instrument_id = str(target_obs["instrument_id"])
        query_identifier, query_identifier_type, authority = self._query_identity(target_obs)
        target = self.paths.ticker_events_file(instrument_id)
        manifest = self.paths.ticker_events_manifest(instrument_id)

        if target.is_file() and manifest.is_file() and not force:
            try:
                meta = json.loads(manifest.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                meta = {}
            if (
                meta.get("contract_version") == TICKER_EVENT_CONTRACT_VERSION
                and meta.get("query_identifier") == query_identifier
                and meta.get("query_identifier_type") == query_identifier_type
            ):
                self._rebuild_event_view()
                return TickerEventSyncResult(
                    instrument_id=instrument_id,
                    query_identifier=query_identifier,
                    query_identifier_type=query_identifier_type,
                    continuity_authority=authority,
                    event_count=int(meta.get("event_count", 0)),
                    path=str(target),
                    skipped=True,
                )

        fetched_at = datetime.now(UTC)
        raw_events = self.provider.ticker_events(query_identifier)
        events = self._normalize_events(
            raw_events,
            instrument_id=instrument_id,
            query_identifier=query_identifier,
            query_identifier_type=query_identifier_type,
            continuity_authority=authority,
            fetched_at_utc=fetched_at,
        )
        self._write_events(events, target)
        atomic_write_text(
            manifest,
            json.dumps(
                {
                    "contract_version": TICKER_EVENT_CONTRACT_VERSION,
                    "instrument_id": instrument_id,
                    "snapshot_ticker": str(target_obs["ticker"]),
                    "snapshot_date": as_of_date.isoformat(),
                    "query_identifier": query_identifier,
                    "query_identifier_type": query_identifier_type,
                    "continuity_authority": authority,
                    "event_count": len(events),
                    "fetched_at_utc": fetched_at.isoformat(),
                    "path": str(target),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
        self._rebuild_event_view()
        return TickerEventSyncResult(
            instrument_id=instrument_id,
            query_identifier=query_identifier,
            query_identifier_type=query_identifier_type,
            continuity_authority=authority,
            event_count=len(events),
            path=str(target),
            skipped=False,
        )

    def timeline_for_ticker(self, ticker: str, as_of_date: date) -> list[dict[str, object]]:
        target_obs = self._resolve_snapshot_target(ticker, as_of_date)
        path = self.paths.ticker_events_file(str(target_obs["instrument_id"]))
        if not path.is_file():
            return []
        con = connect_utc(":memory:")
        try:
            rows = con.execute(
                f"""
                SELECT event_date, ticker, event_type, query_identifier_type,
                       continuity_authority, fetched_at_utc
                FROM read_parquet({sql_string(path)})
                ORDER BY event_date, ticker
                """
            ).fetchall()
        finally:
            con.close()
        columns = (
            "event_date",
            "ticker",
            "event_type",
            "query_identifier_type",
            "continuity_authority",
            "fetched_at_utc",
        )
        return [dict(zip(columns, row)) for row in rows]
