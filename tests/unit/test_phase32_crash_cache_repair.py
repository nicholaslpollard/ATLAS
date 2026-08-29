from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import scripts.repair_phase32_crash_corrupted_cache as repair


class FakeSettings:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.data = SimpleNamespace(paths=SimpleNamespace(provider="data/provider"))

    def resolved_path(self, value: str) -> Path:
        return self.root / value


def _evidence_root(root: Path) -> Path:
    return root / "data/provider/phase32_sec_8k_predictor_acquisition/v1"


def _seed_exact_corruption(root: Path) -> None:
    evidence = _evidence_root(root)
    for spec in repair.EXPECTED_CORRUPT:
        path = evidence / str(spec["relative_path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x00" * int(spec["size"]))


def test_targeted_repair_quarantines_only_exact_diagnosed_files(tmp_path: Path, monkeypatch) -> None:
    _seed_exact_corruption(tmp_path)
    monkeypatch.setattr(repair, "load_settings", lambda: FakeSettings(tmp_path))

    assert repair.main() == 0

    evidence = _evidence_root(tmp_path)
    quarantine = evidence / "quarantine" / repair.INCIDENT_ID
    for spec in repair.EXPECTED_CORRUPT:
        relative = Path(str(spec["relative_path"]))
        assert not (evidence / relative).exists()
        preserved = quarantine / str(spec["quarantine_name"])
        assert preserved.read_bytes() == b"\x00" * int(spec["size"])

    manifest = json.loads((quarantine / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["contract"] == repair.REPAIR_CONTRACT
    assert manifest["market_outcomes_read"] == 0
    assert manifest["protected_returns_read"] == 0
    assert len(manifest["files"]) == 2
    assert {Path(row["quarantine_relative_path"]).name for row in manifest["files"]} == {
        str(spec["quarantine_name"]) for spec in repair.EXPECTED_CORRUPT
    }

    # Idempotent rerun verifies the already-quarantined exact evidence.
    assert repair.main() == 0


def test_targeted_repair_refuses_unexpected_bytes(tmp_path: Path, monkeypatch) -> None:
    _seed_exact_corruption(tmp_path)
    monkeypatch.setattr(repair, "load_settings", lambda: FakeSettings(tmp_path))

    evidence = _evidence_root(tmp_path)
    first = repair.EXPECTED_CORRUPT[0]
    path = evidence / str(first["relative_path"])
    path.write_bytes(b"x" * int(first["size"]))

    assert repair.main() == 2
    assert path.exists()
