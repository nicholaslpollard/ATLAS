from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one match in {path}: found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_once(path: Path, marker: str, addition: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        raise RuntimeError(f"marker already present in {path}: {marker}")
    path.write_text(text.rstrip() + "\n\n" + addition.rstrip() + "\n", encoding="utf-8")


engine = ROOT / "packages/backtesting/successor_development_engine.py"
replace_once(
    engine,
    '"atlas-successor-standalone-engine-v1-shared-daily-single-minute-scan"',
    '"atlas-successor-standalone-engine-v2-flat-prior-geometry-unready"',
)
replace_once(
    engine,
    '''def _new_successor_minute_signals(\n    bars: Sequence[CanonicalBar],\n''',
    '''def _valid_prior_regular_geometry(prior: RawMinuteDailySummary | None) -> bool:\n    return bool(\n        prior is not None\n        and math.isfinite(prior.high)\n        and math.isfinite(prior.low)\n        and prior.high > prior.low > 0.0\n    )\n\n\ndef _new_successor_minute_signals(\n    bars: Sequence[CanonicalBar],\n''',
)
replace_once(
    engine,
    '''    if prior is not None and not history.split_crossed_prior_close(current_epoch):\n''',
    '''    # The failed-break strategy requires an actual prior-session range. A valid\n    # canonical session can still be flat (for example sparse one-trade coverage),\n    # which is missing strategy context rather than a fatal source error. Fail closed\n    # for this route instead of fabricating geometry or aborting the whole group.\n    if _valid_prior_regular_geometry(prior) and not history.split_crossed_prior_close(current_epoch):\n''',
)

engine_tests = ROOT / "tests/test_successor_development_engine.py"
append_once(
    engine_tests,
    "test_flat_prior_regular_geometry_is_unready_not_fatal",
    '''def test_flat_prior_regular_geometry_is_unready_not_fatal(\n    monkeypatch: pytest.MonkeyPatch,\n) -> None:\n    prior_session = date(2026, 3, 31)\n    session = date(2026, 4, 1)\n    history = engine.SuccessorMinuteHistory(\n        daily=[\n            engine.RawMinuteDailySummary(\n                session_date=prior_session,\n                high=100.0,\n                low=100.0,\n                close=100.0,\n                dollar_volume=1_000_000.0,\n                split_epoch=1.0,\n            )\n        ]\n    )\n    bars = [\n        _minute_bar(session, 9, 30, high=100.5, low=99.5, close=100.0),\n        _minute_bar(session, 9, 31, high=100.6, low=99.6, close=100.1),\n    ]\n\n    def should_not_be_called(*args, **kwargs):\n        raise AssertionError("flat prior geometry must make failed-break route unavailable")\n\n    monkeypatch.setattr(engine, "evaluate_session_failed_break_reclaim", should_not_be_called)\n    signals = engine._new_successor_minute_signals(\n        bars,\n        session_date=session,\n        history=history,\n        current_epoch=1.0,\n    )\n\n    assert all(\n        signal.policy_id != "pract_session_failed_break_reclaim_v1"\n        for signal, _, _ in signals\n    )\n\n\ndef test_prior_regular_geometry_helper_requires_real_positive_range() -> None:\n    good = engine.RawMinuteDailySummary(\n        session_date=date(2026, 3, 31),\n        high=101.0,\n        low=99.0,\n        close=100.0,\n        dollar_volume=1_000_000.0,\n        split_epoch=1.0,\n    )\n    flat = engine.RawMinuteDailySummary(\n        session_date=date(2026, 3, 31),\n        high=100.0,\n        low=100.0,\n        close=100.0,\n        dollar_volume=1_000_000.0,\n        split_epoch=1.0,\n    )\n    assert engine._valid_prior_regular_geometry(good) is True\n    assert engine._valid_prior_regular_geometry(flat) is False\n    assert engine._valid_prior_regular_geometry(None) is False\n''',
)

parallel = ROOT / "packages/backtesting/successor_parallel.py"
replace_once(
    parallel,
    '''        heartbeat_seconds: float = 60.0,\n''',
    '''        heartbeat_seconds: float = 30.0,\n''',
)
replace_once(
    parallel,
    '''    ) -> None:\n        new_count = sum(not group.reused for group in completed)\n''',
    '''    ) -> dict[str, object]:\n        new_count = sum(not group.reused for group in completed)\n''',
)
replace_once(
    parallel,
    '''        atomic_write_text(path, _canonical_json(payload) + "\\n")\n\n    def run(\n''',
    '''        atomic_write_text(path, _canonical_json(payload) + "\\n")\n        return payload\n\n    @staticmethod\n    def _format_duration(value: object) -> str:\n        if value is None:\n            return "n/a"\n        seconds = max(0, int(float(value)))\n        hours, remainder = divmod(seconds, 3600)\n        minutes, seconds = divmod(remainder, 60)\n        if hours:\n            return f"{hours:d}h{minutes:02d}m{seconds:02d}s"\n        return f"{minutes:d}m{seconds:02d}s"\n\n    def _print_progress(self, payload: dict[str, object]) -> None:\n        total = int(payload["groups_total"])\n        completed = int(payload["groups_completed"])\n        percent = 100.0 * completed / total if total else 100.0\n        rate = payload.get("new_groups_per_hour")\n        rate_text = "n/a" if rate is None else f"{float(rate):.2f}/h"\n        print(\n            "successor progress "\n            f"state={payload['state']} {completed}/{total} ({percent:.1f}%) "\n            f"reused={payload['groups_reused']} new={payload['groups_new']} "\n            f"active={len(payload['active_group_tokens'])} "\n            f"queued={payload['groups_pending_not_submitted']} "\n            f"elapsed={self._format_duration(payload['elapsed_seconds'])} "\n            f"rate={rate_text} eta={self._format_duration(payload.get('eta_seconds'))}",\n            flush=True,\n        )\n\n    def run(\n''',
)
replace_once(
    parallel,
    '''        self._write_progress(\n            progress_path,\n            state="RUNNING",\n            total=len(ordered),\n            completed=completed,\n            started_monotonic=started,\n            active_tokens=[],\n            remaining_pending=remaining_pending,\n        )\n        if pending:\n''',
    '''        initial_progress = self._write_progress(\n            progress_path,\n            state="RUNNING",\n            total=len(ordered),\n            completed=completed,\n            started_monotonic=started,\n            active_tokens=[],\n            remaining_pending=remaining_pending,\n        )\n        self._print_progress(initial_progress)\n        last_console_report = started\n        last_console_completed = len(completed)\n        if pending:\n''',
)
replace_once(
    parallel,
    '''                    if done or now - last_heartbeat >= self.heartbeat_seconds:\n                        self._write_progress(\n                            progress_path,\n                            state="RUNNING",\n                            total=len(ordered),\n                            completed=completed,\n                            started_monotonic=started,\n                            active_tokens=[unit.token for unit in future_to_unit.values()],\n                            remaining_pending=remaining_pending,\n                        )\n                        last_heartbeat = now\n''',
    '''                    if done or now - last_heartbeat >= self.heartbeat_seconds:\n                        progress = self._write_progress(\n                            progress_path,\n                            state="RUNNING",\n                            total=len(ordered),\n                            completed=completed,\n                            started_monotonic=started,\n                            active_tokens=[unit.token for unit in future_to_unit.values()],\n                            remaining_pending=remaining_pending,\n                        )\n                        should_print = (\n                            now - last_console_report >= self.heartbeat_seconds\n                            or len(completed) - last_console_completed >= 5\n                            or len(completed) == len(ordered)\n                        )\n                        if should_print:\n                            self._print_progress(progress)\n                            last_console_report = now\n                            last_console_completed = len(completed)\n                        last_heartbeat = now\n''',
)
replace_once(
    parallel,
    '''                self._write_progress(\n                    progress_path,\n                    state="INTERRUPTED",\n                    total=len(ordered),\n                    completed=completed,\n                    started_monotonic=started,\n                    active_tokens=[unit.token for unit in future_to_unit.values()],\n                    remaining_pending=remaining_pending,\n                    last_error="KeyboardInterrupt",\n                )\n''',
    '''                interrupted = self._write_progress(\n                    progress_path,\n                    state="INTERRUPTED",\n                    total=len(ordered),\n                    completed=completed,\n                    started_monotonic=started,\n                    active_tokens=[unit.token for unit in future_to_unit.values()],\n                    remaining_pending=remaining_pending,\n                    last_error="KeyboardInterrupt",\n                )\n                self._print_progress(interrupted)\n''',
)
replace_once(
    parallel,
    '''                self._write_progress(\n                    progress_path,\n                    state="FAILED",\n                    total=len(ordered),\n                    completed=completed,\n                    started_monotonic=started,\n                    active_tokens=[unit.token for unit in future_to_unit.values()],\n                    remaining_pending=remaining_pending,\n                    last_error=f"{type(exc).__name__}: {exc}",\n                )\n''',
    '''                failed = self._write_progress(\n                    progress_path,\n                    state="FAILED",\n                    total=len(ordered),\n                    completed=completed,\n                    started_monotonic=started,\n                    active_tokens=[unit.token for unit in future_to_unit.values()],\n                    remaining_pending=remaining_pending,\n                    last_error=f"{type(exc).__name__}: {exc}",\n                )\n                self._print_progress(failed)\n''',
)
replace_once(
    parallel,
    '''        self._write_progress(\n            progress_path,\n            state="COMPLETE",\n            total=len(ordered),\n            completed=completed,\n            started_monotonic=started,\n            active_tokens=[],\n            remaining_pending=0,\n        )\n''',
    '''        complete_progress = self._write_progress(\n            progress_path,\n            state="COMPLETE",\n            total=len(ordered),\n            completed=completed,\n            started_monotonic=started,\n            active_tokens=[],\n            remaining_pending=0,\n        )\n        self._print_progress(complete_progress)\n''',
)

parallel_test = ROOT / "tests/test_successor_parallel_progress.py"
parallel_test.write_text(
    '''from __future__ import annotations\n\nfrom packages.backtesting.successor_parallel import SuccessorParallelCoordinator\nfrom packages.core.successor_execution_profile import SuccessorResearchExecutionProfile\n\n\ndef _profile() -> SuccessorResearchExecutionProfile:\n    return SuccessorResearchExecutionProfile(\n        logical_cpus=4,\n        total_memory_bytes=8 * 1024**3,\n        reserved_logical_cpus=1,\n        workers=2,\n        duckdb_threads_per_worker=1,\n        aggregate_worker_threads=2,\n        profile_source="test",\n        thermal_headroom_policy="test",\n    )\n\n\ndef test_console_progress_reports_counts_rate_and_eta(capsys) -> None:\n    coordinator = SuccessorParallelCoordinator(execution_profile=_profile())\n    coordinator._print_progress(\n        {\n            "state": "RUNNING",\n            "groups_total": 546,\n            "groups_completed": 27,\n            "groups_reused": 2,\n            "groups_new": 25,\n            "groups_pending_not_submitted": 511,\n            "active_group_tokens": ["a", "b", "c", "d", "e", "f", "g", "h"],\n            "elapsed_seconds": 1800.0,\n            "new_groups_per_hour": 50.0,\n            "eta_seconds": 37368.0,\n        }\n    )\n    output = capsys.readouterr().out\n    assert "successor progress state=RUNNING 27/546 (4.9%)" in output\n    assert "reused=2 new=25 active=8 queued=511" in output\n    assert "rate=50.00/h" in output\n    assert "eta=10h22m48s" in output\n\n\ndef test_default_progress_heartbeat_is_thirty_seconds() -> None:\n    coordinator = SuccessorParallelCoordinator(execution_profile=_profile())\n    assert coordinator.heartbeat_seconds == 30.0\n''',
    encoding="utf-8",
)

# Correct the source-verification-vs-outcome-work-group handoff and record the failed v1 attempt.
readme = ROOT / "README.md"
replace_once(
    readme,
    "The next permitted evidence action is the separately authorized full 493-group standalone DEVELOPMENT run;",
    "The next permitted evidence action is the separately authorized full 546-work-group standalone DEVELOPMENT run (64 daily buckets + 482 minute groups); the earlier 493 count is the source-verification grouping, not the outcome-run denominator;",
)
readme_text = readme.read_text(encoding="utf-8")
needle = "the 4x1/6x1/8x1 benchmark remains available only as an optional performance diagnostic."
insert = needle + " The first authorized full standalone attempt then opened the DEVELOPMENT-only runner at 8 workers under run fingerprint `22a2ace77c4c578c30964ba2a645b822738ef667617f0ef6bffb3192f75582ae` and stopped on a real sparse/flat prior-session geometry edge before a complete standalone result existed. The failed-break/reclaim route had passed a flat prior high/low into its strict evaluator and raised instead of treating that route as unavailable. The successor engine is now versioned so finite positive non-flat prior geometry is a readiness prerequisite; invalid/flat prior geometry fails closed for that route only. No geometry is fabricated. Console progress now reports completed/total groups, reused/new counts, active/queued work, elapsed time, new-group throughput and ETA at least every 30 seconds or five new completions."
if needle not in readme_text:
    raise RuntimeError("README audit paragraph marker missing")
readme.write_text(readme_text.replace(needle, insert, 1), encoding="utf-8")

roadmap = ROOT / "docs/roadmap.md"
replace_once(
    roadmap,
    "The next permitted evidence action is the separately authorized complete 493-group standalone run.",
    "The next permitted evidence action is the separately authorized complete 546-work-group standalone run (64 daily buckets + 482 minute groups); 493 is retained only as the earlier source-verification grouping.",
)
append_once(
    roadmap,
    "### 20.2 First full standalone attempt — flat prior geometry repair",
    '''### 20.2 First full standalone attempt — flat prior geometry repair\n\nThe first authorized full successor standalone attempt opened only the frozen DEVELOPMENT interval at 8 workers x 1 DuckDB thread under run-contract fingerprint `22a2ace77c4c578c30964ba2a645b822738ef667617f0ef6bffb3192f75582ae`. Its startup correctly reported **546 outcome work groups = 64 daily buckets + 482 minute groups** and 59,768 minute source units. The previously repeated 493 figure is the source-verification grouping and is not the standalone progress denominator.\n\nThe attempt stopped before a complete standalone result when `pract_session_failed_break_reclaim_v1` received a prior regular session whose observed high equaled its low. The strategy evaluator correctly rejects such geometry, but the shared minute engine incorrectly treated the presence of a prior session as sufficient readiness and propagated the exception. The repair keeps the strict evaluator unchanged and instead makes finite, positive, non-flat prior regular geometry an engine readiness condition. Flat/invalid prior geometry means this route is unavailable for that session; it is not filled, widened, or replaced with an older session. The standalone engine contract is versioned so the failed run identity and any partial artifacts cannot be silently reused under the repaired semantics.\n\nOperationally, the coordinator already maintained an atomic `progress.json` heartbeat but did not expose it to the operator console. It now prints parent-process progress with completed/total, reused/new, active/queued, elapsed time, new-group throughput and ETA on startup, completion/failure, and at least every 30 seconds or five new group completions. These telemetry changes remain excluded from scientific identity. Consumed-master/future/provider/broker access remains forbidden and PAPER/LIVE/promotion authority remains false.''',
)

register = ROOT / "docs/strategy_evidence_register.md"
replace_once(
    register,
    "the next evidence gate is the separately authorized full standalone DEVELOPMENT run.",
    "the next evidence gate is the separately authorized 546-work-group standalone DEVELOPMENT run (64 daily buckets + 482 minute groups); the earlier 493 figure refers only to source verification.",
)
append_once(
    register,
    "### 8.2 First broad successor run attempt — implementation repair, no accepted result",
    '''### 8.2 First broad successor run attempt — implementation repair, no accepted result\n\nThe first explicitly authorized broad DEVELOPMENT standalone attempt used 8 workers x 1 DuckDB thread and run-contract fingerprint `22a2ace77c4c578c30964ba2a645b822738ef667617f0ef6bffb3192f75582ae`. It exposed the correct outcome-run denominator of **546 work groups = 64 daily + 482 minute**, distinct from the accepted 493-group source-verification accounting. The run did not reach a complete/validated standalone summary: a sparse prior regular session produced `high == low`, and the shared engine passed that non-range into the strict failed-break/reclaim evaluator, which correctly raised `prior regular high/low must be finite positive geometry`.\n\nDisposition: **implementation readiness defect, not strategy evidence**. The economic rule remains unchanged. A repaired engine treats finite, positive, strictly ordered prior regular high/low as a prerequisite for that route. If the immediately prior session does not supply valid geometry, the route is unavailable for that session; no older-session substitution or synthetic range is permitted. The engine contract is bumped so partial artifacts from the failed identity are not reused as repaired evidence. No completed broad performance conclusion, conditioning/confluence result, or promotion claim is admitted from the failed attempt. Parent-process console telemetry is also added for transparent long-run progress without entering scientific hashes.''',
)

print("PR89 successor runtime repair applied")
