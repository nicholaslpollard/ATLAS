from __future__ import annotations

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
from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.features.incremental import IncrementalFeatureEngine
from packages.ml.model_registry_policy import ML_MODEL_REGISTRY_ACCEPTED_MODEL_ID


ALPACA_FEATURE_SEAM_AUDIT_CONTRACT_VERSION = (
    "historical-source-audit-v3-alpaca-volume-feature-model-seam"
)
ALPACA_FEATURE_SEAM_START = "2021-08-16"
ALPACA_FEATURE_SEAM_END = "2023-08-15"
ALPACA_FEATURE_SEAM_SYMBOLS = (
    "AAPL",
    "MSFT",
    "NVDA",
    "TSLA",
    "SPY",
    "QQQ",
    "AMZN",
    "GOOG",
)
ALPACA_VOLUME_FEATURES = (
    "obv",
    "relative_volume_20",
    "volume_zscore_20",
    "dollar_volume",
    "relative_dollar_volume_20",
)


@dataclass(frozen=True, slots=True)
class AlpacaFeatureSeamAuditReport:
    contract_version: str
    generated_at_utc: str
    canonical_data_modified: bool
    feed: str
    adjustment: str
    asof: str
    start: str
    end: str
    symbols: tuple[str, ...]
    feature_count: int
    volume_features: tuple[str, ...]
    model_id: str
    model_artifact_present: bool
    per_symbol: dict[str, object]
    aggregate_feature_differences: dict[str, object]
    model_probability_sensitivity: dict[str, object]
    report_path: str


def _pctile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    return float(np.quantile(np.asarray(values, dtype=np.float64), q))


def _correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2 or len(right) != len(left):
        return None
    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    if np.std(a) == 0.0 or np.std(b) == 0.0:
        return 1.0 if np.array_equal(a, b) else None
    return float(np.corrcoef(a, b)[0, 1])


def _feature_summary(left: list[float], right: list[float]) -> dict[str, object]:
    if len(left) != len(right):
        raise ValueError("feature comparison arrays must have equal length")
    abs_diffs = [abs(a - b) for a, b in zip(left, right, strict=True)]
    rel_diffs = [_relative_difference(a, b) for a, b in zip(left, right, strict=True)]
    return {
        "rows": len(left),
        "median_abs_diff": median(abs_diffs) if abs_diffs else None,
        "p95_abs_diff": _pctile(abs_diffs, 0.95),
        "max_abs_diff": max(abs_diffs) if abs_diffs else None,
        "median_abs_relative_diff": median(rel_diffs) if rel_diffs else None,
        "p95_abs_relative_diff": _pctile(rel_diffs, 0.95),
        "correlation": _correlation(left, right),
    }


def _finite_feature_pair(
    massive_values: dict[str, float | None],
    alpaca_values: dict[str, float | None],
    feature_names: tuple[str, ...],
) -> bool:
    for name in feature_names:
        m = massive_values.get(name)
        a = alpaca_values.get(name)
        if m is None or a is None:
            return False
        if not np.isfinite(float(m)) or not np.isfinite(float(a)):
            return False
    return True


