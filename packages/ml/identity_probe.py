from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import InstrumentIdentityQuality, Timeframe
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.ml.universe_probe import (
    ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS,
    ML_HISTORY_ORIGIN_DATE,
)
from packages.universe.eligibility import ACTIVE_UNIVERSE_ELIGIBILITY_POLICY


ML_HISTORICAL_IDENTITY_PROBE_CONTRACT_VERSION = (
    "ml-historical-identity-probe-v1-authority-unique-reference-structural-eligibility"
)

AUTHORITATIVE_INTERVAL = "AUTHORITATIVE_INTERVAL"
UNIQUE_REFERENCE_NO_REUSE = "UNIQUE_REFERENCE_NO_REUSE"
UNRESOLVED_TICKER_REUSE = "UNRESOLVED_TICKER_REUSE"
UNRESOLVED_MULTI_REFERENCE = "UNRESOLVED_MULTI_REFERENCE"
UNRESOLVED_FALLBACK_IDENTITY = "UNRESOLVED_FALLBACK_IDENTITY"
UNRESOLVED_METADATA_CONFLICT = "UNRESOLVED_METADATA_CONFLICT"
UNMAPPED_REFERENCE = "UNMAPPED_REFERENCE"

SAFE_IDENTITY_STATUSES = (AUTHORITATIVE_INTERVAL, UNIQUE_REFERENCE_NO_REUSE)


@dataclass(frozen=True, slots=True)
class AnnualHistoricalIdentityEvidence:
    year: int
    candidate_rows: int
    identity_safe_rows: int
    structurally_eligible_rows: int
    unresolved_rows: int
    structurally_eligible_fraction: float


@dataclass(frozen=True, slots=True)
class MLHistoricalIdentityProbeReport:
    contract_version: str
    generated_at_utc: str
    history_start: str
    history_end: str
    wall_seconds: float
    candidate_rows: int
    candidate_symbols: int
    identity_status_row_counts: dict[str, int]
    identity_status_symbol_counts: dict[str, int]
    identity_safe_rows: int
    identity_safe_symbols: int
    structurally_eligible_rows: int
    structurally_eligible_symbols: int
    structurally_ineligible_rows: int
    unresolved_rows: int
    identity_safe_fraction: float
    structurally_eligible_fraction: float
    structural_ineligibility_reason_rows: dict[str, int]
    current_active_filter_used: bool
    current_delisted_filter_used: bool
    current_route_filter_used: bool
    ticker_text_splicing_used: bool
    authoritative_interval_rows: int
    unique_reference_no_reuse_rows: int
    unresolved_ticker_reuse_rows: int
    unresolved_multi_reference_rows: int
    unresolved_fallback_identity_rows: int
    unresolved_metadata_conflict_rows: int
    unmapped_reference_rows: int
    annual_evidence: tuple[AnnualHistoricalIdentityEvidence, ...]
    historical_identity_policy_locked: bool
    prediction_label_policy_locked: bool
    report_path: str


def _fraction(numerator: int, denominator: int) -> float:
    return 0.0 if denominator <= 0 else float(numerator) / float(denominator)


def _sql_values(values: tuple[str, ...]) -> str:
    return ", ".join("'" + item.replace("'", "''") + "'" for item in values)


def identity_status(
    *,
    authoritative_interval_count: int,
    reference_identity_count: int,
    reuse_identity_count: int,
    identity_quality: str | None,
    metadata_conflict: bool,
) -> str:
    """Classify a historical exact-ticker observation conservatively."""

    if authoritative_interval_count == 1:
        return AUTHORITATIVE_INTERVAL
    if authoritative_interval_count > 1 or metadata_conflict:
        return UNRESOLVED_METADATA_CONFLICT
    if reference_identity_count > 1:
        return UNRESOLVED_MULTI_REFERENCE
    if reuse_identity_count > 1:
        return UNRESOLVED_TICKER_REUSE
    if reference_identity_count == 0:
        return UNMAPPED_REFERENCE
    if str(identity_quality or "").lower() not in {
        InstrumentIdentityQuality.STRONG.value,
        InstrumentIdentityQuality.MEDIUM.value,
    }:
        return UNRESOLVED_FALLBACK_IDENTITY
    return UNIQUE_REFERENCE_NO_REUSE


