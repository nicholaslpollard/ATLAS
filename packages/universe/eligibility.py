from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from packages.core.enums import InstrumentIdentityQuality
from packages.schemas.universe import UniverseReasonCode


UNIVERSE_ELIGIBILITY_POLICY_VERSION = "universe-eligibility-v1-us-listed-core-and-income-securities"


@dataclass(frozen=True, slots=True)
class UniverseEligibilityPolicy:
    """Deterministic metadata gate before Phase 8 data-health/activity ranking.

    The initial policy is intentionally based on the real 2026-08-14 Massive
    inventory.  It keeps ordinary equities and exchange-traded/income products in
    broad discovery while excluding corporate-action/special-situation wrappers
    such as rights, warrants, units, and structured products.  Phase 8 will apply
    data-health, activity, liquidity, and setup filters; those are not hidden here.
    """

    allowed_markets: tuple[str, ...] = ("stocks",)
    allowed_locales: tuple[str, ...] = ("us",)
    allowed_exchanges: tuple[str, ...] = ("ARCX", "BATS", "XASE", "XNAS", "XNYS")
    allowed_security_types: tuple[str, ...] = (
        "ADRC",
        "CS",
        "ETF",
        "ETN",
        "ETS",
        "ETV",
        "FUND",
        "PFD",
    )
    allowed_identity_qualities: tuple[InstrumentIdentityQuality, ...] = (
        InstrumentIdentityQuality.STRONG,
        InstrumentIdentityQuality.MEDIUM,
    )

    @property
    def fingerprint(self) -> str:
        payload = {
            "version": UNIVERSE_ELIGIBILITY_POLICY_VERSION,
            "allowed_markets": sorted(self.allowed_markets),
            "allowed_locales": sorted(self.allowed_locales),
            "allowed_exchanges": sorted(self.allowed_exchanges),
            "allowed_security_types": sorted(self.allowed_security_types),
            "allowed_identity_qualities": sorted(item.value for item in self.allowed_identity_qualities),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def evaluate(
        self,
        *,
        reference_active: bool,
        delisted_utc: datetime | None,
        market: str | None,
        locale: str | None,
        primary_exchange: str | None,
        security_type: str | None,
        identity_quality: InstrumentIdentityQuality,
        data_available: bool = True,
        data_quarantined: bool = False,
        manual_exclude: bool = False,
    ) -> tuple[bool, tuple[UniverseReasonCode, ...]]:
        reasons: set[UniverseReasonCode] = set()

        if not reference_active:
            reasons.add(UniverseReasonCode.REFERENCE_INACTIVE)
        if delisted_utc is not None:
            reasons.add(UniverseReasonCode.REFERENCE_DELISTED)

        market_value = str(market or "").strip().lower()
        locale_value = str(locale or "").strip().lower()
        exchange_value = str(primary_exchange or "").strip().upper()
        security_value = str(security_type or "").strip().upper()

        if not market_value or not locale_value or not exchange_value or not security_value:
            reasons.add(UniverseReasonCode.MISSING_REFERENCE_METADATA)

        if market_value and market_value not in {item.lower() for item in self.allowed_markets}:
            reasons.add(UniverseReasonCode.UNSUPPORTED_MARKET)
        if locale_value and locale_value not in {item.lower() for item in self.allowed_locales}:
            reasons.add(UniverseReasonCode.NON_US_LOCALE)
        if exchange_value and exchange_value not in set(self.allowed_exchanges):
            reasons.add(UniverseReasonCode.UNSUPPORTED_EXCHANGE)
        if security_value and security_value not in set(self.allowed_security_types):
            reasons.add(UniverseReasonCode.UNSUPPORTED_SECURITY_TYPE)
        if identity_quality not in set(self.allowed_identity_qualities):
            reasons.add(UniverseReasonCode.UNSUPPORTED_IDENTITY_QUALITY)

        if not data_available:
            reasons.add(UniverseReasonCode.DATA_UNAVAILABLE)
        if data_quarantined:
            reasons.add(UniverseReasonCode.DATA_QUARANTINED)
        if manual_exclude:
            reasons.add(UniverseReasonCode.MANUAL_EXCLUDE)

        if reasons:
            return False, tuple(sorted(reasons, key=lambda item: item.value))
        return True, (UniverseReasonCode.ELIGIBLE,)


ACTIVE_UNIVERSE_ELIGIBILITY_POLICY = UniverseEligibilityPolicy()
