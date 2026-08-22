from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from packages.control_plane.runtime_state import (
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


def _settings_with_derived(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(update={"derived": tmp_path})
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


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
    assert not store.state_path.exists()


def test_persisted_runtime_state_requires_explicit_broker_environment_pair(tmp_path) -> None:
    store = ControlPlaneRuntimeStateStore(_settings_with_derived(tmp_path))
    store.root.mkdir(parents=True, exist_ok=True)
    payload = {
        "contract_version": CONTROL_PLANE_RUNTIME_CONTRACT_VERSION,
        "revision": 3,
        "updated_at_utc": NOW.isoformat(),
        "selected_broker": "webull",
        "selected_environment": "paper",
        "provider_write_uncertain": False,
        "active_action_id": None,
        "uncertain_action_id": None,
        "source": "persisted",
    }
    store.state_path.write_text(json.dumps(payload), encoding="utf-8")
    state = store.load()
    assert state.source == "persisted"
    assert state.revision == 3
    assert state.selected_broker == BrokerName.WEBULL
    assert state.selected_environment == ExecutionEnvironment.PAPER


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
            source="persisted",
        )
