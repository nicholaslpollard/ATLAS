from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from packages.ai.phase14_closeout import Phase14Closeout
from packages.analogues.phase12_closeout import Phase12Closeout
from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.discovery.current_candidates import CurrentCandidateMaterializer
from packages.execution.phase15_foundation import Phase15CumulativeFoundationResolver
from packages.execution.phase15_source import Phase15ExecutionInputResolver
from packages.features.partition_store import sha256_file
from packages.operations.phase23_current_run import (
    PHASE23_RUN_MANIFEST_CONTRACT_VERSION,
    Phase23CurrentAnalysisCycle,
)
from packages.operations.phase23_handoff import Phase23AnalysisHandoffStore
from packages.operations.phase23_policy import (
    MASSIVE_MARKET_REFERENCE_READS,
    PHASE23_FROZEN_SUPPORTED_STRATEGIES,
    phase23_policy_fingerprint,
)
from packages.operations.phase23_strategy import Phase23CurrentStrategyHandoffStore
from packages.portfolio.phase13_closeout import Phase13Closeout
from packages.regimes.split_origin_state_engine import SplitOriginRegimeStateEngine
from packages.regimes.ticker_state_engine import TickerStateEngine
from packages.schemas.execution import BrokerName


PHASE23_INDEPENDENT_VALIDATION_CONTRACT_VERSION = (
    "phase23-validation-v1-persisted-lineage-zero-downstream-provider-mutation-recompute"
)


