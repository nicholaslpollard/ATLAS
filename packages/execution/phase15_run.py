from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Callable

from packages.brokers.alpaca import AlpacaPaperBroker
from packages.brokers.base import BrokerAdapter, BrokerAdapterError, BrokerSubmissionUncertain
from packages.brokers.paper.broker import ShadowBroker
from packages.brokers.webull import WebullSandboxBroker
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.execution.engine import ExecutionEngine, ExecutionEngineError
from packages.execution.order_builder import ExecutionIntentError, build_execution_intent
from packages.execution.phase15_policy import phase15_policy_fingerprint, phase15_policy_payload
from packages.execution.phase15_source import Phase15ExecutionInputResolver
from packages.execution.quote_source import ExecutionQuoteError, Phase15LiveQuoteResolver
from packages.execution.validator import ExecutionValidationError
from packages.features.partition_store import sha256_file
from packages.schemas.execution import BrokerName, ExecutionEnvironment, ExecutionIntent
from packages.schemas.execution_attempt import ExecutionAttemptRecord
from packages.schemas.execution_run import (
    ExecutionCaseDisposition,
    ExecutionCaseDispositionRecord,
)


PHASE15_RUN_MANIFEST_CONTRACT_VERSION = (
    "phase15-run-manifest-v1-explicit-broker-fresh-quote-idempotent-shadow-paper"
)
PHASE15_NO_CASE_DISPOSITION = "NO_ACCEPTED_PHASE14_EXECUTION_CASES"


class Phase15RunError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _default_broker_factory(environment: ExecutionEnvironment, broker: BrokerName) -> BrokerAdapter:
    if environment == ExecutionEnvironment.SHADOW and broker == BrokerName.SHADOW:
        return ShadowBroker()
    if environment == ExecutionEnvironment.PAPER and broker == BrokerName.WEBULL:
        return WebullSandboxBroker()
    if environment == ExecutionEnvironment.PAPER and broker == BrokerName.ALPACA:
        return AlpacaPaperBroker()
    raise Phase15RunError(f"unsupported Phase 15 broker/environment pair: {broker}/{environment}")


