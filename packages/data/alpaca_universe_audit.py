from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from dotenv import load_dotenv

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.historical_source_probe import (
    ALPACA_CREDENTIAL_PROFILES,
    _alpaca_headers,
    _http_get,
    alpaca_bar_url,
)


ALPACA_UNIVERSE_AUDIT_CONTRACT_VERSION = (
    "historical-source-audit-v4-alpaca-inactive-legacy-ticker-reuse"
)

# Legacy names intentionally span the pre-Massive interval.  These are not used as
# a historical-universe definition; they are sentinels for whether Alpaca still
# exposes bars/assets after the security stopped trading under that ticker.
LEGACY_SENTINELS: tuple[tuple[str, str, str], ...] = (
    ("LNKD", "2016-05-02", "2016-05-13"),
    ("WFM", "2017-07-03", "2017-07-14"),
    ("MON", "2018-05-01", "2018-05-14"),
    ("TWX", "2018-05-01", "2018-05-14"),
    ("RHT", "2019-06-03", "2019-06-14"),
    ("CELG", "2019-10-01", "2019-10-14"),
    ("APC", "2019-07-01", "2019-07-15"),
    ("STI", "2019-10-01", "2019-10-14"),
    ("BBT", "2019-10-01", "2019-10-14"),
    ("FIT", "2020-12-01", "2020-12-14"),
    ("WORK", "2021-06-01", "2021-06-14"),
    ("TIF", "2020-12-01", "2020-12-14"),
)

# S is intentionally special: Sprint used S before SentinelOne later reused S.
# This is a direct check that literal-ticker history cannot itself prove identity.
REUSE_SENTINEL = "S"
REUSE_WINDOWS = (
    ("SPRINT_ERA", "2020-01-02", "2020-01-15"),
    ("SENTINELONE_ERA", "2022-01-03", "2022-01-14"),
)


@dataclass(frozen=True, slots=True)
class AlpacaUniverseAuditReport:
    contract_version: str
    generated_at_utc: str
    canonical_data_modified: bool
    trading_profile: str
    assets_endpoint: str
    inactive_assets: dict[str, object]
    legacy_sentinels: dict[str, object]
    ticker_reuse_sentinel: dict[str, object]
    conclusions: dict[str, object]
    report_path: str


