from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from packages.features.reference_daily import REFERENCE_DAILY_FEATURE_FINGERPRINT
from packages.performance.ledger import (
    StrategyTrialLedger,
    StrategyTrialLedgerConflict,
    StrategyTrialLedgerError,
)
from packages.schemas.strategy_lab import (
    StrategyTrialDisposition,
    StrategyTrialDraft,
    StrategyTrialStage,
)
from packages.strategies.reference_library import REFERENCE_STRATEGY_POLICY_FINGERPRINT


def _draft(trial_id: str) -> StrategyTrialDraft:
    return StrategyTrialDraft(
        trial_id=trial_id,
        registered_at_utc=datetime(2026, 9, 3, 12, 0, tzinfo=UTC),
        stage=StrategyTrialStage.SPECIFICATION,
        disposition=StrategyTrialDisposition.REGISTERED,
        family_ids=("ma_trend_cross_50_200",),
        strategy_ids=("ma_trend_cross_50_200_long_v1",),
        strategy_policy_fingerprint=REFERENCE_STRATEGY_POLICY_FINGERPRINT,
        feature_fingerprint=REFERENCE_DAILY_FEATURE_FINGERPRINT,
        hypotheses=("Frozen before performance.",),
        notes=("No outcomes opened.",),
    )


def test_trial_ledger_appends_hash_chained_records(tmp_path) -> None:
    ledger = StrategyTrialLedger(tmp_path / "trials.jsonl")
    first = ledger.append(_draft("a33-spec-001"))
    second = ledger.append(_draft("a33-spec-002"))
    records = ledger.read()
    assert records == (first, second)
    assert first.sequence == 1
    assert second.sequence == 2
    assert second.previous_record_hash == first.record_hash
    assert all(record.master_protected_return_rows_read == 0 for record in records)


def test_trial_ledger_rejects_duplicate_and_tampering(tmp_path) -> None:
    path = tmp_path / "trials.jsonl"
    ledger = StrategyTrialLedger(path)
    ledger.append(_draft("a33-spec-001"))
    with pytest.raises(StrategyTrialLedgerConflict, match="already exists"):
        ledger.append(_draft("a33-spec-001"))

    payload = json.loads(path.read_text(encoding="utf-8").strip())
    payload["notes"] = ["tampered"]
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(StrategyTrialLedgerError, match="hash mismatch"):
        ledger.read()
