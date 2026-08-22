from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from packages.control_plane.action_ledger import ControlPlaneActionLedger
from packages.control_plane.phase16_closeout import (
    PHASE16_CLOSEOUT_CONTRACT_VERSION,
    Phase16Closeout,
    Phase16CloseoutError,
)
from packages.control_plane.phase16_smoke import (
    PHASE16_OPERATIONAL_SMOKE_CONTRACT_VERSION,
    Phase16OperationalSmoke,
)
from packages.control_plane.phase16_validation import (
    PHASE16_INDEPENDENT_VALIDATION_CONTRACT_VERSION,
    Phase16IndependentValidator,
)
from packages.core.settings import load_settings
from packages.execution.phase15_closeout import PHASE15_CLOSEOUT_CONTRACT_VERSION
from packages.execution.phase15_foundation import PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT
from packages.execution.phase15_policy import phase15_policy_fingerprint
from packages.schemas.control_plane import (
    ControlPlaneActionKind,
    ControlPlaneActionRequest,
    ControlPlaneActionState,
)
from packages.schemas.execution import BrokerName, ExecutionEnvironment


NOW = datetime(2026, 8, 22, 23, 0, tzinfo=UTC)


def _settings(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(update={"derived": tmp_path})
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


def _write_phase15_acceptance(tmp_path) -> None:
    root = tmp_path / "execution" / "phase15" / "v1"
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "contract_version": PHASE15_CLOSEOUT_CONTRACT_VERSION,
        "pass": True,
        "as_of_date": "2026-08-14",
        "phase15_policy_fingerprint": phase15_policy_fingerprint(),
        "cumulative_foundation_fingerprint": PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT,
        "execution_case_count": 0,
        "final_disposition": {
            "phase15_accepted": True,
            "actual_broker_execution_exercised_in_acceptance": False,
            "live_execution_promoted": False,
            "automatic_cross_broker_failover_allowed": False,
        },
    }
    (root / "phase15_final_acceptance.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_independent_phase16_validator_is_provider_inert(tmp_path) -> None:
    settings = _settings(tmp_path)
    report = Phase16IndependentValidator(settings).run(write_report=True)
    assert report["contract_version"] == PHASE16_INDEPENDENT_VALIDATION_CONTRACT_VERSION
    assert report["pass"] is True
    assert report["provider_calls"] == 0
    assert report["provider_writes"] == 0
    assert report["live_writes"] == 0
    assert len(report["implementation_fingerprint"]) == 64
    assert all(report["checks"].values())


def test_default_operational_smoke_forbids_provider_initialization(tmp_path) -> None:
    _write_phase15_acceptance(tmp_path)
    settings = _settings(tmp_path)
    report = Phase16OperationalSmoke(settings).run(
        refresh_brokers=False,
        write_report=True,
    )
    assert report["contract_version"] == PHASE16_OPERATIONAL_SMOKE_CONTRACT_VERSION
    assert report["pass"] is True
    assert report["broker_refresh_requested"] is False
    assert report["provider_factory_calls"] == 0
    assert report["provider_mutation_endpoint_invocations"] == 0
    assert report["provider_writes"] == 0
    assert report["live_writes"] == 0
    assert all(report["checks"].values())


def test_provider_readonly_smoke_has_separate_output_artifact(tmp_path) -> None:
    settings = _settings(tmp_path)
    smoke = Phase16OperationalSmoke(settings)
    acceptance_path = smoke.output_path(refresh_brokers=False)
    readonly_path = smoke.output_path(refresh_brokers=True)
    assert acceptance_path == smoke.report_path
    assert acceptance_path.name == "phase16_operational_smoke.json"
    assert readonly_path == smoke.readonly_report_path
    assert readonly_path.name == "phase16_provider_readonly_smoke.json"
    assert readonly_path != acceptance_path


def test_phase16_closeout_accepts_empty_control_plane_without_provider_activity(tmp_path) -> None:
    _write_phase15_acceptance(tmp_path)
    settings = _settings(tmp_path)
    report = Phase16Closeout(settings).run()
    assert report["contract_version"] == PHASE16_CLOSEOUT_CONTRACT_VERSION
    assert report["pass"] is True
    assert len(report["git_head_sha"]) == 40
    assert len(report["implementation_fingerprint"]) == 64
    assert report["active_action_count"] == 0
    assert report["uncertain_action_count"] == 0
    assert report["provider_read_refresh_exercised_in_acceptance"] is False
    assert report["provider_factory_calls"] == 0
    assert report["provider_write_attempt_count"] == 0
    assert report["provider_write_uncertain_count"] == 0
    assert report["provider_mutation_endpoint_invocations"] == 0
    assert report["broker_writes"] == 0
    assert report["order_writes"] == 0
    assert report["position_writes"] == 0
    assert report["live_writes"] == 0
    final = report["final_disposition"]
    assert final["phase16_accepted"] is True
    assert final["actual_provider_mutation_exercised_in_acceptance"] is False
    assert final["cleanup_provider_writes_promoted"] is False
    assert final["live_execution_promoted"] is False
    assert all(report["checks"].values())


def test_phase16_closeout_refuses_nonterminal_action(tmp_path) -> None:
    _write_phase15_acceptance(tmp_path)
    settings = _settings(tmp_path)
    ledger = ControlPlaneActionLedger(settings, clock=lambda: NOW)
    record = ledger.create_request(
        ControlPlaneActionRequest(
            action_id="closeout-active-action",
            action_kind=ControlPlaneActionKind.EXECUTE_SHADOW,
            requested_at_utc=NOW,
            idempotency_key="closeout-active-action-idem",
            target_broker=BrokerName.SHADOW,
            environment=ExecutionEnvironment.SHADOW,
        )
    )
    assert record.state == ControlPlaneActionState.AUTHORIZED
    with pytest.raises(Phase16CloseoutError, match="active_actions_zero"):
        Phase16Closeout(settings).run()
