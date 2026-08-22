from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Callable

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.discovery.current_candidates import (
    CURRENT_CANDIDATE_SECTOR_POLICY,
    CurrentCandidateMaterializer,
)
from packages.features.partition_store import sha256_file
from packages.ml.model_registry import accepted_model_id, model_registry_fingerprint
from packages.strategies.registry import DEFAULT_STRATEGY_REGISTRY

from .historical_study import StrategyHistoricalStudy
from .phase11_validation import Phase11IndependentValidator


PHASE11_CLOSEOUT_CONTRACT_VERSION = (
    "phase11-closeout-v1-historical-support-current-promotion-independent-validation"
)
PHASE11_NEXT_PHASE = "PHASE_12_DEEP_CANDIDATE_RESEARCH"
PHASE11_PRODUCTION_ML_WRITES = 0
PHASE11_BROKER_WRITES = 0


class Phase11CloseoutError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def phase11_acceptance_checks(
    *,
    study: dict[str, object],
    current: dict[str, object],
    validation: dict[str, object],
) -> dict[str, bool]:
    lineage = dict(current.get("lineage") or {})
    validation_checks = dict(validation.get("checks") or {})
    supported = set(str(value) for value in validation.get("supported_strategy_ids", []))
    registered = {strategy.metadata.strategy_id for strategy in DEFAULT_STRATEGY_REGISTRY.all()}
    return {
        "historical_strategy_study_pass": study.get("pass") is True,
        "strategy_registry_complete": int(study.get("strategy_count", -1)) == len(registered),
        "supported_strategies_are_registered": supported.issubset(registered),
        "protected_confirmation_not_used_for_support": study.get("protected_holdout_role")
        == "CONFIRMATION_ONLY_NOT_SUPPORT_SELECTION",
        "current_candidate_materialization_pass": current.get("pass") is True,
        "accepted_phase10_model_remains_probability_authority": lineage.get("accepted_ml_model_id")
        == accepted_model_id()
        and lineage.get("accepted_ml_model_fingerprint") == model_registry_fingerprint(),
        "sector_context_not_guessed": current.get("sector_context_policy")
        == CURRENT_CANDIDATE_SECTOR_POLICY,
        "independent_validation_pass": validation.get("pass") is True,
        "support_recomputed_exact": validation_checks.get("strategy_support_recomputed_exact") is True,
        "candidate_promotion_recomputed_valid": validation_checks.get(
            "candidate_promotion_recomputed_valid"
        )
        is True,
        "no_trade_or_order_geometry": validation_checks.get("no_trade_or_order_geometry") is True,
        "production_ml_writes_zero": int(study.get("production_writes", -1)) == 0
        and int(current.get("production_ml_writes", -1)) == 0
        and int(validation.get("production_ml_writes", -1)) == 0
        and PHASE11_PRODUCTION_ML_WRITES == 0,
        "broker_writes_zero": int(study.get("broker_writes", -1)) == 0
        and int(current.get("broker_writes", -1)) == 0
        and int(validation.get("broker_writes", -1)) == 0
        and PHASE11_BROKER_WRITES == 0,
    }


