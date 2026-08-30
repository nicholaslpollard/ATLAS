from __future__ import annotations

from datetime import date
from typing import Any

from packages.core.exceptions import ProviderError
from packages.core.settings import AtlasSettings
from packages.providers.massive.reference_data import MassiveReferenceProvider
from packages.providers.massive.rest import MassiveRESTClient


def _normalize_cik(value: object) -> str:
    text = str(value or "").strip()
    if not text.isdigit():
        raise ProviderError(f"Massive PIT CIK is not numeric: {value!r}")
    return str(int(text)).zfill(10)


class MassiveCIKPITReferenceProvider:
    """Read-only CIK/date-filtered Massive stock reference lookup for XBRL PIT work."""

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        client: MassiveRESTClient | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or MassiveRESTClient(settings)

    def cik_snapshot(
        self,
        *,
        cik: object,
        as_of_date: date,
        include_inactive: bool = True,
        security_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return a PIT CIK snapshot.

        ``include_inactive=True`` is retained for exact reproducibility of the
        original v1 source audit.  New tradable-common-equity work must use
        :meth:`tradable_common_stock_snapshot`, because Massive evaluates
        ``active`` on the queried historical date and ``market=stocks`` also
        contains preferreds, warrants, rights, units, ETFs, and other instruments.
        """
        expected_cik = _normalize_cik(cik)
        states = (True, False) if include_inactive else (True,)
        rows: list[dict[str, Any]] = []
        seen: set[tuple[Any, ...]] = set()
        for active in states:
            params: dict[str, Any] = {
                "market": "stocks",
                "date": as_of_date.isoformat(),
                "active": active,
                "cik": expected_cik,
                "order": "asc",
                "limit": self.settings.massive.reference.page_limit,
                "sort": "ticker",
            }
            if security_type is not None:
                params["type"] = security_type
            for page in self.client.iter_pages("/v3/reference/tickers", params):
                results = page.get("results") or []
                if not isinstance(results, list):
                    raise ProviderError("Massive CIK PIT reference response `results` was not a list")
                for raw in results:
                    if not isinstance(raw, dict):
                        continue
                    row = MassiveReferenceProvider._normalize_classification_text(
                        MassiveReferenceProvider._normalize(raw)
                    )
                    actual_cik = _normalize_cik(row.get("cik"))
                    if actual_cik != expected_cik:
                        raise ProviderError(
                            f"Massive CIK filter returned mismatched issuer: expected={expected_cik} actual={actual_cik}"
                        )
                    row["cik"] = expected_cik
                    row["active"] = bool(row.get("active", active))
                    key = (
                        row.get("ticker"),
                        row.get("composite_figi"),
                        row.get("share_class_figi"),
                        row.get("primary_exchange"),
                        row.get("type"),
                        row.get("active"),
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(row)
        rows.sort(
            key=lambda item: (
                str(item.get("ticker", "")),
                str(item.get("composite_figi", "")),
                str(item.get("share_class_figi", "")),
                str(item.get("primary_exchange", "")),
                str(item.get("type", "")),
                bool(item.get("active", False)),
            )
        )
        return rows

    def tradable_common_stock_snapshot(
        self,
        *,
        cik: object,
        as_of_date: date,
    ) -> list[dict[str, Any]]:
        """Return only common stock actively traded on the queried PIT date."""
        return self.cik_snapshot(
            cik=cik,
            as_of_date=as_of_date,
            include_inactive=False,
            security_type="CS",
        )
