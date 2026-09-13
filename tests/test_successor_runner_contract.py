from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from packages.backtesting.successor_parallel import ResearchWorkUnit
from packages.backtesting.successor_runner_contract import (
    ARTIFACT_ORDER,
    COST_GRID_BPS,
    DAILY_GROUP_BUCKETS,
    DAILY_SOURCE_ID,
    MINUTE_SOURCE_ID,
    SUCCESSOR_RUNNER_CONTRACT,
    build_source_binding_payload,
    build_successor_runner_contract,
    canonical_sha256,
    daily_group_token,
    frozen_authority_contract,
    frozen_outcome_contract,
    minute_symbol_groups,
    successor_policy_routes,
)
from scripts.run_successor_development_preflight import verify_source_binding_unit


SHA_A = "a" * 64
SHA_B = "b" * 64


def test_runner_contract_freezes_routes_sources_grouping_and_authority() -> None:
    payload = build_successor_runner_contract(
        daily_source_fingerprint=SHA_A,
        minute_source_fingerprint=SHA_B,
    )
    assert payload["contract"] == SUCCESSOR_RUNNER_CONTRACT
    assert payload["development_scope"] == ["2016-01-04", "2026-04-30"]
    assert len(payload["policy_routes"]) == 28
    assert sum(item["native_timeframe"] == "1d" for item in payload["policy_routes"]) == 18
    assert sum(item["native_timeframe"] == "1m" for item in payload["policy_routes"]) == 10
    assert payload["sources"][DAILY_SOURCE_ID]["source_fingerprint"] == SHA_A
    assert payload["sources"][MINUTE_SOURCE_ID]["source_fingerprint"] == SHA_B
    assert payload["grouping"]["daily"]["group_count"] == 64
    assert payload["artifact_order"] == list(ARTIFACT_ORDER)
    assert payload["outcomes"]["cost_grid_bps_all_in_round_trip"] == list(COST_GRID_BPS)
    assert payload["authority"] == frozen_authority_contract()
    assert payload["scientific_identity_excludes_runtime_profile"] is True
    without_fp = dict(payload)
    fingerprint = without_fp.pop("fingerprint")
    assert fingerprint == canonical_sha256(without_fp)


def test_policy_routes_preserve_challenger_multiplicity_and_concrete_timeframes() -> None:
    routes = {item.policy_id: item for item in successor_policy_routes()}
    assert routes["pract_pivot_sr_breakout_v1"].native_timeframe == "1d"
    assert routes["pract_flag_pennant_v1"].native_timeframe == "1d"
    assert routes["pract_vwap_reclaim_reject_v1"].native_timeframe == "1m"
    assert routes["pract_session_failed_break_reclaim_v1"].native_timeframe == "1m"
    assert routes["orb_stocks_in_play_5m_v1"].same_family_for_multiplicity is True
    assert routes["orb_stocks_in_play_5m_v1"].economic_family_id == "opening_range"
    assert routes["b34_opening_range_breakout_15m_v1"].economic_family_id == "opening_range"


def test_daily_group_token_is_stable_bounded_and_profile_independent() -> None:
    token = daily_group_token("US0378331005")
    assert token == daily_group_token("US0378331005")
    assert token.startswith("daily_")
    bucket = int(token.split("_")[1])
    assert 0 <= bucket < DAILY_GROUP_BUCKETS
    with pytest.raises(ValueError):
        daily_group_token("")


@dataclass(frozen=True)
class FakeUnit:
    symbols: tuple[str, ...]
    year: int
    month: int
    batch_index: int
    unit_id: str


def test_minute_grouping_matches_exact_sorted_symbol_tuple_and_unit_order() -> None:
    units = (
        FakeUnit(("A", "B"), 2020, 2, 1, "z"),
        FakeUnit(("C",), 2020, 1, 2, "c"),
        FakeUnit(("A", "B"), 2019, 12, 3, "a"),
    )
    groups = minute_symbol_groups(units)
    assert [item[0] for item in groups] == [("A", "B"), ("C",)]
    assert [item.unit_id for item in groups[0][1]] == ["a", "z"]


