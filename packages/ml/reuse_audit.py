from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.ml.identity_probe import MLHistoricalIdentityProbe, UNRESOLVED_TICKER_REUSE


ML_TICKER_REUSE_AUDIT_CONTRACT_VERSION = (
    "ml-ticker-reuse-audit-v1-stable-vs-weak-identity-authority-enrichment"
)

MULTI_STABLE_IDENTITIES = "MULTI_STABLE_IDENTITIES"
ONE_STABLE_PLUS_WEAK = "ONE_STABLE_PLUS_WEAK"
WEAK_IDENTITIES_ONLY = "WEAK_IDENTITIES_ONLY"


@dataclass(frozen=True, slots=True)
class ReuseCompositionEvidence:
    category: str
    candidate_rows: int
    candidate_symbols: int
    current_single_stable_reference_symbols: int
    current_composite_figi_symbols: int
    any_authoritative_interval_symbols: int


@dataclass(frozen=True, slots=True)
class MLTickerReuseAuditReport:
    contract_version: str
    generated_at_utc: str
    history_end: str
    wall_seconds: float
    unresolved_reuse_rows: int
    unresolved_reuse_symbols: int
    observed_identity_count_max: int
    stable_identity_count_max: int
    composition: tuple[ReuseCompositionEvidence, ...]
    one_stable_plus_weak_rows: int
    one_stable_plus_weak_symbols: int
    one_stable_plus_weak_current_composite_figi_symbols: int
    one_stable_plus_weak_any_authoritative_interval_symbols: int
    multi_stable_rows: int
    multi_stable_symbols: int
    weak_only_rows: int
    weak_only_symbols: int
    current_composite_figi_reuse_symbols: int
    any_authoritative_interval_reuse_symbols: int
    recoverable_without_date_bounded_authority: bool
    ticker_text_splicing_allowed: bool
    historical_identity_policy_locked: bool
    report_path: str


def reuse_composition_category(stable_identity_count: int, observed_identity_count: int) -> str:
    if stable_identity_count >= 2:
        return MULTI_STABLE_IDENTITIES
    if stable_identity_count == 1 and observed_identity_count >= 2:
        return ONE_STABLE_PLUS_WEAK
    return WEAK_IDENTITIES_ONLY


