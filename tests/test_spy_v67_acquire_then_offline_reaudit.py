from __future__ import annotations

from pathlib import Path

import pytest

from scripts import run_spy_v67_acquire_then_offline_reaudit as v67
from scripts.run_spy_v66_three_missing_exact_tape_acquisition import (
    V65_SHA, write_once,
)


def original_parent(path):
    return V65_SHA, [{"session": d} for d in (16, 18, 20)]


def planned_acquisition(events, *, status="COMPLETE_SOURCE_CENSUS"):
    def acquire(parent, outdir):
        events.append("acquire")
        assert not outdir.exists()
        outdir.mkdir(parents=True)
        doc = v67.signed({
            "contract": v67.V66_CONTRACT,
            "frozen_v65_report_fingerprint": V65_SHA,
            "completed_scopes": 3,
            "status": status,
            "result_counts": {
                "SOURCE_ARCHIVED_AND_REVERIFIED": 2,
                "ABSTAIN_AMBIGUOUS_PRIOR_DISPATCH_NO_RETRY": 1,
            } if status != "COMPLETE_SOURCE_CENSUS" else {
                "SOURCE_ARCHIVED_AND_REVERIFIED": 3,
            },
            "new_provider_request_count_upper_bound": 3,
        })
        write_once(outdir / "summary.json", doc)
        return doc
    return acquire


def offline_replay(events):
    def replay(first, last, output):
        events.append("offline")
        assert first.isoformat() == "2025-06-09"
        assert last.isoformat() == "2025-06-20"
        assert output.parent.joinpath("sources/summary.json").is_file()
        doc = v67.signed({
            "contract": v67.V65_CONTRACT,
            "start": first.isoformat(),
            "end": last.isoformat(),
            "provider_requests": 0,
            "broker_orders": 0,
            "status_counts": {
                "CLOSED_QUOTE_REFERENCE": 3,
                "UNRESOLVED_POSITION": 1,
                "NO_SIGNAL": 4,
                "NO_ENTRY": 2,
            },
            "option_source_state_counts": {"ARCHIVED": 6},
        })
        write_once(output, doc)
        return doc
    return replay


def test_combines_independent_exact_acquisition_then_unchanged_replay(tmp_path):
    events = []
    out = tmp_path / "cohort"
    result = v67.run(
        tmp_path / "v65_original.json", out,
        verify_parent=original_parent,
        acquire=planned_acquisition(events),
        replay=offline_replay(events),
        emit=lambda s: None,
    )
    assert events == ["acquire", "offline"]
    assert result["status"] == "COMPLETE_SOURCE_AND_OFFLINE_CENSUS"
    assert result["v65_refreshed_counts"]["UNRESOLVED_POSITION"] == 1
    assert result["cumulative_cash_reconstructed"] is False
    assert result["broker_orders"] == 0
    assert v67.valid_saved(out / "summary.json", result)


def test_one_uncertain_provider_does_not_cancel_independent_offline_audit(tmp_path):
    events = []
    result = v67.run(
        tmp_path / "v65_original.json", tmp_path / "combined",
        verify_parent=original_parent,
        acquire=planned_acquisition(events, status="COMPLETE_WITH_BLOCKED_SOURCES"),
        replay=offline_replay(events),
        emit=lambda s: None,
    )
    assert events == ["acquire", "offline"]
    assert result["status"] == "OFFLINE_CENSUS_COMPLETE_WITH_UNRESOLVED_SOURCE_DEMANDS"
    assert result["historical_profitability_proven"] is False
    assert result["v65_refreshed_source_counts"]["ARCHIVED"] == 6


def test_uncertified_acquisition_blocks_replay_and_preserves_error_receipt(tmp_path):
    events = []
    def fail(*args):
        events.append("acquire")
        raise RuntimeError("private credential should not be printed")
    out = tmp_path / "combined"
    result = v67.run(
        tmp_path / "v65_original.json", out, verify_parent=original_parent,
        acquire=fail, replay=lambda *args: pytest.fail("must not replay"),
        emit=lambda msg: None,
    )
    assert events == ["acquire"]
    assert result["status"] == "SOURCE_ACQUISITION_UNVERIFIED"
    assert result["failure_class"] == "RuntimeError"
    assert "credential" not in str(result)
    assert v67.valid_saved(out / "summary.json", result)


def test_immutable_output_and_parent_guard_prevent_external_requests(tmp_path):
    out = tmp_path / "combined"
    out.mkdir()
    with pytest.raises(v67.V67Error, match="OUTPUT_ALREADY_EXISTS"):
        v67.run(tmp_path / "original.json", out,
                verify_parent=original_parent,
                acquire=lambda *a: pytest.fail("no dispatch"),
                emit=lambda s: None)
    with pytest.raises(v67.V67Error, match="ORIGINAL_V65_ACCEPTANCE_REQUIRED"):
        v67.run(tmp_path / "original.json", tmp_path / "new",
                verify_parent=lambda *a: ("bad", []),
                acquire=lambda *a: pytest.fail("no dispatch"),
                emit=lambda s: None)
