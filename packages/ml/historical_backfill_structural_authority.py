from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_identity import AlpacaBackfillIdentityBuilder
from packages.data.alpaca_backfill_identity_asset_risk import (
    ALPACA_BACKFILL_IDENTITY_ASSET_RISK_CONTRACT_VERSION,
    AlpacaBackfillIdentityAssetRiskBuilder,
)
from packages.data.alpaca_backfill_identity_segments_policy import (
    ALPACA_BACKFILL_IDENTITY_SEGMENT_POLICY_CONTRACT_VERSION,
    AlpacaBackfillIdentitySegmentPolicyBuilder,
)
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.features.partition_store import sha256_file
from packages.ml.feature_policy import ML_PRODUCTION_CORE_FEATURE_NAMES
from packages.ml.historical_backfill_long_history_preflight import (
    GATE11_LONG_HISTORY_ORIGIN_DATE,
    GATE11_LONG_HISTORY_PREFLIGHT_CONTRACT_VERSION,
    GATE11_PRESEAM_END_DATE,
)
from packages.ml.label_policy import (
    ML_PREDICTION_LABEL_HORIZON_SESSIONS,
    ML_PREDICTION_LABEL_THRESHOLD_MULTIPLIER,
)
from packages.ml.universe_probe import ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS
from packages.regimes.split_origin_state_engine import SplitOriginRegimeStateEngine
from packages.universe.eligibility import (
    ACTIVE_UNIVERSE_ELIGIBILITY_POLICY,
    UNIVERSE_ELIGIBILITY_POLICY_VERSION,
)


GATE11B_STRUCTURAL_AUTHORITY_CONTRACT_VERSION = (
    "historical-backfill-ml-structural-authority-v1-stable-reference-chain-propagation"
)
GATE11B_AUTHORITY_ARTIFACT_CONTRACT_VERSION = (
    "historical-backfill-ml-chain-authority-v1-gate4-chain-stable-structural-metadata"
)
GATE11B_ACCEPTED_GATE11A_SOURCE_FINGERPRINT = (
    "fd1ec38495115a72f16d3a1d53bddfca48b7a2972b25ee502054072564e9ad3a"
)
GATE11B_ACCEPTED_GATE11A_USABLE_ROWS = 6_864_471
GATE11B_REFERENCE_SCOPE = "ALL_RETAINED_MASSIVE_REFERENCE_SNAPSHOTS"
GATE11B_HISTORICAL_IDENTITY_ID = "alpaca-gate4-chain:<identity_chain_id>"
GATE11B_CURRENT_ACTIVE_FILTER_USED = False
GATE11B_CURRENT_DELISTED_FILTER_USED = False
GATE11B_PRESEAM_POINT_IN_TIME_MEMBERSHIP_CLAIMED = False
GATE11B_PRODUCTION_ML_WRITES = 0

AUTH_ELIGIBLE = "ELIGIBLE_STABLE_STRUCTURAL_REFERENCE"
AUTH_INELIGIBLE = "INELIGIBLE_STABLE_STRUCTURAL_REFERENCE"
AUTH_NO_METADATA = "QUARANTINE_NO_STABLE_STRUCTURAL_METADATA"
AUTH_CONFLICT = "QUARANTINE_CONFLICTING_STRUCTURAL_METADATA"
AUTH_IDENTITY_AMBIGUOUS = "QUARANTINE_GATE4_IDENTITY_AMBIGUOUS"


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def normalize_structural_metadata(
    *,
    market: object,
    locale: object,
    primary_exchange: object,
    security_type: object,
) -> tuple[str, str, str, str] | None:
    values = (
        str(market or "").strip().lower(),
        str(locale or "").strip().lower(),
        str(primary_exchange or "").strip().upper(),
        str(security_type or "").strip().upper(),
    )
    if not all(values):
        return None
    return values


def structural_metadata_reasons(metadata: tuple[str, str, str, str] | None) -> tuple[str, ...]:
    if metadata is None:
        return ("MISSING_REFERENCE_METADATA",)
    market, locale, exchange, security_type = metadata
    policy = ACTIVE_UNIVERSE_ELIGIBILITY_POLICY
    reasons: list[str] = []
    if market not in {item.lower() for item in policy.allowed_markets}:
        reasons.append("UNSUPPORTED_MARKET")
    if locale not in {item.lower() for item in policy.allowed_locales}:
        reasons.append("NON_US_LOCALE")
    if exchange not in set(policy.allowed_exchanges):
        reasons.append("UNSUPPORTED_EXCHANGE")
    if security_type not in set(policy.allowed_security_types):
        reasons.append("UNSUPPORTED_SECURITY_TYPE")
    return tuple(sorted(reasons))


