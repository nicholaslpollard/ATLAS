from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from packages.backtesting.b35_split_evidence import (
    B35SplitEvidenceError,
    load_b35_split_evidence,
)
from packages.data.alpaca_v2_acquisition import SOURCE_SNAPSHOT_CONTRACT
from packages.data.alpaca_v2_rebuild import V2Layout


def _write_fixture(tmp_path: Path) -> tuple[V2Layout, Path]:
    layout = V2Layout.beneath(tmp_path / "data")
    layout.create()
    actions_path = layout.corporate_actions / "native_actions.jsonl.gz"
    rows = [
        {
            "action_type": "forward_splits",
            "payload": {"symbol": "TEST", "ex_date": "2026-03-02"},
        },
        {
            "action_type": "cash_dividends",
            "payload": {"symbol": "TEST", "ex_date": "2026-03-10"},
        },
        {
            "action_type": "reverse_splits",
            "payload": {"symbol": "LATE", "ex_date": "2026-05-01"},
        },
    ]
    raw = b"".join(
        json.dumps(item, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        for item in rows
    )
    actions_path.parent.mkdir(parents=True, exist_ok=True)
    actions_path.write_bytes(gzip.compress(raw, mtime=0))
    actions_sha = hashlib.sha256(actions_path.read_bytes()).hexdigest()
    source_snapshot = {
        "contract": SOURCE_SNAPSHOT_CONTRACT,
        "v1_ancestry": "FORBIDDEN",
        "corporate_actions_native": {
            "path": str(actions_path),
            "sha256": actions_sha,
        },
    }
    snapshot_path = layout.manifests / "source_snapshot.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(
        json.dumps(source_snapshot, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return layout, actions_path


def test_split_evidence_binds_only_preprotected_split_actions(tmp_path: Path) -> None:
    layout, _actions_path = _write_fixture(tmp_path)
    evidence = load_b35_split_evidence(layout)
    assert evidence.split_dates_by_symbol == {"TEST": (evidence.split_dates_by_symbol["TEST"][0],)}
    assert evidence.split_dates_by_symbol["TEST"][0].isoformat() == "2026-03-02"
    assert "LATE" not in evidence.split_dates_by_symbol
    assert evidence.split_event_count == 1
    assert len(evidence.fingerprint) == 64


def test_split_evidence_rejects_corporate_action_hash_drift(tmp_path: Path) -> None:
    layout, actions_path = _write_fixture(tmp_path)
    actions_path.write_bytes(actions_path.read_bytes() + b"drift")
    with pytest.raises(B35SplitEvidenceError, match="SHA-256 drifted"):
        load_b35_split_evidence(layout)