def _bars(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    values = payload.get("bars")
    return [row for row in values if isinstance(row, dict)] if isinstance(values, list) else []


class AlpacaHistoricalUniverseAudit:
    """Read-only audit of inactive/legacy coverage and ticker-reuse hazards.

    The assets endpoint is current-state metadata and is never treated as a historical
    membership authority.  The audit deliberately checks both inactive assets and raw
    literal-ticker bars to learn what evidence Alpaca can provide for a 2016-2021
    backfill without weakening ATLAS's accepted identity contract.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        load_dotenv(settings.project_root / ".env", override=False)
        self.profile, self.headers, self.trading_base = self._profile()

    def _profile(self) -> tuple[str, dict[str, str], str]:
        for profile in ("paper", "live"):
            key_env, secret_env = ALPACA_CREDENTIAL_PROFILES[profile]
            key = os.getenv(key_env, "").strip()
            secret = os.getenv(secret_env, "").strip()
            endpoint_env = "ALPACA_PAPER_ENDPOINT" if profile == "paper" else "ALPACA_LIVE_ENDPOINT"
            base = os.getenv(endpoint_env, "").strip().rstrip("/")
            if key and secret and base:
                return profile, _alpaca_headers(key, secret), base
        raise RuntimeError("Alpaca universe audit requires configured credentials and trading endpoint")

    def report_path(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "historical_source_audit" / "alpaca_historical_universe.json"

    def _assets_url(self, status: str) -> str:
        return f"{self.trading_base}/assets?" + urlencode(
            {"status": status, "asset_class": "us_equity"}
        )

    def _inactive_assets(self) -> tuple[dict[str, object], dict[str, dict[str, Any]]]:
        result = _http_get(self._assets_url("inactive"), headers=self.headers)
        rows = result.payload if isinstance(result.payload, list) else []
        assets = [row for row in rows if isinstance(row, dict)]
        by_symbol = {
            str(row.get("symbol")): row
            for row in assets
            if isinstance(row.get("symbol"), str) and str(row.get("symbol")).strip()
        }
        exchanges = Counter(str(row.get("exchange") or "UNKNOWN") for row in assets)
        classes = Counter(str(row.get("class") or "UNKNOWN") for row in assets)
        return (
            {
                "status": result.status,
                "http_status": result.http_status,
                "count": len(assets),
                "unique_symbols": len(by_symbol),
                "exchange_counts": dict(sorted(exchanges.items())),
                "asset_class_counts": dict(sorted(classes.items())),
                "rate_limit": result.response_headers,
            },
            by_symbol,
        )

    def _bar_probe(self, symbol: str, start: str, end: str) -> dict[str, object]:
        result = _http_get(
            alpaca_bar_url(
                symbol,
                start=start,
                end=end,
                feed="sip",
                adjustment="raw",
                asof="-",
            ),
            headers=self.headers,
        )
        bars = _bars(result.payload)
        return {
            "status": result.status,
            "http_status": result.http_status,
            "rows": len(bars),
            "first": bars[0].get("t") if bars else None,
            "last": bars[-1].get("t") if bars else None,
            "provider_message": result.payload.get("message") if isinstance(result.payload, dict) else result.message,
        }

    def run(self) -> AlpacaUniverseAuditReport:
        inactive_summary, inactive_by_symbol = self._inactive_assets()
        legacy: dict[str, object] = {}
        asset_hits = 0
        bar_hits = 0
        for symbol, start, end in LEGACY_SENTINELS:
            probe = self._bar_probe(symbol, start, end)
            asset = inactive_by_symbol.get(symbol)
            in_inactive = asset is not None
            if in_inactive:
                asset_hits += 1
            if int(probe["rows"]) > 0:
                bar_hits += 1
            legacy[symbol] = {
                "window": [start, end],
                "present_in_inactive_assets": in_inactive,
                "inactive_asset_id": asset.get("id") if isinstance(asset, dict) else None,
                "inactive_asset_exchange": asset.get("exchange") if isinstance(asset, dict) else None,
                "bars": probe,
            }

        reuse_windows = {
            label: self._bar_probe(REUSE_SENTINEL, start, end)
            for label, start, end in REUSE_WINDOWS
        }
        active_assets = _http_get(self._assets_url("active"), headers=self.headers)
        active_rows = active_assets.payload if isinstance(active_assets.payload, list) else []
        active_s = next(
            (
                row
                for row in active_rows
                if isinstance(row, dict) and str(row.get("symbol")) == REUSE_SENTINEL
            ),
            None,
        )
        reuse = {
            "symbol": REUSE_SENTINEL,
            "current_active_asset_present": isinstance(active_s, dict),
            "current_active_asset_id": active_s.get("id") if isinstance(active_s, dict) else None,
            "current_active_asset_name": active_s.get("name") if isinstance(active_s, dict) else None,
            "windows": reuse_windows,
            "literal_ticker_has_multiple_eras": all(int(item["rows"]) > 0 for item in reuse_windows.values()),
        }

        conclusions = {
            "legacy_sentinel_count": len(LEGACY_SENTINELS),
            "legacy_present_in_inactive_assets": asset_hits,
            "legacy_with_historical_bars": bar_hits,
            "inactive_assets_are_current_state_only": True,
            "ticker_text_alone_can_prove_identity": False,
            "reuse_sentinel_demonstrates_identity_segmentation_required": bool(
                reuse["literal_ticker_has_multiple_eras"]
            ),
        }
        report = AlpacaUniverseAuditReport(
            contract_version=ALPACA_UNIVERSE_AUDIT_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            canonical_data_modified=False,
            trading_profile=self.profile,
            assets_endpoint=self._assets_url("inactive"),
            inactive_assets=inactive_summary,
            legacy_sentinels=legacy,
            ticker_reuse_sentinel=reuse,
            conclusions=conclusions,
            report_path=str(self.report_path()),
        )
        atomic_write_text(
            self.report_path(),
            json.dumps(asdict(report), indent=2, sort_keys=True, default=str) + "\n",
        )
        return report
