from __future__ import annotations

from datetime import date
from typing import Any

from packages.core.settings import AtlasSettings

from .rest import MassiveRESTClient


class MassiveReferenceProvider:
    """Point-in-time Massive stock reference provider.

    Ticker text is provider-native and case-sensitive. In particular, Massive/SIP
    preferred-share symbols may contain a lowercase ``p`` (for example ``TpC``).
    ATLAS therefore trims ticker whitespace but never case-folds ticker identity.
    """

    def __init__(self, settings: AtlasSettings, *, client: MassiveRESTClient | None = None) -> None:
        self.settings = settings
        self.client = client or MassiveRESTClient(settings)

    @staticmethod
    def _normalize(item: dict[str, Any]) -> dict[str, Any]:
        out = dict(item)
        if out.get("ticker") is not None:
            out["ticker"] = str(out["ticker"]).strip()
        for key in ("composite_figi", "share_class_figi", "cik", "primary_exchange", "type"):
            if out.get(key) is not None:
                value = str(out[key]).strip()
                out[key] = value.upper() if value else None
        return out

    def stock_snapshot(self, as_of_date: date, *, include_inactive: bool = True) -> list[dict[str, Any]]:
        states = (True, False) if include_inactive else (True,)
        rows: list[dict[str, Any]] = []
        seen: set[tuple[Any, ...]] = set()
        for active in states:
            for raw in self.client.list_tickers(as_of_date=as_of_date.isoformat(), active=active, market="stocks"):
                row = self._normalize(raw)
                if not row.get("ticker"):
                    continue
                key = (
                    row.get("ticker"),
                    row.get("composite_figi"),
                    row.get("share_class_figi"),
                    row.get("cik"),
                    bool(row.get("active", active)),
                )
                if key in seen:
                    continue
                seen.add(key)
                row["active"] = bool(row.get("active", active))
                rows.append(row)
        rows.sort(key=lambda item: (str(item.get("ticker", "")), str(item.get("composite_figi", ""))))
        return rows

    def ticker_events(self, identifier: str) -> list[dict[str, Any]]:
        return self.client.ticker_events(identifier)