def structural_eligibility_reasons(
    *,
    market: str | None,
    locale: str | None,
    primary_exchange: str | None,
    security_type: str | None,
) -> tuple[str, ...]:
    """Apply lifetime-structural Phase 7 rules, not current active/delisted state."""

    policy = ACTIVE_UNIVERSE_ELIGIBILITY_POLICY
    reasons: list[str] = []
    market_value = str(market or "").strip().lower()
    locale_value = str(locale or "").strip().lower()
    exchange_value = str(primary_exchange or "").strip().upper()
    security_value = str(security_type or "").strip().upper()

    if not market_value or not locale_value or not exchange_value or not security_value:
        reasons.append("MISSING_REFERENCE_METADATA")
    if market_value and market_value not in {item.lower() for item in policy.allowed_markets}:
        reasons.append("UNSUPPORTED_MARKET")
    if locale_value and locale_value not in {item.lower() for item in policy.allowed_locales}:
        reasons.append("NON_US_LOCALE")
    if exchange_value and exchange_value not in set(policy.allowed_exchanges):
        reasons.append("UNSUPPORTED_EXCHANGE")
    if security_value and security_value not in set(policy.allowed_security_types):
        reasons.append("UNSUPPORTED_SECURITY_TYPE")
    return tuple(sorted(set(reasons)))


