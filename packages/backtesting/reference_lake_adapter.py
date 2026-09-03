from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from packages.core.enums import Timeframe
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.schemas.canonical_market import canonical_stock_daily_schema_matches


REFERENCE_LAKE_ADAPTER_CONTRACT_VERSION = (
    "reference-lake-adapter-v1-massive-development-split-free-identity-exact"
)
REFERENCE_SIGNAL_AVAILABILITY_CONTRACT_VERSION = (
    "reference-signal-availability-v1-xnys-regular-close-next-open"
)
REFERENCE_LAKE_PROVIDER_SEAM_START = date(2021, 8, 16)
REFERENCE_LAKE_DEVELOPMENT_END = date(2026, 5, 11)
REFERENCE_LAKE_PROTECTED_RETURN_READS = 0
REFERENCE_LAKE_PROVIDER_WRITES = 0
REFERENCE_LAKE_BROKER_WRITES = 0
REFERENCE_LAKE_PAPER_SUBMITS = 0
REFERENCE_LAKE_LIVE_WRITES = 0
EXPECTED_SPLIT_REPORT_CONTRACT = (
    "ml-outcome-feasibility-probe-v1-contiguous-horizons-provider-split-adjustment-audit"
)


class ReferenceLakeAdapterError(RuntimeError):
    pass


class ReferenceLakeScopeError(ReferenceLakeAdapterError):
    pass


@dataclass(frozen=True, slots=True)
class ReferenceLakeSourceBundle:
    canonical_partitions: tuple[Path, ...]
    reference_snapshots: tuple[Path, ...]
    authoritative_intervals: Path
    split_report: Path
    split_evidence: Path


@dataclass(frozen=True, slots=True)
class ReferenceLakeAdapterResult:
    bars: pd.DataFrame
    report: dict[str, object]


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sql_string(value: str | Path) -> str:
    return "'" + str(value).replace("\\", "/").replace("'", "''") + "'"


def _sql_path_list(paths: tuple[Path, ...]) -> str:
    return "[" + ",".join(_sql_string(path) for path in paths) + "]"


def _partition_date(path: Path) -> date:
    token = path.parent.name
    if not token.startswith("date="):
        raise ReferenceLakeAdapterError(
            f"canonical partition does not use the accepted date= layout: {path}"
        )
    try:
        return date.fromisoformat(token.split("=", 1)[1])
    except ValueError as exc:
        raise ReferenceLakeAdapterError(f"invalid canonical partition date: {path}") from exc


def _snapshot_date(path: Path) -> date:
    token = path.parent.name
    if not token.startswith("date="):
        raise ReferenceLakeAdapterError(
            f"reference snapshot does not use the accepted date= layout: {path}"
        )
    try:
        return date.fromisoformat(token.split("=", 1)[1])
    except ValueError as exc:
        raise ReferenceLakeAdapterError(f"invalid reference snapshot date: {path}") from exc


