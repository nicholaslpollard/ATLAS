from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.discovery.current_candidates import (
    CURRENT_CANDIDATE_MATERIALIZATION_CONTRACT_VERSION,
    CURRENT_CANDIDATE_SECTOR_POLICY,
    CurrentCandidateMaterializer,
)
from packages.discovery.promotion import support_mapping_from_study
from packages.features.partition_store import FeaturePartitionManifest, sha256_file
from packages.ml.historical_backfill_model_evaluation_design import (
    GATE11D_ACCEPTED_GATE11C_BUILDER_FINGERPRINT,
    GATE11D_ACCEPTED_GATE11C_VALIDATION_FINGERPRINT,
)
from packages.ml.model_registry import accepted_model_id, model_registry_fingerprint
from packages.schemas.candidate_promotion import CandidatePromotionRecord
from packages.schemas.discovery_score import DiscoveryDirection, DiscoveryState
from packages.strategies.registry import DEFAULT_STRATEGY_REGISTRY

from .historical_source import HistoricalStrategyResearchSourceResolver
from .historical_study import STRATEGY_HISTORICAL_STUDY_CONTRACT_VERSION, StrategyHistoricalStudy
from .strategy_evaluation import StrategyEvaluationMetrics, StrategyEvaluationSummary
from .strategy_support import classify_strategy_support


PHASE11_VALIDATION_CONTRACT_VERSION = (
    "phase11-validation-v2-independent-support-current-candidate-canonical-source-recompute"
)
PHASE11_FORBIDDEN_TRADE_KEYS = {
    "entry",
    "entry_price",
    "stop",
    "stop_loss",
    "target",
    "take_profit",
    "quantity",
    "position_size",
    "broker",
    "order",
    "order_id",
    "option_contract",
}


