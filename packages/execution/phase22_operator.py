from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Callable

from packages.core.settings import AtlasSettings
from packages.execution.phase15_run import Phase15ExecutionRunEngine, Phase15RunError
from packages.execution.phase21_authority import (
    Phase21AuthorizationError,
    Phase21PaperExecutionChallenge,
    authorize_phase21_paper_execution,
    require_phase21_paper_execution_authority,
)
from packages.schemas.execution import BrokerName, ExecutionEnvironment


PHASE22_POLICY_CONTRACT_VERSION = (
    "phase22-policy-v1-operational-paper-runner-webull-primary-explicit-run-authority"
)
PHASE22_DEFAULT_BROKER = BrokerName.WEBULL
PHASE22_ENVIRONMENT = ExecutionEnvironment.PAPER
PHASE22_LIVE_EXECUTION_ENABLED = False
PHASE22_AUTOMATIC_BROKER_FAILOVER = False
PHASE22_BROWSER_EXECUTION_ENABLED = False
PHASE22_SCHEDULER_EXECUTION_ENABLED = False
PHASE22_ARBITRARY_CASE_INPUT_ALLOWED = False
PHASE22_ALLOWED_BROKERS = (BrokerName.WEBULL, BrokerName.ALPACA)


class Phase22OperatorError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def phase22_policy_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE22_POLICY_CONTRACT_VERSION,
        "environment": PHASE22_ENVIRONMENT.value,
        "default_broker": PHASE22_DEFAULT_BROKER.value,
        "allowed_brokers": [item.value for item in PHASE22_ALLOWED_BROKERS],
        "live_execution_enabled": PHASE22_LIVE_EXECUTION_ENABLED,
        "automatic_broker_failover": PHASE22_AUTOMATIC_BROKER_FAILOVER,
        "browser_execution_enabled": PHASE22_BROWSER_EXECUTION_ENABLED,
        "scheduler_execution_enabled": PHASE22_SCHEDULER_EXECUTION_ENABLED,
        "arbitrary_case_input_allowed": PHASE22_ARBITRARY_CASE_INPUT_ALLOWED,
        "accepted_input_authority": "PHASE15_RESOLVED_PHASE13_PHASE14_ONLY",
        "paper_submit_authority": "PHASE21_EXACT_RUN_SCOPED_CONFIRMATION",
        "confirmation_transport": "INTERACTIVE_STDIN_NOT_COMMAND_LINE_ARGUMENT",
        "zero_case_behavior": "NO_PROVIDER_INITIALIZATION_NO_AUTHORITY_REQUIRED",
        "provider_uncertainty": "STOP_NO_RETRY_NO_FAILOVER_RECONCILIATION_REQUIRED",
        "outcome_persistence": "PHASE15_IMMUTABLE_OUTCOME_STORE",
        "observability": "PHASE19_READS_PHASE15_LOCAL_OUTCOMES",
    }


def phase22_policy_fingerprint() -> str:
    return _stable_hash(phase22_policy_payload())


def _normalize_broker(broker: BrokerName | str) -> BrokerName:
    normalized = BrokerName(broker)
    if normalized not in PHASE22_ALLOWED_BROKERS:
        raise Phase22OperatorError("Phase 22 PAPER operation supports only Webull or Alpaca")
    return normalized


@dataclass(frozen=True)
class Phase22PaperRunPreparation:
    as_of_date: date
    broker: BrokerName
    execution_case_count: int
    authority_required: bool
    challenge: Phase21PaperExecutionChallenge | None

    def public_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "phase22_policy_fingerprint": phase22_policy_fingerprint(),
            "as_of_date": self.as_of_date.isoformat(),
            "broker": self.broker.value,
            "environment": PHASE22_ENVIRONMENT.value,
            "execution_case_count": self.execution_case_count,
            "authority_required": self.authority_required,
            "live_execution_enabled": False,
            "automatic_broker_failover": False,
        }
        if self.challenge is not None:
            payload["phase21_challenge"] = self.challenge.public_dict()
        else:
            payload["phase21_challenge"] = None
        return payload


