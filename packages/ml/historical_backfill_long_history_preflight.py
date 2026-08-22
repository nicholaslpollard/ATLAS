from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_identity import AlpacaBackfillIdentityBuilder
from packages.data.alpaca_backfill_identity_segments_policy import (
    ALPACA_BACKFILL_IDENTITY_SEGMENT_POLICY_CONTRACT_VERSION,
    AlpacaBackfillIdentitySegmentPolicyBuilder,
)
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.features.partition_store import FeaturePartitionManifest, sha256_file
from packages.ml.dataset_policy import (
    ML_TRAINING_DATASET_ACCEPTED_HISTORY_END,
    ML_TRAINING_DATASET_ACCEPTED_ID,
    ML_TRAINING_DATASET_ACCEPTED_LINEAGE_SHA256,
    ML_TRAINING_DATASET_ACCEPTED_ROWS,
)
from packages.ml.datasets import MLTrainingDatasetManifest, MLTrainingDatasetMaterializer
from packages.ml.feature_policy import ML_PRODUCTION_CORE_FEATURE_NAMES
from packages.ml.label_policy import (
    ML_PREDICTION_LABEL_HORIZON_SESSIONS,
    ML_PREDICTION_LABEL_THRESHOLD_MULTIPLIER,
)
from packages.ml.model_registry import ML_MODEL_REGISTRY_SPEC
from packages.ml.model_registry_policy import ML_MODEL_REGISTRY_ACCEPTED_MODEL_ID
from packages.ml.universe_probe import (
    ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS,
    ML_HISTORY_ORIGIN_DATE,
)
from packages.ml.walk_forward_policy import ML_WALK_FORWARD_FINAL_HOLDOUT_START
from packages.regimes.split_origin_state_engine import SplitOriginRegimeStateEngine


GATE11_LONG_HISTORY_PREFLIGHT_CONTRACT_VERSION = (
    "historical-backfill-ml-long-history-preflight-v1-three-way-lineage-controlled"
)
GATE11_LONG_HISTORY_COMPARISON_POLICY = (
    "gate11-three-way-a-frozen-phase10-b-new-lineage-2021-c-new-lineage-2016"
)
GATE11_LONG_HISTORY_ORIGIN_DATE = date(2016, 1, 4)
GATE11_PRESEAM_END_DATE = date(2021, 8, 13)
GATE11_INTRADAY_SYNTHESIS_ALLOWED = False
GATE11_ACCEPTED_MODEL_REPLACEMENT_ALLOWED = False
GATE11_FINAL_HOLDOUT_USED_FOR_SELECTION = False

OUTCOME_USABLE = "USABLE"
OUTCOME_PROVIDER_SEAM = "PROVIDER_SEAM_CENSORED"
OUTCOME_SAME_SYMBOL_MISSING = "SAME_SYMBOL_FUTURE_MISSING"
OUTCOME_SPLIT = "SPLIT_CENSORED"
OUTCOME_END = "END_OF_HISTORY_CENSORED"


class Gate11LongHistoryPreflightError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def classify_preseam_outcome(
    *,
    future_date: date | None,
    future_close_present: bool,
    split_crossing: bool,
) -> str:
    """Classify one projected pre-seam label window without crossing provider truth."""

    if future_date is None:
        return OUTCOME_END
    if future_date > GATE11_PRESEAM_END_DATE:
        return OUTCOME_PROVIDER_SEAM
    if not future_close_present:
        return OUTCOME_SAME_SYMBOL_MISSING
    if split_crossing:
        return OUTCOME_SPLIT
    return OUTCOME_USABLE


def three_way_comparison_contract() -> dict[str, object]:
    """Return the locked Gate 11 comparison roles.

    A remains the immutable accepted Phase 10 dataset/model. B rebases the same
    2021-origin ML policy onto the promoted long-warmup feature lineage. C adds safe
    pre-seam observations to the same new lineage. This separates feature-lineage
    effects from the marginal effect of older training history.
    """

    return {
        "policy": GATE11_LONG_HISTORY_COMPARISON_POLICY,
        "A": "FROZEN_ACCEPTED_PHASE10_DATASET_AND_MODEL",
        "B": "NEW_FEATURE_LINEAGE_PHASE10_ORIGIN_REBASE",
        "C": "NEW_FEATURE_LINEAGE_2016_HISTORY_EXTENSION",
        "A_to_B_effect": "FEATURE_LINEAGE_WARMUP_POPULATION_AND_LABEL_REBASE",
        "B_to_C_effect": "MARGINAL_PRE2021_HISTORY_AFTER_GATE11_STRUCTURAL_RECONCILIATION",
        "predictor_count": len(ML_PRODUCTION_CORE_FEATURE_NAMES),
        "label_horizon_sessions": ML_PREDICTION_LABEL_HORIZON_SESSIONS,
        "label_threshold_multiplier": ML_PREDICTION_LABEL_THRESHOLD_MULTIPLIER,
        "model_spec": dict(ML_MODEL_REGISTRY_SPEC),
        "final_holdout_used_for_model_selection": GATE11_FINAL_HOLDOUT_USED_FOR_SELECTION,
        "accepted_model_replacement_allowed_by_preflight": GATE11_ACCEPTED_MODEL_REPLACEMENT_ALLOWED,
        "synthetic_pre2021_intraday_allowed": GATE11_INTRADAY_SYNTHESIS_ALLOWED,
    }


