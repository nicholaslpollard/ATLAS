from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pytest

from packages.backtesting.b35_development_replay import (
    B35_DEVELOPMENT_REPLAY_CONTRACT,
    B35DevelopmentReplayError,
    _completed_group,
    _receipt_id,
    _validate_group_receipt,
)
from packages.backtesting.b35_development_source import B35DevelopmentUnitBinding
from packages.strategies.b35_conditional_evidence_contract import (
    B34_STRATEGY_IDS,
    B35_PREOUTCOME_FINGERPRINT,
)


def _unit(tmp_path: Path) -> B35DevelopmentUnitBinding:
    return B35DevelopmentUnitBinding(
        unit_id="a" * 64,
        year=2026,
        month=4,
        batch_index=0,
        window_start=date(2026, 4, 1),
        window_end_exclusive=date(2026, 5, 1),
        symbols=("TEST",),
        policy_sha256="b" * 64,
        universe_sha256="c" * 64,
        canonical_path=tmp_path / "canonical.parquet",
        canonical_sha256="d" * 64,
        checkpoint_path=tmp_path / "checkpoint.json",
    )


def _receipt(output: Path, unit: B35DevelopmentUnitBinding) -> dict[str, object]:
    counts = {
        strategy_id: {"evaluated_fired": 0, "comparable": 0, "noncomparable": 0}
        for strategy_id in B34_STRATEGY_IDS
    }
    document: dict[str, object] = {
        "contract": B35_DEVELOPMENT_REPLAY_CONTRACT,
        "status": "COMPLETE",
        "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
        "source_fingerprint": "e" * 64,
        "split_evidence_fingerprint": "f" * 64,
        "authorization_id": "1" * 64,
        "group_fingerprint": "2" * 64,
        "symbols": ["TEST"],
        "unit_count": 1,
        "unit_bindings": [
            {
                "unit_id": unit.unit_id,
                "canonical_sha256": unit.canonical_sha256,
                "year": unit.year,
                "month": unit.month,
                "batch_index": unit.batch_index,
            }
        ],
        "record_count": 0,
        "strategy_counts": counts,
        "output_path": str(output),
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "consumed_master_rows_read": 0,
        "future_blind_rows_read": 0,
        "provider_calls": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "paper_authority": False,
        "live_authority": False,
        "strategy_promotion": False,
        "selector_promotion": False,
    }
    document["receipt_id"] = _receipt_id(document)
    return document


def test_group_receipt_is_self_hash_bound_and_tamper_evident(tmp_path: Path) -> None:
    output = tmp_path / "group.jsonl"
    output.write_text("", encoding="utf-8")
    unit = _unit(tmp_path)
    receipt = _receipt(output, unit)
    receipt_id = _validate_group_receipt(
        receipt,
        output,
        units=(unit,),
        group_fingerprint="2" * 64,
        source_fingerprint="e" * 64,
        split_evidence_fingerprint="f" * 64,
        authorization_id="1" * 64,
    )
    assert receipt_id == receipt["receipt_id"]

    tampered = dict(receipt)
    tampered["record_count"] = 1
    with pytest.raises(B35DevelopmentReplayError):
        _validate_group_receipt(
            tampered,
            output,
            units=(unit,),
            group_fingerprint="2" * 64,
            source_fingerprint="e" * 64,
            split_evidence_fingerprint="f" * 64,
            authorization_id="1" * 64,
        )


def test_orphan_output_without_receipt_is_removed_for_safe_recompute(tmp_path: Path) -> None:
    output = tmp_path / "group.jsonl"
    receipt_path = tmp_path / "group.receipt.json"
    output.write_text("untrusted derived output\n", encoding="utf-8")
    unit = _unit(tmp_path)
    result = _completed_group(
        receipt_path,
        output,
        units=(unit,),
        group_fingerprint="2" * 64,
        source_fingerprint="e" * 64,
        split_evidence_fingerprint="f" * 64,
        authorization_id="1" * 64,
    )
    assert result is None
    assert not output.exists()


def test_receipt_without_exact_output_fails_closed(tmp_path: Path) -> None:
    output = tmp_path / "group.jsonl"
    output.write_text("", encoding="utf-8")
    unit = _unit(tmp_path)
    receipt = _receipt(output, unit)
    receipt_path = tmp_path / "group.receipt.json"
    import json

    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    output.unlink()
    with pytest.raises(B35DevelopmentReplayError, match="output is missing"):
        _completed_group(
            receipt_path,
            output,
            units=(unit,),
            group_fingerprint="2" * 64,
            source_fingerprint="e" * 64,
            split_evidence_fingerprint="f" * 64,
            authorization_id="1" * 64,
        )