class Phase11Closeout:
    """Run and bind the complete Phase 11 evidence package.

    The closeout deliberately stops before trade construction. It studies strategy
    setup evidence, materializes current promoted/rejected research candidates using
    the already accepted Phase 10 probability model as context, independently
    revalidates support/promotion semantics, and emits one immutable acceptance report.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.study = StrategyHistoricalStudy(settings)
        self.materializer = CurrentCandidateMaterializer(settings)
        self.validator = Phase11IndependentValidator(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase11" / "v1"
        self.report_path = self.root / "phase11_final_acceptance.json"

    def run(
        self,
        *,
        as_of_date: date | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> dict[str, object]:
        study = self.study.run(progress=progress)
        if study.get("pass") is not True:
            raise Phase11CloseoutError("Phase 11 historical strategy study failed")

        resolved_as_of = as_of_date or self.materializer.resolve_latest_as_of()
        if progress is not None:
            progress(f"current candidates: materializing {resolved_as_of}")
        current = self.materializer.materialize(
            resolved_as_of,
            historical_study_path=self.study.report_path,
        )
        if current.get("pass") is not True:
            raise Phase11CloseoutError("Phase 11 current candidate materialization failed")

        if progress is not None:
            progress("independent validator: recomputing support and candidate evidence")
        validation = self.validator.run(as_of_date=resolved_as_of)
        if validation.get("pass") is not True:
            raise Phase11CloseoutError("Phase 11 independent validation failed")

        checks = phase11_acceptance_checks(study=study, current=current, validation=validation)
        if not all(checks.values()):
            failed = sorted(name for name, value in checks.items() if not value)
            raise Phase11CloseoutError("Phase 11 closeout checks failed: " + ", ".join(failed))

        status_counts = Counter(
            str(dict(item["support"])["status"])
            for item in study.get("studies", [])
            if isinstance(item, dict) and isinstance(item.get("support"), dict)
        )
        support_evidence = [
            {
                "strategy_id": str(item["strategy_id"]),
                "status": str(dict(item["support"])["status"]),
                "eligible_for_candidate_promotion": bool(
                    dict(item["support"])["eligible_for_candidate_promotion"]
                ),
                "development_rows": int(dict(item["support"])["development_rows"]),
                "development_mean_return": dict(item["support"])["development_mean_return"],
                "first_half_mean_return": dict(item["support"])["first_half_mean_return"],
                "second_half_mean_return": dict(item["support"])["second_half_mean_return"],
            }
            for item in study.get("studies", [])
            if isinstance(item, dict) and isinstance(item.get("support"), dict)
        ]
        source_payload = {
            "contract_version": PHASE11_CLOSEOUT_CONTRACT_VERSION,
            "as_of_date": resolved_as_of.isoformat(),
            "historical_strategy_study_sha256": sha256_file(self.study.report_path),
            "current_candidate_manifest_sha256": sha256_file(
                self.materializer.manifest_path(resolved_as_of)
            ),
            "independent_validation_sha256": sha256_file(self.validator.report_path),
            "strategy_registry_fingerprint": DEFAULT_STRATEGY_REGISTRY.fingerprint(),
            "accepted_ml_model_id": accepted_model_id(),
            "accepted_ml_model_fingerprint": model_registry_fingerprint(),
            "checks": checks,
        }
        report: dict[str, object] = {
            "contract_version": PHASE11_CLOSEOUT_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": _stable_hash(source_payload),
            "as_of_date": resolved_as_of.isoformat(),
            "historical_strategy_study_sha256": source_payload[
                "historical_strategy_study_sha256"
            ],
            "current_candidate_manifest_sha256": source_payload[
                "current_candidate_manifest_sha256"
            ],
            "independent_validation_sha256": source_payload[
                "independent_validation_sha256"
            ],
            "strategy_registry_fingerprint": DEFAULT_STRATEGY_REGISTRY.fingerprint(),
            "strategy_count": int(study["strategy_count"]),
            "support_status_counts": dict(sorted(status_counts.items())),
            "supported_strategy_ids": list(validation["supported_strategy_ids"]),
            "strategy_support_evidence": support_evidence,
            "protected_holdout_role": study["protected_holdout_role"],
            "current_candidate_as_of": resolved_as_of.isoformat(),
            "considered_warm_hot_directional": int(current["considered_warm_hot_directional"]),
            "promoted_count": int(current["promoted_count"]),
            "promoted_tickers": list(current["promoted_tickers"]),
            "candidate_ranking_policy": current["ranking_policy"],
            "sector_context_policy": current["sector_context_policy"],
            "accepted_phase10_model_id": accepted_model_id(),
            "accepted_phase10_model_fingerprint": model_registry_fingerprint(),
            "ml_probability_role": "EVIDENCE_CONTEXT_ONLY_NOT_DIRECTION_OR_PROMOTION_THRESHOLD",
            "phase11_trade_geometry_present": False,
            "phase11_execution_present": False,
            "production_ml_writes": 0,
            "broker_writes": 0,
            "checks": checks,
            "final_disposition": {
                "phase11_accepted": True,
                "accepted_phase10_model_remains_authoritative": True,
                "historically_supported_strategies_may_promote_current_candidates": True,
                "promoted_candidates_are_research_cases_not_orders": True,
                "next_phase": PHASE11_NEXT_PHASE,
            },
            "pass": True,
        }
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
        report["report_path"] = str(self.report_path.resolve())
        return report
