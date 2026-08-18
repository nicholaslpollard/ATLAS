from __future__ import annotations

from datetime import date
from typing import Any

from packages.core.enums import InstrumentIdentityQuality
from packages.core.identifiers import stable_id


IDENTITY_CONTRACT_VERSION = "instrument-identity-v4-no-issuer-level-medium-collapse"


class InstrumentIdentityResolver:
    """Resolve provider reference rows to conservative stable instrument identities.

    Identity is intentionally asymmetric:

    * Composite FIGI / Share Class FIGI are strong security-level evidence and may
      survive ticker changes.
    * CIK is issuer-level, not security-level.  A CIK therefore MUST NOT be used
      with exchange/security type alone because one issuer can have many common,
      preferred, warrant, unit, note, or fund lines on the same venue.  Medium
      identity includes the exact provider-native ticker to prevent false merges.
    * If no security/issuer identifier exists, fallback identity remains scoped to
      the exact point-in-time ticker observation.  This is conservative with
      respect to ticker reuse; authoritative ticker-event evidence can establish
      continuity later instead of ATLAS guessing.
    """

    @staticmethod
    def resolve(row: dict[str, Any], as_of_date: date) -> tuple[str, str, InstrumentIdentityQuality]:
        composite_figi = str(row.get("composite_figi") or "").strip().upper()
        if composite_figi:
            identity_key = f"massive:composite_figi:{composite_figi}"
            return stable_id(identity_key, prefix="ins"), identity_key, InstrumentIdentityQuality.STRONG

        share_class_figi = str(row.get("share_class_figi") or "").strip().upper()
        if share_class_figi:
            identity_key = f"massive:share_class_figi:{share_class_figi}"
            return stable_id(identity_key, prefix="ins"), identity_key, InstrumentIdentityQuality.STRONG

        ticker = str(row.get("ticker") or "").strip()
        if not ticker:
            raise ValueError("Massive reference row has no usable ticker or stable identifier")

        cik = str(row.get("cik") or "").strip().upper()
        exchange = str(row.get("primary_exchange") or "").strip().upper()
        security_type = str(row.get("type") or row.get("security_type") or "").strip().upper()
        if cik and (exchange or security_type):
            # CIK is issuer-level.  Include exact provider-native ticker so distinct
            # listed securities from the same issuer cannot collapse together.
            identity_key = (
                f"massive:cik:{cik}:ticker:{ticker}:exchange:{exchange}:type:{security_type}"
            )
            return stable_id(identity_key, prefix="ins"), identity_key, InstrumentIdentityQuality.MEDIUM

        # Massive ticker case is provider-significant for preferred shares, so a
        # fallback identity must preserve it rather than fold to uppercase.  Date
        # scoping avoids silently conflating a later ticker reuse with an older
        # security when no stronger continuity evidence exists.
        identity_key = f"massive:ticker_snapshot:{ticker}:{as_of_date.isoformat()}"
        return stable_id(identity_key, prefix="ins"), identity_key, InstrumentIdentityQuality.FALLBACK
