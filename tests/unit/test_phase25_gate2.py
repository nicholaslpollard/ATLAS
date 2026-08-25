from __future__ import annotations

from packages.backtesting.phase25_gate2 import discovery_members_from_reference_rows
from packages.backtesting.phase25_policy import (
    PHASE25_GATE2_DISCOVERY_OVERRIDES_ALLOWED,
    PHASE25_GATE2_PROVIDER_ACQUISITION_AUTHORITY_ALLOWED,
    PHASE25_GATE2_REQUIRES_MATERIALIZED_UNIVERSE_EQUIVALENCE,
    PHASE25_PROVIDER_READS,
    phase25_gate0_policy_fingerprint,
    phase25_gate1_policy_fingerprint,
    phase25_gate2_policy_fingerprint,
)


def _row(
    *,
    instrument_id: str,
    ticker: str,
    active: bool,
    security_type: str = "CS",
) -> dict[str, object]:
    return {
        "instrument_id": instrument_id,
        "identity_quality": "strong",
        "ticker": ticker,
        "name": ticker,
        "market": "stocks",
        "locale": "us",
        "primary_exchange": "XNYS",
        "security_type": security_type,
        "active": active,
        "delisted_utc": None,
    }


def test_gate2_inactive_rows_do_not_change_discovery_membership() -> None:
    rows = [
        _row(instrument_id="i1", ticker="AAA", active=True),
        _row(instrument_id="i1", ticker="OLD", active=False),
        _row(instrument_id="i2", ticker="DEAD", active=False),
        _row(instrument_id="i3", ticker="W", active=True, security_type="WARRANT"),
    ]
    active_rows = [row for row in rows if bool(row["active"])]

    full_members, full_stats = discovery_members_from_reference_rows(rows)
    active_members, active_stats = discovery_members_from_reference_rows(active_rows)

    assert full_members == active_members
    assert {item.ticker for item in full_members} == {"AAA"}
    assert full_stats["mixed_active_inactive_instruments"] == 1
    assert active_stats["mixed_active_inactive_instruments"] == 0


def test_gate2_multiple_active_rows_remain_ambiguous_after_active_filter() -> None:
    rows = [
        _row(instrument_id="i1", ticker="AAA", active=True),
        _row(instrument_id="i1", ticker="AAB", active=True),
        _row(instrument_id="i1", ticker="OLD", active=False),
    ]
    active_rows = [row for row in rows if bool(row["active"])]

    full_members, full_stats = discovery_members_from_reference_rows(rows)
    active_members, active_stats = discovery_members_from_reference_rows(active_rows)

    assert full_members == active_members == set()
    assert full_stats["ambiguous_active_instruments"] == 1
    assert active_stats["ambiguous_active_instruments"] == 1


def test_gate2_policy_is_provider_free_and_requires_materialized_equivalence() -> None:
    assert PHASE25_PROVIDER_READS == 0
    assert PHASE25_GATE2_PROVIDER_ACQUISITION_AUTHORITY_ALLOWED is False
    assert PHASE25_GATE2_DISCOVERY_OVERRIDES_ALLOWED is False
    assert PHASE25_GATE2_REQUIRES_MATERIALIZED_UNIVERSE_EQUIVALENCE is True
    assert len(phase25_gate2_policy_fingerprint()) == 64


def test_gate2_addition_does_not_change_accepted_earlier_policy_fingerprints() -> None:
    assert (
        phase25_gate0_policy_fingerprint()
        == "994b05f2bc7fd8329578e0ca2a621de2602d2d71e7f8c06101a22b9ca9468604"
    )
    assert (
        phase25_gate1_policy_fingerprint()
        == "1c134efdb64ad8ccd527be2ca870d5f3eddba3f6538654e68ca06f0aa4f64207"
    )
