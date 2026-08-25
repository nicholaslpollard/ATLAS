from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.execution.phase15_foundation import Phase15CumulativeFoundationBinding
from packages.operations.phase23_current_run import Phase23CurrentAnalysisCycle
from packages.operations.phase23_handoff import Phase23AnalysisHandoffStore, Phase23HandoffError
from packages.operations.phase23_policy import (
    MASSIVE_MARKET_REFERENCE_READS,
    PHASE23_AUTOMATIC_BROKER_FAILOVER,
    PHASE23_BROKER_MUTATIONS_ALLOWED,
    PHASE23_DEFAULT_BROKER,
    PHASE23_FROZEN_SUPPORTED_STRATEGIES,
    PHASE23_LIVE_EXECUTION_ENABLED,
    PHASE23_ORDER_WRITES_ALLOWED,
    PHASE23_PAPER_SUBMIT_AUTHORITY_ALLOWED,
    Phase23AuthorizationError,
    authorize_phase23_reads,
    build_phase23_read_challenge,
    require_phase23_read_authority,
)
from packages.schemas.execution import BrokerName


AS_OF = date(2026, 8, 21)
BASELINE = date(2026, 8, 14)
SESSIONS = tuple(date(2026, 8, day) for day in (17, 18, 19, 20, 21))


class FakeSettings:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.data = SimpleNamespace(paths=SimpleNamespace(derived="derived"))

    def resolved_path(self, value: str) -> Path:
        return self.root / value


class FakeCalendar:
    def sessions_in_range(self, start: date, end: date):
        return [item for item in SESSIONS if start <= item <= end]


class FakePaths:
    def __init__(self, root: Path) -> None:
        self.root = root

    def reference_snapshot_file(self, trading_date: date) -> Path:
        return self.root / "reference" / f"{trading_date}.parquet"

    def reference_snapshot_manifest(self, trading_date: date) -> Path:
        return self.root / "reference_manifests" / f"{trading_date}.json"

    def provider_file(self, dataset, trading_date: date) -> Path:
        return self.root / "provider" / str(dataset.value) / f"{trading_date}.csv.gz"


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")


def _cumulative_binding(tmp_path: Path) -> Phase15CumulativeFoundationBinding:
    return Phase15CumulativeFoundationBinding(
        contract_version="test",
        acceptance_path=tmp_path / "acceptance.json",
        acceptance_sha256="a" * 64,
        validation_path=tmp_path / "validation.json",
        validation_sha256="b" * 64,
        foundation_fingerprint="6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6",
        policy_fingerprint="c" * 64,
        history_start=date(2016, 1, 4),
        history_end=BASELINE,
    )


def test_phase23_policy_keeps_execution_and_mutation_authority_disabled() -> None:
    assert PHASE23_DEFAULT_BROKER == BrokerName.WEBULL
    assert PHASE23_FROZEN_SUPPORTED_STRATEGIES == ()
    assert PHASE23_LIVE_EXECUTION_ENABLED is False
    assert PHASE23_AUTOMATIC_BROKER_FAILOVER is False
    assert PHASE23_BROKER_MUTATIONS_ALLOWED is False
    assert PHASE23_ORDER_WRITES_ALLOWED is False
    assert PHASE23_PAPER_SUBMIT_AUTHORITY_ALLOWED is False


def test_phase23_read_challenge_is_deterministic_and_confirmation_is_exact() -> None:
    scope = {"as_of_date": AS_OF.isoformat(), "missing": [AS_OF.isoformat()]}
    first = build_phase23_read_challenge(
        as_of_date=AS_OF,
        broker=BrokerName.WEBULL,
        run_scope_payload=scope,
        external_read_classes=(MASSIVE_MARKET_REFERENCE_READS,),
    )
    second = build_phase23_read_challenge(
        as_of_date=AS_OF,
        broker=BrokerName.WEBULL,
        run_scope_payload=scope,
        external_read_classes=(MASSIVE_MARKET_REFERENCE_READS,),
    )
    assert first == second
    assert first.required_confirmation.startswith("AUTHORIZE_ATLAS_PHASE23_READS:webull:p23-")
    assert "required_confirmation" not in first.public_dict()

    with pytest.raises(Phase23AuthorizationError, match="confirmation"):
        authorize_phase23_reads(first, confirmation="WRONG", explicitly_authorized=True)

    authority = authorize_phase23_reads(
        first,
        confirmation=first.required_confirmation,
        explicitly_authorized=True,
    )
    assert require_phase23_read_authority(authority, challenge=first) == authority


