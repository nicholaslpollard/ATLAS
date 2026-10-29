from __future__ import annotations

import time

from packages.simulation.strategy_source_progress_v42 import SourceProgressMonitor


def test_timestamped_progress_and_persistent_log(tmp_path, capsys):
    output = tmp_path / "source.progress.log"
    with SourceProgressMonitor(
        output, expected_source_uses=3, heartbeat_seconds=0.05, every=2
    ) as monitor:
        monitor.event("source_started", {
            "date_et": "2025-06-09", "purpose": "call_1001_quote",
            "counts": {"source_uses_requested": 1}
        })
        monitor.event("provider_dispatch", {
            "date_et": "2025-06-09", "purpose": "call_1001_quote",
            "counts": {"source_uses_requested": 1, "provider_dispatch_attempts": 1}
        })
        time.sleep(0.08)
        monitor.event("source_done", {
            "date_et": "2025-06-09", "purpose": "call_1001_quote",
            "status": "FETCHED_AND_ARCHIVED",
            "counts": {
                "source_uses_requested": 1, "source_uses_resolved": 1,
                "provider_dispatch_attempts": 1, "provider_fetch_successes": 1,
            },
        })
        monitor.event("source_started", {
            "date_et": "2025-06-09", "purpose": "put_1001_quote",
            "counts": {"source_uses_requested": 2, "source_uses_resolved": 1},
        })
        monitor.event("source_failed", {
            "date_et": "2025-06-09", "purpose": "put_1001_quote",
            "status": "SOURCE_RETRY_REQUIRED",
            "error": "RuntimeError:test",
            "counts": {
                "source_uses_requested": 2, "source_uses_resolved": 1,
                "source_uses_failed_or_unresolved": 1,
                "provider_dispatch_attempts": 2,
            },
        })
    text = output.read_text(encoding="utf-8")
    printed = capsys.readouterr().out
    assert "START" in text and "HEARTBEAT" in text and "ERROR" in text
    assert "source_uses/s" in text and "provider_calls=2" in text
    assert "completed=2/3" in text
    assert "active=2025-06-09:put_1001_quote" in text
    assert "eta_rough" in text and "STOPPED_WITH_ERROR" not in text
    assert text == printed


def test_log_not_overwritten(tmp_path):
    p = tmp_path / "keep.log"
    p.write_text("original", encoding="utf-8")
    try:
        with SourceProgressMonitor(p):
            pass
    except ValueError as e:
        assert "EXISTS" in str(e)
    else:
        raise AssertionError("existing progress log must be protected")
    assert p.read_text(encoding="utf-8") == "original"
