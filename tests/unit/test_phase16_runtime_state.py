from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from packages.control_plane.runtime_state import (
    ControlPlaneRuntimeStateConflict,
    ControlPlaneRuntimeStateError,
    ControlPlaneRuntimeStateStore,
)
from packages.control_plane.status import Phase16StatusService
from packages.core.settings import load_settings
from packages.schemas.control_plane_runtime import (
    CONTROL_PLANE_RUNTIME_CONTRACT_VERSION,
    ControlPlaneRuntimeState,
)
from packages.schemas.control_plane_status import ControlPlaneHealthState
from packages.schemas.execution import BrokerName, ExecutionEnvironment


NOW = datetime(2026, 8, 22, 20, 30, tzinfo=UTC)
AUDIT_HASH = "a" * 64


def _settings_with_derived(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(update={"derived": tmp_path})
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


def _persisted_state(*, revision: int = 1, broker: BrokerName = BrokerName.WEBULL):
    return ControlPlaneRuntimeState(
        revision=revision,
        updated_at_utc=NOW + timedelta(seconds=revision),
        selected_broker=broker,
        selected_environment=ExecutionEnvironment.PAPER,
        provider_write_uncertain=False,
        active_action_id=None,
        uncertain_action_id=None,
        last_transition_action_id=f"switch-{revision}",
        last_transition_audit_hash=AUDIT_HASH,
        source="persisted",
    )


def test_missing_runtime_state_returns_nonpersisted_unselected_default(tmp_path) -> None:
    store = ControlPlaneRuntimeStateStore(
        _settings_with_derived(tmp_path), clock=lambda: NOW
    )
    state = store.load()
    assert state.source == "synthetic_default"
    assert state.revision == 0
    assert state.selected_broker is None
    assert state.selected_environment is None
    assert state.provider_write_uncertain is False
    assert state.last_transition_action_id is None
    assert state.last_transition_audit_hash is None
    assert not store.state_path.exists()


def test_persisted_runtime_state_requires_explicit_audit_bound_selection(tmp_path) -> None:
    store = ControlPlaneRuntimeStateStore(_settings_with_derived(tmp_path))
    store.root.mkdir(parents=True, exist_ok=True)
    state = _persisted_state(revision=3)
    store.state_path.write_text(
        json.dumps(state.model_dump(mode="json")), encoding="utf-8"
    )
    loaded = store.load()
    assert loaded == state
    assert loaded.selected_broker == BrokerName.WEBULL
    assert loaded.selected_environment == ExecutionEnvironment.PAPER
    assert loaded.last_transition_action_id == "switch-3"
    assert loaded.last_transition_audit_hash == AUDIT_HASH


def test_persist_transition_atomically_moves_revision_zero_to_one(tmp_path) -> None:
    store = ControlPlaneRuntimeStateStore(
        _settings_with_derived(tmp_path), clock=lambda: NOW
    )
    assert store.load().revision == 0
    state = _persisted_state(revision=1, broker=BrokerName.ALPACA)
    saved = store.persist_transition(state, expected_prior_revision=0)
    assert saved == state
    assert store.load() == state
    assert store.state_path.is_file()


def test_persist_transition_rejects_stale_prior_revision(tmp_path) -> None:
    store = ControlPlaneRuntimeStateStore(_settings_with_derived(tmp_path))
    state1 = _persisted_state(revision=1)
    store.persist_transition(state1, expected_prior_revision=0)
    state2 = ControlPlaneRuntimeState(
        revision=2,
        updated_at_utc=NOW + timedelta(seconds=2),
        selected_broker=BrokerName.ALPACA,
        selected_environment=ExecutionEnvironment.PAPER,
        provider_write_uncertain=False,
        last_transition_action_id="switch-2",
        last_transition_audit_hash="b" * 64,
        source="persisted",
    )
    with pytest.raises(ControlPlaneRuntimeStateConflict, match="expected 0"):
        store.persist_transition(state2, expected_prior_revision=0)
    assert store.load() == state1


def test_invalid_persisted_runtime_state_is_not_replaced_with_default(tmp_path) -> None:
    settings = _settings_with_derived(tmp_path)
    store = ControlPlaneRuntimeStateStore(settings, clock=lambda: NOW)
    store.root.mkdir(parents=True, exist_ok=True)
    store.state_path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ControlPlaneRuntimeStateError):
        store.load()

    service = Phase16StatusService(settings, env={}, runtime_store=store, clock=lambda: NOW)
    status = service.system_status()
    assert status.health == ControlPlaneHealthState.BLOCKED
    assert status.runtime_state_valid is False
    assert status.runtime_state_source == "invalid"
    assert status.runtime_revision is None
    assert status.selected_broker is None
    assert status.selected_environment is None
    assert status.provider_write_uncertain is True


def test_runtime_contract_rejects_live_selection() -> None:
    with pytest.raises(ValueError, match="live"):
        ControlPlaneRuntimeState(
            revision=1,
            updated_at_utc=NOW,
            selected_broker=BrokerName.WEBULL,
            selected_environment=ExecutionEnvironment.LIVE,
            provider_write_uncertain=False,
            last_transition_action_id="switch-live",
            last_transition_audit_hash=AUDIT_HASH,
            source="persisted",
        )


def test_persisted_runtime_requires_audit_binding() -> None:
    with pytest.raises(ValueError, match="audit-bound"):
        ControlPlaneRuntimeState(
            revision=1,
            updated_at_utc=NOW,
            selected_broker=BrokerName.WEBULL,
            selected_environment=ExecutionEnvironment.PAPER,
            provider_write_uncertain=False,
            source="persisted",
        )


def test_synthetic_default_cannot_implicitly_select_primary_broker() -> None:
    with pytest.raises(ValueError, match="synthetic default"):
        ControlPlaneRuntimeState(
            revision=0,
            updated_at_utc=NOW,
            selected_broker=BrokerName.WEBULL,
            selected_environment=ExecutionEnvironment.PAPER,
            provider_write_uncertain=False,
            source="synthetic_default",
        )


def test_provider_write_uncertainty_requires_exact_uncertain_action() -> None:
    with pytest.raises(ValueError, match="uncertain action"):
        ControlPlaneRuntimeState(
            revision=4,
            updated_at_utc=NOW,
            selected_broker=BrokerName.ALPACA,
            selected_environment=ExecutionEnvironment.PAPER,
            provider_write_uncertain=True,
            uncertain_action_id=None,
            last_transition_action_id="switch-4",
            last_transition_audit_hash=AUDIT_HASH,
            source="persisted",
        )
