from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

import joblib
import numpy as np

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.alpaca_history_audit import AlpacaHistoryCompatibilityAudit, _bar_map, _relative_difference
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.features.incremental import IncrementalFeatureEngine
from packages.ml.model_registry_policy import ML_MODEL_REGISTRY_ACCEPTED_MODEL_ID


ALPACA_CROSS_SECTION_AUDIT_CONTRACT_VERSION = (
    "historical-source-audit-v5-alpaca-stratified-liquidity-provider-seam"
)
SAMPLE_START = "2021-08-16"
SAMPLE_END = "2022-12-30"
LIQUIDITY_MEASURE_START = "2022-01-03"
LIQUIDITY_MEASURE_END = "2022-12-30"
SAMPLE_PER_BUCKET = 15
LIQUIDITY_BUCKETS: tuple[tuple[str, float, float | None], ...] = (
    ("250K_TO_1M", 250_000.0, 1_000_000.0),
    ("1M_TO_5M", 1_000_000.0, 5_000_000.0),
    ("5M_TO_25M", 5_000_000.0, 25_000_000.0),
    ("25M_PLUS", 25_000_000.0, None),
)
VOLUME_FEATURES = {
    "obv",
    "relative_volume_20",
    "volume_zscore_20",
    "dollar_volume",
    "relative_dollar_volume_20",
}


@dataclass(frozen=True, slots=True)
class AlpacaCrossSectionAuditReport:
    contract_version: str
    generated_at_utc: str
    canonical_data_modified: bool
    sample_start: str
    sample_end: str
    sample_per_bucket: int
    model_id: str
    model_artifact_present: bool
    selection: dict[str, object]
    per_bucket: dict[str, object]
    aggregate: dict[str, object]
    report_path: str


def liquidity_bucket(value: float) -> str | None:
    for name, lower, upper in LIQUIDITY_BUCKETS:
        if value >= lower and (upper is None or value < upper):
            return name
    return None


def _pctile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    return float(np.quantile(np.asarray(values, dtype=np.float64), q))


def _sample_key(symbol: str) -> str:
    return hashlib.sha256(symbol.encode("utf-8")).hexdigest()


def _probability_summary(model: Any, massive_rows: list[list[float]], alpaca_rows: list[list[float]]) -> dict[str, object]:
    if not massive_rows or len(massive_rows) != len(alpaca_rows):
        return {"rows": 0}
    massive = np.asarray(massive_rows, dtype=np.float64)
    alpaca = np.asarray(alpaca_rows, dtype=np.float64)
    p_m = np.asarray(model.predict_proba(massive), dtype=np.float64)
    p_a = np.asarray(model.predict_proba(alpaca), dtype=np.float64)
    diffs = np.abs(p_m - p_a)
    row_max = diffs.max(axis=1)
    return {
        "rows": int(len(row_max)),
        "mean_abs_probability_diff": float(diffs.mean()),
        "median_row_max_probability_diff": float(np.median(row_max)),
        "p95_row_max_probability_diff": float(np.quantile(row_max, 0.95)),
        "max_row_probability_diff": float(row_max.max()),
        "rows_with_max_diff_le_10bp_fraction": float(np.mean(row_max <= 0.001)),
        "rows_with_max_diff_le_100bp_fraction": float(np.mean(row_max <= 0.01)),
        "argmax_change_fraction": float(np.mean(np.argmax(p_m, axis=1) != np.argmax(p_a, axis=1))),
    }


