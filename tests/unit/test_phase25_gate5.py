from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from packages.backtesting.phase25_gate5 import (
    Phase25Gate5AuthorizationError,
    Phase25Gate5BulkAcquisition,
    Phase25Gate5Preparation,
    Phase25Gate5ReadAuthority,
)
from packages.backtesting.phase25_gate5_policy import (
    ACCEPTED_GATE0_POLICY_FINGERPRINT,
    ACCEPTED_GATE1_POLICY_FINGERPRINT,
    ACCEPTED_GATE2_POLICY_FINGERPRINT,
    ACCEPTED_GATE3_POLICY_FINGERPRINT,
    ACCEPTED_GATE4_POLICY_FINGERPRINT,
    PHASE25_GATE5_AUTHORIZATION_MODE,
    PHASE25_GATE5_BULK_ACQUISITION_ALLOWED,
    PHASE25_GATE5_FORCE_REPLACE_ALLOWED,
    PHASE25_GATE5_INTERACTIVE_CONFIRMATION_REQUIRED,
    PHASE25_GATE5_PROBE_REFETCH_ALLOWED,
    PHASE25_GATE5_PROVIDER_READ_AUTHORITY_ALLOWED,
    PHASE25_GATE5_PROVIDER_WRITES_ALLOWED,
    phase25_gate5_policy_fingerprint,
)
from packages.backtesting.phase25_policy import (
    phase25_gate0_policy_fingerprint,
    phase25_gate1_policy_fingerprint,
    phase25_gate2_policy_fingerprint,
    phase25_gate3_policy_fingerprint,
    phase25_gate4_policy_fingerprint,
)


def _preparation() -> Phase25Gate5Preparation:
    probe = date(2021, 8, 17)
    bulk = (date(2021, 8, 18), date(2021, 8, 19))
    return Phase25Gate5Preparation(
        through_date=date(2026, 8, 21),
        gate3_report_path=Path("gate3.json"),
        gate3_report_sha256="a" * 64,
        gate4_report_path=Path("gate4.json"),
        gate4_report_sha256="b" * 64,
        gate4_validation_path=Path("gate4-validation.json"),
        gate4_validation_sha256="c" * 64,
        probe_session=probe,
        frozen_acquisition_sessions=(probe, *bulk),
        frozen_bulk_sessions=bulk,
        validated_existing_bulk_sessions=(),
        missing_bulk_sessions=bulk,
        execution_scope_id="p25g5-test-scope",
    )


def test_gate5_read_only_acquire_command_is_the_explicit_authority() -> None:
    gate = object.__new__(Phase25Gate5BulkAcquisition)
    preparation = _preparation()
    authority = gate.authorize_cli_acquire(preparation)
    assert authority.explicitly_authorized is True
    assert authority.authorization_mode == "EXPLICIT_CLI_SUBCOMMAND"
    assert authority.execution_scope_id == preparation.execution_scope_id
    Phase25Gate5BulkAcquisition._require_authority(preparation, authority)


def test_gate5_authority_remains_scope_bound_and_default_deny() -> None:
    preparation = _preparation()
    with pytest.raises(Phase25Gate5AuthorizationError):
        Phase25Gate5BulkAcquisition._require_authority(preparation, None)
    bad = Phase25Gate5ReadAuthority(
        through_date=preparation.through_date,
        execution_scope_id="wrong-scope",
        authorization_mode="EXPLICIT_CLI_SUBCOMMAND",
        explicitly_authorized=True,
    )
    with pytest.raises(Phase25Gate5AuthorizationError):
        Phase25Gate5BulkAcquisition._require_authority(preparation, bad)


def test_gate5_is_read_only_resumable_bulk_and_cannot_refetch_probe_or_force() -> None:
    assert PHASE25_GATE5_PROVIDER_READ_AUTHORITY_ALLOWED is True
    assert PHASE25_GATE5_PROVIDER_WRITES_ALLOWED is False
    assert PHASE25_GATE5_BULK_ACQUISITION_ALLOWED is True
    assert PHASE25_GATE5_AUTHORIZATION_MODE == "EXPLICIT_CLI_SUBCOMMAND"
    assert PHASE25_GATE5_INTERACTIVE_CONFIRMATION_REQUIRED is False
    assert PHASE25_GATE5_PROBE_REFETCH_ALLOWED is False
    assert PHASE25_GATE5_FORCE_REPLACE_ALLOWED is False
    assert len(phase25_gate5_policy_fingerprint()) == 64


def test_gate5_addition_preserves_all_accepted_prior_policy_fingerprints() -> None:
    assert ACCEPTED_GATE0_POLICY_FINGERPRINT == "994b05f2bc7fd8329578e0ca2a621de2602d2d71e7f8c06101a22b9ca9468604"
    assert ACCEPTED_GATE1_POLICY_FINGERPRINT == "1c134efdb64ad8ccd527be2ca870d5f3eddba3f6538654e68ca06f0aa4f64207"
    assert ACCEPTED_GATE2_POLICY_FINGERPRINT == "417ef8af0b463a6983e6b54cfb510d8f556245c87818f8b8e24d90737049f083"
    assert ACCEPTED_GATE3_POLICY_FINGERPRINT == "d0e49829132c0c8f2a09c078863ea4871fe36da1067b04c3f367e880a24080b6"
    assert ACCEPTED_GATE4_POLICY_FINGERPRINT == "e8ef1b2f0d020e579e4c8fc92dfa256fea307ce96ed89cee02c4a812b8398d16"
    assert phase25_gate0_policy_fingerprint() == ACCEPTED_GATE0_POLICY_FINGERPRINT
    assert phase25_gate1_policy_fingerprint() == ACCEPTED_GATE1_POLICY_FINGERPRINT
    assert phase25_gate2_policy_fingerprint() == ACCEPTED_GATE2_POLICY_FINGERPRINT
    assert phase25_gate3_policy_fingerprint() == ACCEPTED_GATE3_POLICY_FINGERPRINT
    assert phase25_gate4_policy_fingerprint() == ACCEPTED_GATE4_POLICY_FINGERPRINT
