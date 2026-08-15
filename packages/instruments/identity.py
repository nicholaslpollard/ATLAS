from __future__ import annotations

from datetime import date
from typing import Any

from packages.core.enums import InstrumentIdentityQuality
from packages.core.identifiers import stable_id


class InstrumentIdentityResolver:
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
        cik = str(row.get("cik") or "").strip().upper()
        exchange = str(row.get("primary_exchange") or "").strip().upper()
        security_type = str(row.get("type") or "").strip().upper()
        if cik and (exchange or security_type):
            identity_key = f"massive:cik:{cik}:exchange:{exchange}:type:{security_type}"
            return stable_id(identity_key, prefix="ins"), identity_key, InstrumentIdentityQuality.MEDIUM
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker:
            raise ValueError("Massive reference row has no usable ticker or stable identifier")
        identity_key = f"massive:ticker_snapshot:{ticker}:{as_of_date.isoformat()}"
        return stable_id(identity_key, prefix="ins"), identity_key, InstrumentIdentityQuality.FALLBACK