def test_outcome_contract_preregisters_daily_and_intraday_mechanics() -> None:
    outcome = frozen_outcome_contract()
    assert outcome["daily"]["entry"] == "NEXT_REGULAR_SESSION_OPEN_AFTER_SIGNAL_CLOSE"
    assert outcome["daily"]["forward_horizons_sessions"] == [1, 5, 20]
    assert outcome["intraday"]["base_semantics"] == "ACCEPTED_B35_INTRADAY_OUTCOMES_V1"
    assert outcome["standalone_before_confluence"] is True
    assert outcome["same_outcome_refit_or_search_permitted"] is False


def test_source_binding_payload_is_root_independent(tmp_path: Path) -> None:
    root_a = tmp_path / "root-a"
    root_b = tmp_path / "root-b"
    source_a = root_a / "data" / "source.parquet"
    source_b = root_b / "data" / "source.parquet"
    source_a.parent.mkdir(parents=True)
    source_b.parent.mkdir(parents=True)
    source_a.write_bytes(b"same-source-bytes")
    source_b.write_bytes(b"same-source-bytes")
    expected = hashlib.sha256(source_a.read_bytes()).hexdigest()

    payload_a = build_source_binding_payload(
        token="daily_source_2020",
        source_id=DAILY_SOURCE_ID,
        files=((source_a, expected),),
        project_root=root_a,
    )
    payload_b = build_source_binding_payload(
        token="daily_source_2020",
        source_id=DAILY_SOURCE_ID,
        files=((source_b, expected),),
        project_root=root_b,
    )

    assert payload_a == payload_b
    assert payload_a["files"][0]["relative_path"] == "data/source.parquet"
    assert canonical_sha256(payload_a) == canonical_sha256(payload_b)


def test_source_binding_payload_rejects_file_outside_project_root(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source = tmp_path / "outside.parquet"
    source.write_bytes(b"outside")
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="escapes project root"):
        build_source_binding_payload(
            token="daily_source_2020",
            source_id=DAILY_SOURCE_ID,
            files=((source, expected),),
            project_root=project_root,
        )


def test_source_binding_worker_hashes_bytes_without_opening_outcomes(tmp_path: Path) -> None:
    source = tmp_path / "source.parquet"
    source.write_bytes(b"not-a-real-parquet-needed-for-hash-only-preflight")
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    input_root = tmp_path / "inputs"
    input_root.mkdir()
    payload = build_source_binding_payload(
        token="daily_source_2020",
        source_id=DAILY_SOURCE_ID,
        files=((source, expected),),
        project_root=tmp_path,
    )
    path = input_root / "daily_source_2020.json"
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    unit = ResearchWorkUnit(token="daily_source_2020", input_fingerprint=canonical_sha256(payload))
    result = verify_source_binding_unit(
        unit,
        input_root=str(input_root),
        project_root=str(tmp_path),
    )
    assert result["status"] == "SOURCE_BINDING_VERIFIED"
    assert result["files_verified"] == 1
    assert result["outcome_rows_opened"] == 0
    assert result["authority"]["historical_outcomes_opened_by_preflight"] is False


def test_source_binding_worker_fails_closed_on_hash_drift(tmp_path: Path) -> None:
    source = tmp_path / "source.parquet"
    source.write_bytes(b"original")
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    input_root = tmp_path / "inputs"
    input_root.mkdir()
    payload = build_source_binding_payload(
        token="minute_source_0000",
        source_id=MINUTE_SOURCE_ID,
        files=((source, expected),),
        project_root=tmp_path,
    )
    (input_root / "minute_source_0000.json").write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    unit = ResearchWorkUnit(token="minute_source_0000", input_fingerprint=canonical_sha256(payload))
    source.write_bytes(b"changed")
    with pytest.raises(RuntimeError, match="SHA-256 drifted"):
        verify_source_binding_unit(
            unit,
            input_root=str(input_root),
            project_root=str(tmp_path),
        )
