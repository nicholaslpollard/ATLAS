from __future__ import annotations

from collections import defaultdict
from datetime import date

from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.schemas.instrument import (
    IdentityContinuityReport,
    TickerChangeEvent,
    TickerObservationSummary,
    TickerReuseObservation,
    TickerValidityInterval,
)

try:
    import duckdb  # noqa: F401
except ImportError:  # pragma: no cover
    duckdb = None


class IdentityContinuityReconciler:
    """Reconcile point-in-time ticker observations against explicit provider events.

    This service is deliberately non-destructive. It never rewrites provider ticker
    facts and never merges two instrument IDs. Its job is to classify evidence so a
    later mapping layer can use only deterministic, auditable continuity.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        if duckdb is None:
            raise RuntimeError("duckdb is required for identity continuity reconciliation")
        self.settings = settings
        self.paths = MarketDataPaths(settings)

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
            rows = con.execute(
                f"""
                SELECT instrument_id, ticker, name, composite_figi, share_class_figi,
                       cik, primary_exchange, security_type
                FROM read_parquet({sql_string(snapshot)})
                WHERE ticker = ?
                ORDER BY instrument_id
                """,
                [ticker],
            ).fetchall()
        finally:
            con.close()
        if not rows:
            raise LookupError(f"No exact provider ticker {ticker!r} in reference snapshot {as_of_date}")
        if len(rows) != 1:
            ids = ", ".join(str(row[0]) for row in rows)
            raise LookupError(
                f"Ticker {ticker!r} resolves to {len(rows)} instruments on {as_of_date}; "
                f"reconciliation refuses to choose. Candidates: {ids}"
            )
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
        return dict(zip(columns, rows[0]))

    def _observations(self, instrument_id: str, snapshot_ticker: str, as_of_date: date) -> list[TickerObservationSummary]:
        path = self.paths.ticker_observations_file()
        if not path.is_file():
            return [
                TickerObservationSummary(
                    instrument_id=instrument_id,
                    ticker=snapshot_ticker,
                    first_observed_date=as_of_date,
                    last_observed_date=as_of_date,
                    observation_count=1,
                )
            ]
        con = connect_utc(":memory:")
        try:
            rows = con.execute(
                f"""
                SELECT instrument_id, ticker, first_observed_date, last_observed_date,
                       observation_count
                FROM read_parquet({sql_string(path)})
                WHERE instrument_id = ?
                ORDER BY first_observed_date, ticker
                """,
                [instrument_id],
            ).fetchall()
        finally:
            con.close()
        return [
            TickerObservationSummary(
                instrument_id=str(row[0]),
                ticker=str(row[1]),
                first_observed_date=row[2],
                last_observed_date=row[3],
                observation_count=int(row[4]),
            )
            for row in rows
        ] or [
            TickerObservationSummary(
                instrument_id=instrument_id,
                ticker=snapshot_ticker,
                first_observed_date=as_of_date,
                last_observed_date=as_of_date,
                observation_count=1,
            )
        ]

    def _events(self, instrument_id: str) -> list[TickerChangeEvent]:
        path = self.paths.ticker_events_file(instrument_id)
        if not path.is_file():
            return []
        con = connect_utc(":memory:")
        try:
            rows = con.execute(
                f"""
                SELECT event_id, instrument_id, provider, event_type, event_date, ticker,
                       query_identifier, query_identifier_type, continuity_authority,
                       provider_name, fetched_at_utc
                FROM read_parquet({sql_string(path)})
                ORDER BY event_date, ticker
                """
            ).fetchall()
        finally:
            con.close()
        return [
            TickerChangeEvent(
                event_id=str(row[0]),
                instrument_id=str(row[1]),
                provider=row[2],
                event_type=str(row[3]),
                event_date=row[4],
                ticker=str(row[5]),
                query_identifier=str(row[6]),
                query_identifier_type=str(row[7]),
                continuity_authority=bool(row[8]),
                provider_name=str(row[9]) if row[9] is not None else None,
                fetched_at_utc=row[10],
            )
            for row in rows
        ]

    @staticmethod
    def _authoritative_intervals(events: list[TickerChangeEvent]) -> tuple[list[TickerValidityInterval], list[date]]:
        authoritative = [event for event in events if event.continuity_authority]
        by_date: dict[date, set[str]] = defaultdict(set)
        for event in authoritative:
            by_date[event.event_date].add(event.ticker)
        conflicts = sorted(event_date for event_date, tickers in by_date.items() if len(tickers) > 1)
        if conflicts:
            return [], conflicts

        ordered = sorted(authoritative, key=lambda event: (event.event_date, event.ticker))
        intervals: list[TickerValidityInterval] = []
        for index, event in enumerate(ordered):
            next_date = ordered[index + 1].event_date if index + 1 < len(ordered) else None
            intervals.append(
                TickerValidityInterval(
                    instrument_id=event.instrument_id,
                    ticker=event.ticker,
                    valid_from_date=event.event_date,
                    valid_to_date_exclusive=next_date,
                    query_identifier=event.query_identifier,
                    query_identifier_type=event.query_identifier_type,
                    continuity_authority=True,
                    evidence_source="massive_ticker_events",
                )
            )
        return intervals, []

    def _reuse_observations(
        self,
        instrument_id: str,
        observations: list[TickerObservationSummary],
    ) -> tuple[list[TickerReuseObservation], dict[str, list[date]]]:
        aliases_path = self.paths.ticker_observations_file()
        snapshot_root = self.settings.resolved_path(self.settings.data.paths.canonical) / "reference" / "massive" / "tickers"
        if not aliases_path.is_file() or not any(snapshot_root.glob("date=*/*.parquet")):
            return [], {}

        current_by_ticker = {item.ticker: item for item in observations}
        aliases = list(current_by_ticker)
        if not aliases:
            return [], {}

        placeholders = ",".join("?" for _ in aliases)
        con = connect_utc(":memory:")
        try:
            rows = con.execute(
                f"""
                SELECT ticker, instrument_id, first_observed_date, last_observed_date
                FROM read_parquet({sql_string(aliases_path)})
                WHERE ticker IN ({placeholders}) AND instrument_id <> ?
                ORDER BY ticker, instrument_id
                """,
                [*aliases, instrument_id],
            ).fetchall()

            simultaneous_rows = con.execute(
                f"""
                SELECT ticker, as_of_date
                FROM read_parquet(
                    '{self.paths.reference_snapshot_glob()}',
                    union_by_name=true,
                    hive_partitioning=false
                )
                WHERE ticker IN ({placeholders})
                GROUP BY ticker, as_of_date
                HAVING count(DISTINCT instrument_id) > 1
                ORDER BY ticker, as_of_date
                """,
                aliases,
            ).fetchall()
        finally:
            con.close()

        simultaneous: dict[str, list[date]] = defaultdict(list)
        for ticker, snapshot_date in simultaneous_rows:
            simultaneous[str(ticker)].append(snapshot_date)

        result: list[TickerReuseObservation] = []
        for ticker, other_id, other_first, other_last in rows:
            ticker_text = str(ticker)
            current = current_by_ticker[ticker_text]
            overlap = max(current.first_observed_date, other_first) <= min(current.last_observed_date, other_last)
            result.append(
                TickerReuseObservation(
                    ticker=ticker_text,
                    other_instrument_id=str(other_id),
                    current_first_observed_date=current.first_observed_date,
                    current_last_observed_date=current.last_observed_date,
                    other_first_observed_date=other_first,
                    other_last_observed_date=other_last,
                    observation_ranges_overlap=overlap,
                )
            )
        return result, dict(simultaneous)

    def reconcile_ticker(self, ticker: str, as_of_date: date) -> IdentityContinuityReport:
        target = self._resolve_snapshot_target(ticker, as_of_date)
        instrument_id = str(target["instrument_id"])
        snapshot_ticker = str(target["ticker"])
        observations = self._observations(instrument_id, snapshot_ticker, as_of_date)
        events = self._events(instrument_id)
        authoritative_events = [event for event in events if event.continuity_authority]
        intervals, conflicting_event_dates = self._authoritative_intervals(events)
        reuse, simultaneous_collisions = self._reuse_observations(instrument_id, observations)

        observed_set = {item.ticker for item in observations}
        authoritative_set = {item.ticker for item in authoritative_events}
        all_event_set = {item.ticker for item in events}
        unresolved = sorted(observed_set - authoritative_set)
        warnings: list[str] = []

        if conflicting_event_dates:
            warnings.append(
                "Authoritative provider timeline reports multiple tickers on the same event date: "
                + ", ".join(item.isoformat() for item in conflicting_event_dates)
            )
        for alias, dates in sorted(simultaneous_collisions.items()):
            warnings.append(
                f"Exact ticker {alias!r} resolves to multiple instrument IDs in the same reference snapshot on: "
                + ", ".join(item.isoformat() for item in dates)
            )
        if reuse:
            reused_aliases = sorted({item.ticker for item in reuse})
            warnings.append(
                "Exact ticker text has also been observed on other instrument identities: "
                + ", ".join(reused_aliases)
                + ". This is retained as ticker-reuse evidence and never causes an identity merge."
            )

        blocking = bool(conflicting_event_dates or simultaneous_collisions)
        if authoritative_events and unresolved:
            blocking = True
            warnings.append(
                "Authoritative ticker-event history does not cover every observed snapshot alias: "
                + ", ".join(unresolved)
            )

        if blocking:
            status = "blocking_identity_anomaly"
            confirmed = False
        elif len(observed_set) > 1 and authoritative_events and not unresolved:
            status = "confirmed_ticker_change"
            confirmed = True
        elif len(observed_set) > 1 and not authoritative_events:
            if events and observed_set.issubset(all_event_set):
                status = "non_authoritative_support"
            else:
                status = "needs_authoritative_evidence"
            confirmed = False
        elif authoritative_events and observed_set.issubset(authoritative_set):
            status = "provider_history_confirmed"
            confirmed = True
        else:
            status = "single_observed_ticker"
            confirmed = False

        return IdentityContinuityReport(
            instrument_id=instrument_id,
            snapshot_ticker=snapshot_ticker,
            as_of_date=as_of_date,
            status=status,
            continuity_confirmed=confirmed,
            blocking_anomaly=blocking,
            observed_tickers=observations,
            authoritative_events=authoritative_events,
            authoritative_intervals=intervals,
            unresolved_observed_tickers=unresolved,
            ticker_reuse_observations=reuse,
            warnings=warnings,
        )
