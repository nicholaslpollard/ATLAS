from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.backtesting.successor_parallel import (
    CompletedGroup,
    ResearchWorkUnit,
    publish_completed_group,
    scientific_run_fingerprint,
    validate_completed_group,
)
from packages.core.execution_profile import GIB
from packages.core.successor_execution_profile import resolve_successor_research_execution_profile
from packages.strategies.successor_practitioner_lab import (
    B35_CHALLENGERS,
    CONFLUENCE_CONTRACT,
    EVALUATION_CONTRACT,
    NEW_FAMILIES,
    RETAINED_FAMILIES,
    RUNTIME_CONTRACT,
    SUCCESSOR_FAMILIES,
    SUCCESSOR_LAB_FINGERPRINT,
    frozen_successor_manifest,
)


def test_successor_roster_is_exactly_21_economic_families() -> None:
    assert len(RETAINED_FAMILIES) == 10
    assert len(NEW_FAMILIES) == 11
    assert len(SUCCESSOR_FAMILIES) == 21
    assert len({item.family_id for item in SUCCESSOR_FAMILIES}) == 21


def test_b35_challengers_remain_inside_existing_economic_families() -> None:
    family_ids = {item.family_id for item in SUCCESSOR_FAMILIES}
    assert {item.policy_id for item in B35_CHALLENGERS} == {
        "gap_quality_condition_long_v2",
        "orb_stocks_in_play_5m_v1",
        "orb_15m_close_retest_v2",
        "premarket_relvol_quality_v2",
    }
    assert all(item.economic_family_id in family_ids for item in B35_CHALLENGERS)
    assert all(item.same_family_for_multiplicity for item in B35_CHALLENGERS)
    assert not any("highest_volume_day" in item.policy_id for item in B35_CHALLENGERS)


def test_successor_evidence_boundaries_fail_closed() -> None:
    assert EVALUATION_CONTRACT["master_reuse_permitted"] is False
    assert EVALUATION_CONTRACT["future_blind_read_permitted"] is False
    assert EVALUATION_CONTRACT["promotion_from_this_contract"] is False
    assert EVALUATION_CONTRACT["standalone_before_conditioning"] is True
    assert EVALUATION_CONTRACT["standalone_before_confluence"] is True
    assert EVALUATION_CONTRACT["challenger_inspired_by_development_can_validate_on_same_development"] is False


def test_confluence_does_not_turn_correlated_indicators_into_votes() -> None:
    assert CONFLUENCE_CONTRACT["separate_from_strategy_firing"] is True
    assert CONFLUENCE_CONTRACT["count_distinct_evidence_families"] is True
    assert CONFLUENCE_CONTRACT["correlated_indicator_votes_are_independent"] is False
    assert CONFLUENCE_CONTRACT["arbitrary_subjective_point_score_permitted"] is False


def test_successor_fingerprint_is_deterministic_and_authority_free() -> None:
    first = frozen_successor_manifest()
    second = frozen_successor_manifest()
    assert first == second
    assert first["fingerprint"] == SUCCESSOR_LAB_FINGERPRINT
    assert len(SUCCESSOR_LAB_FINGERPRINT) == 64
    assert first["authority"] == {
        "strategy_authority": "RESEARCH",
        "paper_authority": False,
        "live_authority": False,
        "promotion_authority": False,
        "provider_calls": 0,
        "broker_reads": 0,
        "broker_writes": 0,
    }


def test_i7_8700k_class_auto_profile_prefers_sustained_8x1() -> None:
    profile = resolve_successor_research_execution_profile(
        logical_cpus=12,
        total_memory_bytes=24 * GIB,
    )
    assert profile.reserved_logical_cpus == 2
    assert profile.workers == 8
    assert profile.duckdb_threads_per_worker == 1
    assert profile.aggregate_worker_threads == 8
    assert RUNTIME_CONTRACT["scientific_identity_excludes_execution_profile"] is True


def test_successor_profile_override_cannot_oversubscribe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_SUCCESSOR_REPLAY_WORKERS", "10")
    monkeypatch.setenv("ATLAS_SUCCESSOR_DUCKDB_THREADS_PER_WORKER", "2")
    with pytest.raises(ValueError, match="oversubscribe"):
        resolve_successor_research_execution_profile(
            logical_cpus=12,
            total_memory_bytes=24 * GIB,
        )


def test_receipt_reuse_is_hash_verified_and_execution_profile_independent(tmp_path: Path) -> None:
    unit = ResearchWorkUnit(token="group_001", input_fingerprint="a" * 64)
    group = publish_completed_group(
        tmp_path,
        unit,
        {"answer": 42},
        scientific_contract_fingerprint="b" * 64,
    )
    reused = validate_completed_group(
        tmp_path,
        unit,
        scientific_contract_fingerprint="b" * 64,
    )
    assert reused is not None
    assert reused.reused is True
    assert reused.receipt_id == group.receipt_id

    fingerprint_a = scientific_run_fingerprint(
        scientific_contract_fingerprint="b" * 64,
        completed_groups=[group],
    )
    fingerprint_b = scientific_run_fingerprint(
        scientific_contract_fingerprint="b" * 64,
        completed_groups=[
            CompletedGroup(
                token=group.token,
                receipt_id=group.receipt_id,
                output_sha256=group.output_sha256,
                reused=True,
            )
        ],
    )
    assert fingerprint_a == fingerprint_b


def test_corrupt_receipt_fails_closed(tmp_path: Path) -> None:
    unit = ResearchWorkUnit(token="group_002", input_fingerprint="c" * 64)
    publish_completed_group(
        tmp_path,
        unit,
        {"answer": 7},
        scientific_contract_fingerprint="d" * 64,
    )
    receipt_path = tmp_path / "groups" / unit.token / "receipt.json"
    value = json.loads(receipt_path.read_text(encoding="utf-8"))
    value["input_fingerprint"] = "e" * 64
    receipt_path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(RuntimeError, match="self-hash"):
        validate_completed_group(
            tmp_path,
            unit,
            scientific_contract_fingerprint="d" * 64,
        )
