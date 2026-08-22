from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.discovery.persistence import DISCOVERY_STATE_MANIFEST_VERSION
from packages.features.partition_store import FeaturePartitionManifest, sha256_file
from packages.ml.current_probability import AcceptedProductionProbabilityProvider
from packages.ml.feature_policy import ML_PRODUCTION_CORE_FEATURE_NAMES
from packages.regimes.split_origin_policy import (
    MARKET_SECTOR_HISTORY_ORIGIN_DATE,
    MARKET_SECTOR_MANIFEST_VERSION,
    MARKET_SECTOR_POLICY_GENESIS_FINGERPRINT,
    MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
    MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
    SPLIT_ORIGIN_POLICY_VERSION,
    TICKER_HISTORY_ORIGIN_DATE,
)
from packages.regimes.ticker_state_engine import (
    TICKER_STATE_MANIFEST_VERSION,
    TICKER_STATE_SNAPSHOT_CONTRACT_VERSION,
    TickerStateEngine,
)
from packages.schemas.candidate_promotion import CandidatePromotionRecord
from packages.schemas.discovery_score import DiscoveryDirection, DiscoveryState
from packages.schemas.discovery_state import DISCOVERY_STATE_SNAPSHOT_CONTRACT_VERSION, DiscoveryStateRecord
from packages.schemas.strategy import MLProbabilityEvidence
from packages.strategies.registry import DEFAULT_STRATEGY_REGISTRY

from .promotion import CandidatePromotionEngine, support_mapping_from_study


CURRENT_CANDIDATE_MATERIALIZATION_CONTRACT_VERSION = (
    "current-candidates-v3-canonical-close-split-origin-regime-hash-bound"
)
CURRENT_CANDIDATE_SECTOR_POLICY = "UNAVAILABLE_NO_AUTHORITATIVE_TICKER_TO_SECTOR_MAPPING"


