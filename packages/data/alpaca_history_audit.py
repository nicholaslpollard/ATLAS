from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np

from dotenv import load_dotenv

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.historical_source_probe import (
    ALPACA_CREDENTIAL_PROFILES,
    _alpaca_headers,
    _http_get,
    alpaca_bar_url,
    alpaca_corporate_actions_url,
)
from packages.data.sql import sql_string


ALPACA_HISTORY_AUDIT_CONTRACT_VERSION = (
    "historical-source-audit-v2-alpaca-sip-raw-depth-massive-overlap"
)
ALPACA_DEPTH_START = "2000-01-01"
ALPACA_DEPTH_END = "2016-12-31"
ALPACA_DEPTH_SYMBOLS = ("AAPL", "SPY", "IBM")
ALPACA_OVERLAP_START = "2021-08-16"
ALPACA_OVERLAP_END = "2021-09-10"
ALPACA_OVERLAP_SYMBOLS = ("AAPL", "MSFT", "NVDA", "TSLA", "SPY", "QQQ", "TWTR", "FB")
ALPACA_SPLIT_WINDOWS = (
    ("AMZN", "2022-06-02", "2022-06-09"),
    ("GOOG", "2022-07-14", "2022-07-21"),
    ("TSLA", "2022-08-22", "2022-08-29"),
    ("NVDA", "2024-06-06", "2024-06-13"),
)
ALPACA_CORPORATE_ACTION_SYMBOLS = "AAPL,NVDA,TSLA,AMZN,GOOG,FB,META"
ALPACA_CORPORATE_ACTION_START = "2016-01-01"
ALPACA_CORPORATE_ACTION_END = "2025-12-31"


@dataclass(frozen=True, slots=True)
class AlpacaHistoryAuditReport:
    contract_version: str
    generated_at_utc: str
    canonical_data_modified: bool
    credential_profile_used: str
    feed: str
    adjustment: str
    asof: str
    depth: dict[str, object]
    ordinary_overlap: dict[str, object]
    split_windows: dict[str, object]
    corporate_actions: dict[str, object]
    report_path: str


def _pctile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    return float(np.quantile(np.asarray(values, dtype=np.float64), q))


def _relative_difference(left: float, right: float) -> float:
    denominator = max(abs(left), abs(right), 1e-12)
    return abs(left - right) / denominator