class Phase15ExecutionRunEngine:
    def __init__(
        self,
        settings: AtlasSettings,
        *,
        quote_resolver: Phase15LiveQuoteResolver | None = None,
        broker_factory: Callable[[ExecutionEnvironment, BrokerName], BrokerAdapter] | None = None,
    ) -> None:
        self.settings = settings
        self.input_resolver = Phase15ExecutionInputResolver(settings)
        self._quote_resolver = quote_resolver
        self._broker_factory = broker_factory or _default_broker_factory
        self.executor = ExecutionEngine()
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "execution" / "phase15" / "v1"

    def manifest_path(self, as_of_date: date) -> Path:
        return self.root / "manifests" / f"{as_of_date.year:04d}" / f"{as_of_date}.json"

    def case_dir(self, as_of_date: date, instrument_id: str) -> Path:
        safe = hashlib.sha256(instrument_id.encode("utf-8")).hexdigest()[:20]
        return self.root / "cases" / f"year={as_of_date.year:04d}" / f"date={as_of_date}" / safe

    @staticmethod
    def _write_model(path: Path, model: ExecutionIntent | ExecutionAttemptRecord) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, model.model_dump_json(indent=2) + "\n")
        return sha256_file(path)

    def run(
        self,
        *,
        as_of_date: date | None = None,
        environment: ExecutionEnvironment | str | None = None,
        broker: BrokerName | str | None = None,
        max_abs_correlations: dict[str, float] | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> dict[str, object]:
        execution_input = self.input_resolver.resolve(as_of_date)
        policy = phase15_policy_payload()
        policy_fp = phase15_policy_fingerprint()
        records: list[ExecutionCaseDispositionRecord] = []
        broker_adapter: BrokerAdapter | None = None
        quote_resolver: Phase15LiveQuoteResolver | None = None
        provider_uncertain = False

        if progress is not None:
            progress(
                f"accepted Phase 14 execution cases: {execution_input.execution_case_count} on {execution_input.as_of_date}"
            )

        if execution_input.execution_case_count == 0:
            if progress is not None:
                progress("no accepted Phase 14 execution cases; live quote and broker initialization skipped")
            selected_environment = None
            selected_broker = None
        else:
            if environment is None or broker is None:
                raise Phase15RunError("nonzero Phase 15 run requires explicit environment and broker selection")
            selected_environment = ExecutionEnvironment(environment)
            selected_broker = BrokerName(broker)
            if selected_environment == ExecutionEnvironment.LIVE:
                raise Phase15RunError("Phase 15 live execution is not promoted")
            if selected_environment == ExecutionEnvironment.SHADOW and selected_broker != BrokerName.SHADOW:
                raise Phase15RunError("shadow environment requires the shadow broker")
            if selected_environment == ExecutionEnvironment.PAPER and selected_broker not in {
                BrokerName.WEBULL,
                BrokerName.ALPACA,
            }:
                raise Phase15RunError("paper environment requires Webull or Alpaca")
            quote_resolver = self._quote_resolver or Phase15LiveQuoteResolver(self.settings)

            for index, (case, case_sha) in enumerate(
                zip(
                    execution_input.phase13_cases,
                    execution_input.phase13_case_sha256,
                    strict=True,
                ),
                start=1,
            ):
                if progress is not None:
                    progress(f"Phase 15 case {index}/{execution_input.execution_case_count}: {case.ticker}")
                case_dir = self.case_dir(case.as_of_date, case.instrument_id)
                intent_path: Path | None = None
                intent_sha: str | None = None
                broker_initialized_for_record = broker_adapter is not None
                try:
                    quote = quote_resolver.quote(case.ticker)
                    intent = build_execution_intent(
                        case,
                        phase13_case_sha256=case_sha,
                        phase14_acceptance_sha256=execution_input.phase14_acceptance_sha256,
                        quote=quote,
                        environment=selected_environment,
                        broker=selected_broker,
                    )
                    intent_path = case_dir / "execution_intent.json"
                    intent_sha = self._write_model(intent_path, intent)
                except (ExecutionQuoteError, ExecutionIntentError, ValueError) as exc:
                    records.append(
                        ExecutionCaseDispositionRecord(
                            instrument_id=case.instrument_id,
                            ticker=case.ticker,
                            as_of_date=case.as_of_date,
                            phase13_case_sha256=case_sha,
                            environment=selected_environment,
                            broker=selected_broker,
                            disposition=ExecutionCaseDisposition.BLOCKED,
                            intent_path=str(intent_path.resolve()) if intent_path is not None else None,
                            intent_sha256=intent_sha,
                            attempt_path=None,
                            attempt_sha256=None,
                            quote_read=True,
                            broker_initialized=broker_initialized_for_record,
                            provider_submission_attempted=False,
                            provider_submission_uncertain=False,
                            broker_write_count=0,
                            order_write_count=0,
                            live_write_count=0,
                            reason_codes=(
                                "EXECUTION_BLOCKED_BEFORE_BROKER_SUBMISSION",
                                f"{type(exc).__name__.upper()}",
                            ),
                        )
                    )
                    continue

                if broker_adapter is None:
                    try:
                        broker_adapter = self._broker_factory(selected_environment, selected_broker)
                    except Exception as exc:
                        raise Phase15RunError("explicit Phase 15 broker initialization failed") from exc
                broker_initialized_for_record = True
                correlation = None if max_abs_correlations is None else max_abs_correlations.get(case.instrument_id)
                try:
                    attempt = self.executor.attempt(
                        intent,
                        broker_adapter,
                        max_abs_correlation=correlation,
                    )
                except BrokerSubmissionUncertain as exc:
                    provider_uncertain = True
                    records.append(
                        ExecutionCaseDispositionRecord(
                            instrument_id=case.instrument_id,
                            ticker=case.ticker,
                            as_of_date=case.as_of_date,
                            phase13_case_sha256=case_sha,
                            environment=selected_environment,
                            broker=selected_broker,
                            disposition=ExecutionCaseDisposition.PROVIDER_UNCERTAIN,
                            intent_path=str(intent_path.resolve()),
                            intent_sha256=intent_sha,
                            attempt_path=None,
                            attempt_sha256=None,
                            quote_read=True,
                            broker_initialized=True,
                            provider_submission_attempted=True,
                            provider_submission_uncertain=True,
                            broker_write_count=None,
                            order_write_count=None,
                            live_write_count=0,
                            reason_codes=(
                                "PROVIDER_SUBMISSION_OUTCOME_UNCERTAIN",
                                "DETERMINISTIC_CLIENT_ID_RECONCILIATION_REQUIRED",
                                "AUTOMATIC_RETRY_AND_FAILOVER_FORBIDDEN",
                                type(exc).__name__.upper(),
                            ),
                        )
                    )
                    # Exposure state is now uncertain. Do not process another candidate.
                    break
                except (ExecutionEngineError, ExecutionValidationError, BrokerAdapterError) as exc:
                    attempted = bool(
                        isinstance(exc, ExecutionEngineError)
                        and exc.provider_submission_attempted
                    )
                    stage = exc.stage if isinstance(exc, ExecutionEngineError) else type(exc).__name__
                    records.append(
                        ExecutionCaseDispositionRecord(
                            instrument_id=case.instrument_id,
                            ticker=case.ticker,
                            as_of_date=case.as_of_date,
                            phase13_case_sha256=case_sha,
                            environment=selected_environment,
                            broker=selected_broker,
                            disposition=ExecutionCaseDisposition.BLOCKED,
                            intent_path=str(intent_path.resolve()),
                            intent_sha256=intent_sha,
                            attempt_path=None,
                            attempt_sha256=None,
                            quote_read=True,
                            broker_initialized=True,
                            provider_submission_attempted=attempted,
                            provider_submission_uncertain=False,
                            broker_write_count=0,
                            order_write_count=0,
                            live_write_count=0,
                            reason_codes=(
                                "EXECUTION_BLOCKED_FAIL_CLOSED",
                                f"STAGE_{str(stage).upper()}",
                                type(exc).__name__.upper(),
                            ),
                        )
                    )
                    continue

                attempt_path = case_dir / "execution_attempt.json"
                attempt_sha = self._write_model(attempt_path, attempt)
                if attempt.existing_order_reused:
                    disposition = ExecutionCaseDisposition.EXISTING_RECONCILED
                elif selected_environment == ExecutionEnvironment.SHADOW:
                    disposition = ExecutionCaseDisposition.SHADOW_EXECUTED
                else:
                    disposition = ExecutionCaseDisposition.PAPER_SUBMITTED
                records.append(
                    ExecutionCaseDispositionRecord(
                        instrument_id=case.instrument_id,
                        ticker=case.ticker,
                        as_of_date=case.as_of_date,
                        phase13_case_sha256=case_sha,
                        environment=selected_environment,
                        broker=selected_broker,
                        disposition=disposition,
                        intent_path=str(intent_path.resolve()),
                        intent_sha256=intent_sha,
                        attempt_path=str(attempt_path.resolve()),
                        attempt_sha256=attempt_sha,
                        quote_read=True,
                        broker_initialized=True,
                        provider_submission_attempted=attempt.provider_submission_performed,
                        provider_submission_uncertain=False,
                        broker_write_count=attempt.broker_write_count,
                        order_write_count=attempt.order_write_count,
                        live_write_count=0,
                        reason_codes=(
                            "EXECUTION_ATTEMPT_SCHEMA_VALIDATED",
                            "DETERMINISTIC_CLIENT_ORDER_ID",
                            "LIVE_EXECUTION_ABSENT",
                        ),
                    )
                )

        known_broker_writes = sum(item.broker_write_count or 0 for item in records)
        known_order_writes = sum(item.order_write_count or 0 for item in records)
        unknown_write_records = sum(
            1
            for item in records
            if item.broker_write_count is None or item.order_write_count is None
        )
        quote_reads = quote_resolver.read_count if quote_resolver is not None else 0
        source_payload = {
            "contract_version": PHASE15_RUN_MANIFEST_CONTRACT_VERSION,
            "as_of_date": execution_input.as_of_date.isoformat(),
            "phase15_input_fingerprint": execution_input.source_fingerprint,
            "policy_fingerprint": policy_fp,
            "environment": selected_environment.value if selected_environment is not None else None,
            "broker": selected_broker.value if selected_broker is not None else None,
            "record_hashes": [
                _stable_hash(item.model_dump(mode="json")) for item in records
            ],
        }
        manifest: dict[str, object] = {
            "contract_version": PHASE15_RUN_MANIFEST_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": _stable_hash(source_payload),
            "as_of_date": execution_input.as_of_date.isoformat(),
            "phase15_input": execution_input.public_dict(),
            "policy": policy,
            "policy_fingerprint": policy_fp,
            "execution_case_count": execution_input.execution_case_count,
            "selected_environment": selected_environment.value if selected_environment is not None else None,
            "selected_broker": selected_broker.value if selected_broker is not None else None,
            "records": [item.model_dump(mode="json") for item in records],
            "record_count": len(records),
            "blocked_count": sum(1 for item in records if item.disposition == ExecutionCaseDisposition.BLOCKED),
            "shadow_executed_count": sum(1 for item in records if item.disposition == ExecutionCaseDisposition.SHADOW_EXECUTED),
            "paper_submitted_count": sum(1 for item in records if item.disposition == ExecutionCaseDisposition.PAPER_SUBMITTED),
            "existing_reconciled_count": sum(1 for item in records if item.disposition == ExecutionCaseDisposition.EXISTING_RECONCILED),
            "provider_uncertain_count": sum(1 for item in records if item.disposition == ExecutionCaseDisposition.PROVIDER_UNCERTAIN),
            "quote_source_initialized": quote_resolver is not None,
            "quote_reads": quote_reads,
            "broker_initialized": broker_adapter is not None,
            "provider_submission_attempts": sum(1 for item in records if item.provider_submission_attempted),
            "known_broker_writes": known_broker_writes,
            "known_order_writes": known_order_writes,
            "unknown_write_record_count": unknown_write_records,
            "live_writes": 0,
            "automatic_broker_failover_performed": False,
            "execution_present": any(
                item.disposition
                in {
                    ExecutionCaseDisposition.SHADOW_EXECUTED,
                    ExecutionCaseDisposition.PAPER_SUBMITTED,
                    ExecutionCaseDisposition.EXISTING_RECONCILED,
                    ExecutionCaseDisposition.PROVIDER_UNCERTAIN,
                }
                for item in records
            ),
            "requires_reconciliation": provider_uncertain,
            "no_case_disposition": (
                PHASE15_NO_CASE_DISPOSITION
                if execution_input.execution_case_count == 0
                else None
            ),
            "pass": not provider_uncertain,
        }
        path = self.manifest_path(execution_input.as_of_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n")
        manifest["manifest_path"] = str(path.resolve())
        return manifest
