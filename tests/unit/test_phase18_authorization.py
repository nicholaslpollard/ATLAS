from __future__ import annotations

import pytest

from packages.control_plane.phase18_authorization import (
    Phase18AuthorizationError,
    Phase18MutationAuthorization,
    require_phase18_mutation_authorization,
)
from packages.control_plane.phase18_policy import (
    PHASE18_CONFIRMATION_TEXT,
    phase18_policy_fingerprint,
    validate_phase18_policy,
)


EXPECTED_PHASE18_POLICY_FINGERPRINT = (
    "9a992246fe60526295a714c8b6762eebf131680f5a6fb21d579503757be613b7"
)


def test_phase18_policy_is_exact_and_fail_closed() -> None:
    validate_phase18_policy()
    assert phase18_policy_fingerprint() == EXPECTED_PHASE18_POLICY_FINGERPRINT


def test_phase18_mutation_denied_without_authorization() -> None:
    with pytest.raises(Phase18AuthorizationError, match="no Phase 18 mutation authorization"):
        require_phase18_mutation_authorization(None)


def test_phase18_mutation_denied_without_boolean_authorization() -> None:
    auth = Phase18MutationAuthorization(
        broker="webull",
        authorize_provider_mutation=False,
        confirmation_text=PHASE18_CONFIRMATION_TEXT,
    )
    with pytest.raises(Phase18AuthorizationError, match="explicit per-run authorization"):
        require_phase18_mutation_authorization(auth)


def test_phase18_mutation_denied_without_exact_confirmation_text() -> None:
    auth = Phase18MutationAuthorization(
        broker="webull",
        authorize_provider_mutation=True,
        confirmation_text="yes",
    )
    with pytest.raises(Phase18AuthorizationError, match="confirmation text"):
        require_phase18_mutation_authorization(auth)


def test_phase18_mutation_denied_for_unknown_broker() -> None:
    auth = Phase18MutationAuthorization(
        broker="other",
        authorize_provider_mutation=True,
        confirmation_text=PHASE18_CONFIRMATION_TEXT,
    )
    with pytest.raises(Phase18AuthorizationError, match="broker must be one of"):
        require_phase18_mutation_authorization(auth)


def test_phase18_mutation_accepts_exact_webull_authorization() -> None:
    auth = Phase18MutationAuthorization(
        broker=" Webull ",
        authorize_provider_mutation=True,
        confirmation_text=PHASE18_CONFIRMATION_TEXT,
    )
    accepted = require_phase18_mutation_authorization(auth)
    assert accepted.normalized_broker == "webull"
    assert accepted.authorize_destructive_cleanup is False


def test_phase18_mutation_accepts_exact_alpaca_authorization() -> None:
    auth = Phase18MutationAuthorization(
        broker="alpaca",
        authorize_provider_mutation=True,
        confirmation_text=PHASE18_CONFIRMATION_TEXT,
    )
    accepted = require_phase18_mutation_authorization(auth)
    assert accepted.normalized_broker == "alpaca"
