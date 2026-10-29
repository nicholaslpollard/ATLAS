from __future__ import annotations

import re

import pytest

from packages.simulation.strategy_source_progress_v42 import SourceProgressMonitor


def run_progress(total, capsys):
    with SourceProgressMonitor(expected_source_uses=total) as monitor:
        for index in range(1, total + 1):
            date = "2025-06-09"
            item = {"date_et": date, "purpose": "call_1001_quote",
                    "counts": {"source_uses_requested": index,
                               "source_uses_resolved": index - 1,
                               "provider_dispatch_attempts": index}}
            monitor.event("source_started", item)
            item["counts"]["source_uses_resolved"] = index
            monitor.event("source_done", {**item, "status": "FETCHED_AND_ARCHIVED"})
    return capsys.readouterr().out.splitlines()


@pytest.mark.parametrize(
    "total,step",
    [(10, 1), (100, 10), (1000, 100), (1083, 109)],
)
def test_progress_milestones_are_ten_percent_of_total(total, step, capsys):
    lines = run_progress(total, capsys)
    assert len(lines) == 11  # START and precisely ten 10%-completion updates
    assert "completed=0/" + str(total) in lines[0]
    assert "PROGRESS_10PCT" in lines[1]
    assert f"completed={step}/{total}" in lines[1]
    assert "PROGRESS_100PCT" in lines[-1]
    assert f"completed={total}/{total}" in lines[-1]
    assert all(re.match(r"\[20\d\d-\d\d-\d\d \d\d:\d\d:\d\d E[DS]T\]", line)
               for line in lines)
    assert all("provider_attempts=" in line for line in lines)
    assert all("throughput=" in line and "eta_rough=" in line for line in lines)
    assert not any("HEARTBEAT" in line for line in lines)


def test_failure_is_visible_without_time_based_heartbeat(capsys):
    with SourceProgressMonitor(expected_source_uses=100) as monitor:
        monitor.event("source_failed", {
            "date_et": "2025-06-09",
            "purpose": "put_1001_quote",
            "status": "SOURCE_RETRY_REQUIRED",
            "error": "RuntimeError:sample failure",
            "counts": {
                "source_uses_requested": 1,
                "source_uses_failed_or_unresolved": 1,
                "provider_dispatch_attempts": 1,
            },
        })
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 3
    assert "START" in lines[0]
    assert "ERROR" in lines[1]
    assert "RuntimeError:sample failure" in lines[1]
    assert "STOPPED_INCOMPLETE" in lines[2]


def test_invalid_or_unknown_input_rejected():
    with pytest.raises(ValueError, match="EXPECTED_SOURCE_USES"):
        SourceProgressMonitor(expected_source_uses=0)
    monitor = SourceProgressMonitor(expected_source_uses=10)
    with pytest.raises(ValueError, match="UNKNOWN_PROGRESS_EVENT"):
        monitor.event("wrong_event", {"date_et": "2025-06-09", "purpose": "entry",
                                      "counts": {}})
