from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.discovery.current_candidates import CurrentCandidateMaterializer
from packages.features.partition_store import sha256_file
from packages.operations.phase23_strategy import Phase23CurrentStrategyHandoffStore
from packages.schemas.candidate_promotion import CandidatePromotionRecord
from packages.strategies.base import StrategyContext
from packages.strategies.registry import DEFAULT_STRATEGY_REGISTRY, StrategyRegistry

from .historical_study import (
    STRATEGY_HISTORICAL_STUDY_CONTRACT_VERSION,
    StrategyHistoricalStudy,
)
from .phase24_policy import (
    PHASE24_ACCEPTED_PHASE23_MERGE,
    PHASE24_COUNTERFACTUAL_CURRENT_RULES_ARE_AUTHORITY,
    PHASE24_GATE0_AS_OF,
    PHASE24_GATE0_EXPOSE_PROTECTED_CONFIRMATION,
    PHASE24_PHASE11_SUPPORT_REPLACEMENT_AUTHORITY,
    phase24_policy_fingerprint,
)
from .strategy_support import (
    STRATEGY_SUPPORT_POLICY_CONTRACT_VERSION,
    STRATEGY_SUPPORT_PRIMARY_COST_BPS,
)


PHASE24_GATE0_CONTRACT_VERSION = (
    "phase24-gate0-v1-phase11-forensic-current-counterfactual-no-authority"
)