@dataclass(frozen=True)
class Phase22PaperRunResult:
    as_of_date: date
    broker: BrokerName
    execution_case_count: int
    record_count: int
    blocked_count: int
    paper_submitted_count: int
    existing_reconciled_count: int
    provider_uncertain_count: int
    provider_submission_attempts: int
    known_broker_writes: int
    known_order_writes: int
    unknown_write_record_count: int
    requires_reconciliation: bool
    passed: bool
    manifest_path: str
    source_fingerprint: str

    @classmethod
    def from_manifest(cls, manifest: dict[str, object], *, broker: BrokerName) -> "Phase22PaperRunResult":
        return cls(
            as_of_date=date.fromisoformat(str(manifest["as_of_date"])),
            broker=broker,
            execution_case_count=int(manifest.get("execution_case_count") or 0),
            record_count=int(manifest.get("record_count") or 0),
            blocked_count=int(manifest.get("blocked_count") or 0),
            paper_submitted_count=int(manifest.get("paper_submitted_count") or 0),
            existing_reconciled_count=int(manifest.get("existing_reconciled_count") or 0),
            provider_uncertain_count=int(manifest.get("provider_uncertain_count") or 0),
            provider_submission_attempts=int(manifest.get("provider_submission_attempts") or 0),
            known_broker_writes=int(manifest.get("known_broker_writes") or 0),
            known_order_writes=int(manifest.get("known_order_writes") or 0),
            unknown_write_record_count=int(manifest.get("unknown_write_record_count") or 0),
            requires_reconciliation=bool(manifest.get("requires_reconciliation")),
            passed=bool(manifest.get("pass")),
            manifest_path=str(manifest.get("manifest_path") or ""),
            source_fingerprint=str(manifest.get("source_fingerprint") or ""),
        )

    def public_dict(self) -> dict[str, object]:
        return {
            "phase22_policy_fingerprint": phase22_policy_fingerprint(),
            "as_of_date": self.as_of_date.isoformat(),
            "broker": self.broker.value,
            "environment": PHASE22_ENVIRONMENT.value,
            "execution_case_count": self.execution_case_count,
            "record_count": self.record_count,
            "blocked_count": self.blocked_count,
            "paper_submitted_count": self.paper_submitted_count,
            "existing_reconciled_count": self.existing_reconciled_count,
            "provider_uncertain_count": self.provider_uncertain_count,
            "provider_submission_attempts": self.provider_submission_attempts,
            "known_broker_writes": self.known_broker_writes,
            "known_order_writes": self.known_order_writes,
            "unknown_write_record_count": self.unknown_write_record_count,
            "requires_reconciliation": self.requires_reconciliation,
            "pass": self.passed,
            "manifest_path": self.manifest_path,
            "source_fingerprint": self.source_fingerprint,
            "live_execution_enabled": False,
            "automatic_broker_failover": False,
        }


class Phase22PaperOperator:
    """Operator binding over the already-accepted Phase 15 + Phase 21 PAPER path.

    This coordinator deliberately owns no broker adapter, quote client, order geometry,
    strategy input, or provider-submit implementation. It only resolves accepted Phase 15
    input, prepares the exact Phase 21 challenge, validates explicit run authority, and
    delegates to Phase15ExecutionRunEngine.
    """

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        run_engine: Phase15ExecutionRunEngine | None = None,
    ) -> None:
        self.settings = settings
        self.run_engine = run_engine or Phase15ExecutionRunEngine(settings)

    def prepare(
        self,
        *,
        as_of_date: date | None = None,
        broker: BrokerName | str = PHASE22_DEFAULT_BROKER,
    ) -> Phase22PaperRunPreparation:
        selected_broker = _normalize_broker(broker)
        execution_input = self.run_engine.input_resolver.resolve(as_of_date)
        if execution_input.execution_case_count == 0:
            return Phase22PaperRunPreparation(
                as_of_date=execution_input.as_of_date,
                broker=selected_broker,
                execution_case_count=0,
                authority_required=False,
                challenge=None,
            )
        challenge = self.run_engine.prepare_paper_execution_challenge(
            as_of_date=execution_input.as_of_date,
            broker=selected_broker,
        )
        return Phase22PaperRunPreparation(
            as_of_date=execution_input.as_of_date,
            broker=selected_broker,
            execution_case_count=execution_input.execution_case_count,
            authority_required=True,
            challenge=challenge,
        )

    def execute(
        self,
        preparation: Phase22PaperRunPreparation,
        *,
        confirmation: str = "",
        progress: Callable[[str], None] | None = None,
    ) -> Phase22PaperRunResult:
        selected_broker = _normalize_broker(preparation.broker)
        paper_authority = None
        if preparation.authority_required:
            challenge = preparation.challenge
            if challenge is None:
                raise Phase22OperatorError("Phase 22 preparation requires a missing Phase 21 challenge")
            paper_authority = authorize_phase21_paper_execution(
                challenge,
                explicitly_authorized=True,
                confirmation=confirmation,
            )
            try:
                require_phase21_paper_execution_authority(
                    paper_authority,
                    expected_execution_scope_id=challenge.execution_scope_id,
                    broker=selected_broker,
                    environment=PHASE22_ENVIRONMENT,
                )
            except Phase21AuthorizationError as exc:
                raise Phase22OperatorError(
                    "exact Phase 21 run-scoped PAPER confirmation was not satisfied"
                ) from exc
        elif confirmation:
            raise Phase22OperatorError("zero-case Phase 22 run does not accept mutation authority")

        try:
            manifest = self.run_engine.run(
                as_of_date=preparation.as_of_date,
                environment=PHASE22_ENVIRONMENT,
                broker=selected_broker,
                paper_authority=paper_authority,
                progress=progress,
            )
        except Phase15RunError as exc:
            raise Phase22OperatorError("Phase 22 delegated PAPER run failed closed") from exc

        result = Phase22PaperRunResult.from_manifest(manifest, broker=selected_broker)
        if result.as_of_date != preparation.as_of_date:
            raise Phase22OperatorError("Phase 22 run result as-of date drifted from preparation")
        if result.execution_case_count != preparation.execution_case_count:
            raise Phase22OperatorError("Phase 22 accepted execution-case population changed after preparation")
        if result.provider_uncertain_count or result.requires_reconciliation:
            raise Phase22OperatorError(
                "PAPER provider state is uncertain; stop without retry/failover and reconcile exact client ids"
            )
        return result