class AlpacaFeatureSeamAudit:
    """Measure whether Alpaca-vs-Massive SIP volume differences affect ATLAS features/model output.

    Prices are not rewritten and no provider/canonical partitions are modified. Both feature
    streams are rebuilt in memory on the same matched sessions. The accepted Phase 10 model,
    when present locally, is then scored on both feature matrices to measure probability drift.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.history = AlpacaHistoryCompatibilityAudit(settings)
        self.feature_names = tuple(definition.name for definition in CORE_FEATURE_REGISTRY.all())

    def report_path(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "historical_source_audit" / "alpaca_feature_model_seam.json"

    def model_path(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return (
            root
            / "ml"
            / "model_registry"
            / ML_MODEL_REGISTRY_ACCEPTED_MODEL_ID
            / "final_fit"
            / "model.joblib"
        )

    def _symbol_rows(self, symbol: str) -> dict[str, object]:
        alpaca_bars, access = self.history._alpaca_bars(
            symbol,
            ALPACA_FEATURE_SEAM_START,
            ALPACA_FEATURE_SEAM_END,
        )
        alpaca = _bar_map(alpaca_bars)
        massive = self.history._massive_rows(
            symbol,
            ALPACA_FEATURE_SEAM_START,
            ALPACA_FEATURE_SEAM_END,
        )
        common = sorted(set(alpaca).intersection(massive))
        massive_engine = IncrementalFeatureEngine()
        alpaca_engine = IncrementalFeatureEngine()

        feature_pairs: dict[str, tuple[list[float], list[float]]] = {
            name: ([], []) for name in self.feature_names
        }
        complete_massive: list[list[float]] = []
        complete_alpaca: list[list[float]] = []
        complete_dates: list[str] = []

        for day in common:
            timestamp = datetime.fromisoformat(f"{day}T00:00:00+00:00")
            mbar = massive[day]
            abar = alpaca[day]
            mvalues = massive_engine.update(
                symbol=symbol,
                timestamp_utc=timestamp,
                high=float(mbar["h"]),
                low=float(mbar["l"]),
                close=float(mbar["c"]),
                volume=float(mbar["v"]),
            )
            avalues = alpaca_engine.update(
                symbol=symbol,
                timestamp_utc=timestamp,
                high=float(abar["h"]),
                low=float(abar["l"]),
                close=float(abar["c"]),
                volume=float(abar["v"]),
            )

            for name in self.feature_names:
                mv = mvalues.get(name)
                av = avalues.get(name)
                if mv is None or av is None:
                    continue
                if np.isfinite(float(mv)) and np.isfinite(float(av)):
                    feature_pairs[name][0].append(float(mv))
                    feature_pairs[name][1].append(float(av))

            if _finite_feature_pair(mvalues, avalues, self.feature_names):
                complete_massive.append([float(mvalues[name]) for name in self.feature_names])
                complete_alpaca.append([float(avalues[name]) for name in self.feature_names])
                complete_dates.append(day)

        summaries = {
            name: _feature_summary(*feature_pairs[name])
            for name in self.feature_names
        }
        nonvolume = [name for name in self.feature_names if name not in ALPACA_VOLUME_FEATURES]
        nonvolume_max = max(
            (
                float(summaries[name]["max_abs_diff"])
                for name in nonvolume
                if summaries[name]["max_abs_diff"] is not None
            ),
            default=0.0,
        )
        return {
            "symbol": symbol,
            "alpaca_access": access,
            "alpaca_rows": len(alpaca),
            "massive_rows": len(massive),
            "matched_sessions": len(common),
            "alpaca_only_sessions": sorted(set(alpaca).difference(massive)),
            "massive_only_sessions": sorted(set(massive).difference(alpaca)),
            "complete_feature_rows": len(complete_dates),
            "complete_start": complete_dates[0] if complete_dates else None,
            "complete_end": complete_dates[-1] if complete_dates else None,
            "nonvolume_feature_max_abs_diff": nonvolume_max,
            "feature_differences": summaries,
            "massive_matrix": complete_massive,
            "alpaca_matrix": complete_alpaca,
        }

    @staticmethod
    def _probability_sensitivity(model: Any, massive: np.ndarray, alpaca: np.ndarray) -> dict[str, object]:
        if massive.shape != alpaca.shape:
            raise ValueError("model sensitivity matrices must have equal shape")
        if massive.size == 0:
            return {"rows": 0}
        p_massive = np.asarray(model.predict_proba(massive), dtype=np.float64)
        p_alpaca = np.asarray(model.predict_proba(alpaca), dtype=np.float64)
        diffs = np.abs(p_massive - p_alpaca)
        row_max = diffs.max(axis=1)
        row_mean = diffs.mean(axis=1)
        argmax_changes = np.argmax(p_massive, axis=1) != np.argmax(p_alpaca, axis=1)
        return {
            "rows": int(massive.shape[0]),
            "mean_abs_probability_diff": float(diffs.mean()),
            "median_row_max_probability_diff": float(np.median(row_max)),
            "p95_row_max_probability_diff": float(np.quantile(row_max, 0.95)),
            "max_row_probability_diff": float(row_max.max()),
            "mean_row_probability_diff": float(row_mean.mean()),
            "rows_with_max_diff_le_1bp_fraction": float(np.mean(row_max <= 0.0001)),
            "rows_with_max_diff_le_10bp_fraction": float(np.mean(row_max <= 0.001)),
            "rows_with_max_diff_le_100bp_fraction": float(np.mean(row_max <= 0.01)),
            "argmax_change_fraction": float(np.mean(argmax_changes)),
        }

    def run(self) -> AlpacaFeatureSeamAuditReport:
        raw: dict[str, dict[str, object]] = {
            symbol: self._symbol_rows(symbol) for symbol in ALPACA_FEATURE_SEAM_SYMBOLS
        }

        aggregate_pairs: dict[str, tuple[list[float], list[float]]] = {
            name: ([], []) for name in self.feature_names
        }
        massive_matrix: list[list[float]] = []
        alpaca_matrix: list[list[float]] = []
        per_symbol: dict[str, object] = {}

        for symbol, result in raw.items():
            feature_differences = result["feature_differences"]
            per_symbol[symbol] = {
                key: value
                for key, value in result.items()
                if key not in {"massive_matrix", "alpaca_matrix", "feature_differences"}
            }
            per_symbol[symbol]["volume_feature_differences"] = {
                name: feature_differences[name] for name in ALPACA_VOLUME_FEATURES
            }
            massive_matrix.extend(result["massive_matrix"])
            alpaca_matrix.extend(result["alpaca_matrix"])

        # Re-run lightweight aggregation from per-symbol feature summaries is not valid for
        # medians/correlations, so rebuild feature vectors once more from the symbol data.
        # The matrices already contain only complete rows and preserve the accepted feature order.
        # For aggregate feature metrics, use the complete matrices directly by feature column.
        massive_array = np.asarray(massive_matrix, dtype=np.float64)
        alpaca_array = np.asarray(alpaca_matrix, dtype=np.float64)
        aggregate_features: dict[str, object] = {}
        if massive_array.size:
            for index, name in enumerate(self.feature_names):
                aggregate_features[name] = _feature_summary(
                    massive_array[:, index].tolist(),
                    alpaca_array[:, index].tolist(),
                )

        model_path = self.model_path()
        model_present = model_path.is_file()
        sensitivity: dict[str, object]
        if model_present and massive_array.size:
            model = joblib.load(model_path)
            sensitivity = self._probability_sensitivity(model, massive_array, alpaca_array)
        else:
            sensitivity = {
                "rows": int(massive_array.shape[0]) if massive_array.ndim == 2 else 0,
                "status": "MODEL_ARTIFACT_NOT_PRESENT" if not model_present else "NO_COMPLETE_FEATURE_ROWS",
            }

        report = AlpacaFeatureSeamAuditReport(
            contract_version=ALPACA_FEATURE_SEAM_AUDIT_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            canonical_data_modified=False,
            feed="sip",
            adjustment="raw",
            asof="-",
            start=ALPACA_FEATURE_SEAM_START,
            end=ALPACA_FEATURE_SEAM_END,
            symbols=ALPACA_FEATURE_SEAM_SYMBOLS,
            feature_count=len(self.feature_names),
            volume_features=ALPACA_VOLUME_FEATURES,
            model_id=ML_MODEL_REGISTRY_ACCEPTED_MODEL_ID,
            model_artifact_present=model_present,
            per_symbol=per_symbol,
            aggregate_feature_differences=aggregate_features,
            model_probability_sensitivity=sensitivity,
            report_path=str(self.report_path()),
        )
        atomic_write_text(
            self.report_path(),
            json.dumps(asdict(report), indent=2, sort_keys=True, default=str) + "\n",
        )
        return report
