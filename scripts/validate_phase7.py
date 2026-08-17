from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.enums import InstrumentIdentityQuality
from packages.schemas.universe import (
    UNIVERSE_CONTRACT_VERSION,
    UniverseMember,
    UniverseReasonCode,
    UniverseRoute,
    universe_members_fingerprint,
)
from packages.universe.metadata import REFERENCE_UNIVERSE_INVENTORY_VERSION


def _member(instrument_id: str, ticker: str) -> UniverseMember:
    return UniverseMember(
        instrument_id=instrument_id,
        ticker=ticker,
        as_of_date=date(2026, 8, 14),
        identity_quality=InstrumentIdentityQuality.STRONG,
        name="ATLAS validation instrument",
        market="stocks",
        locale="us",
        primary_exchange="XNAS",
        security_type="CS",
        reference_active=True,
        discovery_eligible=True,
        reason_codes=(UniverseReasonCode.ELIGIBLE,),
        routes=(UniverseRoute.DISCOVERY,),
    )


def main() -> int:
    first = _member("ins_a", "TPC")
    second = _member("ins_b", "TpC")
    args = {
        "as_of_date": date(2026, 8, 14),
        "reference_snapshot_date": date(2026, 8, 14),
    }
    forward = universe_members_fingerprint(members=(first, second), **args)
    reverse = universe_members_fingerprint(members=(second, first), **args)
    if first.ticker == second.ticker:
        raise RuntimeError("provider-native ticker case was not preserved")
    if forward != reverse:
        raise RuntimeError("universe fingerprint is order dependent")

    override = UniverseMember(
        instrument_id="ins_position",
        ticker="OLD",
        as_of_date=date(2026, 8, 14),
        identity_quality=InstrumentIdentityQuality.STRONG,
        reference_active=False,
        discovery_eligible=False,
        reason_codes=(
            UniverseReasonCode.REFERENCE_INACTIVE,
            UniverseReasonCode.POSITION_OVERRIDE,
        ),
        routes=(UniverseRoute.POSITION,),
    )
    if override.discovery_eligible:
        raise RuntimeError("position override incorrectly became discovery eligible")

    print(f"Universe contract: {UNIVERSE_CONTRACT_VERSION}")
    print(f"Reference inventory contract: {REFERENCE_UNIVERSE_INVENTORY_VERSION}")
    print(f"Semantic fingerprint: {forward}")
    print("Provider-native ticker case: PASS")
    print("Discovery/override separation: PASS")
    print("Deterministic universe fingerprint: PASS")
    print("Phase 07 universe foundation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