class CurrentCandidateMaterializationError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise CurrentCandidateMaterializationError(f"missing {label}: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CurrentCandidateMaterializationError(f"invalid JSON for {label}: {path}") from exc


def _validate_split_origin_market_manifest(manifest: dict[str, Any], as_of_date: date) -> None:
    """Require the accepted production v2 split-origin market/sector regime lineage."""
    expected = {
        "manifest_version": MARKET_SECTOR_MANIFEST_VERSION,
        "snapshot_contract_version": MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
        "state_policy_contract_version": MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
        "split_origin_policy_version": SPLIT_ORIGIN_POLICY_VERSION,
        "history_origin_date": MARKET_SECTOR_HISTORY_ORIGIN_DATE.isoformat(),
        "ticker_history_origin_date": TICKER_HISTORY_ORIGIN_DATE.isoformat(),
        "gate10a_source_fingerprint": MARKET_SECTOR_POLICY_GENESIS_FINGERPRINT,
        "as_of_date": as_of_date.isoformat(),
    }
    changed = [key for key, value in expected.items() if manifest.get(key) != value]
    if changed:
        raise CurrentCandidateMaterializationError(
            "market regime split-origin contract changed: " + ", ".join(changed)
        )


def _validate_split_origin_market_snapshot(payload: dict[str, Any], as_of_date: date) -> None:
    expected = {
        "snapshot_contract_version": MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
        "state_policy_contract_version": MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
        "split_origin_policy_version": SPLIT_ORIGIN_POLICY_VERSION,
        "history_origin_date": MARKET_SECTOR_HISTORY_ORIGIN_DATE.isoformat(),
        "ticker_history_origin_date": TICKER_HISTORY_ORIGIN_DATE.isoformat(),
        "as_of_date": as_of_date.isoformat(),
    }
    changed = [key for key, value in expected.items() if payload.get(key) != value]
    if changed:
        raise CurrentCandidateMaterializationError(
            "market regime split-origin snapshot changed: " + ", ".join(changed)
        )


def _validate_feature_source_binding(
    manifest: FeaturePartitionManifest,
    *,
    feature_path: Path,
    feature_sha256: str,
    canonical_path: Path,
    canonical_sha256: str,
) -> None:
    """Prove current strategy raw-price inputs come from the feature partition's source."""
    if manifest.feature_sha256 != feature_sha256:
        raise CurrentCandidateMaterializationError("1d feature snapshot hash changed")
    if Path(manifest.feature_path).resolve() != feature_path.resolve():
        raise CurrentCandidateMaterializationError("1d feature manifest path changed")
    if Path(manifest.source_path).resolve() != canonical_path.resolve():
        raise CurrentCandidateMaterializationError("1d feature canonical source path changed")
    if manifest.source_sha256 != canonical_sha256:
        raise CurrentCandidateMaterializationError("1d feature canonical source hash changed")


class CurrentCandidateMaterializer:
    """Build current Phase 11 candidate decisions from accepted upstream artifacts."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.ticker_engine = TickerStateEngine(settings)
        self.probabilities = AcceptedProductionProbabilityProvider(settings)
        self.promotion = CandidatePromotionEngine(DEFAULT_STRATEGY_REGISTRY)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "candidates" / "phase11" / "v1"

    def all_path(self, as_of_date: date) -> Path:
        return self.root / f"year={as_of_date.year:04d}" / f"date={as_of_date}" / "all.jsonl"

    def promoted_path(self, as_of_date: date) -> Path:
        return self.root / f"year={as_of_date.year:04d}" / f"date={as_of_date}" / "promoted.jsonl"

    def manifest_path(self, as_of_date: date) -> Path:
        return self.root / "manifests" / f"{as_of_date.year:04d}" / f"{as_of_date}.json"

    def resolve_latest_as_of(self) -> date:
        state_root = self.settings.resolved_path(self.settings.data.paths.derived) / "discovery" / "states"
        candidates: list[date] = []
        for path in state_root.glob("year=*/date=*/part-000.parquet"):
            try:
                candidates.append(date.fromisoformat(path.parent.name.removeprefix("date=")))
            except ValueError:
                continue
        for as_of_date in sorted(set(candidates), reverse=True):
            required = (
                self.paths.canonical_file(Timeframe.DAY_1, as_of_date),
                self.paths.feature_file(Timeframe.DAY_1, as_of_date),
                self.paths.feature_manifest_file(Timeframe.DAY_1, as_of_date),
                self.paths.discovery_state_manifest(as_of_date),
                self.paths.regime_state_snapshot(as_of_date),
                self.paths.regime_state_manifest(as_of_date),
                self.ticker_engine.snapshot_path(as_of_date),
                self.ticker_engine.manifest_path(as_of_date),
            )
            if all(path.is_file() for path in required):
                return as_of_date
        raise CurrentCandidateMaterializationError(
            "no session has the complete canonical/features/discovery/market-regime/ticker-regime artifact set"
        )

    def _verify_discovery(self, as_of_date: date) -> tuple[Path, str]:
        snapshot = self.paths.discovery_state_file(as_of_date)
        manifest_path = self.paths.discovery_state_manifest(as_of_date)
        manifest = _read_json(manifest_path, "discovery state manifest")
        if manifest.get("manifest_version") != DISCOVERY_STATE_MANIFEST_VERSION:
            raise CurrentCandidateMaterializationError("discovery state manifest contract changed")
        if manifest.get("snapshot_contract_version") != DISCOVERY_STATE_SNAPSHOT_CONTRACT_VERSION:
            raise CurrentCandidateMaterializationError("discovery state snapshot contract changed")
        if manifest.get("as_of_date") != as_of_date.isoformat():
            raise CurrentCandidateMaterializationError("discovery state date changed")
        digest = sha256_file(snapshot)
        if manifest.get("snapshot_sha256") != digest:
            raise CurrentCandidateMaterializationError("discovery state snapshot hash changed")
        return snapshot, digest

    def _verify_features(
        self, as_of_date: date
    ) -> tuple[Path, str, Path, str, FeaturePartitionManifest]:
        feature_path = self.paths.feature_file(Timeframe.DAY_1, as_of_date)
        manifest_path = self.paths.feature_manifest_file(Timeframe.DAY_1, as_of_date)
        manifest = FeaturePartitionManifest.from_dict(_read_json(manifest_path, "1d feature manifest"))
        manifest.validate_contract(Timeframe.DAY_1, as_of_date)
        canonical_path = self.paths.canonical_file(Timeframe.DAY_1, as_of_date)
        if not canonical_path.is_file():
            raise CurrentCandidateMaterializationError(
                f"missing canonical 1d source for current strategies: {canonical_path}"
            )
        feature_sha = sha256_file(feature_path)
        canonical_sha = sha256_file(canonical_path)
        _validate_feature_source_binding(
            manifest,
            feature_path=feature_path,
            feature_sha256=feature_sha,
            canonical_path=canonical_path,
            canonical_sha256=canonical_sha,
        )
        return feature_path, feature_sha, canonical_path, canonical_sha, manifest

    def _verify_market_regime(self, as_of_date: date) -> tuple[dict[str, Any], str]:
        snapshot = self.paths.regime_state_snapshot(as_of_date)
        manifest_path = self.paths.regime_state_manifest(as_of_date)
        manifest = _read_json(manifest_path, "market regime manifest")
        _validate_split_origin_market_manifest(manifest, as_of_date)
        digest = sha256_file(snapshot)
        if manifest.get("snapshot_sha256") != digest:
            raise CurrentCandidateMaterializationError("market regime snapshot hash changed")
        payload = _read_json(snapshot, "market regime snapshot")
        _validate_split_origin_market_snapshot(payload, as_of_date)
        return payload, digest

    def _verify_ticker_regime(self, as_of_date: date) -> tuple[Path, str]:
        snapshot = self.ticker_engine.snapshot_path(as_of_date)
        manifest_path = self.ticker_engine.manifest_path(as_of_date)
        manifest = _read_json(manifest_path, "ticker regime manifest")
        if manifest.get("manifest_version") != TICKER_STATE_MANIFEST_VERSION:
            raise CurrentCandidateMaterializationError("ticker regime manifest contract changed")
        if manifest.get("snapshot_contract_version") != TICKER_STATE_SNAPSHOT_CONTRACT_VERSION:
            raise CurrentCandidateMaterializationError("ticker regime snapshot contract changed")
        digest = sha256_file(snapshot)
        if manifest.get("snapshot_sha256") != digest:
            raise CurrentCandidateMaterializationError("ticker regime snapshot hash changed")
        return snapshot, digest

    @staticmethod
    def _discovery_record(row: pd.Series) -> DiscoveryStateRecord:
        payload = row.to_dict()
        return DiscoveryStateRecord.model_validate(payload)

    @staticmethod
    def _ml_evidence(row: pd.Series) -> MLProbabilityEvidence:
        return MLProbabilityEvidence(
            model_id=str(row["ml_model_id"]),
            p_down=float(row["p_down"]),
            p_neutral=float(row["p_neutral"]),
            p_up=float(row["p_up"]),
        )

    def materialize(self, as_of_date: date, *, historical_study_path: Path) -> dict[str, object]:
        discovery_path, discovery_sha = self._verify_discovery(as_of_date)
        feature_path, feature_sha, canonical_path, canonical_sha, feature_manifest = self._verify_features(
            as_of_date
        )
        market_payload, market_sha = self._verify_market_regime(as_of_date)
        ticker_path, ticker_sha = self._verify_ticker_regime(as_of_date)
        study = _read_json(historical_study_path, "historical strategy study")
        if study.get("pass") is not True:
            raise CurrentCandidateMaterializationError("historical strategy study is not passing")
        support = support_mapping_from_study(study)

        con = connect_utc(":memory:")
        try:
            discovery = con.execute(
                f"""
                SELECT * FROM read_parquet({sql_string(discovery_path)})
                WHERE effective_state IN ('warm','hot')
                  AND direction IN ('bullish','bearish')
                ORDER BY priority_score DESC, ticker, instrument_id
                """
            ).fetch_df()
            canonical_duplicate_keys = int(
                con.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM (
                        SELECT symbol, timestamp_utc
                        FROM read_parquet({sql_string(canonical_path)})
                        GROUP BY symbol, timestamp_utc
                        HAVING COUNT(*) > 1
                    )
                    """
                ).fetchone()[0]
            )
            if canonical_duplicate_keys:
                raise CurrentCandidateMaterializationError(
                    "canonical 1d source contains duplicate symbol/timestamp keys"
                )
            features = con.execute(
                f"""
                SELECT f.*, b.close
                FROM read_parquet({sql_string(feature_path)}) AS f
                INNER JOIN read_parquet({sql_string(canonical_path)}) AS b
                  ON f.symbol = b.symbol
                 AND f.timestamp_utc = b.timestamp_utc
                ORDER BY f.symbol
                """
            ).fetch_df()
            ticker = con.execute(
                f"SELECT instrument_id, effective_ticker_state FROM read_parquet({sql_string(ticker_path)})"
            ).fetch_df()
        finally:
            con.close()

        if len(features) != int(feature_manifest.row_count):
            raise CurrentCandidateMaterializationError(
                "canonical/feature exact-key join did not preserve the feature partition row count"
            )
        if features["close"].isna().any():
            raise CurrentCandidateMaterializationError("canonical close is missing after exact-key join")
        if discovery["instrument_id"].duplicated().any():
            raise CurrentCandidateMaterializationError("discovery candidate identities are duplicated")
        if features["symbol"].duplicated().any():
            raise CurrentCandidateMaterializationError("daily feature symbols are duplicated")
        if ticker["instrument_id"].duplicated().any():
            raise CurrentCandidateMaterializationError("ticker regime identities are duplicated")

        feature_by_symbol = features.set_index("symbol", drop=False)
        ticker_by_id = ticker.set_index("instrument_id", drop=False)
        missing_feature_symbols = [
            str(symbol) for symbol in discovery["ticker"].tolist() if str(symbol) not in feature_by_symbol.index
        ]
        if missing_feature_symbols:
            raise CurrentCandidateMaterializationError(
                "WARM/HOT candidate is missing exact-case 1d features: "
                + ", ".join(missing_feature_symbols[:20])
            )

        predictor_frame = feature_by_symbol.loc[
            [str(value) for value in discovery["ticker"].tolist()],
            list(ML_PRODUCTION_CORE_FEATURE_NAMES),
        ].reset_index(drop=True)
        probability_frame = self.probabilities.predict_frame(predictor_frame).reset_index(drop=True)
        if len(probability_frame) != len(discovery):
            raise CurrentCandidateMaterializationError("ML probability row count changed")

        market_state = str(market_payload["market"]["effective"]["composite"])
        required_features = sorted(
            {name for strategy in DEFAULT_STRATEGY_REGISTRY.all() for name in strategy.metadata.required_features}
        )
        missing_required_columns = sorted(set(required_features).difference(features.columns))
        if missing_required_columns:
            raise CurrentCandidateMaterializationError(
                "current strategy input columns are unavailable: " + ", ".join(missing_required_columns)
            )

        records: list[CandidatePromotionRecord] = []
        for position, (_, discovery_row) in enumerate(discovery.iterrows()):
            ticker_symbol = str(discovery_row["ticker"])
            feature_row = feature_by_symbol.loc[ticker_symbol]
            feature_values = {name: float(feature_row[name]) for name in required_features}
            instrument_id = str(discovery_row["instrument_id"])
            ticker_state = None
            if instrument_id in ticker_by_id.index:
                value = ticker_by_id.loc[instrument_id]["effective_ticker_state"]
                ticker_state = None if pd.isna(value) else str(value)
            record = self.promotion.evaluate(
                discovery=self._discovery_record(discovery_row),
                features=feature_values,
                market_state=market_state,
                sector_state=None,
                ticker_state=ticker_state,
                ml_probability_evidence=self._ml_evidence(probability_frame.iloc[position]),
                historical_support=support,
            )
            records.append(record)

        records.sort(
            key=lambda item: (
                0 if item.discovery_effective_state == DiscoveryState.HOT else 1,
                -item.discovery_priority_score,
                item.ticker,
                item.instrument_id,
            )
        )
        promoted = [record for record in records if record.promoted]
        all_path = self.all_path(as_of_date)
        promoted_path = self.promoted_path(as_of_date)
        all_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            all_path,
            "".join(record.model_dump_json() + "\n" for record in records),
        )
        atomic_write_text(
            promoted_path,
            "".join(record.model_dump_json() + "\n" for record in promoted),
        )
        lineage = {
            "discovery_state_sha256": discovery_sha,
            "feature_1d_sha256": feature_sha,
            "canonical_1d_source_path": str(canonical_path.resolve()),
            "canonical_1d_source_sha256": canonical_sha,
            "canonical_feature_exact_key_join": "symbol+timestamp_utc",
            "market_regime_sha256": market_sha,
            "market_regime_manifest_version": MARKET_SECTOR_MANIFEST_VERSION,
            "market_regime_split_origin_policy": SPLIT_ORIGIN_POLICY_VERSION,
            "ticker_regime_sha256": ticker_sha,
            "historical_strategy_study_sha256": sha256_file(historical_study_path),
            "strategy_registry_fingerprint": DEFAULT_STRATEGY_REGISTRY.fingerprint(),
            "accepted_ml_model_id": self.probabilities.model_id,
            "accepted_ml_model_fingerprint": self.probabilities.model_fingerprint,
            "sector_policy": CURRENT_CANDIDATE_SECTOR_POLICY,
        }
        manifest: dict[str, object] = {
            "contract_version": CURRENT_CANDIDATE_MATERIALIZATION_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "as_of_date": as_of_date.isoformat(),
            "lineage": lineage,
            "dependency_fingerprint": _stable_hash(lineage),
            "considered_warm_hot_directional": len(records),
            "promoted_count": len(promoted),
            "promoted_tickers": [record.ticker for record in promoted],
            "sector_context_policy": CURRENT_CANDIDATE_SECTOR_POLICY,
            "ranking_policy": "HOT_BEFORE_WARM_THEN_EXISTING_DISCOVERY_PRIORITY_NO_NEW_COMPOSITE_SCORE",
            "all_path": str(all_path.resolve()),
            "all_sha256": sha256_file(all_path),
            "promoted_path": str(promoted_path.resolve()),
            "promoted_sha256": sha256_file(promoted_path),
            "production_ml_writes": 0,
            "broker_writes": 0,
            "pass": True,
        }
        manifest_path = self.manifest_path(as_of_date)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        manifest["manifest_path"] = str(manifest_path.resolve())
        return manifest
