from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.enums import InstrumentIdentityQuality
from packages.instruments.identity import IDENTITY_CONTRACT_VERSION, InstrumentIdentityResolver
from packages.schemas.universe import (
    UNIVERSE_CONTRACT_VERSION,
    UniverseMember,
    UniverseReasonCode,
    UniverseRoute,
    universe_members_fingerprint,
)
from packages.universe.eligibility import (
    ACTIVE_UNIVERSE_ELIGIBILITY_POLICY,
    UNIVERSE_ELIGIBILITY_POLICY_VERSION,
)
from packages.universe.manager import UNIVERSE_MANIFEST_VERSION
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

    resolver = InstrumentIdentityResolver()
    medium_base = {
        "cik": "0000070858",
        "primary_exchange": "XNYS",
        "type": "PFD",
    }
    bac_a, _, quality_a = resolver.resolve(
        {**medium_base, "ticker": "BACpA"}, date(2026, 8, 14)
    )
    bac_b, _, quality_b = resolver.resolve(
        {**medium_base, "ticker": "BACpB"}, date(2026, 8, 14)
    )
    if quality_a != InstrumentIdentityQuality.MEDIUM or quality_b != InstrumentIdentityQuality.MEDIUM:
        raise RuntimeError("medium identity validation did not use medium-quality path")
    if bac_a == bac_b:
        raise RuntimeError("distinct issuer securities collapsed into one medium identity")

    policy = ACTIVE_UNIVERSE_ELIGIBILITY_POLICY
    eligible, reasons = policy.evaluate(
        reference_active=True,
        delisted_utc=None,
        market="stocks",
        locale="us",
        primary_exchange="XNAS",
        security_type="CS",
        identity_quality=InstrumentIdentityQuality.STRONG,
    )
    if not eligible or reasons != (UniverseReasonCode.ELIGIBLE,):
        raise RuntimeError("core common-stock eligibility validation failed")
    fallback_eligible, fallback_reasons = policy.evaluate(
        reference_active=True,
        delisted_utc=None,
        market="stocks",
        locale="us",
        primary_exchange="XNAS",
        security_type="CS",
        identity_quality=InstrumentIdentityQuality.FALLBACK,
    )
    if fallback_eligible or UniverseReasonCode.UNSUPPORTED_IDENTITY_QUALITY not in fallback_reasons:
        raise RuntimeError("fallback identity was incorrectly admitted to broad discovery")
    special_eligible, special_reasons = policy.evaluate(
        reference_active=True,
        delisted_utc=None,
        market="stocks",
        locale="us",
        primary_exchange="XNAS",
        security_type="WARRANT",
        identity_quality=InstrumentIdentityQuality.STRONG,
    )
    if special_eligible or UniverseReasonCode.UNSUPPORTED_SECURITY_TYPE not in special_reasons:
        raise RuntimeError("special-situation wrapper was incorrectly admitted to broad discovery")

    print(f"Universe contract: {UNIVERSE_CONTRACT_VERSION}")
    print(f"Instrument identity contract: {IDENTITY_CONTRACT_VERSION}")
    print(f"Reference inventory contract: {REFERENCE_UNIVERSE_INVENTORY_VERSION}")
    print(f"Eligibility policy: {UNIVERSE_ELIGIBILITY_POLICY_VERSION}")
    print(f"Eligibility policy fingerprint: {policy.fingerprint}")
    print(f"Universe manifest contract: {UNIVERSE_MANIFEST_VERSION}")
    print(f"Semantic fingerprint: {forward}")
    print("Provider-native ticker case: PASS")
    print("Medium issuer-security separation: PASS")
    print("Discovery/override separation: PASS")
    print("Observed metadata eligibility policy: PASS")
    print("Fallback identity exclusion: PASS")
    print("Deterministic universe fingerprint: PASS")
    print("Phase 07 universe foundation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
