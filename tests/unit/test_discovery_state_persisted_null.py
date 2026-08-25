from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from pydantic import ValidationError

from packages.discovery.current_candidates import CurrentCandidateMaterializer
from packages.schemas.discovery_state import DiscoveryStateRecord


def _payload(*, transition: str = "bootstrap_warm_pending") -> dict[str, object]:
    return {
        "instrument_id": "figi-test",
        "ticker": "TEST",
        "as_of_date": date(2026, 8, 21),
        "raw_state": "warm",
        "effective_state": "watch",
        "previous_effective_state": float("nan"),
        "warm_confirmation_streak": 1,
        "demotion_streak": 0,
        "transition": transition,
        "priority_score": 0.6,
        "bull_evidence": 0.7,
        "bear_evidence": 0.2,
        "direction": "bullish",
        "scored_timeframes": 3,
        "top_setup": "momentum",
    }


def test_discovery_state_normalizes_parquet_nan_optional_previous_state_to_none() -> None:
    record = DiscoveryStateRecord.model_validate(_payload())
    assert record.previous_effective_state is None
    assert record.transition == "bootstrap_warm_pending"


def test_current_candidate_pandas_row_roundtrip_normalizes_optional_previous_state_nan() -> None:
    row = pd.Series(_payload())
    record = CurrentCandidateMaterializer._discovery_record(row)
    assert record.previous_effective_state is None


def test_nan_normalization_does_not_bypass_bootstrap_semantics() -> None:
    with pytest.raises(ValidationError, match="bootstrap"):
        DiscoveryStateRecord.model_validate(_payload(transition="hold_watch"))