class Phase11ValidationError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise Phase11ValidationError(f"missing {label}: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase11ValidationError(f"invalid JSON for {label}: {path}") from exc


def _metric(payload: dict[str, Any]) -> StrategyEvaluationMetrics:
    return StrategyEvaluationMetrics(
        rows=int(payload["rows"]),
        mean_return=None if payload.get("mean_return") is None else float(payload["mean_return"]),
        median_return=None if payload.get("median_return") is None else float(payload["median_return"]),
        positive_rate=None if payload.get("positive_rate") is None else float(payload["positive_rate"]),
        stddev_return=None if payload.get("stddev_return") is None else float(payload["stddev_return"]),
        p10_return=None if payload.get("p10_return") is None else float(payload["p10_return"]),
        p25_return=None if payload.get("p25_return") is None else float(payload["p25_return"]),
        p75_return=None if payload.get("p75_return") is None else float(payload["p75_return"]),
        p90_return=None if payload.get("p90_return") is None else float(payload["p90_return"]),
        worst_return=None if payload.get("worst_return") is None else float(payload["worst_return"]),
        best_return=None if payload.get("best_return") is None else float(payload["best_return"]),
    )


def _summary(payload: dict[str, Any]) -> StrategyEvaluationSummary:
    return StrategyEvaluationSummary(
        contract_version=str(payload["contract_version"]),
        strategy_id=str(payload["strategy_id"]),
        direction=str(payload["direction"]),
        evaluation_start=None if payload.get("evaluation_start") is None else str(payload["evaluation_start"]),
        evaluation_end=None if payload.get("evaluation_end") is None else str(payload["evaluation_end"]),
        source_rows=int(payload["source_rows"]),
        fired_rows=int(payload["fired_rows"]),
        routed_rows=int(payload["routed_rows"]),
        cost_grid_bps=tuple(float(value) for value in payload["cost_grid_bps"]),
        aggregate_by_cost_bps={
            str(key): _metric(dict(value))
            for key, value in dict(payload["aggregate_by_cost_bps"]).items()
        },
        by_year={str(key): _metric(dict(value)) for key, value in dict(payload["by_year"]).items()},
        by_market_regime={
            str(key): _metric(dict(value))
            for key, value in dict(payload["by_market_regime"]).items()
        },
    )


def _forbidden_keys(payload: object, *, found: set[str] | None = None) -> set[str]:
    result = set() if found is None else found
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized = str(key).lower()
            if normalized in PHASE11_FORBIDDEN_TRADE_KEYS:
                result.add(normalized)
            _forbidden_keys(value, found=result)
    elif isinstance(payload, list):
        for value in payload:
            _forbidden_keys(value, found=result)
    return result


class Phase11IndependentValidator:
    """Independently validate Phase 11 persisted historical/current evidence."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.study = StrategyHistoricalStudy(settings)
        self.materializer = CurrentCandidateMaterializer(settings)
        self.source_resolver = HistoricalStrategyResearchSourceResolver(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.report_path = derived / "strategy_evaluation" / "phase11" / "v1" / "phase11_validation.json"

    def _validate_study(self, study: dict[str, Any]) -> tuple[dict[str, object], set[str]]:
        if study.get("contract_version") != STRATEGY_HISTORICAL_STUDY_CONTRACT_VERSION:
            raise Phase11ValidationError("historical strategy study contract changed")
        if study.get("pass") is not True:
            raise Phase11ValidationError("historical strategy study did not pass")
        research = dict(study.get("research_source") or {})
        if research.get("builder_source_fingerprint") != GATE11D_ACCEPTED_GATE11C_BUILDER_FINGERPRINT:
            raise Phase11ValidationError("strategy study builder lineage is not accepted Gate 11-C")
        if research.get("validation_source_fingerprint") != GATE11D_ACCEPTED_GATE11C_VALIDATION_FINGERPRINT:
            raise Phase11ValidationError("strategy study validation lineage is not accepted Gate 11-C")

        independently_resolved = self.source_resolver.resolve()
        if research.get("source_fingerprint") != independently_resolved.source_fingerprint:
            raise Phase11ValidationError("strategy study research-source fingerprint changed")

        expected_registry = DEFAULT_STRATEGY_REGISTRY.fingerprint()
        if study.get("strategy_registry_fingerprint") != expected_registry:
            raise Phase11ValidationError("strategy registry fingerprint changed")
        studies = study.get("studies")
        if not isinstance(studies, list) or len(studies) != len(DEFAULT_STRATEGY_REGISTRY.all()):
            raise Phase11ValidationError("historical strategy study count changed")

        support_recomputed: dict[str, object] = {}
        supported_ids: set[str] = set()
        for item in studies:
            if not isinstance(item, dict):
                raise Phase11ValidationError("malformed historical strategy item")
            development = _summary(dict(item["development"]))
            first_half = _summary(dict(item["first_half_primary_cost"]))
            second_half = _summary(dict(item["second_half_primary_cost"]))
            decision = classify_strategy_support(
                development=development,
                first_half=first_half,
                second_half=second_half,
            )
            reported = dict(item["support"])
            reported_status = str(reported["status"])
            if decision.status.value != reported_status:
                raise Phase11ValidationError(
                    f"strategy support decision changed for {decision.strategy_id}: "
                    f"{reported_status} != {decision.status.value}"
                )
            if decision.eligible_for_candidate_promotion != bool(
                reported["eligible_for_candidate_promotion"]
            ):
                raise Phase11ValidationError("strategy promotion eligibility changed")
            if item.get("protected_confirmation_used_for_support") is not False:
                raise Phase11ValidationError("protected confirmation leaked into strategy support")
            support_recomputed[decision.strategy_id] = asdict(decision) | {
                "status": decision.status.value,
                "eligible_for_candidate_promotion": decision.eligible_for_candidate_promotion,
            }
            if decision.eligible_for_candidate_promotion:
                supported_ids.add(decision.strategy_id)

        reported_supported = set(str(value) for value in study.get("supported_strategy_ids", []))
        if supported_ids != reported_supported:
            raise Phase11ValidationError("supported strategy-id set changed")
        return support_recomputed, supported_ids

    def _verify_current_feature_lineage(
        self,
        *,
        as_of_date: date,
        lineage: dict[str, Any],
    ) -> dict[str, object]:
        feature_path = self.paths.feature_file(Timeframe.DAY_1, as_of_date)
        feature_manifest_path = self.paths.feature_manifest_file(Timeframe.DAY_1, as_of_date)
        feature_manifest = FeaturePartitionManifest.from_dict(
            _read_json(feature_manifest_path, "independent 1d feature manifest")
        )
        feature_manifest.validate_contract(Timeframe.DAY_1, as_of_date)
        canonical_path = self.paths.canonical_file(Timeframe.DAY_1, as_of_date)
        if not feature_path.is_file() or not canonical_path.is_file():
            raise Phase11ValidationError("independent current feature/canonical source is missing")

        feature_sha = sha256_file(feature_path)
        canonical_sha = sha256_file(canonical_path)
        if feature_manifest.feature_sha256 != feature_sha:
            raise Phase11ValidationError("independent 1d feature hash changed")
        if Path(feature_manifest.feature_path).resolve() != feature_path.resolve():
            raise Phase11ValidationError("independent 1d feature path changed")
        if Path(feature_manifest.source_path).resolve() != canonical_path.resolve():
            raise Phase11ValidationError("independent canonical feature-source path changed")
        if feature_manifest.source_sha256 != canonical_sha:
            raise Phase11ValidationError("independent canonical feature-source hash changed")
        if lineage.get("feature_1d_sha256") != feature_sha:
            raise Phase11ValidationError("current candidate feature hash lineage changed")
        if lineage.get("canonical_1d_source_path") != str(canonical_path.resolve()):
            raise Phase11ValidationError("current candidate canonical source path lineage changed")
        if lineage.get("canonical_1d_source_sha256") != canonical_sha:
            raise Phase11ValidationError("current candidate canonical source hash lineage changed")
        if lineage.get("canonical_feature_exact_key_join") != "symbol+timestamp_utc":
            raise Phase11ValidationError("current candidate canonical/feature join key changed")

        return {
            "feature_sha256": feature_sha,
            "canonical_sha256": canonical_sha,
            "feature_manifest_source_sha256": feature_manifest.source_sha256,
            "canonical_feature_binding_exact": True,
        }

    def _validate_current(
        self,
        *,
        as_of_date: date,
        manifest: dict[str, Any],
        study: dict[str, Any],
        supported_ids: set[str],
    ) -> tuple[list[dict[str, Any]], dict[str, object]]:
        if manifest.get("contract_version") != CURRENT_CANDIDATE_MATERIALIZATION_CONTRACT_VERSION:
            raise Phase11ValidationError("current candidate manifest contract changed")
        if manifest.get("as_of_date") != as_of_date.isoformat():
            raise Phase11ValidationError("current candidate manifest date changed")
        if manifest.get("sector_context_policy") != CURRENT_CANDIDATE_SECTOR_POLICY:
            raise Phase11ValidationError("current candidate sector policy changed")
        all_path = Path(str(manifest["all_path"]))
        promoted_path = Path(str(manifest["promoted_path"]))
        if sha256_file(all_path) != manifest.get("all_sha256"):
            raise Phase11ValidationError("all-candidate artifact hash changed")
        if sha256_file(promoted_path) != manifest.get("promoted_sha256"):
            raise Phase11ValidationError("promoted-candidate artifact hash changed")
        lineage = dict(manifest.get("lineage") or {})
        current_input_proof = self._verify_current_feature_lineage(
            as_of_date=as_of_date,
            lineage=lineage,
        )
        if lineage.get("historical_strategy_study_sha256") != sha256_file(self.study.report_path):
            raise Phase11ValidationError("current candidates are not bound to current strategy study")
        if lineage.get("strategy_registry_fingerprint") != DEFAULT_STRATEGY_REGISTRY.fingerprint():
            raise Phase11ValidationError("current candidate registry lineage changed")
        if lineage.get("accepted_ml_model_id") != accepted_model_id():
            raise Phase11ValidationError("current candidates use a non-accepted ML model id")
        if lineage.get("accepted_ml_model_fingerprint") != model_registry_fingerprint():
            raise Phase11ValidationError("current candidates use a non-accepted ML fingerprint")

        raw_records: list[dict[str, Any]] = []
        if all_path.stat().st_size:
            for line in all_path.read_text(encoding="utf-8").splitlines():
                payload = json.loads(line)
                CandidatePromotionRecord.model_validate(payload)
                raw_records.append(payload)
        if len(raw_records) != int(manifest["considered_warm_hot_directional"]):
            raise Phase11ValidationError("current candidate count changed")

        promoted_records = [payload for payload in raw_records if bool(payload["promoted"])]
        if len(promoted_records) != int(manifest["promoted_count"]):
            raise Phase11ValidationError("promoted candidate count changed")
        expected_promoted_lines = "".join(
            CandidatePromotionRecord.model_validate(payload).model_dump_json() + "\n"
            for payload in promoted_records
        )
        if expected_promoted_lines != promoted_path.read_text(encoding="utf-8"):
            raise Phase11ValidationError("promoted artifact is not the exact promoted subset")

        support_from_study = support_mapping_from_study(study)
        promoted_checks: list[bool] = []
        for payload in raw_records:
            record = CandidatePromotionRecord.model_validate(payload)
            if record.sector_state is not None:
                raise Phase11ValidationError("sector context was guessed despite unavailable policy")
            if _forbidden_keys(payload):
                raise Phase11ValidationError("Phase 11 candidate contains trade/order geometry")
            if record.ml_probability_evidence.model_id != accepted_model_id():
                raise Phase11ValidationError("candidate probability evidence uses wrong model id")
            if record.promoted:
                route_by_id = {item.strategy_id: item for item in record.route_decisions}
                assessment_by_id = {item.strategy_id: item for item in record.strategy_assessments}
                for strategy_id in record.supported_fired_strategy_ids:
                    support = support_from_study.get(strategy_id)
                    route = route_by_id.get(strategy_id)
                    assessment = assessment_by_id.get(strategy_id)
                    if (
                        strategy_id not in supported_ids
                        or support is None
                        or not support.eligible_for_candidate_promotion
                        or route is None
                        or not route.eligible
                        or assessment is None
                        or not assessment.fired
                    ):
                        raise Phase11ValidationError(
                            f"promoted candidate lacks complete supported evidence: {record.ticker}/{strategy_id}"
                        )
                promoted_checks.append(
                    record.discovery_effective_state in {DiscoveryState.WARM, DiscoveryState.HOT}
                    and record.discovery_direction != DiscoveryDirection.NEUTRAL
                    and bool(record.supported_fired_strategy_ids)
                )

        return raw_records, {
            "candidate_count": len(raw_records),
            "promoted_count": len(promoted_records),
            "all_promoted_records_recompute_valid": all(promoted_checks),
            "current_input_lineage": current_input_proof,
        }

    def run(self, *, as_of_date: date) -> dict[str, object]:
        study = _read_json(self.study.report_path, "historical strategy study")
        support_recomputed, supported_ids = self._validate_study(study)
        current_manifest_path = self.materializer.manifest_path(as_of_date)
        current_manifest = _read_json(current_manifest_path, "current candidate manifest")
        current_records, current_proof = self._validate_current(
            as_of_date=as_of_date,
            manifest=current_manifest,
            study=study,
            supported_ids=supported_ids,
        )
        checks = {
            "historical_study_pass": study.get("pass") is True,
            "accepted_gate11c_source_reverified": True,
            "strategy_support_recomputed_exact": True,
            "protected_confirmation_not_used_for_support": all(
                item.get("protected_confirmation_used_for_support") is False
                for item in study["studies"]
            ),
            "current_candidate_manifest_pass": current_manifest.get("pass") is True,
            "canonical_feature_source_binding_reverified": bool(
                dict(current_proof["current_input_lineage"]).get("canonical_feature_binding_exact")
            ),
            "accepted_phase10_model_only": dict(current_manifest["lineage"]).get("accepted_ml_model_id")
            == accepted_model_id(),
            "sector_context_not_guessed": current_manifest.get("sector_context_policy")
            == CURRENT_CANDIDATE_SECTOR_POLICY,
            "candidate_promotion_recomputed_valid": bool(
                current_proof["all_promoted_records_recompute_valid"]
            ),
            "no_trade_or_order_geometry": all(not _forbidden_keys(payload) for payload in current_records),
            "production_ml_writes_zero": int(study.get("production_writes", -1)) == 0
            and int(current_manifest.get("production_ml_writes", -1)) == 0,
            "broker_writes_zero": int(study.get("broker_writes", -1)) == 0
            and int(current_manifest.get("broker_writes", -1)) == 0,
        }
        fingerprint_payload = {
            "contract_version": PHASE11_VALIDATION_CONTRACT_VERSION,
            "historical_study_sha256": sha256_file(self.study.report_path),
            "current_candidate_manifest_sha256": sha256_file(current_manifest_path),
            "support_recomputed": support_recomputed,
            "current_proof": current_proof,
            "checks": checks,
        }
        report: dict[str, object] = {
            "contract_version": PHASE11_VALIDATION_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": _stable_hash(fingerprint_payload),
            "as_of_date": as_of_date.isoformat(),
            "historical_study_sha256": sha256_file(self.study.report_path),
            "current_candidate_manifest_sha256": sha256_file(current_manifest_path),
            "supported_strategy_ids": sorted(supported_ids),
            "support_recomputed": support_recomputed,
            "current_candidate_proof": current_proof,
            "checks": checks,
            "production_ml_writes": 0,
            "broker_writes": 0,
            "pass": all(bool(value) for value in checks.values()),
        }
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
        report["report_path"] = str(self.report_path.resolve())
        return report