class AlpacaCrossSectionSeamAudit:
    """Stratified read-only provider-seam audit across ATLAS liquidity buckets."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.history = AlpacaHistoryCompatibilityAudit(settings)
        canonical_root = settings.resolved_path(settings.data.paths.canonical)
        self.canonical_glob = (canonical_root / "stocks" / "1d" / "**" / "*.parquet").as_posix()
        self.feature_names = tuple(definition.name for definition in CORE_FEATURE_REGISTRY.all())

    def report_path(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "historical_source_audit" / "alpaca_cross_section_seam.json"

    def model_path(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "ml" / "model_registry" / ML_MODEL_REGISTRY_ACCEPTED_MODEL_ID / "final_fit" / "model.joblib"

    def _selection(self) -> dict[str, list[dict[str, object]]]:
        con = connect_utc(":memory:")
        try:
            rows = con.execute(
                f"""
                SELECT
                    symbol,
                    COUNT(*) AS sessions,
                    MEDIAN(CAST(close AS DOUBLE) * CAST(volume AS DOUBLE)) AS median_dollar_volume
                FROM read_parquet({sql_string(self.canonical_glob)}, hive_partitioning=true)
                WHERE CAST(timestamp_utc AS DATE)
                    BETWEEN DATE {sql_string(LIQUIDITY_MEASURE_START)} AND DATE {sql_string(LIQUIDITY_MEASURE_END)}
                  AND CAST(close AS DOUBLE) > 0
                  AND CAST(volume AS DOUBLE) >= 0
                GROUP BY symbol
                HAVING COUNT(*) >= 200
                """
            ).fetchall()
        finally:
            con.close()

        buckets: dict[str, list[dict[str, object]]] = {name: [] for name, _, _ in LIQUIDITY_BUCKETS}
        for symbol, sessions, mdv in rows:
            if mdv is None:
                continue
            bucket = liquidity_bucket(float(mdv))
            if bucket is None:
                continue
            buckets[bucket].append(
                {
                    "symbol": str(symbol),
                    "sessions": int(sessions),
                    "median_dollar_volume": float(mdv),
                }
            )
        for name in buckets:
            buckets[name] = sorted(buckets[name], key=lambda item: _sample_key(str(item["symbol"])))[:SAMPLE_PER_BUCKET]
        return buckets

    def _symbol(self, symbol: str, model: Any | None) -> dict[str, object]:
        alpaca_bars, access = self.history._alpaca_bars(symbol, SAMPLE_START, SAMPLE_END)
        alpaca = _bar_map(alpaca_bars)
        massive = self.history._massive_rows(symbol, SAMPLE_START, SAMPLE_END)
        common = sorted(set(alpaca).intersection(massive))
        if not common:
            return {
                "symbol": symbol,
                "access": access,
                "matched_sessions": 0,
                "massive_rows": len(massive),
                "alpaca_rows": len(alpaca),
                "probability": {"rows": 0},
            }

        ohlc_rel: list[float] = []
        volume_rel: list[float] = []
        price_feature_rel: list[float] = []
        volume_feature_rel: list[float] = []
        massive_matrix: list[list[float]] = []
        alpaca_matrix: list[list[float]] = []
        m_engine = IncrementalFeatureEngine()
        a_engine = IncrementalFeatureEngine()

        for day in common:
            mbar = massive[day]
            abar = alpaca[day]
            for field in ("o", "h", "l", "c"):
                ohlc_rel.append(_relative_difference(float(mbar[field]), float(abar[field])))
            volume_rel.append(_relative_difference(float(mbar["v"]), float(abar["v"])))
            timestamp = datetime.fromisoformat(f"{day}T00:00:00+00:00")
            mv = m_engine.update(
                symbol=symbol,
                timestamp_utc=timestamp,
                high=float(mbar["h"]),
                low=float(mbar["l"]),
                close=float(mbar["c"]),
                volume=float(mbar["v"]),
            )
            av = a_engine.update(
                symbol=symbol,
                timestamp_utc=timestamp,
                high=float(abar["h"]),
                low=float(abar["l"]),
                close=float(abar["c"]),
                volume=float(abar["v"]),
            )
            complete = True
            mrow: list[float] = []
            arow: list[float] = []
            for name in self.feature_names:
                left = mv.get(name)
                right = av.get(name)
                if left is None or right is None or not np.isfinite(float(left)) or not np.isfinite(float(right)):
                    complete = False
                    continue
                rel = _relative_difference(float(left), float(right))
                (volume_feature_rel if name in VOLUME_FEATURES else price_feature_rel).append(rel)
                mrow.append(float(left))
                arow.append(float(right))
            if complete and len(mrow) == len(self.feature_names):
                massive_matrix.append(mrow)
                alpaca_matrix.append(arow)

        probability = _probability_summary(model, massive_matrix, alpaca_matrix) if model is not None else {"rows": len(massive_matrix), "status": "MODEL_NOT_PRESENT"}
        return {
            "symbol": symbol,
            "access": access,
            "matched_sessions": len(common),
            "massive_rows": len(massive),
            "alpaca_rows": len(alpaca),
            "median_ohlc_relative_diff": median(ohlc_rel) if ohlc_rel else None,
            "p95_ohlc_relative_diff": _pctile(ohlc_rel, 0.95),
            "median_volume_relative_diff": median(volume_rel) if volume_rel else None,
            "p95_volume_relative_diff": _pctile(volume_rel, 0.95),
            "median_nonvolume_feature_relative_diff": median(price_feature_rel) if price_feature_rel else None,
            "p95_nonvolume_feature_relative_diff": _pctile(price_feature_rel, 0.95),
            "median_volume_feature_relative_diff": median(volume_feature_rel) if volume_feature_rel else None,
            "p95_volume_feature_relative_diff": _pctile(volume_feature_rel, 0.95),
            "probability": probability,
        }

    @staticmethod
    def _aggregate(items: list[dict[str, object]]) -> dict[str, object]:
        usable = [item for item in items if int(item.get("matched_sessions", 0)) > 0]
        prob_rows = sum(int(item.get("probability", {}).get("rows", 0)) for item in usable)
        p95_probs = [
            float(item["probability"]["p95_row_max_probability_diff"])
            for item in usable
            if item.get("probability", {}).get("p95_row_max_probability_diff") is not None
        ]
        argmax = [
            float(item["probability"]["argmax_change_fraction"])
            for item in usable
            if item.get("probability", {}).get("argmax_change_fraction") is not None
        ]
        med_vol = [float(item["median_volume_relative_diff"]) for item in usable if item.get("median_volume_relative_diff") is not None]
        p95_price_features = [float(item["p95_nonvolume_feature_relative_diff"]) for item in usable if item.get("p95_nonvolume_feature_relative_diff") is not None]
        return {
            "sampled_symbols": len(items),
            "usable_symbols": len(usable),
            "matched_sessions": sum(int(item["matched_sessions"]) for item in usable),
            "model_rows": prob_rows,
            "median_of_symbol_median_volume_relative_diff": median(med_vol) if med_vol else None,
            "median_of_symbol_p95_nonvolume_feature_relative_diff": median(p95_price_features) if p95_price_features else None,
            "median_of_symbol_p95_probability_diff": median(p95_probs) if p95_probs else None,
            "max_symbol_p95_probability_diff": max(p95_probs) if p95_probs else None,
            "max_symbol_argmax_change_fraction": max(argmax) if argmax else None,
        }

    def run(self) -> AlpacaCrossSectionAuditReport:
        selected = self._selection()
        model_path = self.model_path()
        model = joblib.load(model_path) if model_path.is_file() else None
        per_bucket: dict[str, object] = {}
        all_results: list[dict[str, object]] = []
        selection_summary: dict[str, object] = {}
        for bucket, rows in selected.items():
            results = [self._symbol(str(item["symbol"]), model) for item in rows]
            all_results.extend(results)
            per_bucket[bucket] = {
                "selection": rows,
                "symbols": results,
                "summary": self._aggregate(results),
            }
            selection_summary[bucket] = {
                "eligible_before_sample": None,
                "selected": len(rows),
                "symbols": [str(item["symbol"]) for item in rows],
            }

        report = AlpacaCrossSectionAuditReport(
            contract_version=ALPACA_CROSS_SECTION_AUDIT_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            canonical_data_modified=False,
            sample_start=SAMPLE_START,
            sample_end=SAMPLE_END,
            sample_per_bucket=SAMPLE_PER_BUCKET,
            model_id=ML_MODEL_REGISTRY_ACCEPTED_MODEL_ID,
            model_artifact_present=model is not None,
            selection=selection_summary,
            per_bucket=per_bucket,
            aggregate=self._aggregate(all_results),
            report_path=str(self.report_path()),
        )
        atomic_write_text(
            self.report_path(),
            json.dumps(asdict(report), indent=2, sort_keys=True, default=str) + "\n",
        )
        return report