class Phase23IndependentValidationError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise Phase23IndependentValidationError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase23IndependentValidationError(f"invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase23IndependentValidationError(f"{label} must be a JSON object")
    return payload


class Phase23RunIndependentValidator:
    """Independently re-open and validate one completed Phase23 persisted run.

    This validator performs no provider, broker, AI, or execution calls. It recomputes
    hashes from the durable artifacts, re-resolves the Phase23 strategy/analysis
    handoffs, verifies the downstream zero-path contracts, and proves Phase15 sees the
    same post-baseline handoff with zero executable cases.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.cycle = Phase23CurrentAnalysisCycle(settings)
        self.candidates = CurrentCandidateMaterializer(settings)
        self.strategy = Phase23CurrentStrategyHandoffStore(settings)
        self.analysis = Phase23AnalysisHandoffStore(settings)
        self.phase12 = Phase12Closeout(settings)
        self.phase13 = Phase13Closeout(settings)
        self.phase14 = Phase14Closeout(settings)
        self.cumulative = Phase15CumulativeFoundationResolver(settings)
        self.phase15 = Phase15ExecutionInputResolver(settings)

    def report_path(self, as_of_date: date, broker: BrokerName) -> Path:
        return self.cycle.run_dir(as_of_date, broker) / "independent_validation.json"

    def _expected_stage_paths(self, as_of_date: date) -> dict[str, Path]:
        return {
            "reference": self.paths.reference_snapshot_file(as_of_date),
            "canonical_1d": self.paths.canonical_file(Timeframe.DAY_1, as_of_date),
            "bars_1h": self.paths.derived_file(Timeframe.HOUR_1, as_of_date),
            "bars_4h": self.paths.derived_file(Timeframe.HOUR_4, as_of_date),
            "features_1d": self.paths.feature_file(Timeframe.DAY_1, as_of_date),
            "features_1h": self.paths.feature_file(Timeframe.HOUR_1, as_of_date),
            "features_4h": self.paths.feature_file(Timeframe.HOUR_4, as_of_date),
            "universe": self.paths.universe_snapshot_file(as_of_date),
            "discovery": self.paths.discovery_state_file(as_of_date),
            "market_regime": SplitOriginRegimeStateEngine(self.settings).snapshot_path(as_of_date),
            "ticker_regime": TickerStateEngine(self.settings).snapshot_path(as_of_date),
            "current_candidates": self.candidates.manifest_path(as_of_date),
            "strategy_handoff": self.strategy.path(as_of_date),
            "phase12_acceptance": self.phase12.report_path,
            "phase13_acceptance": self.phase13.report_path,
            "phase14_acceptance": self.phase14.report_path,
        }

    def _expected_archives(self, as_of_date: date, broker: BrokerName) -> dict[str, Path]:
        root = self.cycle.run_dir(as_of_date, broker) / "evidence"
        return {
            "strategy_handoff": root / "phase23_strategy_handoff.json",
            "phase12": root / "phase12_final_acceptance.json",
            "phase13": root / "phase13_final_acceptance.json",
            "phase14": root / "phase14_final_acceptance.json",
            "analysis_handoff": root / "phase23_analysis_handoff.json",
        }

    @staticmethod
    def _source_payload(manifest: dict[str, Any]) -> dict[str, object]:
        return {
            key: manifest[key]
            for key in (
                "contract_version",
                "phase23_policy_fingerprint",
                "run_scope_fingerprint",
                "as_of_date",
                "broker",
                "stage_hashes",
                "archive_hashes",
                "phase15_input_fingerprint",
            )
        }

    def run(self, *, as_of_date: date, broker: BrokerName | str) -> dict[str, object]:
        selected = BrokerName(broker)
        manifest_path = self.cycle.manifest_path(as_of_date, selected)
        manifest = _read_json(manifest_path, "Phase 23 run manifest")
        stage_hashes = manifest.get("stage_hashes")
        archive_hashes = manifest.get("archive_hashes")
        if not isinstance(stage_hashes, dict) or not isinstance(archive_hashes, dict):
            raise Phase23IndependentValidationError("Phase 23 run lineage hashes are malformed")

        expected_stage_paths = self._expected_stage_paths(as_of_date)
        missing_stage_paths = sorted(
            name for name, path in expected_stage_paths.items() if not path.is_file()
        )
        if missing_stage_paths:
            raise Phase23IndependentValidationError(
                "Phase 23 persisted stage evidence is missing: " + ", ".join(missing_stage_paths)
            )
        recomputed_stage_hashes = {
            name: sha256_file(path) for name, path in expected_stage_paths.items()
        }

        expected_archives = self._expected_archives(as_of_date, selected)
        missing_archives = sorted(name for name, path in expected_archives.items() if not path.is_file())
        if missing_archives:
            raise Phase23IndependentValidationError(
                "Phase 23 archived evidence is missing: " + ", ".join(missing_archives)
            )
        recomputed_archive_hashes = {
            name: sha256_file(path) for name, path in expected_archives.items()
        }

        current = _read_json(self.candidates.manifest_path(as_of_date), "current candidate manifest")
        phase12 = _read_json(self.phase12.report_path, "Phase 12 acceptance")
        phase13 = _read_json(self.phase13.report_path, "Phase 13 acceptance")
        phase14 = _read_json(self.phase14.report_path, "Phase 14 acceptance")
        strategy = self.strategy.resolve(as_of_date)
        cumulative = self.cumulative.resolve()
        analysis = self.analysis.resolve(
            as_of_date=as_of_date,
            cumulative=cumulative,
            expected_phase14_acceptance_sha256=sha256_file(self.phase14.report_path),
        )
        phase15 = self.phase15.resolve(as_of_date)

        external_classes = manifest.get("external_read_classes_used")
        external_classes_valid = isinstance(external_classes, list) and all(
            str(value) == MASSIVE_MARKET_REFERENCE_READS for value in external_classes
        ) and len(external_classes) <= 1
        source_fingerprint = manifest.get("source_fingerprint")
        source_payload_valid = False
        try:
            source_payload_valid = source_fingerprint == _stable_hash(self._source_payload(manifest))
        except KeyError:
            source_payload_valid = False

        checks = {
            "manifest_contract_exact": manifest.get("contract_version")
            == PHASE23_RUN_MANIFEST_CONTRACT_VERSION,
            "manifest_pass": manifest.get("pass") is True,
            "policy_fingerprint_exact": manifest.get("phase23_policy_fingerprint")
            == phase23_policy_fingerprint(),
            "as_of_exact": manifest.get("as_of_date") == as_of_date.isoformat(),
            "broker_context_exact": manifest.get("broker") == selected.value,
            "manifest_source_fingerprint_recomputed": source_payload_valid,
            "stage_hashes_recomputed_exact": stage_hashes == recomputed_stage_hashes,
            "archive_hashes_recomputed_exact": archive_hashes == recomputed_archive_hashes,
            "external_read_classes_narrow": external_classes_valid,
            "frozen_supported_set_empty": PHASE23_FROZEN_SUPPORTED_STRATEGIES == (),
            "strategy_handoff_reverified": strategy.promoted_count == 0
            and stage_hashes.get("strategy_handoff") == strategy.sha256,
            "current_candidate_manifest_pass": current.get("pass") is True,
            "current_promotions_zero": int(current.get("promoted_count", -1)) == 0
            and int(manifest.get("promoted_count", -1)) == 0,
            "phase12_zero_research_noop": phase12.get("pass") is True
            and int(phase12.get("research_case_count", -1)) == 0
            and phase12.get("historical_source_accessed") is False,
            "phase13_zero_case_noop": phase13.get("pass") is True
            and int(phase13.get("case_file_count", -1)) == 0
            and phase13.get("provider_initialized") is False
            and int(phase13.get("news_provider_calls", -1)) == 0
            and int(phase13.get("option_chain_provider_calls", -1)) == 0
            and int(phase13.get("portfolio_snapshot_reads", -1)) == 0,
            "phase14_zero_review_noop": phase14.get("pass") is True
            and int(phase14.get("ai_review_count", -1)) == 0
            and phase14.get("provider_initialized") is False
            and int(phase14.get("provider_calls", -1)) == 0,
            "analysis_handoff_reverified": stage_hashes.get("phase14_acceptance")
            == analysis.phase14_acceptance_sha256,
            "phase15_consumes_same_phase23_handoff": phase15.phase23_handoff is not None
            and phase15.phase23_handoff.sha256 == analysis.sha256
            and phase15.source_fingerprint == manifest.get("phase15_input_fingerprint"),
            "phase22_ready_cases_zero": phase15.execution_case_count == 0
            and int(manifest.get("phase22_ready_execution_case_count", -1)) == 0,
            "historical_study_not_rerun": manifest.get("historical_strategy_study_rerun") is False,
            "broker_reads_zero": int(manifest.get("broker_reads", -1)) == 0,
            "broker_writes_zero": int(manifest.get("broker_writes", -1)) == 0,
            "order_writes_zero": int(manifest.get("order_writes", -1)) == 0,
            "paper_submits_zero": int(manifest.get("paper_submits", -1)) == 0,
            "live_writes_zero": int(manifest.get("live_writes", -1)) == 0,
            "automatic_failover_disabled": manifest.get("automatic_broker_failover") is False,
        }
        failed = tuple(sorted(name for name, value in checks.items() if not value))
        report: dict[str, object] = {
            "contract_version": PHASE23_INDEPENDENT_VALIDATION_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "as_of_date": as_of_date.isoformat(),
            "broker": selected.value,
            "phase23_policy_fingerprint": phase23_policy_fingerprint(),
            "manifest_path": str(manifest_path.resolve()),
            "manifest_sha256": sha256_file(manifest_path),
            "recomputed_stage_hashes": recomputed_stage_hashes,
            "recomputed_archive_hashes": recomputed_archive_hashes,
            "checks": checks,
            "failed_checks": list(failed),
            "provider_calls": 0,
            "provider_mutation_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "pass": not failed,
        }
        path = self.report_path(as_of_date, selected)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
        report["report_path"] = str(path.resolve())
        if failed:
            raise Phase23IndependentValidationError(
                "Phase 23 independent persisted-run validation failed: " + ", ".join(failed)
            )
        return report