class MLTickerReuseAudit:
    """Diagnose Gate 2 reuse blocks without weakening identity safety.

    Phase 7 fallback identities are intentionally date-scoped. Therefore a ticker
    can appear to have multiple historical instrument IDs even when only one strong
    or medium stable identity was ever observed. This audit measures that composition
    and the amount of provider-authoritative evidence available for possible recovery.

    It does not make sparse observation spans authoritative, does not splice ticker
    text, and never marks a blocked row safe. Only a future date-bounded authoritative
    interval may recover an unresolved reuse observation.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.identity_probe = MLHistoricalIdentityProbe(settings)

    def report_path(self, end_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "ml" / "ticker_reuse_audit" / f"{end_date.year:04d}" / f"{end_date}.json"

    def _prepare_views(self, con: Any, end_date: date) -> None:
        paths = self.identity_probe._required_paths(end_date)
        self.identity_probe._prepare_views(con, end_date, paths)

        registry = self.paths.instrument_registry_file()
        if not registry.is_file():
            raise FileNotFoundError(f"Instrument registry is missing: {registry}")
        observations = self.paths.ticker_observations_file()
        reference = self.paths.reference_snapshot_file(end_date)

        con.execute(
            f"""
            CREATE TEMP VIEW ml_reuse_candidates AS
            SELECT symbol, session_date
            FROM ml_identity_evidence
            WHERE identity_status = '{UNRESOLVED_TICKER_REUSE}'
            """
        )
        con.execute(
            f"""
            CREATE TEMP VIEW ml_reuse_identity_composition AS
            SELECT
                o.ticker,
                count(DISTINCT o.instrument_id) AS observed_identity_count,
                count(DISTINCT o.instrument_id) FILTER (
                    WHERE lower(coalesce(r.identity_quality, '')) IN ('strong', 'medium')
                ) AS stable_identity_count,
                count(DISTINCT o.instrument_id) FILTER (
                    WHERE lower(coalesce(r.identity_quality, '')) = 'fallback'
                ) AS fallback_identity_count
            FROM read_parquet({sql_string(observations)}) o
            LEFT JOIN read_parquet({sql_string(registry)}) r USING (instrument_id)
            GROUP BY o.ticker
            """
        )
        con.execute(
            f"""
            CREATE TEMP VIEW ml_reuse_current_reference AS
            SELECT
                ticker,
                count(DISTINCT instrument_id) AS reference_identity_count,
                count(DISTINCT instrument_id) FILTER (
                    WHERE lower(coalesce(identity_quality, '')) IN ('strong', 'medium')
                ) AS stable_reference_identity_count,
                count(DISTINCT composite_figi) FILTER (
                    WHERE composite_figi IS NOT NULL AND trim(composite_figi) <> ''
                ) AS composite_figi_count
            FROM read_parquet({sql_string(reference)})
            GROUP BY ticker
            """
        )

        intervals = self.paths.authoritative_ticker_intervals_file()
        if intervals.is_file():
            con.execute(
                f"""
                CREATE TEMP VIEW ml_reuse_authority AS
                SELECT
                    ticker,
                    count(*) AS interval_count,
                    count(DISTINCT instrument_id) AS interval_identity_count
                FROM read_parquet({sql_string(intervals)})
                WHERE coalesce(continuity_authority, TRUE)
                GROUP BY ticker
                """
            )
        else:
            con.execute(
                """
                CREATE TEMP VIEW ml_reuse_authority AS
                SELECT
                    CAST(NULL AS VARCHAR) AS ticker,
                    0::BIGINT AS interval_count,
                    0::BIGINT AS interval_identity_count
                WHERE FALSE
                """
            )

        con.execute(
            """
            CREATE TEMP VIEW ml_reuse_symbol_evidence AS
            SELECT
                c.symbol,
                count(*) AS candidate_rows,
                coalesce(i.observed_identity_count, 0) AS observed_identity_count,
                coalesce(i.stable_identity_count, 0) AS stable_identity_count,
                coalesce(i.fallback_identity_count, 0) AS fallback_identity_count,
                coalesce(r.reference_identity_count, 0) AS reference_identity_count,
                coalesce(r.stable_reference_identity_count, 0) AS stable_reference_identity_count,
                coalesce(r.composite_figi_count, 0) AS composite_figi_count,
                coalesce(a.interval_count, 0) AS interval_count,
                CASE
                    WHEN coalesce(i.stable_identity_count, 0) >= 2
                        THEN 'MULTI_STABLE_IDENTITIES'
                    WHEN coalesce(i.stable_identity_count, 0) = 1
                         AND coalesce(i.observed_identity_count, 0) >= 2
                        THEN 'ONE_STABLE_PLUS_WEAK'
                    ELSE 'WEAK_IDENTITIES_ONLY'
                END AS composition_category
            FROM ml_reuse_candidates c
            LEFT JOIN ml_reuse_identity_composition i ON i.ticker = c.symbol
            LEFT JOIN ml_reuse_current_reference r ON r.ticker = c.symbol
            LEFT JOIN ml_reuse_authority a ON a.ticker = c.symbol
            GROUP BY ALL
            """
        )

    def run(self, end_date: date) -> MLTickerReuseAuditReport:
        started = perf_counter()
        con = connect_utc(":memory:")
        try:
            self._prepare_views(con, end_date)
            overall = con.execute(
                """
                SELECT
                    coalesce(sum(candidate_rows), 0),
                    count(*),
                    coalesce(max(observed_identity_count), 0),
                    coalesce(max(stable_identity_count), 0),
                    count(*) FILTER (WHERE composite_figi_count > 0),
                    count(*) FILTER (WHERE interval_count > 0)
                FROM ml_reuse_symbol_evidence
                """
            ).fetchone()
            rows = con.execute(
                """
                SELECT
                    composition_category,
                    sum(candidate_rows),
                    count(*),
                    count(*) FILTER (WHERE stable_reference_identity_count = 1),
                    count(*) FILTER (WHERE composite_figi_count > 0),
                    count(*) FILTER (WHERE interval_count > 0)
                FROM ml_reuse_symbol_evidence
                GROUP BY 1
                ORDER BY 1
                """
            ).fetchall()
        finally:
            con.close()

        composition = tuple(
            ReuseCompositionEvidence(
                category=str(row[0]),
                candidate_rows=int(row[1]),
                candidate_symbols=int(row[2]),
                current_single_stable_reference_symbols=int(row[3]),
                current_composite_figi_symbols=int(row[4]),
                any_authoritative_interval_symbols=int(row[5]),
            )
            for row in rows
        )
        by_category = {item.category: item for item in composition}

        def item(category: str) -> ReuseCompositionEvidence:
            return by_category.get(
                category,
                ReuseCompositionEvidence(category, 0, 0, 0, 0, 0),
            )

        one_stable = item(ONE_STABLE_PLUS_WEAK)
        multi_stable = item(MULTI_STABLE_IDENTITIES)
        weak_only = item(WEAK_IDENTITIES_ONLY)
        target = self.report_path(end_date)
        report = MLTickerReuseAuditReport(
            contract_version=ML_TICKER_REUSE_AUDIT_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            history_end=end_date.isoformat(),
            wall_seconds=perf_counter() - started,
            unresolved_reuse_rows=int(overall[0]),
            unresolved_reuse_symbols=int(overall[1]),
            observed_identity_count_max=int(overall[2]),
            stable_identity_count_max=int(overall[3]),
            composition=composition,
            one_stable_plus_weak_rows=one_stable.candidate_rows,
            one_stable_plus_weak_symbols=one_stable.candidate_symbols,
            one_stable_plus_weak_current_composite_figi_symbols=one_stable.current_composite_figi_symbols,
            one_stable_plus_weak_any_authoritative_interval_symbols=one_stable.any_authoritative_interval_symbols,
            multi_stable_rows=multi_stable.candidate_rows,
            multi_stable_symbols=multi_stable.candidate_symbols,
            weak_only_rows=weak_only.candidate_rows,
            weak_only_symbols=weak_only.candidate_symbols,
            current_composite_figi_reuse_symbols=int(overall[4]),
            any_authoritative_interval_reuse_symbols=int(overall[5]),
            recoverable_without_date_bounded_authority=False,
            ticker_text_splicing_allowed=False,
            historical_identity_policy_locked=False,
            report_path=str(target),
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