def validate_reference_lake_scope(start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise ReferenceLakeScopeError("reference lake end_date precedes start_date")
    if start_date < REFERENCE_LAKE_PROVIDER_SEAM_START:
        raise ReferenceLakeScopeError(
            "adapter v1 is Massive-only and cannot cross the 2021-08-16 provider seam"
        )
    if end_date > REFERENCE_LAKE_DEVELOPMENT_END:
        raise ReferenceLakeScopeError(
            "adapter v1 is DEVELOPMENT-only and cannot read the master protected window"
        )


class ReferenceDailyLakeAdapter:
    """Read accepted canonical daily facts into the frozen reference-runner contract.

    V1 intentionally uses only the post-seam Massive DEVELOPMENT interval. Canonical
    prices are unadjusted, so an instrument is eligible only when complete, hash-bound
    split evidence proves that none of its observed tickers had a split in the
    requested interval. For those retained streams the split factor is exactly 1.0;
    no price or volume is altered and no adjustment factor is guessed.

    Identity may be resolved by one authoritative ticker interval or by one exact
    stable instrument observed for that ticker in all retained point-in-time reference
    snapshots through the requested end date. Current active/delisted fields are never
    used. A contemporaneous canonical regular-session bar is the PIT activity fact.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = MarketCalendar(exchange=settings.data.calendar.exchange)

    def _sessions(self, start_date: date, end_date: date) -> tuple[date, ...]:
        validate_reference_lake_scope(start_date, end_date)
        sessions = tuple(self.calendar.sessions_in_range(start_date, end_date))
        if not sessions:
            raise ReferenceLakeScopeError("reference lake scope contains no XNYS sessions")
        if sessions[0] != start_date or sessions[-1] != end_date:
            raise ReferenceLakeScopeError(
                "reference lake start_date and end_date must both be XNYS sessions"
            )
        return sessions

    def _find_split_report(self, start_date: date, end_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        candidates = sorted(
            (root / "ml" / "outcome_feasibility_probe").glob("*/*.json"), reverse=True
        )
        for path in candidates:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                history_start = date.fromisoformat(str(payload["history_start"]))
                history_end = date.fromisoformat(str(payload["history_end"]))
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                continue
            if (
                payload.get("contract_version") == EXPECTED_SPLIT_REPORT_CONTRACT
                and history_start <= start_date
                and history_end >= end_date
            ):
                return path
        raise FileNotFoundError(
            "no accepted split-evidence report covers the requested DEVELOPMENT interval"
        )

    @staticmethod
    def _split_path_from_report(report_path: Path, payload: dict[str, Any]) -> Path:
        recorded = Path(str(payload.get("split_evidence_path") or ""))
        if recorded.is_file():
            return recorded
        sibling = report_path.with_name(f"{payload.get('history_end')}-splits.jsonl")
        if sibling.is_file():
            return sibling
        raise FileNotFoundError(
            "split evidence referenced by the accepted report is not available: "
            f"{recorded}"
        )

    def discover_sources(
        self,
        start_date: date,
        end_date: date,
        *,
        split_report: Path | None = None,
    ) -> ReferenceLakeSourceBundle:
        sessions = self._sessions(start_date, end_date)
        canonical = tuple(
            self.paths.canonical_file(Timeframe.DAY_1, session) for session in sessions
        )
        missing = [path for path in canonical if not path.is_file()]
        if missing:
            preview = ", ".join(str(path) for path in missing[:5])
            raise FileNotFoundError(
                f"reference lake is missing {len(missing)} canonical session partitions: {preview}"
            )

        reference_root = (
            self.settings.resolved_path(self.settings.data.paths.canonical)
            / "reference"
            / "massive"
            / "tickers"
        )
        references = tuple(
            path
            for path in sorted(reference_root.glob("date=*/*.parquet"))
            if _snapshot_date(path) <= end_date
        )
        if not references:
            raise FileNotFoundError(
                "reference lake requires retained Massive reference snapshots no later than end_date"
            )

        intervals = self.paths.authoritative_ticker_intervals_file()
        if not intervals.is_file():
            raise FileNotFoundError(
                f"reference lake requires authoritative ticker intervals: {intervals}"
            )

        report_path = Path(split_report) if split_report is not None else self._find_split_report(
            start_date, end_date
        )
        if not report_path.is_file():
            raise FileNotFoundError(f"reference lake split report is missing: {report_path}")
        try:
            report_payload = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ReferenceLakeAdapterError("reference lake split report is invalid JSON") from exc
        split_path = self._split_path_from_report(report_path, report_payload)
        return ReferenceLakeSourceBundle(
            canonical_partitions=canonical,
            reference_snapshots=references,
            authoritative_intervals=intervals,
            split_report=report_path,
            split_evidence=split_path,
        )

    @staticmethod
    def _validate_bundle_files(bundle: ReferenceLakeSourceBundle) -> None:
        required = (
            *bundle.canonical_partitions,
            *bundle.reference_snapshots,
            bundle.authoritative_intervals,
            bundle.split_report,
            bundle.split_evidence,
        )
        missing = [path for path in required if not Path(path).is_file()]
        if missing:
            raise FileNotFoundError(
                "reference lake source bundle is incomplete: "
                + ", ".join(str(path) for path in missing[:5])
            )
        if not bundle.canonical_partitions:
            raise ReferenceLakeAdapterError("reference lake canonical inventory is empty")
        if not bundle.reference_snapshots:
            raise ReferenceLakeAdapterError("reference lake reference inventory is empty")

    @staticmethod
    def _split_events(
        bundle: ReferenceLakeSourceBundle,
        start_date: date,
        end_date: date,
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        try:
            report = json.loads(bundle.split_report.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ReferenceLakeAdapterError("split report is invalid JSON") from exc
        if report.get("contract_version") != EXPECTED_SPLIT_REPORT_CONTRACT:
            raise ReferenceLakeAdapterError("split evidence report contract is stale")
        try:
            report_start = date.fromisoformat(str(report["history_start"]))
            report_end = date.fromisoformat(str(report["history_end"]))
        except (KeyError, ValueError) as exc:
            raise ReferenceLakeAdapterError("split report has an invalid history range") from exc
        if report_start > start_date or report_end < end_date:
            raise ReferenceLakeAdapterError(
                "split evidence does not cover the requested reference-lake interval"
            )
        split_sha = _sha256_file(bundle.split_evidence)
        if split_sha != str(report.get("split_evidence_sha256") or ""):
            raise ReferenceLakeAdapterError("split evidence SHA-256 does not match its report")

        rows: list[dict[str, object]] = []
        total_rows = 0
        total_tickers: set[str] = set()
        with bundle.split_evidence.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                    ticker = str(item["ticker"]).strip()
                    execution_date = date.fromisoformat(str(item["execution_date"]))
                except (json.JSONDecodeError, KeyError, ValueError) as exc:
                    raise ReferenceLakeAdapterError(
                        f"split evidence row {line_number} is invalid"
                    ) from exc
                if not ticker:
                    raise ReferenceLakeAdapterError(
                        f"split evidence row {line_number} has a blank ticker"
                    )
                total_rows += 1
                total_tickers.add(ticker)
                if start_date <= execution_date <= end_date:
                    rows.append({"ticker": ticker, "execution_date": execution_date})
        split_summary = report.get("split_adjustment")
        if not isinstance(split_summary, dict):
            raise ReferenceLakeAdapterError("split report lacks its accepted event summary")
        if int(split_summary.get("fetched_split_events", -1)) != total_rows:
            raise ReferenceLakeAdapterError(
                "split evidence row count does not match its accepted report"
            )
        if int(split_summary.get("fetched_split_symbols", -1)) != len(total_tickers):
            raise ReferenceLakeAdapterError(
                "split evidence ticker count does not match its accepted report"
            )
        if report.get("corporate_action_evidence_source") != "Massive /stocks/v1/splits":
            raise ReferenceLakeAdapterError("split report corporate-action source is not Massive")
        return pd.DataFrame(rows, columns=["ticker", "execution_date"]), report

    @staticmethod
    def _inventory(bundle: ReferenceLakeSourceBundle) -> dict[str, object]:
        canonical = [
            {
                "session_date": _partition_date(path).isoformat(),
                "sha256": _sha256_file(path),
            }
            for path in bundle.canonical_partitions
        ]
        references = [
            {
                "as_of_date": _snapshot_date(path).isoformat(),
                "sha256": _sha256_file(path),
            }
            for path in bundle.reference_snapshots
        ]
        return {
            "canonical": canonical,
            "references": references,
            "authoritative_intervals_sha256": _sha256_file(bundle.authoritative_intervals),
            "split_report_sha256": _sha256_file(bundle.split_report),
            "split_evidence_sha256": _sha256_file(bundle.split_evidence),
        }

    @staticmethod
    def _canonical_schema(con: duckdb.DuckDBPyConnection, paths: tuple[Path, ...]) -> None:
        description = con.execute(
            f"DESCRIBE SELECT * FROM read_parquet({_sql_path_list(paths)}, "
            "hive_partitioning=false)"
        ).fetchall()
        if not canonical_stock_daily_schema_matches(description):
            raise ReferenceLakeAdapterError("canonical daily physical schema is not exact")

    def load(
        self,
        start_date: date,
        end_date: date,
        *,
        bundle: ReferenceLakeSourceBundle | None = None,
        split_report: Path | None = None,
    ) -> ReferenceLakeAdapterResult:
        sessions = self._sessions(start_date, end_date)
        sources = bundle or self.discover_sources(
            start_date, end_date, split_report=split_report
        )
        self._validate_bundle_files(sources)

        partition_dates = tuple(_partition_date(path) for path in sources.canonical_partitions)
        if partition_dates != sessions:
            raise ReferenceLakeAdapterError(
                "canonical source inventory does not exactly match requested XNYS sessions"
            )
        if any(_snapshot_date(path) > end_date for path in sources.reference_snapshots):
            raise ReferenceLakeAdapterError(
                "reference source inventory contains a snapshot after the DEVELOPMENT end_date"
            )

        splits, split_report_payload = self._split_events(sources, start_date, end_date)
        inventory = self._inventory(sources)
        source_fingerprint = _stable_hash(
            {
                "contract_version": REFERENCE_LAKE_ADAPTER_CONTRACT_VERSION,
                "start_date": start_date,
                "end_date": end_date,
                "inventory": inventory,
                "adjustment_policy": "factor-1-only-exclude-any-observed-split-ticker",
                "identity_policy": "one-authoritative-interval-else-unique-retained-reference",
                "gap_policy": "complete-between-first-and-last-observed-session",
            }
        )

        expected_sessions = pd.DataFrame(
            {
                "session_date": list(sessions),
                "session_sequence": range(len(sessions)),
                "regular_open_utc": [
                    self.calendar.regular_open_close(session)[0] for session in sessions
                ],
                "regular_close_utc": [
                    self.calendar.regular_open_close(session)[1] for session in sessions
                ],
            }
        )
        source_partitions = pd.DataFrame(
            {
                "source_filename": [path.resolve().as_posix() for path in sources.canonical_partitions],
                "partition_date": list(partition_dates),
            }
        )
        reference_partitions = pd.DataFrame(
            {
                "source_filename": [path.resolve().as_posix() for path in sources.reference_snapshots],
                "snapshot_date": [_snapshot_date(path) for path in sources.reference_snapshots],
            }
        )
        con = duckdb.connect(":memory:")
        try:
            self._canonical_schema(con, sources.canonical_partitions)
            con.register("expected_sessions_input", expected_sessions)
            con.register("source_partitions_input", source_partitions)
            con.register("reference_partitions_input", reference_partitions)
            con.register("split_events_input", splits)
            con.execute(
                "CREATE TEMP TABLE expected_sessions AS "
                "SELECT CAST(session_date AS DATE) session_date, "
                "CAST(session_sequence AS BIGINT) session_sequence, "
                "CAST(regular_open_utc AS TIMESTAMPTZ) regular_open_utc, "
                "CAST(regular_close_utc AS TIMESTAMPTZ) regular_close_utc "
                "FROM expected_sessions_input"
            )
            con.execute(
                "CREATE TEMP TABLE source_partitions AS "
                "SELECT CAST(source_filename AS VARCHAR) source_filename, "
                "CAST(partition_date AS DATE) partition_date FROM source_partitions_input"
            )
            con.execute(
                "CREATE TEMP TABLE reference_partitions AS "
                "SELECT CAST(source_filename AS VARCHAR) source_filename, "
                "CAST(snapshot_date AS DATE) snapshot_date FROM reference_partitions_input"
            )
            con.execute(
                "CREATE TEMP TABLE split_events AS "
                "SELECT CAST(ticker AS VARCHAR) ticker, "
                "CAST(execution_date AS DATE) execution_date FROM split_events_input"
            )

            canonical_sql = _sql_path_list(sources.canonical_partitions)
            reference_sql = _sql_path_list(sources.reference_snapshots)
            interval_sql = _sql_string(sources.authoritative_intervals)
            con.execute(
                f"""
                CREATE TEMP VIEW source_bars AS
                SELECT b.*, p.partition_date, s.regular_open_utc, s.regular_close_utc
                FROM read_parquet(
                    {canonical_sql}, hive_partitioning=false, filename=true
                ) b
                LEFT JOIN source_partitions p
                  ON replace(CAST(b.filename AS VARCHAR), '\\', '/') = p.source_filename
                LEFT JOIN expected_sessions s
                  ON s.session_date = CAST(b.session_date AS DATE)
                """
            )
            source_stats = con.execute(
                """
                SELECT count(*), count(DISTINCT session_date),
                       count(*) FILTER (
                           WHERE provider <> 'massive'
                              OR timeframe <> '1d'
                              OR dataset <> 'stock_daily_aggregates'
                              OR session_segment <> 'regular'
                              OR is_adjusted IS NOT NULL
                              OR partition_date IS NULL
                              OR CAST(session_date AS DATE) <> partition_date
                       ),
                       count(*) - count(DISTINCT (symbol, session_date)),
                       count(*) FILTER (
                           WHERE regular_open_utc IS NULL
                              OR timestamp_utc <> regular_open_utc
                              OR symbol IS NULL OR trim(CAST(symbol AS VARCHAR)) = ''
                              OR source_id IS NULL OR trim(CAST(source_id AS VARCHAR)) = ''
                              OR NOT isfinite(open) OR NOT isfinite(high)
                              OR NOT isfinite(low) OR NOT isfinite(close)
                              OR NOT isfinite(volume)
                              OR open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
                              OR volume < 0 OR high < greatest(open, close)
                              OR low > least(open, close) OR high < low
                              OR (vwap IS NOT NULL AND (NOT isfinite(vwap) OR vwap <= 0))
                              OR (transaction_count IS NOT NULL AND transaction_count < 0)
                       )
                FROM source_bars
                """
            ).fetchone()
            assert source_stats is not None
            if int(source_stats[1]) != len(sessions):
                raise ReferenceLakeAdapterError(
                    "canonical rows do not cover every requested XNYS session"
                )
            if int(source_stats[2]) != 0:
                raise ReferenceLakeAdapterError(
                    "canonical source contains non-Massive, adjusted, or wrong-session rows"
                )
            if int(source_stats[3]) != 0:
                raise ReferenceLakeAdapterError(
                    "canonical source contains duplicate symbol/session rows"
                )
            if int(source_stats[4]) != 0:
                raise ReferenceLakeAdapterError("canonical source contains invalid daily OHLCV")

            con.execute(
                f"""
                CREATE TEMP VIEW retained_reference_raw AS
                SELECT
                    CAST(instrument_id AS VARCHAR) instrument_id,
                    CAST(ticker AS VARCHAR) ticker,
                    lower(CAST(identity_quality AS VARCHAR)) identity_quality,
                    lower(CAST(market AS VARCHAR)) market,
                    lower(CAST(locale AS VARCHAR)) locale,
                    upper(CAST(primary_exchange AS VARCHAR)) primary_exchange,
                    upper(CAST(security_type AS VARCHAR)) security_type,
                    CAST(as_of_date AS DATE) as_of_date,
                    p.snapshot_date
                FROM read_parquet(
                    {reference_sql}, union_by_name=true, hive_partitioning=false,
                    filename=true
                ) r
                LEFT JOIN reference_partitions p
                  ON replace(CAST(r.filename AS VARCHAR), '\\', '/') = p.source_filename
                """
            )
            reference_mismatches = int(
                con.execute(
                    """
                    SELECT count(*)
                    FROM retained_reference_raw
                    WHERE snapshot_date IS NULL OR as_of_date <> snapshot_date
                       OR instrument_id IS NULL OR trim(instrument_id) = ''
                       OR ticker IS NULL OR trim(ticker) = ''
                    """
                ).fetchone()[0]
            )
            if reference_mismatches:
                raise ReferenceLakeAdapterError(
                    "reference snapshots contain path/date or required-identity mismatches"
                )
            con.execute(
                """
                CREATE TEMP VIEW retained_reference AS
                SELECT instrument_id, ticker, identity_quality, market, locale,
                       primary_exchange, security_type, as_of_date
                FROM retained_reference_raw
                """
            )
            con.execute(
                """
                CREATE TEMP TABLE stable_metadata AS
                SELECT
                    instrument_id,
                    min(market) market,
                    min(locale) locale,
                    min(primary_exchange) primary_exchange,
                    min(security_type) security_type,
                    count(DISTINCT identity_quality) identity_quality_count,
                    count(DISTINCT market) market_count,
                    count(DISTINCT locale) locale_count,
                    count(DISTINCT primary_exchange) primary_exchange_count,
                    count(DISTINCT security_type) security_type_count,
                    count(*) FILTER (WHERE identity_quality IN ('strong','medium'))
                        trusted_identity_rows
                FROM retained_reference
                GROUP BY instrument_id
                """
            )
            con.execute(
                """
                CREATE TEMP TABLE unique_ticker_identity AS
                SELECT ticker, min(instrument_id) instrument_id,
                       count(DISTINCT instrument_id) instrument_count
                FROM retained_reference
                GROUP BY ticker
                """
            )
            con.execute(
                f"""
                CREATE TEMP VIEW authoritative_intervals AS
                SELECT
                    CAST(instrument_id AS VARCHAR) instrument_id,
                    CAST(ticker AS VARCHAR) ticker,
                    CAST(valid_from_date AS DATE) valid_from_date,
                    CAST(valid_to_date_exclusive AS DATE) valid_to_date_exclusive
                FROM read_parquet({interval_sql}, hive_partitioning=false)
                WHERE coalesce(continuity_authority, FALSE)
                """
            )
            con.execute(
                """
                CREATE TEMP TABLE identity_resolution AS
                SELECT
                    b.symbol,
                    CAST(b.session_date AS DATE) session_date,
                    count(DISTINCT i.instrument_id) interval_count,
                    min(i.instrument_id) interval_instrument_id,
                    min(u.instrument_id) unique_instrument_id,
                    coalesce(min(u.instrument_count), 0) unique_instrument_count
                FROM source_bars b
                LEFT JOIN authoritative_intervals i
                  ON i.ticker = b.symbol
                 AND i.valid_from_date <= CAST(b.session_date AS DATE)
                 AND (
                    i.valid_to_date_exclusive IS NULL
                    OR CAST(b.session_date AS DATE) < i.valid_to_date_exclusive
                 )
                LEFT JOIN unique_ticker_identity u ON u.ticker = b.symbol
                GROUP BY b.symbol, CAST(b.session_date AS DATE)
                """
            )
            con.execute(
                """
                CREATE TEMP VIEW resolved_bars AS
                SELECT
                    CASE
                        WHEN r.interval_count = 1 THEN r.interval_instrument_id
                        WHEN r.interval_count = 0 AND r.unique_instrument_count = 1
                            THEN r.unique_instrument_id
                        ELSE NULL
                    END instrument_id,
                    b.symbol ticker,
                    CAST(b.session_date AS DATE) session_date,
                    b.timestamp_utc,
                    b.regular_close_utc,
                    b.open, b.high, b.low, b.close, b.volume,
                    b.provider, b.dataset, b.source_id, b.is_adjusted,
                    r.interval_count, r.unique_instrument_count
                FROM source_bars b
                INNER JOIN identity_resolution r
                  ON r.symbol = b.symbol
                 AND r.session_date = CAST(b.session_date AS DATE)
                """
            )
            con.execute(
                """
                CREATE TEMP VIEW metadata_clear_bars AS
                SELECT r.*, m.market, m.locale, m.primary_exchange, m.security_type,
                       s.session_sequence
                FROM resolved_bars r
                INNER JOIN stable_metadata m USING (instrument_id)
                INNER JOIN expected_sessions s USING (session_date)
                WHERE r.instrument_id IS NOT NULL
                  AND m.identity_quality_count = 1
                  AND m.trusted_identity_rows > 0
                  AND m.market_count = 1 AND m.locale_count = 1
                  AND m.primary_exchange_count = 1 AND m.security_type_count = 1
                """
            )
            con.execute(
                """
                CREATE TEMP TABLE split_identities AS
                SELECT DISTINCT instrument_id
                FROM (
                    SELECT b.instrument_id
                    FROM metadata_clear_bars b
                    INNER JOIN split_events s ON s.ticker = b.ticker
                    UNION
                    SELECT u.instrument_id
                    FROM split_events s
                    INNER JOIN unique_ticker_identity u ON u.ticker = s.ticker
                    WHERE u.instrument_count = 1
                    UNION
                    SELECT i.instrument_id
                    FROM split_events s
                    INNER JOIN authoritative_intervals i
                      ON i.ticker = s.ticker
                     AND i.valid_from_date <= s.execution_date
                     AND (
                        i.valid_to_date_exclusive IS NULL
                        OR s.execution_date < i.valid_to_date_exclusive
                     )
                ) resolved_split_identities
                WHERE instrument_id IS NOT NULL
                """
            )
            con.execute(
                """
                CREATE TEMP VIEW no_split_bars AS
                SELECT b.*
                FROM metadata_clear_bars b
                LEFT JOIN split_identities s USING (instrument_id)
                WHERE s.instrument_id IS NULL
                """
            )
            con.execute(
                """
                CREATE TEMP TABLE stream_quality AS
                SELECT
                    instrument_id,
                    count(*) row_count,
                    count(DISTINCT session_date) session_count,
                    min(session_sequence) first_sequence,
                    max(session_sequence) last_sequence,
                    count(*) - count(DISTINCT session_date) duplicate_sessions
                FROM no_split_bars
                GROUP BY instrument_id
                """
            )
            output = con.execute(
                f"""
                SELECT
                    b.instrument_id,
                    b.ticker,
                    b.session_date,
                    b.timestamp_utc,
                    b.regular_close_utc AS signal_available_at_utc,
                    CAST(b.open AS DOUBLE) AS open,
                    CAST(b.high AS DOUBLE) AS high,
                    CAST(b.low AS DOUBLE) AS low,
                    CAST(b.close AS DOUBLE) AS close,
                    CAST(b.volume AS DOUBLE) AS volume,
                    TRUE AS pit_active,
                    b.security_type,
                    TRUE AS identity_clear,
                    'SPLIT_ADJUSTED' AS price_adjustment_mode,
                    '{source_fingerprint}' AS raw_price_lineage_id,
                    CAST(b.provider AS VARCHAR) AS source_provider,
                    CAST(b.dataset AS VARCHAR) AS source_dataset,
                    CAST(b.source_id AS VARCHAR) AS source_id,
                    'FACTOR_1_CERTIFIED_NO_DOCUMENTED_SPLIT' AS split_adjustment_method
                FROM no_split_bars b
                INNER JOIN stream_quality q USING (instrument_id)
                WHERE q.duplicate_sessions = 0
                  AND q.row_count = q.session_count
                  AND q.session_count = q.last_sequence - q.first_sequence + 1
                ORDER BY b.instrument_id, b.session_date, b.timestamp_utc
                """
            ).fetchdf()
            counts = con.execute(
                """
                SELECT
                    (SELECT count(*) FROM source_bars),
                    (SELECT count(*) FROM resolved_bars WHERE instrument_id IS NULL),
                    (SELECT count(*) FROM resolved_bars r
                       LEFT JOIN stable_metadata m USING (instrument_id)
                       WHERE r.instrument_id IS NOT NULL AND (
                         m.instrument_id IS NULL OR m.identity_quality_count <> 1
                         OR m.trusted_identity_rows = 0 OR m.market_count <> 1
                         OR m.locale_count <> 1 OR m.primary_exchange_count <> 1
                         OR m.security_type_count <> 1
                       )),
                    (SELECT count(*) FROM split_identities),
                    (SELECT coalesce(sum(row_count), 0) FROM stream_quality
                       WHERE duplicate_sessions <> 0
                          OR row_count <> session_count
                          OR session_count <> last_sequence - first_sequence + 1),
                    (SELECT count(*) FROM stream_quality
                       WHERE duplicate_sessions <> 0
                          OR row_count <> session_count
                          OR session_count <> last_sequence - first_sequence + 1)
                """
            ).fetchone()
        finally:
            con.close()

        assert counts is not None
        if output.empty:
            raise ReferenceLakeAdapterError(
                "reference lake adapter produced no identity-safe split-free contiguous rows"
            )
        output["timestamp_utc"] = pd.to_datetime(output["timestamp_utc"], utc=True)
        output["signal_available_at_utc"] = pd.to_datetime(
            output["signal_available_at_utc"], utc=True
        )
        output["session_date"] = pd.to_datetime(output["session_date"]).dt.date
        report: dict[str, object] = {
            "contract_version": REFERENCE_LAKE_ADAPTER_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "status": "PASS",
            "scope": "POST_SEAM_MASSIVE_DEVELOPMENT_ONLY",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "xnys_sessions": len(sessions),
            "provider_boundary": {
                "alpaca_last_session": "2021-08-13",
                "massive_first_session": "2021-08-16",
                "adapter_v1_provider": "massive",
            },
            "canonical_partitions": len(sources.canonical_partitions),
            "reference_snapshots": len(sources.reference_snapshots),
            "source_rows": int(counts[0]),
            "unresolved_identity_rows": int(counts[1]),
            "conflicting_metadata_rows": int(counts[2]),
            "documented_split_events_in_scope": int(len(splits)),
            "split_excluded_instruments": int(counts[3]),
            "gap_excluded_rows": int(counts[4]),
            "gap_excluded_instruments": int(counts[5]),
            "output_rows": int(len(output)),
            "output_instruments": int(output["instrument_id"].nunique()),
            "price_adjustment_policy": "FACTOR_1_ONLY_EXCLUDE_ANY_DOCUMENTED_SPLIT_IDENTITY",
            "signal_availability_contract": REFERENCE_SIGNAL_AVAILABILITY_CONTRACT_VERSION,
            "canonical_bar_timestamp_semantics": "PROVIDER_REGULAR_OPEN_STAMP_PRESERVED",
            "signal_available_at_semantics": "XNYS_REGULAR_CLOSE_AFTER_DAILY_BAR_FINALIZATION",
            "entry_timing_semantics": "NO_EARLIER_THAN_NEXT_REGULAR_SESSION_OPEN",
            "current_active_filter_used": False,
            "current_delisted_filter_used": False,
            "future_reference_snapshot_used": False,
            "source_fingerprint": source_fingerprint,
            "split_report_contract": split_report_payload["contract_version"],
            "split_evidence_sha256": inventory["split_evidence_sha256"],
            "protected_master_return_rows_read": REFERENCE_LAKE_PROTECTED_RETURN_READS,
            "provider_writes": REFERENCE_LAKE_PROVIDER_WRITES,
            "broker_writes": REFERENCE_LAKE_BROKER_WRITES,
            "paper_submits": REFERENCE_LAKE_PAPER_SUBMITS,
            "live_writes": REFERENCE_LAKE_LIVE_WRITES,
            "performance_opened": False,
            "checks": {
                "development_scope_only": True,
                "canonical_session_inventory_exact": True,
                "canonical_schema_exact": True,
                "massive_postseam_semantics_exact": True,
                "daily_close_availability_clock_explicit": True,
                "identity_fail_closed": True,
                "stable_metadata_only": True,
                "split_affected_identity_excluded": True,
                "internal_session_gaps_excluded": True,
                "protected_returns_unread": True,
                "external_writes_zero": True,
            },
        }
        return ReferenceLakeAdapterResult(bars=output, report=report)
