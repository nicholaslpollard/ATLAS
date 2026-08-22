from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from packages.core.settings import load_settings
from packages.ml.current_probability import (
    AcceptedProductionProbabilityProvider,
    CurrentMLProbabilityError,
)
from packages.ml.feature_policy import ML_PRODUCTION_CORE_FEATURE_NAMES


class _FakeModel:
    classes_ = np.asarray([0, 1, 2])

    def predict_proba(self, x):
        rows = len(x)
        return np.repeat(np.asarray([[0.2, 0.3, 0.5]], dtype=np.float64), rows, axis=0)


def _frame(rows: int = 2) -> pd.DataFrame:
    return pd.DataFrame(
        {name: np.repeat(float(index + 1), rows) for index, name in enumerate(ML_PRODUCTION_CORE_FEATURE_NAMES)}
    )


def test_probability_provider_returns_raw_three_class_evidence() -> None:
    provider = AcceptedProductionProbabilityProvider(load_settings())
    provider._model = _FakeModel()  # noqa: SLF001 - unit isolates inference shape from local registry files
    result = provider.predict_frame(_frame())
    assert list(result.columns[-3:]) == ["p_down", "p_neutral", "p_up"]
    assert np.allclose(result[["p_down", "p_neutral", "p_up"]].sum(axis=1), 1.0)
    assert (result["p_up"] == 0.5).all()
    assert "prediction_label" not in result.columns
    assert "direction" not in result.columns


def test_probability_provider_fails_closed_on_missing_predictor() -> None:
    provider = AcceptedProductionProbabilityProvider(load_settings())
    provider._model = _FakeModel()  # noqa: SLF001
    frame = _frame().drop(columns=[ML_PRODUCTION_CORE_FEATURE_NAMES[0]])
    with pytest.raises(CurrentMLProbabilityError):
        provider.predict_frame(frame)
