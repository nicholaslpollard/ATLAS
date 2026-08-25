from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Callable

from packages.analogues.engine import DeepCandidateResearchEngine
from packages.analogues.phase12_validation import Phase12IndependentValidator
from packages.analogues.policy import (
    PHASE12_BROKER_WRITES,
    PHASE12_PRODUCTION_ML_WRITES,
    PHASE12_TRADE_GEOMETRY_PRESENT,
)
from packages.analogues.source import Phase12ResearchInputResolver
from packages.backtesting.phase11_closeout import PHASE11_CLOSEOUT_CONTRACT_VERSION
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.operations.phase23_strategy import PHASE23_CURRENT_STRATEGY_HANDOFF_CONTRACT_VERSION


PHASE12_CLOSEOUT_CONTRACT_VERSION = (
    "phase12-closeout-v1-promoted-only-deep-research-independent-validation"
)
PHASE12_NEXT_PHASE = "PHASE_13_CONTEXT_INSTRUMENT_GEOMETRY_PORTFOLIO_RISK"


class Phase12CloseoutError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def phase12_acceptance_checks(
    *,
    research: dict[str, object],
    validation: dict[str, object],
) -> dict[str, bool]:
    validation_checks = dict(validation.get("checks") or {})
    promoted = int(research.get("promoted_input_count", -1))
    cases = int(research.get("research_case_count", -1))
    return {
        "research_manifest_pass": research.get("pass") is True,
        "promoted_only_case_count_exact": promoted == cases,
        "zero_candidate_noop_is_valid": promoted != 0
        or (
            cases == 0
            and research.get("historical_source_accessed") is False
            and research.get("no_candidate_disposition") == "NO_PHASE11_PROMOTED_CANDIDATES"
        ),
        "independent_validation_pass": validation.get("pass") is True,
        "accepted_phase11_input_reverified": validation_checks.get(
            "accepted_phase11_input_reverified"
        )
        is True,
        "preregistered_policy_exact": validation_checks.get("preregistered_policy_exact") is True,
        "case_evidence_independently_recomputed": validation_checks.get(
            "case_evidence_independently_recomputed"
        )
        is True,
        "research_only_not_trade_signal": research.get("research_only_not_trade_signal") is True,
        "trade_geometry_absent": research.get("trade_geometry_present") is PHASE12_TRADE_GEOMETRY_PRESENT,
        "production_ml_writes_zero": int(research.get("production_ml_writes", -1)) == 0
        and int(validation.get("production_ml_writes", -1)) == 0
        and PHASE12_PRODUCTION_ML_WRITES == 0,
        "broker_writes_zero": int(research.get("broker_writes", -1)) == 0
        and int(validation.get("broker_writes", -1)) == 0
        and PHASE12_BROKER_WRITES == 0,
    }


class Phase12Closeout:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.input_resolver = Phase12ResearchInputResolver(settings)
        self.engine = DeepCandidateResearchEngine(settings)
        self.validator = Phase12IndependentValidator(settings)
        self.root = self.engine.root
        self.report_path = self.root / "phase12_final_acceptance.json"

    def run(
        self,
        *,
        as_of_date: date | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> dict[str, object]:
        research_input = self.input_resolver.resolve(as_of_date)
        if progress is not None:
            progress(
                f"accepted strategy promotions: {research_input.promoted_count} on {research_input.as_of_date}"
            )
        research = self.engine.run(as_of_date=research_input.as_of_date, progress=progress)
        if research.get("pass") is not True:
            raise Phase12CloseoutError("Phase 12 deep research manifest failed")
        if progress is not None:
            progress("independent validator: recomputing Phase 12 evidence")
        validation = self.validator.run(as_of_date=research_input.as_of_date)
        if validation.get("pass") is not True:
            raise Phase12CloseoutError("Phase 12 independent validation failed")
        checks = phase12_acceptance_checks(research=research, validation=validation)
        if not all(checks.values()):
            failed = sorted(name for name, value in checks.items() if not value)
            raise Phase12CloseoutError("Phase 12 closeout checks failed: " + ", ".join(failed))

        strategy_payload = json.loads(
            research_input.phase11_acceptance_path.read_text(encoding="utf-8")
        )
        strategy_contract = strategy_payload.get("contract_version")
        if strategy_contract not in {
            PHASE11_CLOSEOUT_CONTRACT_VERSION,
            PHASE23_CURRENT_STRATEGY_HANDOFF_CONTRACT_VERSION,
        }:
            raise Phase12CloseoutError("accepted strategy-authority contract changed during closeout")
        source_payload = {
            "contract_version": PHASE12_CLOSEOUT_CONTRACT_VERSION,
            "as_of_date": research_input.as_of_date.isoformat(),
            "strategy_authority_contract_version": strategy_contract,
            "strategy_authority_sha256": research_input.phase11_acceptance_sha256,
            "phase11_acceptance_sha256": research_input.phase11_acceptance_sha256,
            "research_manifest_sha256": sha256_file(self.engine.manifest_path(research_input.as_of_date)),
            "validation_sha256": sha256_file(self.validator.report_path),
            "checks": checks,
        }
        report: dict[str, object] = {
            "contract_version": PHASE12_CLOSEOUT_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": _stable_hash(source_payload),
            "as_of_date": research_input.as_of_date.isoformat(),
            "strategy_authority_contract_version": strategy_contract,
            "strategy_authority_sha256": research_input.phase11_acceptance_sha256,
            "phase11_acceptance_sha256": research_input.phase11_acceptance_sha256,
            "phase12_research_manifest_sha256": source_payload["research_manifest_sha256"],
            "phase12_validation_sha256": source_payload["validation_sha256"],
            "phase11_promoted_count": research_input.promoted_count,
            "research_case_count": int(research["research_case_count"]),
            "research_complete_count": int(research["research_complete_count"]),
            "research_limited_count": int(research["research_limited_count"]),
            "historical_source_accessed": bool(research["historical_source_accessed"]),
            "zero_candidate_noop": research_input.promoted_count == 0,
            "checks": checks,
            "production_ml_writes": 0,
            "broker_writes": 0,
            "trade_geometry_present": False,
            "execution_present": False,
            "final_disposition": {
                "phase12_accepted": True,
                "phase11_promoted_candidates_remain_research_cases_not_orders": True,
                "no_candidates_does_not_trigger_threshold_relaxation": True,
                "deep_research_is_evidence_only": True,
                "next_phase": PHASE12_NEXT_PHASE,
            },
            "pass": True,
        }
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
        report["report_path"] = str(self.report_path.resolve())
        return report
