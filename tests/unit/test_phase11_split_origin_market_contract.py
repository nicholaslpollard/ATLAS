from __future__ import annotations

from datetime import date

import pytest

from packages.discovery.current_candidates import (
    CurrentCandidateMaterializationError,
    _validate_split_origin_market_manifest,
    _validate_split_origin_market_snapshot,
)
from packages.regimes.split_origin_policy import (
    MARKET_SECTOR_HISTORY_ORIGIN_DATE,
    MARKET_SECTOR_MANIFEST_VERSION,
    MARKET_SECTOR_POLICY_GENESIS_FINGERPRINT,
    MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
    MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
    SPLIT_ORIGIN_POLICY_VERSION,
    TICKER_HISTORY_ORIGIN_DATE,
)


AS_OF = date(2026, 8, 14)


def _manifest() -> dict[str, object]:
    return {
        "manifest_version": MARKET_SECTOR_MANIFEST_VERSION,
        "snapshot_contract_version": MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
        "state_policy_contract_version": MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
        "split_origin_policy_version": SPLIT_ORIGIN_POLICY_VERSION,
        "history_origin_date": MARKET_SECTOR_HISTORY_ORIGIN_DATE.isoformat(),
        "ticker_history_origin_date": TICKER_HISTORY_ORIGIN_DATE.isoformat(),
        "gate10a_source_fingerprint": MARKET_SECTOR_POLICY_GENESIS_FINGERPRINT,
        "as_of_date": AS_OF.isoformat(),
    }


def _snapshot() -> dict[str, object]:
    return {
        "snapshot_contract_version": MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
        "state_policy_contract_version": MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
        "split_origin_policy_version": SPLIT_ORIGIN_POLICY_VERSION,
        "history_origin_date": MARKET_SECTOR_HISTORY_ORIGIN_DATE.isoformat(),
        "ticker_history_origin_date": TICKER_HISTORY_ORIGIN_DATE.isoformat(),
        "as_of_date": AS_OF.isoformat(),
    }


def test_phase11_requires_accepted_split_origin_v2_market_contract() -> None:
    _validate_split_origin_market_manifest(_manifest(), AS_OF)
    _validate_split_origin_market_snapshot(_snapshot(), AS_OF)


def test_phase11_rejects_legacy_phase9_v1_market_contract() -> None:
    manifest = _manifest()
    manifest["manifest_version"] = "regime-state-manifest-v1-policy-source-lineage"
    with pytest.raises(CurrentCandidateMaterializationError, match="split-origin contract changed"):
        _validate_split_origin_market_manifest(manifest, AS_OF)