def _bars_from_payload(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    bars = payload.get("bars")
    return [bar for bar in bars if isinstance(bar, dict)] if isinstance(bars, list) else []


def _session_date(timestamp: object) -> str:
    return str(timestamp)[:10]


def _bar_map(bars: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_session_date(bar.get("t")): bar for bar in bars if bar.get("t")}


def _largest_adjacent_close_ratio(rows: dict[str, dict[str, Any]], close_field: str) -> dict[str, object] | None:
    dates = sorted(rows)
    best: dict[str, object] | None = None
    for left_date, right_date in zip(dates, dates[1:], strict=False):
        left = float(rows[left_date][close_field])
        right = float(rows[right_date][close_field])
        if left <= 0 or right <= 0:
            continue
        ratio = max(left / right, right / left)
        candidate = {
            "from": left_date,
            "to": right_date,
            "left_close": left,
            "right_close": right,
            "max_ratio": ratio,
        }
        if best is None or float(candidate["max_ratio"]) > float(best["max_ratio"]):
            best = candidate
    return best


class AlpacaHistoryCompatibilityAudit:
    """Read-only audit of Alpaca raw SIP history against ATLAS Massive daily history."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        load_dotenv(settings.project_root / ".env", override=False)
        self.profile, self.headers = self._credential_profile()
        canonical_root = settings.resolved_path(settings.data.paths.canonical)
        self.canonical_glob = (canonical_root / "stocks" / "1d" / "**" / "*.parquet").as_posix()

    def _credential_profile(self) -> tuple[str, dict[str, str]]:
        for profile in ("paper", "live"):
            key_env, secret_env = ALPACA_CREDENTIAL_PROFILES[profile]
            key = os.getenv(key_env, "").strip()
            secret = os.getenv(secret_env, "").strip()
            if key and secret:
                return profile, _alpaca_headers(key, secret)
        raise RuntimeError("Alpaca audit requires one configured paper or live key/secret pair")

    def report_path(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "historical_source_audit" / "alpaca_sip_massive_overlap.json"

    def _alpaca_bars(self, symbol: str, start: str, end: str) -> tuple[list[dict[str, Any]], dict[str, object]]:
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
        bars = _bars_from_payload(result.payload)
        return bars, {
            "status": result.status,
            "http_status": result.http_status,
            "provider_message": (
                result.payload.get("message") if isinstance(result.payload, dict) else result.message
            ),
            "rows": len(bars),
            "first": bars[0].get("t") if bars else None,
            "last": bars[-1].get("t") if bars else None,
            "rate_limit": result.response_headers,
        }

    def _massive_rows(self, symbol: str, start: str, end: str) -> dict[str, dict[str, Any]]:
        con = connect_utc(":memory:")
        try:
            rows = con.execute(
                f"""
                SELECT
                    CAST(timestamp_utc AS DATE)::VARCHAR AS session_date,
                    CAST(open AS DOUBLE), CAST(high AS DOUBLE), CAST(low AS DOUBLE),
                    CAST(close AS DOUBLE), CAST(volume AS DOUBLE)
                FROM read_parquet({sql_string(self.canonical_glob)}, hive_partitioning=true)
                WHERE symbol = {sql_string(symbol)}
                  AND CAST(timestamp_utc AS DATE) BETWEEN DATE {sql_string(start)} AND DATE {sql_string(end)}
                ORDER BY timestamp_utc
                """
            ).fetchall()
        finally:
            con.close()
        return {
            str(row[0]): {
                "o": float(row[1]),
                "h": float(row[2]),
                "l": float(row[3]),
                "c": float(row[4]),
                "v": float(row[5]),
            }
            for row in rows
        }

    def _comparison(self, symbol: str, start: str, end: str) -> dict[str, object]:
        bars, access = self._alpaca_bars(symbol, start, end)
        alpaca = _bar_map(bars)
        massive = self._massive_rows(symbol, start, end)
        common = sorted(set(alpaca).intersection(massive))
        price_diffs: list[float] = []
        close_diffs: list[float] = []
        volume_diffs: list[float] = []
        for day in common:
            a = alpaca[day]
            m = massive[day]
            for field in ("o", "h", "l", "c"):
                price_diffs.append(_relative_difference(float(a[field]), float(m[field])))
            close_diffs.append(_relative_difference(float(a["c"]), float(m["c"])))
            volume_diffs.append(_relative_difference(float(a["v"]), float(m["v"])))
        return {
            "symbol": symbol,
            "start": start,
            "end": end,
            "alpaca_access": access,
            "alpaca_rows": len(alpaca),
            "massive_rows": len(massive),
            "matched_sessions": len(common),
            "alpaca_only_sessions": sorted(set(alpaca).difference(massive)),
            "massive_only_sessions": sorted(set(massive).difference(alpaca)),
            "median_abs_ohlc_relative_diff": (median(price_diffs) if price_diffs else None),
            "p95_abs_ohlc_relative_diff": _pctile(price_diffs, 0.95),
            "max_abs_ohlc_relative_diff": (max(price_diffs) if price_diffs else None),
            "median_abs_close_relative_diff": (median(close_diffs) if close_diffs else None),
            "p95_abs_close_relative_diff": _pctile(close_diffs, 0.95),
            "close_within_1bp_fraction": (
                sum(value <= 0.0001 for value in close_diffs) / len(close_diffs) if close_diffs else None
            ),
            "close_within_10bp_fraction": (
                sum(value <= 0.001 for value in close_diffs) / len(close_diffs) if close_diffs else None
            ),
            "median_abs_volume_relative_diff": (median(volume_diffs) if volume_diffs else None),
            "p95_abs_volume_relative_diff": _pctile(volume_diffs, 0.95),
            "volume_within_1pct_fraction": (
                sum(value <= 0.01 for value in volume_diffs) / len(volume_diffs) if volume_diffs else None
            ),
            "volume_within_5pct_fraction": (
                sum(value <= 0.05 for value in volume_diffs) / len(volume_diffs) if volume_diffs else None
            ),
            "alpaca_largest_adjacent_close_ratio": _largest_adjacent_close_ratio(alpaca, "c"),
            "massive_largest_adjacent_close_ratio": _largest_adjacent_close_ratio(massive, "c"),
        }

    def _depth(self) -> dict[str, object]:
        evidence: dict[str, object] = {}
        for symbol in ALPACA_DEPTH_SYMBOLS:
            bars, access = self._alpaca_bars(symbol, ALPACA_DEPTH_START, ALPACA_DEPTH_END)
            evidence[symbol] = {
                **access,
                "requested_start": ALPACA_DEPTH_START,
                "requested_end": ALPACA_DEPTH_END,
                "earliest_session": _session_date(bars[0].get("t")) if bars else None,
                "latest_session": _session_date(bars[-1].get("t")) if bars else None,
            }
        return evidence

    def _corporate_actions(self) -> dict[str, object]:
        result = _http_get(
            alpaca_corporate_actions_url(
                symbols=ALPACA_CORPORATE_ACTION_SYMBOLS,
                start=ALPACA_CORPORATE_ACTION_START,
                end=ALPACA_CORPORATE_ACTION_END,
            ),
            headers=self.headers,
        )
        output: dict[str, object] = {
            "status": result.status,
            "http_status": result.http_status,
            "symbols": ALPACA_CORPORATE_ACTION_SYMBOLS,
            "start": ALPACA_CORPORATE_ACTION_START,
            "end": ALPACA_CORPORATE_ACTION_END,
            "type_counts": {},
            "next_page_token_present": False,
        }
        payload = result.payload
        if not isinstance(payload, dict):
            output["message"] = result.message
            return output
        actions = payload.get("corporate_actions")
        counts: dict[str, int] = {}
        samples: dict[str, object] = {}
        if isinstance(actions, dict):
            for action_type, items in actions.items():
                if isinstance(items, list):
                    counts[str(action_type)] = len(items)
                    if items:
                        samples[str(action_type)] = items[0]
        output["type_counts"] = counts
        output["sample_by_type"] = samples
        output["next_page_token_present"] = bool(payload.get("next_page_token"))
        return output

    def run(self) -> AlpacaHistoryAuditReport:
        ordinary = {
            symbol: self._comparison(symbol, ALPACA_OVERLAP_START, ALPACA_OVERLAP_END)
            for symbol in ALPACA_OVERLAP_SYMBOLS
        }
        split = {
            f"{symbol}_{start}_{end}": self._comparison(symbol, start, end)
            for symbol, start, end in ALPACA_SPLIT_WINDOWS
        }
        report = AlpacaHistoryAuditReport(
            contract_version=ALPACA_HISTORY_AUDIT_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            canonical_data_modified=False,
            credential_profile_used=self.profile,
            feed="sip",
            adjustment="raw",
            asof="-",
            depth=self._depth(),
            ordinary_overlap=ordinary,
            split_windows=split,
            corporate_actions=self._corporate_actions(),
            report_path=str(self.report_path()),
        )
        atomic_write_text(self.report_path(), json.dumps(asdict(report), indent=2, sort_keys=True, default=str) + "\n")
        return report