class HistoricalBackfillLongHistoryMLPreflight:
    """Gate 11-A read-only feasibility proof for a separately versioned ML extension."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = MarketCalendar(exchange=settings.data.calendar.exchange)
        self.materializer = MLTrainingDatasetMaterializer(settings)
        self.identity = AlpacaBackfillIdentityBuilder(settings)
        self.segment_policy = AlpacaBackfillIdentitySegmentPolicyBuilder(settings)
        self.market_engine = SplitOriginRegimeStateEngine(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "historical_backfill" / "alpaca" / "ml_long_history" / "v1"
        self.report_path = self.root / "gate11a_preflight_report.json"
        self.gate9_validation_path = (
            derived
            / "historical_backfill"
            / "alpaca"
            / "feature_replay"
            / "v1"
            / "promotion"
            / "v1"
            / "gate9c_handoff_validation_report.json"
        )
        self.gate10_report_path = (
            derived
            / "historical_backfill"
            / "alpaca"
            / "regime_replay"
            / "v1"
            / "promotion"
            / "v1"
            / "gate10c_handoff_report.json"
        )
        self.gate10_validation_path = self.gate10_report_path.with_name(
            "gate10c_handoff_validation_report.json"
        )
        self.production_ml_write_count = 0

    @staticmethod
    def _read_json(path: Path, label: str) -> dict[str, Any]:
        if not Path(path).is_file():
            raise Gate11LongHistoryPreflightError(f"Gate 11-A requires {label}: {path}")
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise Gate11LongHistoryPreflightError(f"invalid JSON for {label}: {path}") from exc

    def _feature_lineage(self, start_date: date, end_date: date) -> dict[str, object]:
        entries: list[dict[str, object]] = []
        missing: list[str] = []
        sessions = self.calendar.sessions_in_range(start_date, end_date)
        for session in sessions:
            path = self.paths.feature_manifest_file(Timeframe.DAY_1, session)
            if not path.is_file():
                missing.append(str(path))
                continue
            payload = self._read_json(path, f"1d feature manifest {session}")
            manifest = FeaturePartitionManifest.from_dict(dict(payload))
            manifest.validate_contract(Timeframe.DAY_1, session)
            entries.append(
                {
                    "date": session.isoformat(),
                    "feature_sha256": manifest.feature_sha256,
                    "source_sha256": manifest.source_sha256,
                    "dependency_fingerprint": manifest.dependency_fingerprint,
                    "feature_contract_version": manifest.feature_contract_version,
                    "feature_registry_fingerprint": manifest.feature_registry_fingerprint,
                }
            )
        return {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "expected_sessions": len(sessions),
            "manifest_count": len(entries),
            "missing_count": len(missing),
            "missing_examples": missing[:10],
            "fingerprint": _stable_hash(entries),
        }

    def _accepted_phase10(self) -> dict[str, object]:
        dataset_root = self.materializer.dataset_parent() / ML_TRAINING_DATASET_ACCEPTED_ID
        manifest_path = self.materializer.manifest_path(dataset_root)
        payload = self._read_json(manifest_path, "accepted Phase 10 training dataset manifest")
        manifest = MLTrainingDatasetManifest.from_dict(dict(payload))
        if manifest.dataset_id != ML_TRAINING_DATASET_ACCEPTED_ID:
            raise Gate11LongHistoryPreflightError("accepted ML dataset id changed")
        if manifest.dataset_lineage_fingerprint != ML_TRAINING_DATASET_ACCEPTED_LINEAGE_SHA256:
            raise Gate11LongHistoryPreflightError("accepted ML dataset lineage changed")
        if manifest.row_count != ML_TRAINING_DATASET_ACCEPTED_ROWS:
            raise Gate11LongHistoryPreflightError("accepted ML dataset row count changed")

        partition_failures = 0
        for partition in manifest.partitions:
            path = dataset_root / partition.relative_path
            if not path.is_file() or sha256_file(path) != partition.sha256:
                partition_failures += 1

        derived = self.settings.resolved_path(self.settings.data.paths.derived)
        final_report_path = derived / "ml" / "final_acceptance" / "2026" / "2026-08-14.json"
        final_report = self._read_json(final_report_path, "accepted Phase 10 final acceptance report")
        registry_root = derived / "ml" / "model_registry" / ML_MODEL_REGISTRY_ACCEPTED_MODEL_ID
        model_path = registry_root / "final_fit" / "model.joblib"
        production_manifest_path = registry_root / "production_manifest.json"
        artifact = final_report.get("final_model_artifact")
        expected_model_sha = artifact.get("sha256") if isinstance(artifact, dict) else None
        model_hash_exact = bool(
            model_path.is_file()
            and expected_model_sha
            and sha256_file(model_path) == str(expected_model_sha)
        )

        return {
            "dataset_id": manifest.dataset_id,
            "dataset_lineage": manifest.dataset_lineage_fingerprint,
            "dataset_rows": manifest.row_count,
            "dataset_first_session": manifest.first_session_date,
            "dataset_last_session": manifest.last_session_date,
            "dataset_feature_lineage": manifest.feature_source_lineage_fingerprint,
            "dataset_manifest_path": str(manifest_path.resolve()),
            "dataset_manifest_sha256": sha256_file(manifest_path),
            "dataset_partition_hash_failures": partition_failures,
            "dataset_glob": (dataset_root / "year=*" / "*.parquet").as_posix(),
            "model_id": ML_MODEL_REGISTRY_ACCEPTED_MODEL_ID,
            "final_acceptance": bool(final_report.get("accepted")),
            "final_report_path": str(final_report_path.resolve()),
            "final_report_sha256": sha256_file(final_report_path),
            "model_path": str(model_path.resolve()),
            "model_hash_exact": model_hash_exact,
            "production_manifest_present": production_manifest_path.is_file(),
            "production_manifest_path": str(production_manifest_path.resolve()),
            "production_manifest_sha256": (
                sha256_file(production_manifest_path) if production_manifest_path.is_file() else None
            ),
        }

    def _rebase_evidence(self, end_date: date, accepted: dict[str, object]) -> dict[str, object]:
        splits, split_path = self.materializer.family._load_split_evidence(end_date)
        con = connect_utc(":memory:")
        try:
            self.materializer.base._prepare_label_views(con, end_date, splits)
            self.materializer._prepare_labeled_candidates(con)
            summary = con.execute(
                """
                SELECT
                    count(*), count(DISTINCT (instrument_id, symbol, session_date)),
                    count(DISTINCT symbol), min(session_date), max(session_date),
                    count(*) FILTER (WHERE prediction_label='DOWN'),
                    count(*) FILTER (WHERE prediction_label='NEUTRAL'),
                    count(*) FILTER (WHERE prediction_label='UP')
                FROM ml_gate6_labeled_candidates
                """
            ).fetchone()
            con.execute(
                """
                CREATE TEMP VIEW gate11_rebase_keys AS
                SELECT
                    concat(instrument_id, '|', symbol, '|', CAST(session_date AS VARCHAR)) AS observation_key,
                    prediction_label
                FROM ml_gate6_labeled_candidates
                """
            )
            con.execute(
                f"""
                CREATE TEMP VIEW gate11_accepted AS
                SELECT observation_key, prediction_label
                FROM read_parquet({sql_string(str(accepted['dataset_glob']))}, hive_partitioning=true)
                """
            )
            overlap = con.execute(
                """
                SELECT
                    count(*) FILTER (WHERE a.observation_key IS NOT NULL) AS overlap_rows,
                    count(*) FILTER (WHERE a.observation_key IS NULL) AS rebase_only_rows,
                    count(*) FILTER (
                        WHERE a.observation_key IS NOT NULL
                          AND a.prediction_label <> b.prediction_label
                    ) AS overlap_label_mismatches
                FROM gate11_rebase_keys b
                LEFT JOIN gate11_accepted a USING (observation_key)
                """
            ).fetchone()
            accepted_only = int(
                con.execute(
                    """
                    SELECT count(*)
                    FROM gate11_accepted a
                    LEFT JOIN gate11_rebase_keys b USING (observation_key)
                    WHERE b.observation_key IS NULL
                    """
                ).fetchone()[0]
            )
        finally:
            con.close()

        rows = int(summary[0])
        keys = int(summary[1])
        return {
            "role": "B_NEW_FEATURE_LINEAGE_PHASE10_ORIGIN_REBASE",
            "history_origin": ML_HISTORY_ORIGIN_DATE.isoformat(),
            "rows": rows,
            "distinct_keys": keys,
            "symbols": int(summary[2]),
            "first_session": str(summary[3]),
            "last_session": str(summary[4]),
            "class_rows": {
                "DOWN": int(summary[5]),
                "NEUTRAL": int(summary[6]),
                "UP": int(summary[7]),
            },
            "overlap_with_A_rows": int(overlap[0]),
            "B_only_rows": int(overlap[1]),
            "A_only_rows": accepted_only,
            "overlap_label_mismatches": int(overlap[2]),
            "split_evidence_path": str(split_path.resolve()),
            "split_evidence_sha256": sha256_file(split_path),
            "candidate_keys_unique": rows == keys,
        }

    def _preseam_evidence(self, end_date: date) -> dict[str, object]:
        segment_report = self._read_json(
            self.segment_policy.base.report_path,
            "Gate 4-C v2 identity segment report",
        )
        if segment_report.get("contract_version") != ALPACA_BACKFILL_IDENTITY_SEGMENT_POLICY_CONTRACT_VERSION:
            raise Gate11LongHistoryPreflightError("Gate 11-A requires accepted Gate 4-C v2 identity segments")
        segment_path = self.segment_policy.base.segment_path
        event_path = self.identity.event_ledger_path
        if not segment_path.is_file() or not event_path.is_file():
            raise Gate11LongHistoryPreflightError("Gate 11-A pre-seam identity/corporate-action evidence is missing")

        bar_glob = self.paths.glob_for_timeframe(Timeframe.DAY_1)
        feature_glob = self.paths.feature_glob(Timeframe.DAY_1)
        complete = " AND ".join(
            f"f.{name} IS NOT NULL AND isfinite(CAST(f.{name} AS DOUBLE))"
            for name in ML_PRODUCTION_CORE_FEATURE_NAMES
        )
        threshold_scale = float(ML_PREDICTION_LABEL_THRESHOLD_MULTIPLIER) * math.sqrt(
            float(ML_PREDICTION_LABEL_HORIZON_SESSIONS)
        )
        market_history = self.market_engine.history_paths(end_date)["market_effective"]
        if not market_history.is_file():
            raise Gate11LongHistoryPreflightError(
                f"Gate 11-A requires promoted split-origin market history: {market_history}"
            )

        con = connect_utc(":memory:")
        try:
            con.execute("SET preserve_insertion_order=false")
            con.execute(
                f"""
                CREATE TEMP VIEW gate11_daily AS
                SELECT symbol, CAST(session_date AS DATE) AS session_date,
                       CAST(close AS DOUBLE) AS close, CAST(volume AS DOUBLE) AS volume,
                       lower(CAST(provider AS VARCHAR)) AS provider,
                       CAST(is_adjusted AS BOOLEAN) AS is_adjusted
                FROM read_parquet({sql_string(bar_glob)}, hive_partitioning=true)
                WHERE CAST(session_date AS DATE) BETWEEN DATE '{GATE11_LONG_HISTORY_ORIGIN_DATE}'
                                                      AND DATE '{end_date}'
                """
            )
            con.execute(
                f"""
                CREATE TEMP VIEW gate11_pre_bars AS
                SELECT * FROM gate11_daily
                WHERE session_date <= DATE '{GATE11_PRESEAM_END_DATE}'
                """
            )
            source = con.execute(
                """
                SELECT count(*),
                       count(*) FILTER (WHERE provider='alpaca'),
                       count(*) FILTER (WHERE coalesce(is_adjusted, FALSE)),
                       count(DISTINCT symbol), min(session_date), max(session_date)
                FROM gate11_pre_bars
                """
            ).fetchone()

            con.execute(
                f"""
                CREATE TEMP VIEW gate11_segments AS
                SELECT identity_chain_id, segment_id, symbol,
                       CAST(first_date AS DATE) AS first_date,
                       CAST(last_date AS DATE) AS last_date,
                       coalesce(CAST(identity_ambiguous AS BOOLEAN), FALSE) AS identity_ambiguous
                FROM read_parquet({sql_string(str(segment_path))})
                """
            )
            segment_stats = con.execute(
                "SELECT count(*), count(DISTINCT symbol), count(*) FILTER (WHERE identity_ambiguous) FROM gate11_segments"
            ).fetchone()
            con.execute(
                """
                CREATE TEMP TABLE gate11_pre_identity AS
                SELECT b.*, s.identity_chain_id, s.segment_id, s.identity_ambiguous
                FROM gate11_pre_bars b
                LEFT JOIN gate11_segments s
                  ON s.symbol=b.symbol
                 AND b.session_date BETWEEN s.first_date AND s.last_date
                """
            )
            identity_stats = con.execute(
                """
                SELECT count(*),
                       count(*) FILTER (WHERE segment_id IS NULL),
                       count(*) FILTER (WHERE identity_ambiguous),
                       count(DISTINCT identity_chain_id) FILTER (WHERE identity_chain_id IS NOT NULL)
                FROM gate11_pre_identity
                """
            ).fetchone()

            con.execute(
                f"""
                CREATE TEMP TABLE gate11_pre_feature AS
                SELECT i.*, CAST(f.natr_14 AS DOUBLE) AS natr_14,
                       ({complete}) AS complete_features
                FROM gate11_pre_identity i
                LEFT JOIN read_parquet(
                    {sql_string(feature_glob)}, hive_partitioning=true, union_by_name=true
                ) f
                  ON f.symbol=i.symbol
                 AND CAST(f.timestamp_utc AS DATE)=i.session_date
                """
            )
            feature_stats = con.execute(
                f"""
                SELECT count(*),
                       count(*) FILTER (WHERE complete_features),
                       count(*) FILTER (
                           WHERE complete_features
                             AND close*volume >= {float(ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS):.17g}
                       ),
                       count(*) FILTER (
                           WHERE complete_features
                             AND close*volume >= {float(ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS):.17g}
                             AND natr_14 IS NOT NULL AND isfinite(natr_14) AND natr_14 > 0
                             AND segment_id IS NOT NULL AND NOT identity_ambiguous
                       )
                FROM gate11_pre_feature
                """
            ).fetchone()
            con.execute(
                f"""
                CREATE TEMP VIEW gate11_pre_candidates AS
                SELECT symbol, session_date, close, identity_chain_id, natr_14
                FROM gate11_pre_feature
                WHERE complete_features
                  AND close*volume >= {float(ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS):.17g}
                  AND natr_14 IS NOT NULL AND isfinite(natr_14) AND natr_14 > 0
                  AND segment_id IS NOT NULL AND NOT identity_ambiguous
                """
            )
            con.execute(
                """
                CREATE TEMP TABLE gate11_sessions AS
                SELECT session_date, row_number() OVER (ORDER BY session_date) AS session_seq
                FROM (SELECT DISTINCT session_date FROM gate11_daily)
                """
            )
            con.execute(
                f"""
                CREATE TEMP VIEW gate11_alpaca_splits AS
                SELECT source_symbol AS symbol, try_cast(event_date AS DATE) AS event_date
                FROM read_parquet({sql_string(str(event_path))})
                WHERE event_type IN ('forward_splits','reverse_splits')
                  AND source_symbol IS NOT NULL
                  AND try_cast(event_date AS DATE) IS NOT NULL
                  AND try_cast(event_date AS DATE) BETWEEN DATE '{GATE11_LONG_HISTORY_ORIGIN_DATE}'
                                                       AND DATE '{GATE11_PRESEAM_END_DATE}'
                """
            )
            split_stats = con.execute(
                "SELECT count(*), count(DISTINCT symbol) FROM gate11_alpaca_splits"
            ).fetchone()
            horizon = int(ML_PREDICTION_LABEL_HORIZON_SESSIONS)
            con.execute(
                f"""
                CREATE TEMP TABLE gate11_pre_outcomes AS
                SELECT
                    c.*,
                    fs.session_date AS future_date,
                    fb.close AS future_close,
                    EXISTS (
                        SELECT 1 FROM gate11_alpaca_splits sp
                        WHERE sp.symbol=c.symbol
                          AND sp.event_date > c.session_date
                          AND sp.event_date <= fs.session_date
                    ) AS split_crossing
                FROM gate11_pre_candidates c
                INNER JOIN gate11_sessions s ON s.session_date=c.session_date
                LEFT JOIN gate11_sessions fs ON fs.session_seq=s.session_seq+{horizon}
                LEFT JOIN gate11_daily fb
                  ON fb.symbol=c.symbol
                 AND fb.session_date=fs.session_date
                 AND fb.provider='alpaca'
                """
            )
            usable = (
                f"future_date <= DATE '{GATE11_PRESEAM_END_DATE}' "
                "AND future_close IS NOT NULL AND future_close > 0 AND NOT split_crossing"
            )
            outcome = con.execute(
                f"""
                SELECT
                    count(*) AS candidates,
                    count(*) FILTER (WHERE future_date IS NULL) AS end_censored,
                    count(*) FILTER (WHERE future_date > DATE '{GATE11_PRESEAM_END_DATE}') AS seam_censored,
                    count(*) FILTER (
                        WHERE future_date <= DATE '{GATE11_PRESEAM_END_DATE}' AND future_close IS NULL
                    ) AS same_symbol_missing,
                    count(*) FILTER (
                        WHERE future_date <= DATE '{GATE11_PRESEAM_END_DATE}'
                          AND future_close IS NOT NULL AND future_close > 0 AND split_crossing
                    ) AS split_censored,
                    count(*) FILTER (WHERE {usable}) AS usable,
                    min(session_date) FILTER (WHERE {usable}) AS first_usable,
                    max(session_date) FILTER (WHERE {usable}) AS last_usable,
                    count(*) FILTER (
                        WHERE {usable}
                          AND (future_close/close)-1.0 <= -(natr_14*{threshold_scale:.17g})
                    ) AS down_rows,
                    count(*) FILTER (
                        WHERE {usable}
                          AND (future_close/close)-1.0 > -(natr_14*{threshold_scale:.17g})
                          AND (future_close/close)-1.0 < (natr_14*{threshold_scale:.17g})
                    ) AS neutral_rows,
                    count(*) FILTER (
                        WHERE {usable}
                          AND (future_close/close)-1.0 >= (natr_14*{threshold_scale:.17g})
                    ) AS up_rows
                FROM gate11_pre_outcomes
                """
            ).fetchone()

            con.execute(
                f"""
                CREATE TEMP VIEW gate11_market_context_dates AS
                SELECT DISTINCT CAST(trading_date AS DATE) AS trading_date
                FROM read_parquet({sql_string(str(market_history))})
                """
            )
            context_rows = int(
                con.execute(
                    f"""
                    SELECT count(*)
                    FROM gate11_pre_outcomes o
                    INNER JOIN gate11_market_context_dates m ON m.trading_date=o.session_date
                    WHERE {usable}
                    """
                ).fetchone()[0]
            )

            reference = self.paths.reference_snapshot_file(end_date)
            observations = self.paths.ticker_observations_file()
            if not reference.is_file() or not observations.is_file():
                raise Gate11LongHistoryPreflightError(
                    "Gate 11-A unique-reference structural coverage inputs are missing"
                )
            con.execute(
                f"""
                CREATE TEMP VIEW gate11_ref AS
                SELECT ticker,
                       count(DISTINCT instrument_id) AS identity_count,
                       min(identity_quality) AS identity_quality,
                       min(market) AS market,
                       min(locale) AS locale,
                       min(primary_exchange) AS primary_exchange,
                       min(security_type) AS security_type
                FROM read_parquet({sql_string(str(reference))})
                WHERE ticker IS NOT NULL
                GROUP BY ticker
                """
            )
            con.execute(
                f"""
                CREATE TEMP VIEW gate11_reuse AS
                SELECT ticker, count(DISTINCT instrument_id) AS reuse_count
                FROM read_parquet({sql_string(str(observations))})
                GROUP BY ticker
                """
            )
            structural = con.execute(
                f"""
                WITH usable_rows AS (
                    SELECT o.symbol
                    FROM gate11_pre_outcomes o
                    WHERE {usable}
                )
                SELECT
                    count(*) AS usable_rows,
                    count(*) FILTER (
                        WHERE r.identity_count=1
                          AND coalesce(u.reuse_count,0) <= 1
                          AND lower(coalesce(r.identity_quality,'')) IN ('strong','medium')
                          AND nullif(trim(coalesce(r.market,'')),'') IS NOT NULL
                          AND nullif(trim(coalesce(r.locale,'')),'') IS NOT NULL
                          AND nullif(trim(coalesce(r.primary_exchange,'')),'') IS NOT NULL
                          AND nullif(trim(coalesce(r.security_type,'')),'') IS NOT NULL
                    ) AS unique_reference_metadata_rows,
                    count(DISTINCT x.symbol) AS usable_symbols,
                    count(DISTINCT x.symbol) FILTER (
                        WHERE r.identity_count=1
                          AND coalesce(u.reuse_count,0) <= 1
                          AND lower(coalesce(r.identity_quality,'')) IN ('strong','medium')
                          AND nullif(trim(coalesce(r.market,'')),'') IS NOT NULL
                          AND nullif(trim(coalesce(r.locale,'')),'') IS NOT NULL
                          AND nullif(trim(coalesce(r.primary_exchange,'')),'') IS NOT NULL
                          AND nullif(trim(coalesce(r.security_type,'')),'') IS NOT NULL
                    ) AS unique_reference_metadata_symbols
                FROM usable_rows x
                LEFT JOIN gate11_ref r ON r.ticker=x.symbol
                LEFT JOIN gate11_reuse u ON u.ticker=x.symbol
                """
            ).fetchone()
        finally:
            con.close()

        usable_rows = int(outcome[5])
        unique_reference_rows = int(structural[1])
        return {
            "source_rows": int(source[0]),
            "alpaca_provider_rows": int(source[1]),
            "adjusted_rows": int(source[2]),
            "symbols": int(source[3]),
            "first_session": str(source[4]),
            "last_session": str(source[5]),
            "segment_rows": int(segment_stats[0]),
            "segment_symbols": int(segment_stats[1]),
            "ambiguous_segment_symbols": int(segment_stats[2]),
            "identity_unmatched_rows": int(identity_stats[1]),
            "identity_ambiguous_rows": int(identity_stats[2]),
            "identity_chains_observed": int(identity_stats[3]),
            "feature_join_rows": int(feature_stats[0]),
            "complete_feature_rows": int(feature_stats[1]),
            "complete_liquid_rows": int(feature_stats[2]),
            "identity_feature_label_candidates": int(feature_stats[3]),
            "split_events": int(split_stats[0]),
            "split_symbols": int(split_stats[1]),
            "outcome_candidates": int(outcome[0]),
            "end_of_history_censored": int(outcome[1]),
            "provider_seam_censored": int(outcome[2]),
            "same_symbol_future_missing": int(outcome[3]),
            "split_censored": int(outcome[4]),
            "usable_before_structural_reconciliation": usable_rows,
            "first_usable_session": str(outcome[6]),
            "last_usable_session": str(outcome[7]),
            "class_rows_before_structural_reconciliation": {
                "DOWN": int(outcome[8]),
                "NEUTRAL": int(outcome[9]),
                "UP": int(outcome[10]),
            },
            "market_context_rows": context_rows,
            "market_context_fraction": 0.0 if usable_rows <= 0 else context_rows / usable_rows,
            "unique_reference_metadata_rows_lower_bound": unique_reference_rows,
            "unique_reference_metadata_row_fraction_lower_bound": (
                0.0 if usable_rows <= 0 else unique_reference_rows / usable_rows
            ),
            "usable_symbols": int(structural[2]),
            "unique_reference_metadata_symbols_lower_bound": int(structural[3]),
            "structural_reconciliation_status": "PENDING_GATE11_B_POINT_IN_TIME_AUTHORITY_AND_METADATA_RECONCILIATION",
            "identity_segment_contract": segment_report["contract_version"],
            "identity_segment_path": str(segment_path.resolve()),
            "identity_segment_sha256": sha256_file(segment_path),
            "corporate_action_event_path": str(event_path.resolve()),
            "corporate_action_event_sha256": sha256_file(event_path),
            "market_history_path": str(market_history.resolve()),
            "market_history_sha256": sha256_file(market_history),
        }

    def run(self) -> dict[str, Any]:
        gate9 = self._read_json(self.gate9_validation_path, "Gate 9-C production validation")
        gate10_writer = self._read_json(self.gate10_report_path, "Gate 10-C production writer report")
        gate10 = self._read_json(self.gate10_validation_path, "Gate 10-C production validation")
        if gate9.get("pass") is not True or gate10.get("pass") is not True or gate10_writer.get("pass") is not True:
            raise Gate11LongHistoryPreflightError("Gate 11-A requires accepted Gate 9-C and Gate 10-C production state")

        end_date = date.fromisoformat(str(gate10_writer["as_of_date"]))
        if end_date.isoformat() != ML_TRAINING_DATASET_ACCEPTED_HISTORY_END:
            raise Gate11LongHistoryPreflightError(
                "Gate 11-A comparison requires the same 2026-08-14 evidence horizon as Phase 10"
            )
        accepted = self._accepted_phase10()
        long_lineage = self._feature_lineage(GATE11_LONG_HISTORY_ORIGIN_DATE, end_date)
        rebase_lineage = self._feature_lineage(ML_HISTORY_ORIGIN_DATE, end_date)
        rebase = self._rebase_evidence(end_date, accepted)
        preseam = self._preseam_evidence(end_date)
        comparison = three_way_comparison_contract()

        checks = {
            "preflight_contract": True,
            "gate9c_production_validation_pass": gate9.get("pass") is True,
            "gate10c_production_validation_pass": gate10.get("pass") is True,
            "gate10c_writer_pass": gate10_writer.get("pass") is True,
            "accepted_dataset_lineage_exact": accepted["dataset_lineage"]
            == ML_TRAINING_DATASET_ACCEPTED_LINEAGE_SHA256,
            "accepted_dataset_partitions_exact": accepted["dataset_partition_hash_failures"] == 0,
            "accepted_model_final_acceptance": accepted["final_acceptance"] is True,
            "accepted_model_hash_exact": accepted["model_hash_exact"] is True,
            "accepted_model_production_manifest_present": accepted["production_manifest_present"] is True,
            "long_history_feature_manifest_coverage_complete": (
                long_lineage["manifest_count"] == long_lineage["expected_sessions"]
                and long_lineage["missing_count"] == 0
            ),
            "rebase_feature_manifest_coverage_complete": (
                rebase_lineage["manifest_count"] == rebase_lineage["expected_sessions"]
                and rebase_lineage["missing_count"] == 0
            ),
            "rebase_feature_lineage_differs_from_frozen_A": rebase_lineage["fingerprint"]
            != accepted["dataset_feature_lineage"],
            "rebase_population_nonempty": int(rebase["rows"]) > 0,
            "rebase_keys_unique": rebase["candidate_keys_unique"] is True,
            "accepted_vs_rebase_overlap_nonempty": int(rebase["overlap_with_A_rows"]) > 0,
            "preseam_provider_is_alpaca_only": preseam["source_rows"] == preseam["alpaca_provider_rows"],
            "preseam_rows_are_raw_unadjusted": int(preseam["adjusted_rows"]) == 0,
            "gate4_v2_identity_segment_contract_current": preseam["identity_segment_contract"]
            == ALPACA_BACKFILL_IDENTITY_SEGMENT_POLICY_CONTRACT_VERSION,
            "preseam_identity_segment_coverage_exact": int(preseam["identity_unmatched_rows"]) == 0,
            "preseam_feature_join_exact": int(preseam["feature_join_rows"]) == int(preseam["source_rows"]),
            "preseam_candidate_population_nonempty": int(preseam["identity_feature_label_candidates"]) > 0,
            "preseam_split_evidence_present": int(preseam["split_events"]) > 0,
            "preseam_provider_seam_windows_identified": int(preseam["provider_seam_censored"]) > 0,
            "preseam_usable_label_population_nonempty": int(preseam["usable_before_structural_reconciliation"]) > 0,
            "three_way_comparison_policy_locked": comparison["policy"]
            == GATE11_LONG_HISTORY_COMPARISON_POLICY,
            "accepted_model_replacement_forbidden": comparison["accepted_model_replacement_allowed_by_preflight"] is False,
            "final_holdout_not_used_for_gate11_selection": comparison["final_holdout_used_for_model_selection"] is False,
            "synthetic_pre2021_intraday_forbidden": comparison["synthetic_pre2021_intraday_allowed"] is False,
            "production_ml_writes_zero": self.production_ml_write_count == 0,
        }

        fingerprint_payload = {
            "contract_version": GATE11_LONG_HISTORY_PREFLIGHT_CONTRACT_VERSION,
            "comparison_policy": comparison,
            "gate9c_validation_sha256": sha256_file(self.gate9_validation_path),
            "gate10c_writer_sha256": sha256_file(self.gate10_report_path),
            "gate10c_validation_sha256": sha256_file(self.gate10_validation_path),
            "accepted_phase10": accepted,
            "long_feature_lineage": long_lineage,
            "rebase_feature_lineage": rebase_lineage,
            "rebase": rebase,
            "preseam": preseam,
        }
        source_fingerprint = _stable_hash(fingerprint_payload)
        report = {
            "contract_version": GATE11_LONG_HISTORY_PREFLIGHT_CONTRACT_VERSION,
            "role": "READ_ONLY_LONGER_HISTORY_ML_FEASIBILITY_AND_COMPARISON_DESIGN",
            "source_fingerprint": source_fingerprint,
            "as_of_date": end_date.isoformat(),
            "history_origins": {
                "A_frozen_phase10": ML_HISTORY_ORIGIN_DATE.isoformat(),
                "B_rebase": ML_HISTORY_ORIGIN_DATE.isoformat(),
                "C_extension": GATE11_LONG_HISTORY_ORIGIN_DATE.isoformat(),
                "preseam_end": GATE11_PRESEAM_END_DATE.isoformat(),
            },
            "comparison_policy": comparison,
            "accepted_phase10_A": accepted,
            "feature_lineage": {
                "B_rebase": rebase_lineage,
                "C_full": long_lineage,
            },
            "B_rebase_evidence": rebase,
            "C_preseam_feasibility_before_structural_reconciliation": preseam,
            "gate11b_requirement": (
                "Reconcile pre-2021 Gate 4 chain identity to point-in-time/lifetime-structural "
                "reference authority without current-route or current-active survivorship filters; "
                "unresolved rows remain excluded rather than guessed."
            ),
            "selection_guard": {
                "accepted_model_id": ML_MODEL_REGISTRY_ACCEPTED_MODEL_ID,
                "accepted_model_remains_production": True,
                "final_holdout_start": ML_WALK_FORWARD_FINAL_HOLDOUT_START,
                "final_holdout_used_for_gate11_model_selection": False,
                "initial_B_and_C_model_spec": dict(ML_MODEL_REGISTRY_SPEC),
            },
            "checks": checks,
            "production_ml_writes": self.production_ml_write_count,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "pass": all(checks.values()),
        }
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        report["report_path"] = str(self.report_path.resolve())
        return report
