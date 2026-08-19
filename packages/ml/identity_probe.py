from __future__ import annotations

import json
from collections import Counter
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


def identity_status(
    *,
    authoritative_interval_count: int,
    reference_identity_count: int,
    reuse_identity_count: int,
    identity_quality: str | None,
    metadata_conflict: bool,
) -> str:
    """Classify one historical ticker observation without ticker-text splicing.

    Exact authoritative validity evidence wins. Without it, a historical provider
    ticker may map operationally only when the current inclusive reference inventory
    resolves that exact ticker to one strong/medium stable identity and the accumulated
    ticker-observation registry contains no evidence of reuse by another identity.
    """

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
    """Apply only lifetime-structural Phase 7 metadata rules.

    Current active/delisted state is intentionally excluded because using a 2026
    status to remove earlier observations would introduce survivorship bias.
    """

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
    """Measure identity-safe, observation-driven historical ML coverage.

    This probe deliberately does not use the current routed universe, current active
    flag, or current delisted flag. It asks how much fully-warmed/liquid historical
    evidence can be assigned conservatively to stable identities using exact
    authoritative intervals or a unique unreused strong/medium reference identity.
    """

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
        complete = " AND ".join(f"f.{name} IS NOT NULL" for name in self.feature_names)

        con.execute(
            f"""
            CREATE TEMP VIEW ml_identity_candidates AS
            SELECT
                b.symbol,
                CAST(b.session_date AS DATE) AS session_date,
                b.close * b.volume AS source_dollar_volume
            FROM read_parquet({sql_string(bar_glob)}, hive_partitioning=true) b
            INNER JOIN read_parquet({sql_string(feature_glob)}, hive_partitioning=true) f
              ON f.symbol = b.symbol
             AND CAST(f.timestamp_utc AS DATE) = CAST(b.session_date AS DATE)
            WHERE CAST(b.session_date AS DATE) BETWEEN DATE '{start}' AND DATE '{end}'
              AND ({complete})
              AND (b.close * b.volume) >= {ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS}
            """
        )

        con.execute(
            f"""
            CREATE TEMP VIEW ml_reference_by_ticker AS
            SELECT
                ticker,
                count(DISTINCT instrument_id) AS reference_identity_count,
                min(instrument_id) AS reference_instrument_id,
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
            FROM read_parquet({sql_string(paths['reference'])})
            WHERE ticker IS NOT NULL
            GROUP BY ticker
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
            interval_source = sql_string(intervals)
            con.execute(
                f"""
                CREATE TEMP VIEW ml_authoritative_intervals AS
                SELECT instrument_id, ticker, valid_from_date, valid_to_date_exclusive
                FROM read_parquet({interval_source})
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
            CREATE TEMP VIEW ml_identity_evidence AS
            SELECT
                c.symbol,
                c.session_date,
                coalesce(r.reference_identity_count, 0) AS reference_identity_count,
                r.reference_instrument_id,
                r.identity_quality,
                coalesce(t.reuse_identity_count, 0) AS reuse_identity_count,
                r.market,
                r.locale,
                r.primary_exchange,
                r.security_type,
                (
                    coalesce(r.identity_quality_count, 0) > 1
                    OR coalesce(r.market_count, 0) > 1
                    OR coalesce(r.locale_count, 0) > 1
                    OR coalesce(r.exchange_count, 0) > 1
                    OR coalesce(r.security_type_count, 0) > 1
                ) AS metadata_conflict,
                count(a.instrument_id) FILTER (
                    WHERE a.valid_from_date <= c.session_date
                      AND (a.valid_to_date_exclusive IS NULL OR c.session_date < a.valid_to_date_exclusive)
                ) AS authoritative_interval_count
            FROM ml_identity_candidates c
            LEFT JOIN ml_reference_by_ticker r ON r.ticker = c.symbol
            LEFT JOIN ml_ticker_reuse t ON t.ticker = c.symbol
            LEFT JOIN ml_authoritative_intervals a
              ON a.ticker = c.symbol
             AND a.instrument_id = r.reference_instrument_id
             AND a.valid_from_date <= c.session_date
             AND (a.valid_to_date_exclusive IS NULL OR c.session_date < a.valid_to_date_exclusive)
            GROUP BY ALL
            """
        )

    @staticmethod
    def _status_for_row(row: tuple[object, ...]) -> str:
        return identity_status(
            authoritative_interval_count=int(row[2]),
            reference_identity_count=int(row[3]),
            reuse_identity_count=int(row[4]),
            identity_quality=None if row[5] is None else str(row[5]),
            metadata_conflict=bool(row[10]),
        )

    def run(self, end_date: date) -> MLHistoricalIdentityProbeReport:
        started = perf_counter()
        if end_date < ML_HISTORY_ORIGIN_DATE:
            raise ValueError("end_date predates the Phase 10 ML history origin")
        paths = self._required_paths(end_date)
        con = connect_utc(":memory:")
        try:
            self._prepare_views(con, end_date, paths)
            rows = con.execute(
                """
                SELECT
                    symbol,
                    session_date,
                    authoritative_interval_count,
                    reference_identity_count,
                    reuse_identity_count,
                    identity_quality,
                    market,
                    locale,
                    primary_exchange,
                    security_type,
                    metadata_conflict
                FROM ml_identity_evidence
                ORDER BY session_date, symbol
                """
            ).fetchall()
        finally:
            con.close()

        status_rows: Counter[str] = Counter()
        status_symbols: dict[str, set[str]] = {}
        reason_rows: Counter[str] = Counter()
        safe_symbols: set[str] = set()
        eligible_symbols: set[str] = set()
        annual: dict[int, Counter[str]] = {}

        for row in rows:
            symbol = str(row[0])
            session_date = row[1]
            status = self._status_for_row(row)
            status_rows[status] += 1
            status_symbols.setdefault(status, set()).add(symbol)
            year = int(session_date.year)
            year_counts = annual.setdefault(year, Counter())
            year_counts["candidate"] += 1

            if status not in SAFE_IDENTITY_STATUSES:
                year_counts["unresolved"] += 1
                continue

            safe_symbols.add(symbol)
            year_counts["safe"] += 1
            reasons = structural_eligibility_reasons(
                market=None if row[6] is None else str(row[6]),
                locale=None if row[7] is None else str(row[7]),
                primary_exchange=None if row[8] is None else str(row[8]),
                security_type=None if row[9] is None else str(row[9]),
            )
            if reasons:
                for reason in reasons:
                    reason_rows[reason] += 1
                continue
            eligible_symbols.add(symbol)
            year_counts["eligible"] += 1

        candidate_rows = len(rows)
        identity_safe_rows = sum(status_rows[name] for name in SAFE_IDENTITY_STATUSES)
        structurally_eligible_rows = sum(item["eligible"] for item in annual.values())
        structurally_ineligible_rows = identity_safe_rows - structurally_eligible_rows
        unresolved_rows = candidate_rows - identity_safe_rows
        annual_evidence = tuple(
            AnnualHistoricalIdentityEvidence(
                year=year,
                candidate_rows=int(counts["candidate"]),
                identity_safe_rows=int(counts["safe"]),
                structurally_eligible_rows=int(counts["eligible"]),
                unresolved_rows=int(counts["unresolved"]),
                structurally_eligible_fraction=_fraction(
                    int(counts["eligible"]), int(counts["candidate"])
                ),
            )
            for year, counts in sorted(annual.items())
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
            candidate_symbols=len({str(row[0]) for row in rows}),
            identity_status_row_counts=dict(sorted(status_rows.items())),
            identity_status_symbol_counts={
                key: len(value) for key, value in sorted(status_symbols.items())
            },
            identity_safe_rows=identity_safe_rows,
            identity_safe_symbols=len(safe_symbols),
            structurally_eligible_rows=structurally_eligible_rows,
            structurally_eligible_symbols=len(eligible_symbols),
            structurally_ineligible_rows=structurally_ineligible_rows,
            unresolved_rows=unresolved_rows,
            identity_safe_fraction=_fraction(identity_safe_rows, candidate_rows),
            structurally_eligible_fraction=_fraction(structurally_eligible_rows, candidate_rows),
            structural_ineligibility_reason_rows=dict(sorted(reason_rows.items())),
            current_active_filter_used=False,
            current_delisted_filter_used=False,
            current_route_filter_used=False,
            ticker_text_splicing_used=False,
            authoritative_interval_rows=int(status_rows[AUTHORITATIVE_INTERVAL]),
            unique_reference_no_reuse_rows=int(status_rows[UNIQUE_REFERENCE_NO_REUSE]),
            unresolved_ticker_reuse_rows=int(status_rows[UNRESOLVED_TICKER_REUSE]),
            unresolved_multi_reference_rows=int(status_rows[UNRESOLVED_MULTI_REFERENCE]),
            unresolved_fallback_identity_rows=int(status_rows[UNRESOLVED_FALLBACK_IDENTITY]),
            unresolved_metadata_conflict_rows=int(status_rows[UNRESOLVED_METADATA_CONFLICT]),
            unmapped_reference_rows=int(status_rows[UNMAPPED_REFERENCE]),
            annual_evidence=annual_evidence,
            historical_identity_policy_locked=False,
            prediction_label_policy_locked=False,
            report_path=str(target),
        )
        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
