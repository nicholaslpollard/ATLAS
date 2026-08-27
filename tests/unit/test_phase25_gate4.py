from __future__ import annotations

from datetime import date

import pytest

from packages.backtesting.phase25_gate4 import (
    Phase25Gate4AuthorizationError,
    Phase25Gate4Error,
    authorize_phase25_gate4_probe,
    build_phase25_gate4_read_challenge,
    validate_gate4_probe_rows,
)
from packages.backtesting.phase25_policy import (
    PHASE25_GATE4_BULK_ACQUISITION_ALLOWED,
    PHASE25_GATE4_MAX_PROBE_SESSIONS,
    PHASE25_GATE4_PROVIDER_READ_AUTHORITY_ALLOWED,
    PHASE25_GATE4_PROVIDER_WRITES_ALLOWED,
    phase25_gate0_policy_fingerprint,
    phase25_gate1_policy_fingerprint,
    phase25_gate2_policy_fingerprint,
    phase25_gate3_policy_fingerprint,
    phase25_gate4_policy_fingerprint,
)


def _challenge():
    return build_phase25_gate4_read_challenge(
        through_date=date(2026, 8, 21),
        entitlement_probe_session=date(2021, 8, 17),
        gate3_report_sha256="a" * 64,
        gate3_source_fingerprint="b" * 64,
    )


def test_gate4_exact_run_scoped_authority_required() -> None:
    challenge = _challenge()
    with pytest.raises(Phase25Gate4AuthorizationError):
        authorize_phase25_gate4_probe(
            challenge,
            confirmation="WRONG",
            explicitly_authorized=True,
        )
    authority = authorize_phase25_gate4_probe(
        challenge,
        confirmation=challenge.required_confirmation,
        explicitly_authorized=True,
    )
    assert authority.explicitly_authorized is True
    assert authority.entitlement_probe_session == date(2021, 8, 17)
    assert challenge.required_confirmation.startswith(
        "AUTHORIZE_ATLAS_PHASE25_GATE4_PROBE:2021-08-17:p25g4-"
    )


def test_gate4_probe_rows_require_positive_active_provider_native_tickers() -> None:
    result = validate_gate4_probe_rows(
        [
            {"ticker": "TpC", "active": True},
            {"ticker": "A", "active": True},
        ]
    )
    assert result["row_count"] == 2
    with pytest.raises(Phase25Gate4Error):
        validate_gate4_probe_rows([])
    with pytest.raises(Phase25Gate4Error):
        validate_gate4_probe_rows([{"ticker": "A", "active": False}])
    with pytest.raises(Phase25Gate4Error):
        validate_gate4_probe_rows([{"ticker": "", "active": True}])


def test_gate4_allows_only_one_probe_and_forbids_bulk_or_provider_writes() -> None:
    assert PHASE25_GATE4_PROVIDER_READ_AUTHORITY_ALLOWED is True
    assert PHASE25_GATE4_PROVIDER_WRITES_ALLOWED is False
    assert PHASE25_GATE4_MAX_PROBE_SESSIONS == 1
    assert PHASE25_GATE4_BULK_ACQUISITION_ALLOWED is False
    assert len(phase25_gate4_policy_fingerprint()) == 64


def test_gate4_addition_preserves_all_accepted_prior_policy_fingerprints() -> None:
    assert phase25_gate0_policy_fingerprint() == "994b05f2bc7fd8329578e0ca2a621de2602d2d71e7f8c06101a22b9ca9468604"
    assert phase25_gate1_policy_fingerprint() == "1c134efdb64ad8ccd527be2ca870d5f3eddba3f6538654e68ca06f0aa4f64207"
    assert phase25_gate2_policy_fingerprint() == "417ef8af0b463a6983e6b54cfb510d8f556245c87818f8b8e24d90737049f083"
    assert phase25_gate3_policy_fingerprint() == "d0e49829132c0c8f2a09c078863ea4871fe36da1067b04c3f367e880a24080b6"
