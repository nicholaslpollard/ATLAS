from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.execution.order_builder import build_broker_order_plan
from packages.execution.phase15_policy import (
    PHASE15_AUTOMATIC_BROKER_FAILOVER,
    PHASE15_LIVE_EXECUTION_ENABLED,
    PHASE15_MAX_ADVERSE_ENTRY_DRIFT_R,
    PHASE15_MAX_QUOTE_AGE_SECONDS,
    PHASE15_MIN_EXECUTABLE_REWARD_TO_RISK,
    phase15_policy_fingerprint,
    phase15_policy_payload,
)
from packages.execution.phase15_run import (
    PHASE15_NO_CASE_DISPOSITION,
    PHASE15_RUN_MANIFEST_CONTRACT_VERSION,
    Phase15ExecutionRunEngine,
)
from packages.execution.phase15_source import Phase15ExecutionInputResolver
from packages.features.partition_store import sha256_file
from packages.portfolio.phase13_policy import (
    PHASE13_MAX_ABS_CORRELATION,
    PHASE13_MAX_GROSS_NOTIONAL_FRACTION,
    PHASE13_MAX_OPEN_POSITIONS,
    PHASE13_MAX_SINGLE_NAME_NOTIONAL_FRACTION,
    PHASE13_RISK_PER_TRADE_FRACTION,
)
from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.execution import BrokerName, ExecutionEnvironment, ExecutionIntent
from packages.schemas.execution_attempt import ExecutionAttemptRecord
from packages.schemas.execution_run import ExecutionCaseDisposition, ExecutionCaseDispositionRecord


PHASE15_VALIDATION_CONTRACT_VERSION = (
    "phase15-validation-v1-independent-lineage-intent-risk-idempotency-write-audit"
)