def test_phase23_read_authority_is_run_and_broker_scoped() -> None:
    challenge = build_phase23_read_challenge(
        as_of_date=AS_OF,
        broker=BrokerName.WEBULL,
        run_scope_payload={"date": AS_OF.isoformat()},
        external_read_classes=(MASSIVE_MARKET_REFERENCE_READS,),
    )
    authority = authorize_phase23_reads(
        challenge,
        confirmation=challenge.required_confirmation,
        explicitly_authorized=True,
    )
    other = build_phase23_read_challenge(
        as_of_date=AS_OF,
        broker=BrokerName.ALPACA,
        run_scope_payload={"date": AS_OF.isoformat()},
        external_read_classes=(MASSIVE_MARKET_REFERENCE_READS,),
    )
    with pytest.raises(Phase23AuthorizationError, match="broker mismatch|scope mismatch"):
        require_phase23_read_authority(authority, challenge=other)


def test_prepare_is_provider_free_and_requests_reads_only_for_missing_local_evidence(tmp_path: Path) -> None:
    cycle = object.__new__(Phase23CurrentAnalysisCycle)
    cycle.paths = FakePaths(tmp_path)
    cycle.calendar = FakeCalendar()
    cycle._validate_as_of = lambda value: None
    cycle._baseline_discovery_date = lambda value: BASELINE

    preparation = cycle.prepare(as_of_date=AS_OF, broker=BrokerName.WEBULL)
    assert preparation.sessions_to_advance == SESSIONS
    assert preparation.missing_reference_sessions == SESSIONS
    assert preparation.missing_daily_sessions == SESSIONS
    assert preparation.missing_minute_sessions == SESSIONS
    assert preparation.external_read_classes == (MASSIVE_MARKET_REFERENCE_READS,)
    assert preparation.authority_required is True

    for trading_date in SESSIONS:
        _touch(cycle.paths.reference_snapshot_file(trading_date))
        _touch(cycle.paths.reference_snapshot_manifest(trading_date))
        from packages.core.enums import DatasetType

        _touch(cycle.paths.provider_file(DatasetType.STOCK_DAILY_AGGREGATES, trading_date))
        _touch(cycle.paths.provider_file(DatasetType.STOCK_MINUTE_AGGREGATES, trading_date))

    local = cycle.prepare(as_of_date=AS_OF, broker=BrokerName.WEBULL)
    assert local.external_read_classes == ()
    assert local.authority_required is False
    assert local.challenge is None


def test_analysis_handoff_distinguishes_local_persistence_from_external_mutation(tmp_path: Path) -> None:
    settings = FakeSettings(tmp_path)
    store = Phase23AnalysisHandoffStore(settings)
    phase14 = tmp_path / "phase14.json"
    phase14.write_text('{"pass": true}\n', encoding="utf-8")
    binding = store.write(
        as_of_date=AS_OF,
        phase14_acceptance_path=phase14,
        stage_hashes={"phase14_acceptance": "d" * 64},
        sessions_advanced=SESSIONS,
        external_read_classes_used=(MASSIVE_MARKET_REFERENCE_READS,),
    )
    payload = json.loads(binding.path.read_text(encoding="utf-8"))
    assert payload["local_analytical_writes_allowed"] is True
    assert "canonical_writes" not in payload
    assert payload["production_model_writes"] == 0
    assert payload["external_provider_mutation_writes"] == 0
    assert payload["broker_writes"] == 0
    assert payload["order_writes"] == 0
    assert payload["paper_submits"] == 0
    assert payload["live_writes"] == 0

    cumulative = _cumulative_binding(tmp_path)
    resolved = store.resolve(
        as_of_date=AS_OF,
        cumulative=cumulative,
        expected_phase14_acceptance_sha256=binding.phase14_acceptance_sha256,
    )
    assert resolved.source_fingerprint == binding.source_fingerprint


def test_analysis_handoff_tamper_fails_closed(tmp_path: Path) -> None:
    settings = FakeSettings(tmp_path)
    store = Phase23AnalysisHandoffStore(settings)
    phase14 = tmp_path / "phase14.json"
    phase14.write_text('{"pass": true}\n', encoding="utf-8")
    binding = store.write(
        as_of_date=AS_OF,
        phase14_acceptance_path=phase14,
        stage_hashes={"phase14_acceptance": "d" * 64},
        sessions_advanced=SESSIONS,
        external_read_classes_used=(),
    )
    payload = json.loads(binding.path.read_text(encoding="utf-8"))
    payload["broker_writes"] = 1
    binding.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(Phase23HandoffError, match="mutation boundary"):
        store.resolve(
            as_of_date=AS_OF,
            cumulative=_cumulative_binding(tmp_path),
            expected_phase14_acceptance_sha256=binding.phase14_acceptance_sha256,
        )
