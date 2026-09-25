from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from packages.backtesting.recurrent_successor_dynamic_exit_v1_contract import (
    RECURRENT_SUCCESSOR_DYNAMIC_EXIT_V1_CONTRACT_FINGERPRINT,
)
from scripts.inspect_recurrent_successor_dynamic_exit_v1 import (
    RUN_FINGERPRINT,
    main,
    read_closeout,
)


def _report() -> dict[str, object]:
    payload: dict[str, object] = {
        "status": "COMPLETE_DYNAMIC_EXIT_V1_SELECTOR_DIAGNOSTIC",
        "contract_fingerprint": RECURRENT_SUCCESSOR_DYNAMIC_EXIT_V1_CONTRACT_FINGERPRINT,
        "run_fingerprint": RUN_FINGERPRINT,
        "usable_cases": 3,
        "selected_cases": 1,
        "abstained_cases": 2,
        "abstain_reasons": {
            "INSUFFICIENT_PRIOR_CONTEXT_SUPPORT": 1,
            "NO_SUPPORTED_ACTION_HAS_POSITIVE_ROBUST_LCB": 1,
        },
        "selected_fallback_level_counts": {"5": 1},
        "year_summary": [
            {
                "year": 2025,
                "cases": 3,
                "abstain_reasons": {
                    "INSUFFICIENT_PRIOR_CONTEXT_SUPPORT": 1,
                    "NO_SUPPORTED_ACTION_HAS_POSITIVE_ROBUST_LCB": 1,
                },
            },
        ],
    }
    payload["report_fingerprint"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    return payload


def test_read_only_closeout_accepts_reconciled_retained_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "dynamic_exit_v1_summary.json"
    path.write_text(json.dumps(_report()), encoding="utf-8")
    assert read_closeout(path)["selected_cases"] == 1
    assert main(["--report", str(path)]) == 0
    output = capsys.readouterr().out
    assert "INSUFFICIENT_PRIOR_CONTEXT_SUPPORT: 1" in output
    assert "NO_SUPPORTED_ACTION_HAS_POSITIVE_ROBUST_LCB: 1" in output
    assert "provider reads: 0; stock-source scans: 0" in output


def test_closeout_refuses_tampered_summary(tmp_path: Path) -> None:
    path = tmp_path / "dynamic_exit_v1_summary.json"
    payload = _report()
    payload["selected_cases"] = 2
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="fingerprint"):
        read_closeout(path)


def test_closeout_refuses_inconsistent_reasons(tmp_path: Path) -> None:
    path = tmp_path / "dynamic_exit_v1_summary.json"
    payload = _report()
    payload["abstain_reasons"] = {"INSUFFICIENT_PRIOR_CONTEXT_SUPPORT": 1}
    unsigned = dict(payload)
    unsigned.pop("report_fingerprint")
    payload["report_fingerprint"] = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="abstain reasons"):
        read_closeout(path)