class MLHistoricalIdentityProbe:
    """Measure anti-survivorship historical identity/eligibility coverage in DuckDB."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.feature_names = tuple(definition.name for definition in CORE_FEATURE_REGISTRY.all())

    def report_path(self, end_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "ml" / "historical_identity_probe" / f"{end_date.year:04d}" / f"{end_date}.json"

    def _required_paths(self, end_date: date) -> dict[str, Path]:
        result = {
            "reference": self.paths.reference_snapshot_file(end_date),
            "ticker_observations": self.paths.ticker_observations_file(),
        }
        missing = [f"{name}: {path}" for name, path in result.items() if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                "Phase 10 historical identity inputs are missing:\n  " + "\n  ".join(missing)
            )
        return result

    def _prepare_views(self, con: Any, end_date: date, paths: dict[str, Path]) -> None:
        bar_glob = self.paths.glob_for_timeframe(Timeframe.DAY_1)
        feature_glob = self.paths.feature_glob(Timeframe.DAY_1)
        start = ML_HISTORY_ORIGIN_DATE.isoformat()
        end = end_date.isoformat()
        complete = " AND ".join(
            f"f.{name} IS NOT NULL AND isfinite(f.{name})" for name in self.feature_names
        )

        con.execute(
            f"""
            CREATE TEMP VIEW ml_identity_candidates AS
            SELECT
                b.symbol,
                CAST(b.session_date AS DATE) AS session_date
            FROM read_parquet({sql_string(bar_glob)}, hive_partitioning=true) b
            INNER JOIN read_parquet({sql_string(feature_glob)}, hive_partitioning=true) f
              ON f.symbol = b.symbol
             AND CAST(f.timestamp_utc AS DATE) = CAST(b.session_date AS DATE)
            WHERE CAST(b.session_date AS DATE) BETWEEN DATE '{start}' AND DATE '{end}'
              AND ({complete})
              AND (b.close * b.volume) >= {ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS}
            """
        )

        reference = sql_string(paths["reference"])
        con.execute(
            f"""
            CREATE TEMP VIEW ml_reference_ticker AS
            SELECT
                ticker,
                count(DISTINCT instrument_id) AS reference_identity_count,
                min(instrument_id) AS reference_instrument_id
            FROM read_parquet({reference})
            WHERE ticker IS NOT NULL
            GROUP BY ticker
            """
        )
        con.execute(
            f"""
            CREATE TEMP VIEW ml_reference_instrument AS
            SELECT
                instrument_id,
                count(DISTINCT identity_quality) AS identity_quality_count,
                min(identity_quality) AS identity_quality,
                count(DISTINCT coalesce(market, '<NULL>')) AS market_count,
                min(market) AS market,
                count(DISTINCT coalesce(locale, '<NULL>')) AS locale_count,
                min(locale) AS locale,
                count(DISTINCT coalesce(primary_exchange, '<NULL>')) AS exchange_count,
                min(primary_exchange) AS primary_exchange,
                count(DISTINCT coalesce(security_type, '<NULL>')) AS security_type_count,
                min(security_type) AS security_type
            FROM read_parquet({reference})
            GROUP BY instrument_id
            """
        )

        observations = sql_string(paths["ticker_observations"])
        con.execute(
            f"""
            CREATE TEMP VIEW ml_ticker_reuse AS
            SELECT ticker, count(DISTINCT instrument_id) AS reuse_identity_count
            FROM read_parquet({observations})
            GROUP BY ticker
            """
        )

        intervals = self.paths.authoritative_ticker_intervals_file()
        if intervals.is_file():
            con.execute(
                f"""
                CREATE TEMP VIEW ml_authoritative_intervals AS
                SELECT instrument_id, ticker, valid_from_date, valid_to_date_exclusive
                FROM read_parquet({sql_string(intervals)})
                WHERE coalesce(continuity_authority, TRUE)
                """
            )
        else:
            con.execute(
                """
                CREATE TEMP VIEW ml_authoritative_intervals AS
                SELECT
                    CAST(NULL AS VARCHAR) AS instrument_id,
                    CAST(NULL AS VARCHAR) AS ticker,
                    CAST(NULL AS DATE) AS valid_from_date,
                    CAST(NULL AS DATE) AS valid_to_date_exclusive
                WHERE FALSE
                """
            )

        con.execute(
            """
            CREATE TEMP VIEW ml_identity_base AS
            SELECT
                c.symbol,
                c.session_date,
                coalesce(r.reference_identity_count, 0) AS reference_identity_count,
                r.reference_instrument_id,
                coalesce(t.reuse_identity_count, 0) AS reuse_identity_count,
                count(DISTINCT a.instrument_id) AS authoritative_interval_count,
                min(a.instrument_id) AS authoritative_instrument_id
            FROM ml_identity_candidates c
            LEFT JOIN ml_reference_ticker r ON r.ticker = c.symbol
            LEFT JOIN ml_ticker_reuse t ON t.ticker = c.symbol
            LEFT JOIN ml_authoritative_intervals a
              ON a.ticker = c.symbol
             AND a.valid_from_date <= c.session_date
             AND (a.valid_to_date_exclusive IS NULL OR c.session_date < a.valid_to_date_exclusive)
            GROUP BY ALL
            """
        )

        con.execute(
            """
            CREATE TEMP VIEW ml_identity_evidence_pre AS
            SELECT
                b.*,
                CASE
                    WHEN b.authoritative_interval_count = 1 THEN b.authoritative_instrument_id
                    WHEN b.reference_identity_count = 1 THEN b.reference_instrument_id
                    ELSE NULL
                END AS selected_instrument_id
            FROM ml_identity_base b
            """
        )
        con.execute(
            """
            CREATE TEMP VIEW ml_identity_evidence AS
            SELECT
                e.*,
                i.identity_quality,
                i.market,
                i.locale,
                i.primary_exchange,
                i.security_type,
                (
                    coalesce(i.identity_quality_count, 0) > 1
                    OR coalesce(i.market_count, 0) > 1
                    OR coalesce(i.locale_count, 0) > 1
                    OR coalesce(i.exchange_count, 0) > 1
                    OR coalesce(i.security_type_count, 0) > 1
                ) AS metadata_conflict,
                CASE
                    WHEN e.authoritative_interval_count = 1 THEN 'AUTHORITATIVE_INTERVAL'
                    WHEN e.authoritative_interval_count > 1 OR (
                        coalesce(i.identity_quality_count, 0) > 1
                        OR coalesce(i.market_count, 0) > 1
                        OR coalesce(i.locale_count, 0) > 1
                        OR coalesce(i.exchange_count, 0) > 1
                        OR coalesce(i.security_type_count, 0) > 1
                    ) THEN 'UNRESOLVED_METADATA_CONFLICT'
                    WHEN e.reference_identity_count > 1 THEN 'UNRESOLVED_MULTI_REFERENCE'
                    WHEN e.reuse_identity_count > 1 THEN 'UNRESOLVED_TICKER_REUSE'
                    WHEN e.reference_identity_count = 0 THEN 'UNMAPPED_REFERENCE'
                    WHEN lower(coalesce(i.identity_quality, '')) NOT IN ('strong', 'medium')
                        THEN 'UNRESOLVED_FALLBACK_IDENTITY'
                    ELSE 'UNIQUE_REFERENCE_NO_REUSE'
                END AS identity_status
            FROM ml_identity_evidence_pre e
            LEFT JOIN ml_reference_instrument i
              ON i.instrument_id = e.selected_instrument_id
            """
        )

    @staticmethod
    def _eligibility_sql() -> str:
        policy = ACTIVE_UNIVERSE_ELIGIBILITY_POLICY
        markets = _sql_values(tuple(item.lower() for item in policy.allowed_markets))
        locales = _sql_values(tuple(item.lower() for item in policy.allowed_locales))
        exchanges = _sql_values(tuple(item.upper() for item in policy.allowed_exchanges))
        security_types = _sql_values(tuple(item.upper() for item in policy.allowed_security_types))
        return (
            "market IS NOT NULL AND locale IS NOT NULL AND primary_exchange IS NOT NULL "
            "AND security_type IS NOT NULL "
            f"AND lower(market) IN ({markets}) "
            f"AND lower(locale) IN ({locales}) "
            f"AND upper(primary_exchange) IN ({exchanges}) "
            f"AND upper(security_type) IN ({security_types})"
        )

    def run(self, end_date: date) -> MLHistoricalIdentityProbeReport:
        started = perf_counter()
        if end_date < ML_HISTORY_ORIGIN_DATE:
            raise ValueError("end_date predates the Phase 10 ML history origin")
        paths = self._required_paths(end_date)
        eligible = self._eligibility_sql()
        safe = "identity_status IN ('AUTHORITATIVE_INTERVAL', 'UNIQUE_REFERENCE_NO_REUSE')"

        con = connect_utc(":memory:")
        try:
            self._prepare_views(con, end_date, paths)
            candidate = con.execute(
                "SELECT count(*), count(DISTINCT symbol) FROM ml_identity_evidence"
            ).fetchone()
            status_rows = {
                str(key): int(value)
                for key, value in con.execute(
                    "SELECT identity_status, count(*) FROM ml_identity_evidence GROUP BY 1 ORDER BY 1"
                ).fetchall()
            }
            status_symbols = {
                str(key): int(value)
                for key, value in con.execute(
                    "SELECT identity_status, count(DISTINCT symbol) FROM ml_identity_evidence GROUP BY 1 ORDER BY 1"
                ).fetchall()
            }
            summary = con.execute(
                f"""
                SELECT
                    count(*) FILTER (WHERE {safe}),
                    count(DISTINCT symbol) FILTER (WHERE {safe}),
                    count(*) FILTER (WHERE {safe} AND ({eligible})),
                    count(DISTINCT symbol) FILTER (WHERE {safe} AND ({eligible}))
                FROM ml_identity_evidence
                """
            ).fetchone()
            reasons = con.execute(
                f"""
                SELECT
                    count(*) FILTER (WHERE {safe} AND (
                        market IS NULL OR locale IS NULL OR primary_exchange IS NULL OR security_type IS NULL
                    )),
                    count(*) FILTER (WHERE {safe} AND market IS NOT NULL AND lower(market) NOT IN ({_sql_values(tuple(item.lower() for item in ACTIVE_UNIVERSE_ELIGIBILITY_POLICY.allowed_markets))})),
                    count(*) FILTER (WHERE {safe} AND locale IS NOT NULL AND lower(locale) NOT IN ({_sql_values(tuple(item.lower() for item in ACTIVE_UNIVERSE_ELIGIBILITY_POLICY.allowed_locales))})),
                    count(*) FILTER (WHERE {safe} AND primary_exchange IS NOT NULL AND upper(primary_exchange) NOT IN ({_sql_values(tuple(item.upper() for item in ACTIVE_UNIVERSE_ELIGIBILITY_POLICY.allowed_exchanges))})),
                    count(*) FILTER (WHERE {safe} AND security_type IS NOT NULL AND upper(security_type) NOT IN ({_sql_values(tuple(item.upper() for item in ACTIVE_UNIVERSE_ELIGIBILITY_POLICY.allowed_security_types))}))
                FROM ml_identity_evidence
                """
            ).fetchone()
            annual_rows = con.execute(
                f"""
                SELECT
                    year(session_date),
                    count(*),
                    count(*) FILTER (WHERE {safe}),
                    count(*) FILTER (WHERE {safe} AND ({eligible})),
                    count(*) FILTER (WHERE NOT ({safe}))
                FROM ml_identity_evidence
                GROUP BY 1
                ORDER BY 1
                """
            ).fetchall()
        finally:
            con.close()

        candidate_rows = int(candidate[0])
        identity_safe_rows = int(summary[0])
        structurally_eligible_rows = int(summary[2])
        reason_names = (
            "MISSING_REFERENCE_METADATA",
            "UNSUPPORTED_MARKET",
            "NON_US_LOCALE",
            "UNSUPPORTED_EXCHANGE",
            "UNSUPPORTED_SECURITY_TYPE",
        )
        reason_counts = {
            name: int(value) for name, value in zip(reason_names, reasons, strict=True) if int(value) > 0
        }
        annual = tuple(
            AnnualHistoricalIdentityEvidence(
                year=int(row[0]),
                candidate_rows=int(row[1]),
                identity_safe_rows=int(row[2]),
                structurally_eligible_rows=int(row[3]),
                unresolved_rows=int(row[4]),
                structurally_eligible_fraction=_fraction(int(row[3]), int(row[1])),
            )
            for row in annual_rows
        )

        target = self.report_path(end_date)
        target.parent.mkdir(parents=True, exist_ok=True)
        report = MLHistoricalIdentityProbeReport(
            contract_version=ML_HISTORICAL_IDENTITY_PROBE_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            history_start=ML_HISTORY_ORIGIN_DATE.isoformat(),
            history_end=end_date.isoformat(),
            wall_seconds=perf_counter() - started,
            candidate_rows=candidate_rows,
            candidate_symbols=int(candidate[1]),
            identity_status_row_counts=status_rows,
            identity_status_symbol_counts=status_symbols,
            identity_safe_rows=identity_safe_rows,
            identity_safe_symbols=int(summary[1]),
            structurally_eligible_rows=structurally_eligible_rows,
            structurally_eligible_symbols=int(summary[3]),
            structurally_ineligible_rows=identity_safe_rows - structurally_eligible_rows,
            unresolved_rows=candidate_rows - identity_safe_rows,
            identity_safe_fraction=_fraction(identity_safe_rows, candidate_rows),
            structurally_eligible_fraction=_fraction(structurally_eligible_rows, candidate_rows),
            structural_ineligibility_reason_rows=reason_counts,
            current_active_filter_used=False,
            current_delisted_filter_used=False,
            current_route_filter_used=False,
            ticker_text_splicing_used=False,
            authoritative_interval_rows=status_rows.get(AUTHORITATIVE_INTERVAL, 0),
            unique_reference_no_reuse_rows=status_rows.get(UNIQUE_REFERENCE_NO_REUSE, 0),
            unresolved_ticker_reuse_rows=status_rows.get(UNRESOLVED_TICKER_REUSE, 0),
            unresolved_multi_reference_rows=status_rows.get(UNRESOLVED_MULTI_REFERENCE, 0),
            unresolved_fallback_identity_rows=status_rows.get(UNRESOLVED_FALLBACK_IDENTITY, 0),
            unresolved_metadata_conflict_rows=status_rows.get(UNRESOLVED_METADATA_CONFLICT, 0),
            unmapped_reference_rows=status_rows.get(UNMAPPED_REFERENCE, 0),
            annual_evidence=annual,
            historical_identity_policy_locked=False,
            prediction_label_policy_locked=False,
            report_path=str(target),
        )
        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
