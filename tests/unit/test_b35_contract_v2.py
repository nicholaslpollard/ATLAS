from __future__ import annotations

from datetime import time

import pytest

from packages.strategies.b35_conditional_evidence_contract import (
    B34_PACK_FINGERPRINT,
    B35_PREOUTCOME_CONTRACT,
    B35_PREOUTCOME_FINGERPRINT,
    B35_SUPERSEDED_PREOUTCOME_FINGERPRINT,
    bucket_absolute_gap_pct,
    bucket_signal_time_et,
    frozen_contract_manifest,
)


ACTIVE_FP = "145cc8983439b6062fd5e60303539d1611cdf7db0119ed68a7da1e68ffd8eda6"
OLD_FP = "7bfd1cfdd65e946d45caa99dd2a35a90d8b424cb82cad5941ad26cac51816c4c"
B34_FP = "6f7239fcda11ac6c890d2635980d431ec49e346707d9cc549f111bd50daaa4bf"


def test_v2_preoutcome_contract_supersedes_v1_without_changing_b34() -> None:
    assert B35_PREOUTCOME_CONTRACT == (
        "atlas-b35-a36-conditional-evidence-v2-pre-outcome-clock-split-corrected"
    )
    assert B35_PREOUTCOME_FINGERPRINT == ACTIVE_FP
    assert B35_SUPERSEDED_PREOUTCOME_FINGERPRINT == OLD_FP
    assert B34_PACK_FINGERPRINT == B34_FP
    manifest = frozen_contract_manifest()
    assert manifest["fingerprint"] == ACTIVE_FP
    superseded = manifest["supersedes_preoutcome"]
    assert superseded["fingerprint"] == OLD_FP
    assert superseded["outcomes_opened"] is False


def test_signal_time_bucket_accepts_information_safe_1131_only() -> None:
    assert bucket_signal_time_et(time(11, 30)) == "1031_TO_1131"
    assert bucket_signal_time_et(time(11, 31)) == "1031_TO_1131"
    with pytest.raises(ValueError, match="09:31..11:31"):
        bucket_signal_time_et(time(11, 32))


def test_split_crossed_raw_gap_has_explicit_unavailable_bucket() -> None:
    assert bucket_absolute_gap_pct(None) == "UNAVAILABLE"
    assert bucket_absolute_gap_pct(0.021) == "2_TO_5PCT"
