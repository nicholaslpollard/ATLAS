from datetime import UTC, date, datetime

import pytest

from packages.core.enums import InstrumentIdentityQuality
from packages.schemas.universe import (
    UniverseMember,
    UniverseReasonCode,
    UniverseRoute,
    UniverseSnapshot,
    universe_members_fingerprint,
)


def member(**overrides):
    payload = {
        "instrument_id": "ins_abc123",
        "ticker": "TpC",
        "as_of_date": date(2026, 8, 14),
        "identity_quality": InstrumentIdentityQuality.STRONG,
        "name": "Example",
        "market": "stocks",
        "locale": "us",
        "primary_exchange": "XNYS",
        "security_type": "CS",
        "reference_active": True,
        "discovery_eligible": True,
        "reason_codes": (UniverseReasonCode.ELIGIBLE,),
        "routes": (UniverseRoute.DISCOVERY,),
    }
    payload.update(overrides)
    return UniverseMember(**payload)


def test_provider_native_ticker_case_is_preserved():
    assert member(ticker="TpC").ticker == "TpC"
    assert member(ticker="TPC").ticker == "TPC"


def test_discovery_route_must_match_discovery_eligibility():
    with pytest.raises(ValueError, match="discovery route"):
        member(discovery_eligible=False, reason_codes=(UniverseReasonCode.REFERENCE_INACTIVE,))


def test_position_can_bypass_discovery_ineligibility_with_explicit_reason():
    value = member(
        discovery_eligible=False,
        reference_active=False,
        reason_codes=(
            UniverseReasonCode.REFERENCE_INACTIVE,
            UniverseReasonCode.POSITION_OVERRIDE,
        ),
        routes=(UniverseRoute.POSITION,),
    )
    assert not value.discovery_eligible
    assert value.routes == (UniverseRoute.POSITION,)


def test_watchlist_bypass_requires_explicit_override_reason():
    with pytest.raises(ValueError, match="watchlist_override"):
        member(
            discovery_eligible=False,
            reason_codes=(UniverseReasonCode.DATA_UNAVAILABLE,),
            routes=(UniverseRoute.WATCHLIST,),
        )


def test_eligible_member_cannot_contain_blocking_reason():
    with pytest.raises(ValueError, match="blocking reason"):
        member(
            reason_codes=(UniverseReasonCode.ELIGIBLE, UniverseReasonCode.DATA_QUARANTINED)
        )


def test_snapshot_rejects_duplicate_stable_instrument_identity():
    first = member(ticker="TPC")
    second = member(ticker="TpC")
    with pytest.raises(ValueError, match="duplicate instrument_id"):
        UniverseSnapshot(
            as_of_date=date(2026, 8, 14),
            reference_snapshot_date=date(2026, 8, 14),
            generated_at_utc=datetime(2026, 8, 17, 14, 0, tzinfo=UTC),
            members=(first, second),
            fingerprint="abc",
        )


def test_members_fingerprint_is_order_independent_and_generation_time_free():
    first = member(instrument_id="ins_a", ticker="TPC")
    second = member(instrument_id="ins_b", ticker="TpC")
    args = {
        "as_of_date": date(2026, 8, 14),
        "reference_snapshot_date": date(2026, 8, 14),
    }
    assert universe_members_fingerprint(members=(first, second), **args) == universe_members_fingerprint(
        members=(second, first), **args
    )
