from __future__ import annotations

import numpy as np

from packages.data.alpaca_cross_section_audit import (
    LIQUIDITY_BUCKETS,
    _probability_summary,
    _sample_key,
    liquidity_bucket,
)
from packages.data.alpaca_universe_audit import LEGACY_SENTINELS, REUSE_SENTINEL, REUSE_WINDOWS


class _Model:
    def predict_proba(self, rows: np.ndarray) -> np.ndarray:
        # Deterministic three-class surface that changes smoothly with the first feature.
        x = np.asarray(rows, dtype=np.float64)[:, 0]
        p0 = np.clip(0.2 + x * 0.01, 0.01, 0.8)
        p1 = np.full_like(p0, 0.5)
        p2 = 1.0 - p0 - p1
        return np.column_stack([p0, p1, p2])


def test_liquidity_bucket_boundaries_match_locked_gate11_family() -> None:
    assert liquidity_bucket(249_999.0) is None
    assert liquidity_bucket(250_000.0) == "250K_TO_1M"
    assert liquidity_bucket(999_999.0) == "250K_TO_1M"
    assert liquidity_bucket(1_000_000.0) == "1M_TO_5M"
    assert liquidity_bucket(5_000_000.0) == "5M_TO_25M"
    assert liquidity_bucket(25_000_000.0) == "25M_PLUS"


def test_liquidity_bucket_contract_has_four_nonoverlapping_buckets() -> None:
    assert [name for name, _, _ in LIQUIDITY_BUCKETS] == [
        "250K_TO_1M",
        "1M_TO_5M",
        "5M_TO_25M",
        "25M_PLUS",
    ]


def test_cross_section_sample_key_is_deterministic() -> None:
    assert _sample_key("AAPL") == _sample_key("AAPL")
    assert _sample_key("AAPL") != _sample_key("MSFT")


def test_probability_summary_detects_zero_provider_drift() -> None:
    rows = [[1.0, 2.0], [2.0, 3.0], [3.0, 4.0]]
    result = _probability_summary(_Model(), rows, rows)
    assert result["rows"] == 3
    assert result["max_row_probability_diff"] == 0.0
    assert result["argmax_change_fraction"] == 0.0


def test_probability_summary_detects_nonzero_provider_drift() -> None:
    left = [[1.0, 2.0], [2.0, 3.0], [3.0, 4.0]]
    right = [[1.5, 2.0], [2.5, 3.0], [3.5, 4.0]]
    result = _probability_summary(_Model(), left, right)
    assert result["rows"] == 3
    assert result["mean_abs_probability_diff"] > 0.0
    assert result["max_row_probability_diff"] > 0.0


def test_universe_audit_has_legacy_and_reuse_sentinels() -> None:
    assert len(LEGACY_SENTINELS) >= 10
    assert REUSE_SENTINEL == "S"
    assert [label for label, _, _ in REUSE_WINDOWS] == ["SPRINT_ERA", "SENTINELONE_ERA"]