class Phase15ValidationError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise Phase15ValidationError(f"missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase15ValidationError(f"invalid JSON for {label}: {path}") from exc
    if not isinstance(value, dict):
        raise Phase15ValidationError(f"{label} must be a JSON object")
    return value


def _expected_intent_id(intent: ExecutionIntent) -> str:
    payload = {
        "phase13_case_sha256": intent.phase13_case_sha256,
        "phase14_acceptance_sha256": intent.phase14_acceptance_sha256,
        "environment": intent.environment.value,
        "broker": intent.broker.value,
        "ticker": intent.ticker,
        "quote_provider_timestamp_utc": intent.quote_provider_timestamp_utc.isoformat(),
        "quote_bid": float(intent.quote_bid),
        "quote_ask": float(intent.quote_ask),
        "entry_limit": float(intent.entry_limit),
        "quantity": int(intent.executable_quantity),
        "stop": float(intent.stop),
        "target": float(intent.target),
    }
    return "p15-" + _stable_hash(payload)


def _intent_matches_case(intent: ExecutionIntent, case: Any, case_sha: str, phase14_sha: str) -> bool:
    geometry = case.geometry
    risk = case.portfolio_risk
    if any(
        value is None
        for value in (
            geometry.reference_entry,
            geometry.stop,
            geometry.target,
            risk.proposed_risk_budget,
            risk.proposed_quantity,
        )
    ):
        return False
    reference = float(geometry.reference_entry)
    stop = float(geometry.stop)
    target = float(geometry.target)
    original_risk = abs(reference - stop)
    if case.direction == DiscoveryDirection.BULLISH:
        expected_entry = float(intent.quote_ask)
        adverse = max(0.0, expected_entry - reference) / original_risk
        executable_risk = expected_entry - stop
        executable_reward = target - expected_entry
    elif case.direction == DiscoveryDirection.BEARISH:
        expected_entry = float(intent.quote_bid)
        adverse = max(0.0, reference - expected_entry) / original_risk
        executable_risk = stop - expected_entry
        executable_reward = expected_entry - target
    else:
        return False
    if executable_risk <= 0.0 or executable_reward <= 0.0:
        return False
    rr = executable_reward / executable_risk
    quantity = min(
        int(risk.proposed_quantity),
        math.floor(float(risk.proposed_risk_budget) / executable_risk),
    )
    expected = (
        intent.instrument_id == case.instrument_id
        and intent.ticker == case.ticker
        and intent.as_of_date == case.as_of_date
        and intent.direction == case.direction
        and intent.phase13_case_sha256 == case_sha
        and intent.phase14_acceptance_sha256 == phase14_sha
        and math.isclose(intent.reference_entry, reference, rel_tol=1e-12, abs_tol=1e-12)
        and math.isclose(intent.entry_limit, expected_entry, rel_tol=1e-12, abs_tol=1e-12)
        and math.isclose(intent.stop, stop, rel_tol=1e-12, abs_tol=1e-12)
        and math.isclose(intent.target, target, rel_tol=1e-12, abs_tol=1e-12)
        and math.isclose(intent.original_risk_per_share, original_risk, rel_tol=1e-12, abs_tol=1e-12)
        and math.isclose(intent.executable_risk_per_share, executable_risk, rel_tol=1e-12, abs_tol=1e-12)
        and math.isclose(intent.executable_reward_per_share, executable_reward, rel_tol=1e-12, abs_tol=1e-12)
        and math.isclose(intent.adverse_entry_drift_r, adverse, rel_tol=1e-12, abs_tol=1e-12)
        and math.isclose(intent.executable_reward_to_risk, rr, rel_tol=1e-12, abs_tol=1e-12)
        and math.isclose(intent.accepted_risk_budget, float(risk.proposed_risk_budget), rel_tol=1e-12, abs_tol=1e-12)
        and intent.accepted_proposed_quantity == int(risk.proposed_quantity)
        and intent.executable_quantity == quantity
        and intent.adverse_entry_drift_r <= PHASE15_MAX_ADVERSE_ENTRY_DRIFT_R + 1e-12
        and intent.executable_reward_to_risk >= PHASE15_MIN_EXECUTABLE_REWARD_TO_RISK - 1e-12
        and intent.quote_age_seconds <= PHASE15_MAX_QUOTE_AGE_SECONDS + 1e-12
        and intent.quote_feed_mode == "realtime"
        and intent.quote_expected_delay_seconds == 0
        and intent.session_segment == "regular"
        and intent.live_execution_enabled is False
        and intent.intent_id == _expected_intent_id(intent)
    )
    return bool(expected)


def _risk_matches_attempt(attempt: ExecutionAttemptRecord) -> bool:
    risk = attempt.risk_revalidation
    reconciliation = attempt.reconciliation_before
    intent = attempt.intent
    account = reconciliation.account
    if attempt.existing_order_reused:
        return (
            risk.new_submission_evaluated is False
            and risk.admissible is False
            and attempt.provider_submission_performed is False
            and attempt.broker_write_count == 0
            and attempt.order_write_count == 0
        )
    equity = float(account.equity)
    if equity <= 0.0:
        return False
    same = [item for item in reconciliation.positions if item.ticker == intent.ticker]
    existing_value = sum(abs(float(item.market_value)) for item in same)
    loss = intent.executable_risk_per_share * intent.executable_quantity
    notional = intent.entry_limit * intent.executable_quantity
    projected_loss = loss / equity
    projected_single = (existing_value + notional) / equity
    projected_gross = (float(account.gross_market_value) + notional) / equity
    projected_positions = len(reconciliation.positions) + (0 if same else 1)
    corr = risk.max_abs_correlation
    admissible = (
        not same
        and projected_loss <= PHASE13_RISK_PER_TRADE_FRACTION + 1e-12
        and projected_single <= PHASE13_MAX_SINGLE_NAME_NOTIONAL_FRACTION + 1e-12
        and projected_gross <= PHASE13_MAX_GROSS_NOTIONAL_FRACTION + 1e-12
        and projected_positions <= PHASE13_MAX_OPEN_POSITIONS
        and (corr is None or corr <= PHASE13_MAX_ABS_CORRELATION + 1e-12)
        and (len(reconciliation.positions) == 0 or corr is not None)
    )
    return (
        risk.new_submission_evaluated is True
        and risk.admissible == admissible
        and math.isclose(risk.account_equity, equity, rel_tol=1e-12, abs_tol=1e-12)
        and math.isclose(risk.account_gross_market_value, float(account.gross_market_value), rel_tol=1e-12, abs_tol=1e-12)
        and risk.open_positions_before == len(reconciliation.positions)
        and math.isclose(risk.existing_same_name_market_value, existing_value, rel_tol=1e-12, abs_tol=1e-12)
        and math.isclose(risk.proposed_loss_at_stop, loss, rel_tol=1e-12, abs_tol=1e-12)
        and math.isclose(risk.proposed_notional, notional, rel_tol=1e-12, abs_tol=1e-12)
        and math.isclose(risk.projected_loss_fraction, projected_loss, rel_tol=1e-12, abs_tol=1e-12)
        and math.isclose(risk.projected_single_name_fraction, projected_single, rel_tol=1e-12, abs_tol=1e-12)
        and math.isclose(risk.projected_gross_fraction, projected_gross, rel_tol=1e-12, abs_tol=1e-12)
        and risk.projected_position_count == projected_positions
    )


class Phase15IndependentValidator:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.input_resolver = Phase15ExecutionInputResolver(settings)
        self.engine = Phase15ExecutionRunEngine(settings)
        self.root = self.engine.root
        self.report_path = self.root / "phase15_validation.json"

    def run(self, *, as_of_date: date | None = None) -> dict[str, object]:
        execution_input = self.input_resolver.resolve(as_of_date)
        manifest_path = self.engine.manifest_path(execution_input.as_of_date)
        manifest = _read_json(manifest_path, "Phase 15 execution manifest")
        if manifest.get("contract_version") != PHASE15_RUN_MANIFEST_CONTRACT_VERSION:
            raise Phase15ValidationError("Phase 15 execution manifest contract changed")
        if manifest.get("pass") is not True:
            raise Phase15ValidationError("Phase 15 execution manifest is not passing")

        checks: dict[str, bool] = {
            "accepted_phase14_input_reverified": dict(manifest.get("phase15_input") or {})
            == execution_input.public_dict(),
            "preregistered_policy_exact": manifest.get("policy") == phase15_policy_payload()
            and manifest.get("policy_fingerprint") == phase15_policy_fingerprint(),
            "execution_case_count_exact": int(manifest.get("execution_case_count", -1))
            == execution_input.execution_case_count,
            "automatic_broker_failover_absent": manifest.get("automatic_broker_failover_performed") is False
            and PHASE15_AUTOMATIC_BROKER_FAILOVER is False,
            "live_execution_not_promoted": PHASE15_LIVE_EXECUTION_ENABLED is False
            and int(manifest.get("live_writes", -1)) == 0,
            "provider_write_state_known": int(manifest.get("unknown_write_record_count", -1)) == 0
            and manifest.get("requires_reconciliation") is False,
            "production_ml_writes_zero": int(manifest.get("production_ml_writes", -1)) == 0,
        }
        raw_records = manifest.get("records")
        if not isinstance(raw_records, list):
            raise Phase15ValidationError("Phase 15 manifest records are malformed")
        if len(raw_records) != execution_input.execution_case_count:
            raise Phase15ValidationError("passing Phase 15 run must disposition every accepted execution case")

        record_checks: list[bool] = []
        intent_checks: list[bool] = []
        attempt_checks: list[bool] = []
        disposition_counts = {item.value: 0 for item in ExecutionCaseDisposition}
        known_broker_writes = 0
        known_order_writes = 0

        for index, (raw, case, case_sha) in enumerate(
            zip(
                raw_records,
                execution_input.phase13_cases,
                execution_input.phase13_case_sha256,
                strict=True,
            )
        ):
            try:
                record = ExecutionCaseDispositionRecord.model_validate(raw)
            except ValueError as exc:
                raise Phase15ValidationError(f"invalid Phase 15 disposition record {index}") from exc
            record_checks.append(
                record.instrument_id == case.instrument_id
                and record.ticker == case.ticker
                and record.as_of_date == case.as_of_date
                and record.phase13_case_sha256 == case_sha
                and record.environment != ExecutionEnvironment.LIVE
                and record.live_write_count == 0
            )
            disposition_counts[record.disposition.value] += 1
            known_broker_writes += record.broker_write_count or 0
            known_order_writes += record.order_write_count or 0

            intent: ExecutionIntent | None = None
            if record.intent_path is not None:
                intent_path = Path(record.intent_path)
                if not intent_path.is_file() or sha256_file(intent_path) != record.intent_sha256:
                    raise Phase15ValidationError("Phase 15 execution-intent artifact hash changed")
                intent = ExecutionIntent.model_validate_json(intent_path.read_text(encoding="utf-8"))
                intent_checks.append(
                    _intent_matches_case(
                        intent,
                        case,
                        case_sha,
                        execution_input.phase14_acceptance_sha256,
                    )
                    and intent.environment == record.environment
                    and intent.broker == record.broker
                )
            else:
                intent_checks.append(record.disposition == ExecutionCaseDisposition.BLOCKED)

            if record.attempt_path is not None:
                attempt_path = Path(record.attempt_path)
                if not attempt_path.is_file() or sha256_file(attempt_path) != record.attempt_sha256:
                    raise Phase15ValidationError("Phase 15 execution-attempt artifact hash changed")
                attempt = ExecutionAttemptRecord.model_validate_json(attempt_path.read_text(encoding="utf-8"))
                if intent is None:
                    raise Phase15ValidationError("execution attempt exists without immutable intent")
                expected_plan = build_broker_order_plan(intent)
                attempt_ok = (
                    attempt.intent == intent
                    and attempt.order_plan == expected_plan
                    and _risk_matches_attempt(attempt)
                    and attempt.live_submission_performed is False
                    and attempt.order_snapshot.client_order_id == expected_plan.client_order_id
                )
                if record.disposition == ExecutionCaseDisposition.PAPER_SUBMITTED:
                    attempt_ok = attempt_ok and (
                        intent.environment == ExecutionEnvironment.PAPER
                        and intent.broker in {BrokerName.WEBULL, BrokerName.ALPACA}
                        and attempt.provider_submission_performed is True
                        and record.broker_write_count == 1
                        and record.order_write_count == 1
                    )
                elif record.disposition == ExecutionCaseDisposition.SHADOW_EXECUTED:
                    attempt_ok = attempt_ok and (
                        intent.environment == ExecutionEnvironment.SHADOW
                        and intent.broker == BrokerName.SHADOW
                        and attempt.provider_submission_performed is False
                        and record.broker_write_count == 0
                        and record.order_write_count == 0
                    )
                elif record.disposition == ExecutionCaseDisposition.EXISTING_RECONCILED:
                    attempt_ok = attempt_ok and (
                        attempt.existing_order_reused is True
                        and attempt.provider_submission_performed is False
                        and record.broker_write_count == 0
                        and record.order_write_count == 0
                    )
                else:
                    attempt_ok = False
                attempt_checks.append(attempt_ok)
            else:
                attempt_checks.append(
                    record.disposition == ExecutionCaseDisposition.BLOCKED
                    and record.broker_write_count == 0
                    and record.order_write_count == 0
                )

        if execution_input.execution_case_count == 0:
            zero_noop = (
                manifest.get("selected_environment") is None
                and manifest.get("selected_broker") is None
                and int(manifest.get("record_count", -1)) == 0
                and manifest.get("quote_source_initialized") is False
                and int(manifest.get("quote_reads", -1)) == 0
                and manifest.get("broker_initialized") is False
                and int(manifest.get("provider_submission_attempts", -1)) == 0
                and int(manifest.get("known_broker_writes", -1)) == 0
                and int(manifest.get("known_order_writes", -1)) == 0
                and int(manifest.get("unknown_write_record_count", -1)) == 0
                and int(manifest.get("live_writes", -1)) == 0
                and manifest.get("execution_present") is False
                and manifest.get("no_case_disposition") == PHASE15_NO_CASE_DISPOSITION
            )
        else:
            zero_noop = True
            checks["explicit_broker_environment_selected"] = (
                manifest.get("selected_environment") in {"shadow", "paper"}
                and manifest.get("selected_broker") in {"shadow", "webull", "alpaca"}
            )

        checks.update(
            {
                "zero_case_noop_is_valid": zero_noop,
                "disposition_records_independently_validated": all(record_checks),
                "execution_intents_independently_recomputed": all(intent_checks),
                "attempts_and_current_risk_independently_recomputed": all(attempt_checks),
                "disposition_counts_exact": all(
                    int(manifest.get(f"{key.lower()}_count", 0)) == value
                    for key, value in disposition_counts.items()
                    if key != "PROVIDER_UNCERTAIN"
                )
                and int(manifest.get("provider_uncertain_count", 0))
                == disposition_counts["PROVIDER_UNCERTAIN"],
                "broker_write_count_exact": int(manifest.get("known_broker_writes", -1))
                == known_broker_writes,
                "order_write_count_exact": int(manifest.get("known_order_writes", -1))
                == known_order_writes,
            }
        )
        # Manifest names are intentionally human-readable and do not all match enum
        # spellings; validate the exact known counters separately.
        checks["execution_disposition_counters_exact"] = (
            int(manifest.get("blocked_count", -1)) == disposition_counts["BLOCKED"]
            and int(manifest.get("shadow_executed_count", -1)) == disposition_counts["SHADOW_EXECUTED"]
            and int(manifest.get("paper_submitted_count", -1)) == disposition_counts["PAPER_SUBMITTED"]
            and int(manifest.get("existing_reconciled_count", -1)) == disposition_counts["EXISTING_RECONCILED"]
            and int(manifest.get("provider_uncertain_count", -1)) == disposition_counts["PROVIDER_UNCERTAIN"]
        )
        # The generic key loop above intentionally excludes mismatched human names.
        checks["disposition_counts_exact"] = checks["execution_disposition_counters_exact"]

        passed = all(checks.values())
        source_payload = {
            "contract_version": PHASE15_VALIDATION_CONTRACT_VERSION,
            "as_of_date": execution_input.as_of_date.isoformat(),
            "manifest_sha256": sha256_file(manifest_path),
            "phase15_input_fingerprint": execution_input.source_fingerprint,
            "policy_fingerprint": phase15_policy_fingerprint(),
            "checks": checks,
        }
        report: dict[str, object] = {
            "contract_version": PHASE15_VALIDATION_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": _stable_hash(source_payload),
            "as_of_date": execution_input.as_of_date.isoformat(),
            "phase15_manifest_sha256": source_payload["manifest_sha256"],
            "phase15_input_fingerprint": execution_input.source_fingerprint,
            "execution_case_count": execution_input.execution_case_count,
            "record_count": len(raw_records),
            "checks": checks,
            "known_broker_writes": known_broker_writes,
            "known_order_writes": known_order_writes,
            "unknown_write_record_count": 0,
            "live_writes": 0,
            "automatic_broker_failover_performed": False,
            "production_ml_writes": 0,
            "pass": passed,
        }
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
        report["report_path"] = str(self.report_path.resolve())
        if not passed:
            failed = sorted(name for name, value in checks.items() if not value)
            raise Phase15ValidationError("Phase 15 independent validation failed: " + ", ".join(failed))
        return report