def classify_chain_structural_authority(
    *,
    identity_ambiguous: bool,
    metadata_candidates: Iterable[tuple[str, str, str, str]],
) -> tuple[str, bool, tuple[str, str, str, str] | None, tuple[str, ...]]:
    """Classify one Gate-4 identity chain without consulting current status fields."""

    if identity_ambiguous:
        return AUTH_IDENTITY_AMBIGUOUS, False, None, ("GATE4_IDENTITY_AMBIGUOUS",)
    unique = sorted(set(metadata_candidates))
    if not unique:
        return AUTH_NO_METADATA, False, None, ("NO_STABLE_STRUCTURAL_METADATA",)
    if len(unique) > 1:
        return AUTH_CONFLICT, False, None, ("CONFLICTING_STRUCTURAL_METADATA",)
    metadata = unique[0]
    reasons = structural_metadata_reasons(metadata)
    if reasons:
        return AUTH_INELIGIBLE, False, metadata, reasons
    return AUTH_ELIGIBLE, True, metadata, ()


class HistoricalBackfillStructuralAuthorityAudit:
    """Gate 11-B structural authority reconciliation for the pre-Massive ML extension.

    The audit intentionally does not claim that a 2026 reference row existed in 2016.
    It uses only structural metadata that is stable across every retained Massive
    reference observation of one exact ticker identity, then permits propagation to
    another pre-seam ticker only through an already accepted Gate-4 identity chain.
    Current active/delisted state is never an eligibility input.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.identity = AlpacaBackfillIdentityBuilder(settings)
        self.segment_policy = AlpacaBackfillIdentitySegmentPolicyBuilder(settings)
        self.asset_risk = AlpacaBackfillIdentityAssetRiskBuilder(settings)
        self.market_engine = SplitOriginRegimeStateEngine(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.long_root = derived / "historical_backfill" / "alpaca" / "ml_long_history" / "v1"
        self.gate11a_report_path = self.long_root / "gate11a_preflight_report.json"
        self.root = self.long_root / "structural_authority" / "v1"
        self.authority_path = self.root / "gate11b_chain_authority.parquet"
        self.report_path = self.root / "gate11b_structural_authority_report.json"

    @staticmethod
    def _read_json(path: Path, label: str) -> dict[str, Any]:
        if not path.is_file():
            raise RuntimeError(f"Gate 11-B requires {label}: {path}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Gate 11-B invalid JSON for {label}: {path}") from exc

    def _reference_files(self) -> list[Path]:
        root = (
            self.settings.resolved_path(self.settings.data.paths.canonical)
            / "reference"
            / "massive"
            / "tickers"
        )
        files = sorted(root.glob("date=*/*.parquet"))
        if not files:
            raise RuntimeError("Gate 11-B retained Massive reference corpus is empty")
        return files

    def _reference_fingerprint(self, files: list[Path]) -> str:
        entries = [
            {
                "as_of_date": path.parent.name.split("=", 1)[1],
                "sha256": sha256_file(path),
            }
            for path in files
        ]
        return _stable_hash(entries)

    @staticmethod
    def _list_value(value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, tuple):
            return [str(item) for item in value]
        try:
            if pd.isna(value):
                return []
        except (TypeError, ValueError):
            pass
        return [str(value)]

    def _write_authority(self, rows: list[dict[str, object]]) -> str:
        if not rows:
            raise RuntimeError("Gate 11-B produced no chain authority rows")
        frame = pd.DataFrame(rows)
        self.authority_path.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(self.authority_path)
        temp.unlink(missing_ok=True)
        con = connect_utc(":memory:")
        try:
            con.register("gate11b_authority", frame)
            con.execute(
                f"""
                COPY (
                    SELECT * FROM gate11b_authority ORDER BY identity_chain_id
                ) TO {sql_string(temp)}
                (FORMAT PARQUET, COMPRESSION ZSTD)
                """
            )
        finally:
            con.close()
        promote(temp, self.authority_path)
        return sha256_file(self.authority_path)

    def _chain_authority(
        self,
        con: Any,
        *,
        segment_path: Path,
    ) -> tuple[list[dict[str, object]], dict[str, object]]:
        reference_glob = self.paths.reference_snapshot_glob()
        con.execute(
            f"""
            CREATE TEMP VIEW gate11b_reference AS
            SELECT
                trim(CAST(ticker AS VARCHAR)) AS ticker,
                CAST(instrument_id AS VARCHAR) AS instrument_id,
                lower(trim(CAST(identity_quality AS VARCHAR))) AS identity_quality,
                lower(trim(CAST(market AS VARCHAR))) AS market,
                lower(trim(CAST(locale AS VARCHAR))) AS locale,
                upper(trim(CAST(primary_exchange AS VARCHAR))) AS primary_exchange,
                upper(trim(CAST(security_type AS VARCHAR))) AS security_type,
                CAST(as_of_date AS DATE) AS as_of_date
            FROM read_parquet(
                {sql_string(reference_glob)},
                union_by_name=true,
                hive_partitioning=false
            )
            WHERE ticker IS NOT NULL AND trim(CAST(ticker AS VARCHAR)) <> ''
            """
        )
        reference_stats = con.execute(
            f"""
            SELECT
                count(*), count(DISTINCT as_of_date), min(as_of_date), max(as_of_date),
                count(*) FILTER (WHERE as_of_date <= DATE '{GATE11_PRESEAM_END_DATE}'),
                count(DISTINCT as_of_date) FILTER (WHERE as_of_date <= DATE '{GATE11_PRESEAM_END_DATE}')
            FROM gate11b_reference
            """
        ).fetchone()

        complete = (
            "market IS NOT NULL AND market <> '' "
            "AND locale IS NOT NULL AND locale <> '' "
            "AND primary_exchange IS NOT NULL AND primary_exchange <> '' "
            "AND security_type IS NOT NULL AND security_type <> ''"
        )
        metadata_tuple = (
            "market || '|' || locale || '|' || primary_exchange || '|' || security_type"
        )
        con.execute(
            f"""
            CREATE TEMP TABLE gate11b_symbol_reference AS
            SELECT
                ticker,
                count(*) AS reference_rows,
                count(DISTINCT as_of_date) AS snapshot_count,
                count(DISTINCT instrument_id) AS instrument_id_count,
                count(*) FILTER (WHERE identity_quality NOT IN ('strong','medium'))
                    AS unsupported_quality_rows,
                count(*) FILTER (WHERE NOT ({complete})) AS missing_metadata_rows,
                count(DISTINCT CASE WHEN {complete} THEN {metadata_tuple} ELSE NULL END)
                    AS metadata_tuple_count,
                min(instrument_id) AS representative_instrument_id,
                min(market) FILTER (WHERE {complete}) AS market,
                min(locale) FILTER (WHERE {complete}) AS locale,
                min(primary_exchange) FILTER (WHERE {complete}) AS primary_exchange,
                min(security_type) FILTER (WHERE {complete}) AS security_type
            FROM gate11b_reference
            GROUP BY ticker
            """
        )
        con.execute(
            f"""
            CREATE TEMP VIEW gate11b_stable_reference AS
            SELECT *,
                (
                    instrument_id_count = 1
                    AND unsupported_quality_rows = 0
                    AND missing_metadata_rows = 0
                    AND metadata_tuple_count = 1
                ) AS stable_reference,
                CASE
                    WHEN metadata_tuple_count = 1
                    THEN market || '|' || locale || '|' || primary_exchange || '|' || security_type
                    ELSE NULL
                END AS metadata_tuple
            FROM gate11b_symbol_reference
            """
        )
        symbol_stats = con.execute(
            """
            SELECT
                count(*) AS symbols,
                count(*) FILTER (WHERE stable_reference) AS stable_symbols,
                count(*) FILTER (WHERE instrument_id_count > 1) AS reused_symbols,
                count(*) FILTER (WHERE missing_metadata_rows > 0) AS incomplete_symbols,
                count(*) FILTER (WHERE metadata_tuple_count > 1) AS conflicting_metadata_symbols
            FROM gate11b_stable_reference
            """
        ).fetchone()

        con.execute(
            f"""
            CREATE TEMP VIEW gate11b_segments AS
            SELECT
                CAST(identity_chain_id AS VARCHAR) AS identity_chain_id,
                CAST(segment_id AS VARCHAR) AS segment_id,
                CAST(symbol AS VARCHAR) AS symbol,
                CAST(chain_length AS BIGINT) AS chain_length,
                coalesce(CAST(identity_ambiguous AS BOOLEAN), FALSE) AS identity_ambiguous
            FROM read_parquet({sql_string(segment_path)})
            """
        )
        chain_rows = con.execute(
            """
            SELECT
                s.identity_chain_id,
                count(DISTINCT s.symbol) AS chain_members,
                max(CAST(s.identity_ambiguous AS INTEGER)) AS identity_ambiguous,
                count(DISTINCT s.symbol) FILTER (WHERE r.stable_reference) AS stable_source_members,
                count(DISTINCT r.metadata_tuple) FILTER (WHERE r.stable_reference)
                    AS stable_metadata_tuple_count,
                count(DISTINCT s.symbol) FILTER (WHERE coalesce(r.instrument_id_count,0) > 1)
                    AS reused_reference_members,
                count(DISTINCT s.symbol) FILTER (
                    WHERE r.ticker IS NOT NULL AND NOT r.stable_reference
                ) AS nonstable_reference_members,
                list_sort(list(DISTINCT s.symbol)) AS member_symbols,
                list_sort(list(DISTINCT s.symbol) FILTER (WHERE r.stable_reference))
                    AS metadata_source_symbols,
                list_sort(list(DISTINCT r.representative_instrument_id)
                    FILTER (WHERE r.stable_reference)) AS metadata_source_instrument_ids,
                min(r.market) FILTER (WHERE r.stable_reference) AS market,
                min(r.locale) FILTER (WHERE r.stable_reference) AS locale,
                min(r.primary_exchange) FILTER (WHERE r.stable_reference) AS primary_exchange,
                min(r.security_type) FILTER (WHERE r.stable_reference) AS security_type
            FROM gate11b_segments s
            LEFT JOIN gate11b_stable_reference r ON r.ticker=s.symbol
            GROUP BY s.identity_chain_id
            ORDER BY s.identity_chain_id
            """
        ).fetchall()
        columns = [item[0] for item in con.description]

        authority_rows: list[dict[str, object]] = []
        for values in chain_rows:
            row = dict(zip(columns, values, strict=True))
            candidates: list[tuple[str, str, str, str]] = []
            if int(row["stable_metadata_tuple_count"] or 0) == 1:
                normalized = normalize_structural_metadata(
                    market=row.get("market"),
                    locale=row.get("locale"),
                    primary_exchange=row.get("primary_exchange"),
                    security_type=row.get("security_type"),
                )
                if normalized is not None:
                    candidates.append(normalized)
            elif int(row["stable_metadata_tuple_count"] or 0) > 1:
                # The exact candidate values are intentionally represented as a conflict,
                # never collapsed through min()/max() into a synthetic tuple.
                candidates = [
                    ("__conflict_a__", "__conflict_a__", "__CONFLICT_A__", "__CONFLICT_A__"),
                    ("__conflict_b__", "__conflict_b__", "__CONFLICT_B__", "__CONFLICT_B__"),
                ]

            status, eligible, metadata, reasons = classify_chain_structural_authority(
                identity_ambiguous=bool(row["identity_ambiguous"]),
                metadata_candidates=candidates,
            )
            market = metadata[0] if metadata is not None else None
            locale = metadata[1] if metadata is not None else None
            exchange = metadata[2] if metadata is not None else None
            security_type = metadata[3] if metadata is not None else None
            source_symbols = self._list_value(row.get("metadata_source_symbols"))
            source_ids = self._list_value(row.get("metadata_source_instrument_ids"))
            member_symbols = self._list_value(row.get("member_symbols"))
            authority_rows.append(
                {
                    "artifact_contract_version": GATE11B_AUTHORITY_ARTIFACT_CONTRACT_VERSION,
                    "identity_chain_id": str(row["identity_chain_id"]),
                    "historical_instrument_id": f"alpaca-gate4-chain:{row['identity_chain_id']}",
                    "chain_members": int(row["chain_members"]),
                    "identity_ambiguous": bool(row["identity_ambiguous"]),
                    "stable_source_members": int(row["stable_source_members"]),
                    "stable_metadata_tuple_count": int(row["stable_metadata_tuple_count"]),
                    "reused_reference_members": int(row["reused_reference_members"]),
                    "nonstable_reference_members": int(row["nonstable_reference_members"]),
                    "member_symbols_json": json.dumps(member_symbols, separators=(",", ":")),
                    "metadata_source_symbols_json": json.dumps(source_symbols, separators=(",", ":")),
                    "metadata_source_instrument_ids_json": json.dumps(source_ids, separators=(",", ":")),
                    "market": market,
                    "locale": locale,
                    "primary_exchange": exchange,
                    "security_type": security_type,
                    "authority_status": status,
                    "structural_eligible": eligible,
                    "policy_reasons_json": json.dumps(list(reasons), separators=(",", ":")),
                    "reference_scope": GATE11B_REFERENCE_SCOPE,
                    "current_active_filter_used": False,
                    "current_delisted_filter_used": False,
                    "preseam_point_in_time_membership_claimed": False,
                }
            )

        stats = {
            "reference_rows": int(reference_stats[0]),
            "reference_snapshots": int(reference_stats[1]),
            "reference_first_snapshot": str(reference_stats[2]),
            "reference_last_snapshot": str(reference_stats[3]),
            "preseam_reference_rows": int(reference_stats[4]),
            "preseam_reference_snapshots": int(reference_stats[5]),
            "reference_symbols": int(symbol_stats[0]),
            "stable_reference_symbols": int(symbol_stats[1]),
            "reference_reused_symbols": int(symbol_stats[2]),
            "reference_incomplete_symbols": int(symbol_stats[3]),
            "reference_conflicting_metadata_symbols": int(symbol_stats[4]),
        }
        return authority_rows, stats

    def _population_evidence(
        self,
        con: Any,
        *,
        authority_rows: list[dict[str, object]],
        segment_path: Path,
        event_path: Path,
        end_date: date,
    ) -> dict[str, object]:
        frame = pd.DataFrame(authority_rows)
        con.register("gate11b_authority_input", frame)
        con.execute(
            """
            CREATE TEMP VIEW gate11b_authority AS
            SELECT
                CAST(identity_chain_id AS VARCHAR) AS identity_chain_id,
                CAST(historical_instrument_id AS VARCHAR) AS historical_instrument_id,
                CAST(authority_status AS VARCHAR) AS authority_status,
                CAST(structural_eligible AS BOOLEAN) AS structural_eligible
            FROM gate11b_authority_input
            """
        )

        bar_glob = self.paths.glob_for_timeframe(Timeframe.DAY_1)
        feature_glob = self.paths.feature_glob(Timeframe.DAY_1)
        complete = " AND ".join(
            f"f.{name} IS NOT NULL AND isfinite(CAST(f.{name} AS DOUBLE))"
            for name in ML_PRODUCTION_CORE_FEATURE_NAMES
        )
        con.execute(
            f"""
            CREATE TEMP VIEW gate11b_daily AS
            SELECT symbol, CAST(session_date AS DATE) AS session_date,
                   CAST(close AS DOUBLE) AS close, CAST(volume AS DOUBLE) AS volume,
                   CAST(provider AS VARCHAR) AS provider
            FROM read_parquet({sql_string(bar_glob)}, hive_partitioning=true)
            WHERE CAST(session_date AS DATE)
                BETWEEN DATE '{GATE11_LONG_HISTORY_ORIGIN_DATE}' AND DATE '{end_date}'
            """
        )
        con.execute(
            f"""
            CREATE TEMP VIEW gate11b_segments_population AS
            SELECT identity_chain_id, segment_id, symbol,
                   CAST(first_date AS DATE) AS first_date,
                   CAST(last_date AS DATE) AS last_date,
                   coalesce(CAST(identity_ambiguous AS BOOLEAN), FALSE) AS identity_ambiguous
            FROM read_parquet({sql_string(segment_path)})
            """
        )
        con.execute(
            f"""
            CREATE TEMP TABLE gate11b_candidates AS
            SELECT
                b.symbol, b.session_date, b.close, b.volume,
                s.identity_chain_id,
                CAST(f.natr_14 AS DOUBLE) AS natr_14
            FROM gate11b_daily b
            INNER JOIN gate11b_segments_population s
              ON s.symbol=b.symbol
             AND b.session_date BETWEEN s.first_date AND s.last_date
            INNER JOIN read_parquet(
                {sql_string(feature_glob)}, hive_partitioning=true, union_by_name=true
            ) f
              ON f.symbol=b.symbol
             AND CAST(f.timestamp_utc AS DATE)=b.session_date
            WHERE b.session_date BETWEEN DATE '{GATE11_LONG_HISTORY_ORIGIN_DATE}'
                                     AND DATE '{GATE11_PRESEAM_END_DATE}'
              AND b.provider='alpaca'
              AND NOT s.identity_ambiguous
              AND ({complete})
              AND b.close*b.volume >= {float(ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS):.17g}
              AND f.natr_14 IS NOT NULL
              AND isfinite(CAST(f.natr_14 AS DOUBLE))
              AND CAST(f.natr_14 AS DOUBLE) > 0
            """
        )
        con.execute(
            """
            CREATE TEMP TABLE gate11b_sessions AS
            SELECT session_date, row_number() OVER (ORDER BY session_date) AS session_seq
            FROM (SELECT DISTINCT session_date FROM gate11b_daily)
            """
        )
        con.execute(
            f"""
            CREATE TEMP VIEW gate11b_splits AS
            SELECT source_symbol AS symbol, try_cast(event_date AS DATE) AS event_date
            FROM read_parquet({sql_string(event_path)})
            WHERE event_type IN ('forward_splits','reverse_splits')
              AND source_symbol IS NOT NULL
              AND try_cast(event_date AS DATE) IS NOT NULL
              AND try_cast(event_date AS DATE) BETWEEN DATE '{GATE11_LONG_HISTORY_ORIGIN_DATE}'
                                                   AND DATE '{GATE11_PRESEAM_END_DATE}'
            """
        )
        horizon = int(ML_PREDICTION_LABEL_HORIZON_SESSIONS)
        con.execute(
            f"""
            CREATE TEMP TABLE gate11b_outcomes AS
            SELECT
                c.*,
                fs.session_date AS future_date,
                fb.close AS future_close,
                EXISTS (
                    SELECT 1 FROM gate11b_splits sp
                    WHERE sp.symbol=c.symbol
                      AND sp.event_date > c.session_date
                      AND sp.event_date <= fs.session_date
                ) AS split_crossing
            FROM gate11b_candidates c
            INNER JOIN gate11b_sessions s ON s.session_date=c.session_date
            LEFT JOIN gate11b_sessions fs ON fs.session_seq=s.session_seq+{horizon}
            LEFT JOIN gate11b_daily fb
              ON fb.symbol=c.symbol
             AND fb.session_date=fs.session_date
             AND fb.provider='alpaca'
            """
        )
        usable = (
            f"future_date <= DATE '{GATE11_PRESEAM_END_DATE}' "
            "AND future_close IS NOT NULL AND future_close > 0 AND NOT split_crossing"
        )
        con.execute(
            f"""
            CREATE TEMP VIEW gate11b_usable AS
            SELECT
                o.*,
                a.historical_instrument_id,
                a.authority_status,
                a.structural_eligible,
                coalesce(r.stable_reference, FALSE) AS exact_stable_reference
            FROM gate11b_outcomes o
            INNER JOIN gate11b_authority a USING (identity_chain_id)
            LEFT JOIN gate11b_stable_reference r ON r.ticker=o.symbol
            WHERE {usable}
            """
        )

        threshold_scale = float(ML_PREDICTION_LABEL_THRESHOLD_MULTIPLIER) * math.sqrt(
            float(ML_PREDICTION_LABEL_HORIZON_SESSIONS)
        )
        summary = con.execute(
            f"""
            SELECT
                count(*) AS usable_rows,
                count(*) FILTER (WHERE structural_eligible) AS eligible_rows,
                count(*) FILTER (WHERE NOT structural_eligible) AS excluded_rows,
                count(*) FILTER (WHERE structural_eligible AND exact_stable_reference)
                    AS exact_authority_rows,
                count(*) FILTER (WHERE structural_eligible AND NOT exact_stable_reference)
                    AS chain_propagated_rows,
                count(DISTINCT identity_chain_id) AS usable_chains,
                count(DISTINCT identity_chain_id) FILTER (WHERE structural_eligible)
                    AS eligible_chains,
                count(DISTINCT symbol) AS usable_symbols,
                count(DISTINCT symbol) FILTER (WHERE structural_eligible) AS eligible_symbols,
                count(*) FILTER (
                    WHERE structural_eligible
                      AND (future_close/close)-1.0 <= -(natr_14*{threshold_scale:.17g})
                ) AS down_rows,
                count(*) FILTER (
                    WHERE structural_eligible
                      AND (future_close/close)-1.0 > -(natr_14*{threshold_scale:.17g})
                      AND (future_close/close)-1.0 < (natr_14*{threshold_scale:.17g})
                ) AS neutral_rows,
                count(*) FILTER (
                    WHERE structural_eligible
                      AND (future_close/close)-1.0 >= (natr_14*{threshold_scale:.17g})
                ) AS up_rows,
                min(session_date) FILTER (WHERE structural_eligible) AS first_eligible,
                max(session_date) FILTER (WHERE structural_eligible) AS last_eligible
            FROM gate11b_usable
            """
        ).fetchone()
        status_rows = con.execute(
            """
            SELECT authority_status, count(*) AS rows, count(DISTINCT identity_chain_id) AS chains
            FROM gate11b_usable
            GROUP BY authority_status
            ORDER BY authority_status
            """
        ).fetchall()
        annual_rows = con.execute(
            f"""
            SELECT
                year(session_date) AS year,
                count(*) AS usable_rows,
                count(*) FILTER (WHERE structural_eligible) AS eligible_rows,
                count(*) FILTER (
                    WHERE structural_eligible
                      AND (future_close/close)-1.0 <= -(natr_14*{threshold_scale:.17g})
                ) AS down_rows,
                count(*) FILTER (
                    WHERE structural_eligible
                      AND (future_close/close)-1.0 > -(natr_14*{threshold_scale:.17g})
                      AND (future_close/close)-1.0 < (natr_14*{threshold_scale:.17g})
                ) AS neutral_rows,
                count(*) FILTER (
                    WHERE structural_eligible
                      AND (future_close/close)-1.0 >= (natr_14*{threshold_scale:.17g})
                ) AS up_rows
            FROM gate11b_usable
            GROUP BY year(session_date)
            ORDER BY year
            """
        ).fetchall()

        market_history = self.market_engine.history_paths(end_date)["market_effective"]
        if not market_history.is_file():
            raise RuntimeError(f"Gate 11-B market history is missing: {market_history}")
        context_rows = int(
            con.execute(
                f"""
                SELECT count(*)
                FROM gate11b_usable u
                INNER JOIN read_parquet({sql_string(market_history)}) m
                  ON CAST(m.trading_date AS DATE)=u.session_date
                WHERE u.structural_eligible
                """
            ).fetchone()[0]
        )

        eligible = int(summary[1])
        return {
            "usable_rows": int(summary[0]),
            "eligible_rows": eligible,
            "excluded_rows": int(summary[2]),
            "eligible_fraction": 0.0 if int(summary[0]) <= 0 else eligible / int(summary[0]),
            "exact_authority_rows": int(summary[3]),
            "chain_propagated_rows": int(summary[4]),
            "usable_chains": int(summary[5]),
            "eligible_chains": int(summary[6]),
            "usable_symbols": int(summary[7]),
            "eligible_symbols": int(summary[8]),
            "class_rows": {
                "DOWN": int(summary[9]),
                "NEUTRAL": int(summary[10]),
                "UP": int(summary[11]),
            },
            "first_eligible_session": str(summary[12]),
            "last_eligible_session": str(summary[13]),
            "market_context_rows": context_rows,
            "market_context_fraction": 0.0 if eligible <= 0 else context_rows / eligible,
            "authority_status_rows": {
                str(status): {"rows": int(rows), "chains": int(chains)}
                for status, rows, chains in status_rows
            },
            "annual_evidence": [
                {
                    "year": int(year),
                    "usable_rows": int(usable_rows),
                    "eligible_rows": int(eligible_rows),
                    "class_rows": {
                        "DOWN": int(down_rows),
                        "NEUTRAL": int(neutral_rows),
                        "UP": int(up_rows),
                    },
                }
                for year, usable_rows, eligible_rows, down_rows, neutral_rows, up_rows in annual_rows
            ],
            "market_history_sha256": sha256_file(market_history),
        }

    def run(self) -> dict[str, object]:
        gate11a = self._read_json(self.gate11a_report_path, "accepted Gate 11-A report")
        if gate11a.get("contract_version") != GATE11_LONG_HISTORY_PREFLIGHT_CONTRACT_VERSION:
            raise RuntimeError("Gate 11-B Gate 11-A contract mismatch")
        if gate11a.get("source_fingerprint") != GATE11B_ACCEPTED_GATE11A_SOURCE_FINGERPRINT:
            raise RuntimeError("Gate 11-B refuses an unaccepted Gate 11-A source fingerprint")
        if gate11a.get("pass") is not True:
            raise RuntimeError("Gate 11-B requires a passing Gate 11-A report")

        segment_report = self._read_json(
            self.segment_policy.base.report_path,
            "Gate 4-C v2 identity segment report",
        )
        asset_report = self._read_json(
            self.asset_risk.report_path,
            "Gate 4-D asset-risk identity report",
        )
        if segment_report.get("contract_version") != ALPACA_BACKFILL_IDENTITY_SEGMENT_POLICY_CONTRACT_VERSION:
            raise RuntimeError("Gate 11-B requires the Gate 4-C v2 identity segment contract")
        if asset_report.get("contract_version") != ALPACA_BACKFILL_IDENTITY_ASSET_RISK_CONTRACT_VERSION:
            raise RuntimeError("Gate 11-B requires the Gate 4-D non-retroactive asset-risk contract")
        if asset_report.get("historical_chain_structure_unchanged") is not True:
            raise RuntimeError("Gate 11-B Gate 4-D chain structure is not locked")

        segment_path = self.segment_policy.base.segment_path
        event_path = self.identity.event_ledger_path
        if not segment_path.is_file() or not event_path.is_file():
            raise RuntimeError("Gate 11-B identity/corporate-action evidence is missing")

        reference_files = self._reference_files()
        reference_fingerprint = self._reference_fingerprint(reference_files)
        end_date = date.fromisoformat(str(gate11a["as_of_date"]))

        con = connect_utc(":memory:")
        try:
            con.execute("SET preserve_insertion_order=false")
            authority_rows, reference_stats = self._chain_authority(
                con,
                segment_path=segment_path,
            )
            population = self._population_evidence(
                con,
                authority_rows=authority_rows,
                segment_path=segment_path,
                event_path=event_path,
                end_date=end_date,
            )
        finally:
            con.close()

        authority_semantic_fingerprint = _stable_hash(authority_rows)
        authority_sha = self._write_authority(authority_rows)
        authority_counts: dict[str, int] = {}
        for row in authority_rows:
            status = str(row["authority_status"])
            authority_counts[status] = authority_counts.get(status, 0) + 1
        eligible_chain_rows = sum(1 for row in authority_rows if bool(row["structural_eligible"]))

        checks = {
            "gate11a_contract_current": gate11a.get("contract_version")
            == GATE11_LONG_HISTORY_PREFLIGHT_CONTRACT_VERSION,
            "gate11a_source_fingerprint_accepted": gate11a.get("source_fingerprint")
            == GATE11B_ACCEPTED_GATE11A_SOURCE_FINGERPRINT,
            "gate11a_pass": gate11a.get("pass") is True,
            "gate4_v2_identity_segments_current": segment_report.get("contract_version")
            == ALPACA_BACKFILL_IDENTITY_SEGMENT_POLICY_CONTRACT_VERSION,
            "gate4d_asset_state_remains_nonretroactive": (
                asset_report.get("contract_version") == ALPACA_BACKFILL_IDENTITY_ASSET_RISK_CONTRACT_VERSION
                and asset_report.get("historical_identity_effect") == "NO_RETROACTIVE_IDENTITY_SEGMENTATION"
            ),
            "reference_corpus_nonempty": int(reference_stats["reference_rows"]) > 0,
            "authority_chain_coverage_exact": len(authority_rows)
            == int(segment_report.get("identity_chains", -1)),
            "authority_chain_ids_unique": len({str(row["identity_chain_id"]) for row in authority_rows})
            == len(authority_rows),
            "current_active_filter_unused": GATE11B_CURRENT_ACTIVE_FILTER_USED is False,
            "current_delisted_filter_unused": GATE11B_CURRENT_DELISTED_FILTER_USED is False,
            "preseam_point_in_time_membership_not_claimed": (
                GATE11B_PRESEAM_POINT_IN_TIME_MEMBERSHIP_CLAIMED is False
            ),
            "gate11a_usable_population_reconciled": int(population["usable_rows"])
            == GATE11B_ACCEPTED_GATE11A_USABLE_ROWS,
            "eligible_population_nonempty": int(population["eligible_rows"]) > 0,
            "eligible_authority_mode_accounting_exact": (
                int(population["eligible_rows"])
                == int(population["exact_authority_rows"])
                + int(population["chain_propagated_rows"])
            ),
            "eligible_class_accounting_exact": int(population["eligible_rows"])
            == sum(int(value) for value in dict(population["class_rows"]).values()),
            "usable_authority_status_accounting_exact": int(population["usable_rows"])
            == sum(
                int(item["rows"])
                for item in dict(population["authority_status_rows"]).values()
            ),
            "authority_artifact_written": self.authority_path.is_file(),
            "production_ml_writes_zero": GATE11B_PRODUCTION_ML_WRITES == 0,
        }

        fingerprint_payload = {
            "contract_version": GATE11B_STRUCTURAL_AUTHORITY_CONTRACT_VERSION,
            "authority_artifact_contract": GATE11B_AUTHORITY_ARTIFACT_CONTRACT_VERSION,
            "gate11a_source_fingerprint": GATE11B_ACCEPTED_GATE11A_SOURCE_FINGERPRINT,
            "gate11a_usable_rows": GATE11B_ACCEPTED_GATE11A_USABLE_ROWS,
            "reference_scope": GATE11B_REFERENCE_SCOPE,
            "reference_corpus_fingerprint": reference_fingerprint,
            "identity_segment_sha256": sha256_file(segment_path),
            "corporate_action_event_sha256": sha256_file(event_path),
            "universe_eligibility_policy": UNIVERSE_ELIGIBILITY_POLICY_VERSION,
            "universe_eligibility_policy_fingerprint": ACTIVE_UNIVERSE_ELIGIBILITY_POLICY.fingerprint,
            "core_feature_registry_fingerprint": CORE_FEATURE_REGISTRY.fingerprint(),
            "current_active_filter_used": GATE11B_CURRENT_ACTIVE_FILTER_USED,
            "current_delisted_filter_used": GATE11B_CURRENT_DELISTED_FILTER_USED,
            "preseam_point_in_time_membership_claimed": GATE11B_PRESEAM_POINT_IN_TIME_MEMBERSHIP_CLAIMED,
            "authority_semantic_fingerprint": authority_semantic_fingerprint,
            "authority_counts": authority_counts,
            "reference_stats": reference_stats,
            "population": population,
        }
        source_fingerprint = _stable_hash(fingerprint_payload)
        report: dict[str, object] = {
            "contract_version": GATE11B_STRUCTURAL_AUTHORITY_CONTRACT_VERSION,
            "authority_artifact_contract_version": GATE11B_AUTHORITY_ARTIFACT_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "as_of_date": end_date.isoformat(),
            "source_fingerprint": source_fingerprint,
            "fingerprint_scope": "CONTENT_ONLY_NO_ABSOLUTE_PATHS",
            "gate11a_source_fingerprint": GATE11B_ACCEPTED_GATE11A_SOURCE_FINGERPRINT,
            "reference_scope": GATE11B_REFERENCE_SCOPE,
            "reference_corpus_fingerprint": reference_fingerprint,
            "reference": reference_stats,
            "authority": {
                "chains": len(authority_rows),
                "eligible_chains": eligible_chain_rows,
                "status_counts": dict(sorted(authority_counts.items())),
                "semantic_fingerprint": authority_semantic_fingerprint,
                "artifact_sha256": authority_sha,
                "artifact_path": str(self.authority_path.resolve()),
                "historical_identity_id_contract": GATE11B_HISTORICAL_IDENTITY_ID,
            },
            "population": population,
            "policy": {
                "universe_eligibility_policy": UNIVERSE_ELIGIBILITY_POLICY_VERSION,
                "universe_eligibility_policy_fingerprint": ACTIVE_UNIVERSE_ELIGIBILITY_POLICY.fingerprint,
                "current_active_filter_used": GATE11B_CURRENT_ACTIVE_FILTER_USED,
                "current_delisted_filter_used": GATE11B_CURRENT_DELISTED_FILTER_USED,
                "preseam_point_in_time_membership_claimed": GATE11B_PRESEAM_POINT_IN_TIME_MEMBERSHIP_CLAIMED,
                "stable_reference_definition": (
                    "ONE_EXACT_MASSIVE_INSTRUMENT_ID + STRONG_OR_MEDIUM_IDENTITY + "
                    "COMPLETE_UNCHANGED_STRUCTURAL_METADATA_ACROSS_ALL_RETAINED_SNAPSHOTS"
                ),
                "chain_propagation_rule": (
                    "ONLY_ACROSS_ACCEPTED_GATE4_IDENTITY_CHAIN_AND_ONLY_IF_ALL_STABLE_"
                    "STRUCTURAL_METADATA_SOURCES_AGREE"
                ),
                "unknown_or_conflicting_metadata_policy": "QUARANTINE_NOT_GUESS",
            },
            "checks": checks,
            "production_ml_writes": GATE11B_PRODUCTION_ML_WRITES,
            "pass": all(bool(value) for value in checks.values()),
            "report_path": str(self.report_path.resolve()),
        }
        atomic_write_text(
            self.report_path,
            json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        )
        return report