class Phase24Gate0Error(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def phase11_support_policy_audit_fingerprint() -> str:
    return _stable_hash(
        {
            "contract_version": STRATEGY_SUPPORT_POLICY_CONTRACT_VERSION,
            "primary_cost_bps": STRATEGY_SUPPORT_PRIMARY_COST_BPS,
        }
    )


def support_evidence_from_study(study: Mapping[str, Any]) -> list[dict[str, object]]:
    if study.get("contract_version") != STRATEGY_HISTORICAL_STUDY_CONTRACT_VERSION:
        raise Phase24Gate0Error("accepted Phase 11 historical-study contract changed")
    rows = study.get("studies")
    if not isinstance(rows, list):
        raise Phase24Gate0Error("accepted Phase 11 study has no studies list")
    evidence: list[dict[str, object]] = []
    for item in rows:
        if not isinstance(item, dict) or not isinstance(item.get("support"), dict):
            raise Phase24Gate0Error("accepted Phase 11 study contains malformed support evidence")
        support = dict(item["support"])
        if support.get("contract_version") != STRATEGY_SUPPORT_POLICY_CONTRACT_VERSION:
            raise Phase24Gate0Error("accepted Phase 11 support-policy contract changed")
        if float(support.get("primary_cost_bps", -1.0)) != STRATEGY_SUPPORT_PRIMARY_COST_BPS:
            raise Phase24Gate0Error("accepted Phase 11 primary support cost changed")
        evidence.append(
            {
                "strategy_id": str(item.get("strategy_id") or support.get("strategy_id") or ""),
                "status": str(support.get("status") or ""),
                "eligible_for_candidate_promotion": bool(
                    support.get("eligible_for_candidate_promotion", False)
                ),
                "primary_cost_bps": float(support["primary_cost_bps"]),
                "development_mean_return": support.get("development_mean_return"),
                "first_half_mean_return": support.get("first_half_mean_return"),
                "second_half_mean_return": support.get("second_half_mean_return"),
                "development_rows": int(support.get("development_rows", -1)),
                "first_half_rows": int(support.get("first_half_rows", -1)),
                "second_half_rows": int(support.get("second_half_rows", -1)),
                "reason_codes": list(support.get("reason_codes") or ()),
            }
        )
    if any(not item["strategy_id"] for item in evidence):
        raise Phase24Gate0Error("accepted Phase 11 support evidence has a blank strategy id")
    return sorted(evidence, key=lambda item: str(item["strategy_id"]))


def evaluate_counterfactual_records(
    records: Sequence[Any],
    features_by_symbol: Mapping[str, Mapping[str, float]],
    *,
    registry: StrategyRegistry = DEFAULT_STRATEGY_REGISTRY,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    rows: list[dict[str, object]] = []
    by_strategy: dict[str, Counter[str]] = {
        strategy.metadata.strategy_id: Counter() for strategy in registry.all()
    }
    candidates_with_fire: set[str] = set()
    for record in records:
        ticker = str(record.ticker)
        if ticker not in features_by_symbol:
            raise Phase24Gate0Error(f"current candidate is missing exact feature evidence: {ticker}")
        support_by_id = {str(item.strategy_id): item for item in tuple(record.historical_support)}
        context = StrategyContext(
            instrument_id=str(record.instrument_id),
            ticker=ticker,
            as_of_date=record.as_of_date,
            features=features_by_symbol[ticker],
            ml_probability_evidence=record.ml_probability_evidence,
        )
        for route in tuple(record.route_decisions):
            if not route.eligible:
                continue
            strategy = registry.get(str(route.strategy_id))
            assessment = strategy.evaluate(context)
            support = support_by_id.get(str(route.strategy_id))
            rows.append(
                {
                    "instrument_id": str(record.instrument_id),
                    "ticker": ticker,
                    "strategy_id": str(route.strategy_id),
                    "historical_support_status": None if support is None else str(support.status),
                    "route_eligible": True,
                    "fired": bool(assessment.fired),
                    "conditions_met": int(assessment.conditions_met),
                    "condition_count": int(assessment.condition_count),
                    "evidence_score": float(assessment.evidence_score),
                    "authoritative": False,
                }
            )
            by_strategy[str(route.strategy_id)]["eligible_routes"] += 1
            if assessment.fired:
                by_strategy[str(route.strategy_id)]["fires"] += 1
                candidates_with_fire.add(str(record.instrument_id))
    rows.sort(key=lambda item: (str(item["ticker"]), str(item["strategy_id"])))
    return rows, {
        "eligible_route_evaluations": len(rows),
        "counterfactual_fires": sum(1 for item in rows if item["fired"]),
        "candidates_with_counterfactual_fire": len(candidates_with_fire),
        "by_strategy": {
            key: {
                "eligible_routes": int(value["eligible_routes"]),
                "fires": int(value["fires"]),
            }
            for key, value in sorted(by_strategy.items())
        },
    }


class Phase24Gate0Diagnostic:
    """Provider-free forensic diagnostic over accepted Phase11 and Phase23 artifacts."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.study = StrategyHistoricalStudy(settings)
        self.candidates = CurrentCandidateMaterializer(settings)
        self.phase23 = Phase23CurrentStrategyHandoffStore(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase24" / "v1" / "gate0"

    def report_path(self, as_of_date: date) -> Path:
        return self.root / f"year={as_of_date.year:04d}" / f"{as_of_date}.json"

    @staticmethod
    def _read_json(path: Path, label: str) -> dict[str, Any]:
        if not path.is_file():
            raise Phase24Gate0Error(f"missing {label}: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise Phase24Gate0Error(f"invalid JSON for {label}: {path}") from exc
        if not isinstance(payload, dict):
            raise Phase24Gate0Error(f"{label} must be a JSON object")
        return payload

    @staticmethod
    def _read_records(path: Path) -> list[CandidatePromotionRecord]:
        if not path.is_file():
            raise Phase24Gate0Error(f"missing accepted Phase 23 current candidate evidence: {path}")
        records: list[CandidatePromotionRecord] = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                records.append(CandidatePromotionRecord.model_validate_json(line))
            except ValueError as exc:
                raise Phase24Gate0Error(
                    f"invalid candidate record at {path}:{line_number}"
                ) from exc
        return records

    def _feature_map(self, as_of_date: date) -> tuple[dict[str, dict[str, float]], dict[str, object]]:
        feature_path, feature_sha, canonical_path, canonical_sha, feature_manifest = (
            self.candidates._verify_features(as_of_date)  # noqa: SLF001
        )
        required_features = sorted(
            {
                name
                for strategy in DEFAULT_STRATEGY_REGISTRY.all()
                for name in strategy.metadata.required_features
            }
        )
        select_features = ", ".join(f'f."{name}"' for name in required_features if name != "close")
        select_prefix = "f.symbol, b.close" + (", " + select_features if select_features else "")
        con = connect_utc(":memory:")
        try:
            frame = con.execute(
                f"""
                SELECT {select_prefix}
                FROM read_parquet({sql_string(feature_path)}) AS f
                INNER JOIN read_parquet({sql_string(canonical_path)}) AS b
                  ON f.symbol = b.symbol
                 AND f.timestamp_utc = b.timestamp_utc
                ORDER BY f.symbol
                """
            ).fetch_df()
        finally:
            con.close()
        if len(frame) != int(feature_manifest.row_count):
            raise Phase24Gate0Error("canonical/feature exact-key join changed row count")
        if frame["symbol"].duplicated().any():
            raise Phase24Gate0Error("current daily feature evidence contains duplicate symbols")
        return {
            str(row["symbol"]): {name: float(row[name]) for name in required_features}
            for _, row in frame.iterrows()
        }, {
            "feature_1d_path": str(feature_path.resolve()),
            "feature_1d_sha256": feature_sha,
            "canonical_1d_path": str(canonical_path.resolve()),
            "canonical_1d_sha256": canonical_sha,
        }

    def run(self, *, as_of_date: date) -> dict[str, object]:
        if as_of_date.isoformat() != PHASE24_GATE0_AS_OF:
            raise Phase24Gate0Error(
                f"Phase 24 Gate 0 is locked to accepted Phase 23 session {PHASE24_GATE0_AS_OF}"
            )
        if PHASE24_COUNTERFACTUAL_CURRENT_RULES_ARE_AUTHORITY:
            raise Phase24Gate0Error("counterfactual current rules unexpectedly have authority")
        if PHASE24_PHASE11_SUPPORT_REPLACEMENT_AUTHORITY:
            raise Phase24Gate0Error("Gate 0 unexpectedly has Phase 11 support replacement authority")
        if PHASE24_GATE0_EXPOSE_PROTECTED_CONFIRMATION:
            raise Phase24Gate0Error("Gate 0 protected-confirmation exposure unexpectedly enabled")

        handoff = self.phase23.resolve(as_of_date)
        study = self.phase23.verify_frozen_study(self.study.report_path)
        study_sha = sha256_file(self.study.report_path)
        registry_fingerprint = DEFAULT_STRATEGY_REGISTRY.fingerprint()
        if study.get("contract_version") != STRATEGY_HISTORICAL_STUDY_CONTRACT_VERSION:
            raise Phase24Gate0Error("accepted Phase 11 historical-study contract changed")
        if str(study.get("strategy_registry_fingerprint")) != registry_fingerprint:
            raise Phase24Gate0Error("accepted Phase 11 strategy registry fingerprint changed")
        support_evidence = support_evidence_from_study(study)

        manifest_path = self.candidates.manifest_path(as_of_date)
        manifest = self._read_json(manifest_path, "accepted Phase 23 current candidate manifest")
        if manifest.get("pass") is not True or manifest.get("as_of_date") != as_of_date.isoformat():
            raise Phase24Gate0Error("accepted Phase 23 current candidate manifest is not passing")
        if sha256_file(manifest_path) != handoff.current_candidate_manifest_sha256:
            raise Phase24Gate0Error("Phase 23 strategy handoff candidate-manifest hash changed")
        manifest_lineage = dict(manifest.get("lineage") or {})
        if manifest_lineage.get("historical_strategy_study_sha256") != study_sha:
            raise Phase24Gate0Error("current candidate manifest historical-study hash changed")
        if manifest_lineage.get("strategy_registry_fingerprint") != registry_fingerprint:
            raise Phase24Gate0Error("current candidate manifest strategy registry changed")
        all_path = self.candidates.all_path(as_of_date)
        if str(manifest.get("all_sha256") or "") != sha256_file(all_path):
            raise Phase24Gate0Error("accepted current candidate population hash changed")
        records = self._read_records(all_path)
        if len(records) != int(manifest.get("considered_warm_hot_directional", -1)):
            raise Phase24Gate0Error("accepted current candidate population count changed")

        features_by_symbol, feature_lineage = self._feature_map(as_of_date)
        counterfactual_rows, counterfactual_summary = evaluate_counterfactual_records(
            records,
            features_by_symbol,
        )
        support_counts = Counter(str(item["status"]) for item in support_evidence)
        lineage = {
            "accepted_phase23_merge": PHASE24_ACCEPTED_PHASE23_MERGE,
            "phase24_policy_fingerprint": phase24_policy_fingerprint(),
            "phase11_historical_study_path": str(self.study.report_path.resolve()),
            "phase11_historical_study_sha256": study_sha,
            "phase11_historical_study_contract": STRATEGY_HISTORICAL_STUDY_CONTRACT_VERSION,
            "phase11_strategy_registry_fingerprint": registry_fingerprint,
            "phase11_support_policy_contract": STRATEGY_SUPPORT_POLICY_CONTRACT_VERSION,
            "phase11_support_policy_audit_fingerprint": phase11_support_policy_audit_fingerprint(),
            "phase23_strategy_handoff_path": str(handoff.path.resolve()),
            "phase23_strategy_handoff_sha256": handoff.sha256,
            "current_candidate_manifest_path": str(manifest_path.resolve()),
            "current_candidate_manifest_sha256": handoff.current_candidate_manifest_sha256,
            "current_candidate_all_path": str(all_path.resolve()),
            "current_candidate_all_sha256": sha256_file(all_path),
            **feature_lineage,
        }
        checks = {
            "phase23_handoff_resolved": True,
            "phase11_frozen_study_verified": True,
            "phase11_contract_exact": True,
            "phase11_support_policy_exact": True,
            "strategy_registry_exact": True,
            "candidate_manifest_hash_bound": True,
            "candidate_manifest_study_lineage_exact": True,
            "candidate_population_hash_bound": True,
            "candidate_population_count_exact": True,
            "counterfactual_non_authoritative": PHASE24_COUNTERFACTUAL_CURRENT_RULES_ARE_AUTHORITY is False,
            "phase11_support_replacement_disabled": PHASE24_PHASE11_SUPPORT_REPLACEMENT_AUTHORITY is False,
            "protected_confirmation_not_exposed": PHASE24_GATE0_EXPOSE_PROTECTED_CONFIRMATION is False,
        }
        source_payload = {
            "contract_version": PHASE24_GATE0_CONTRACT_VERSION,
            "as_of_date": as_of_date.isoformat(),
            "lineage": lineage,
            "support_evidence": support_evidence,
            "counterfactual_rows": counterfactual_rows,
            "counterfactual_summary": counterfactual_summary,
            "checks": checks,
        }
        report: dict[str, object] = {
            **source_payload,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": _stable_hash(source_payload),
            "support_status_counts": dict(sorted(support_counts.items())),
            "accepted_current_considered": len(records),
            "accepted_current_promoted": int(manifest.get("promoted_count", -1)),
            "external_provider_reads": 0,
            "external_provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "production_ml_writes": 0,
            "phase11_support_writes": 0,
            "pass": all(checks.values()),
        }
        path = self.report_path(as_of_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
        report["report_path"] = str(path.resolve())
        return report
