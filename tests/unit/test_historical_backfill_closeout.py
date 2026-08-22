from __future__ import annotations

from packages.ml.historical_backfill_closeout import (
    HISTORICAL_BACKFILL_CLOSEOUT_BROKER_WRITES,
    HISTORICAL_BACKFILL_CLOSEOUT_CONTRACT_VERSION,
    HISTORICAL_BACKFILL_CLOSEOUT_PRODUCTION_MODEL_REPLACEMENT_ALLOWED,
)


def test_historical_closeout_is_phase_level_and_nonproduction() -> None:
    assert HISTORICAL_BACKFILL_CLOSEOUT_CONTRACT_VERSION == (
        "historical-backfill-closeout-v1-phase-level-acceptance"
    )
    assert HISTORICAL_BACKFILL_CLOSEOUT_PRODUCTION_MODEL_REPLACEMENT_ALLOWED is False
    assert HISTORICAL_BACKFILL_CLOSEOUT_BROKER_WRITES == 0
