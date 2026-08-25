from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.core.enums import DatasetType, Timeframe
from packages.operations.phase23_current_run import (
    Phase23CurrentAnalysisCycle,
    Phase23CurrentRunError,
    Phase23Preparation,
)
from packages.schemas.execution import BrokerName


AS_OF = date(2026, 8, 21)
FROZEN = date(2026, 8, 14)
SESSIONS = tuple(date(2026, 8, day) for day in (17, 18, 19, 20, 21))


class GuardPaths:
    def __init__(self, root: Path) -> None:
        self.root = root

    def provider_file(self, dataset: DatasetType, trading_date: date) -> Path:
        return self.root / "provider" / dataset.value / f"{trading_date}.csv.gz"

    def canonical_file(self, timeframe: Timeframe, trading_date: date) -> Path:
        return self.root / "canonical" / timeframe.value / f"{trading_date}.parquet"

    def derived_file(self, timeframe: Timeframe, trading_date: date) -> Path:
        return self.root / "derived" / "bars" / timeframe.value / f"{trading_date}.parquet"

    def feature_file(self, timeframe: Timeframe, trading_date: date) -> Path:
        return self.root / "derived" / "features" / timeframe.value / f"{trading_date}.parquet"

    def feature_manifest_file(self, timeframe: Timeframe, trading_date: date) -> Path:
        return self.root / "manifests" / "features" / timeframe.value / f"{trading_date}.json"

    def discovery_state_file(self, trading_date: date) -> Path:
        return self.root / "discovery" / f"{trading_date}.parquet"

    def discovery_state_manifest(self, trading_date: date) -> Path:
        return self.root / "discovery_manifests" / f"{trading_date}.json"


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")


def _preparation() -> Phase23Preparation:
    return Phase23Preparation(
        as_of_date=AS_OF,
        broker=BrokerName.WEBULL,
        baseline_discovery_date=FROZEN,
        sessions_to_advance=SESSIONS,
        missing_reference_sessions=(),
        missing_daily_sessions=(),
        missing_minute_sessions=(),
        external_read_classes=(),
        run_scope_fingerprint="a" * 64,
        challenge=None,
    )


def _complete_market_paths(cycle: Phase23CurrentAnalysisCycle) -> None:
    for trading_date in SESSIONS:
        for path in cycle._market_data_paths(trading_date).values():
            _touch(path)


def test_unaccepted_partial_discovery_does_not_advance_operational_baseline(tmp_path: Path) -> None:
    cycle = object.__new__(Phase23CurrentAnalysisCycle)
    cycle.paths = GuardPaths(tmp_path)
    cycle._accepted_phase23_dates = lambda value: []
    _touch(cycle.paths.discovery_state_file(FROZEN))
    _touch(cycle.paths.discovery_state_manifest(FROZEN))
    # Simulate artifacts written by a failed partial Phase23 attempt.
    _touch(cycle.paths.discovery_state_file(AS_OF))
    _touch(cycle.paths.discovery_state_manifest(AS_OF))

    assert cycle._baseline_discovery_date(AS_OF) == FROZEN


def test_market_data_entitlement_gap_fails_closed_even_when_files_exist(tmp_path: Path) -> None:
    cycle = object.__new__(Phase23CurrentAnalysisCycle)
    cycle.paths = GuardPaths(tmp_path)
    _complete_market_paths(cycle)
    result = SimpleNamespace(
        inaccessible_sessions_skipped=1,
        sessions_requested=len(SESSIONS),
        sessions_processed=len(SESSIONS) - 1,
        effective_start_date=SESSIONS[1],
        effective_end_date=SESSIONS[-1],
    )

    with pytest.raises(Phase23CurrentRunError, match="entitlement skipped"):
        cycle._verify_market_data_completion(_preparation(), result)


def test_market_data_requires_every_raw_canonical_and_derived_partition(tmp_path: Path) -> None:
    cycle = object.__new__(Phase23CurrentAnalysisCycle)
    cycle.paths = GuardPaths(tmp_path)
    _complete_market_paths(cycle)
    cycle.paths.derived_file(Timeframe.HOUR_4, AS_OF).unlink()
    result = SimpleNamespace(
        inaccessible_sessions_skipped=0,
        sessions_requested=len(SESSIONS),
        sessions_processed=len(SESSIONS),
        effective_start_date=SESSIONS[0],
        effective_end_date=SESSIONS[-1],
    )

    with pytest.raises(Phase23CurrentRunError, match="market-data advancement is incomplete"):
        cycle._verify_market_data_completion(_preparation(), result)


def test_feature_checkpoint_must_finish_exactly_at_requested_as_of(tmp_path: Path) -> None:
    cycle = object.__new__(Phase23CurrentAnalysisCycle)
    cycle.paths = GuardPaths(tmp_path)
    materializer = SimpleNamespace(stale_source_sessions=lambda **kwargs: ())

    with pytest.raises(Phase23CurrentRunError, match="feature checkpoint did not finish"):
        cycle._verify_feature_completion(
            _preparation(),
            materializer=materializer,
            timeframe=Timeframe.DAY_1,
            checkpoint_as_of=date(2026, 8, 20),
        )


def test_feature_guard_requires_partitions_manifests_and_current_source_lineage(tmp_path: Path) -> None:
    cycle = object.__new__(Phase23CurrentAnalysisCycle)
    cycle.paths = GuardPaths(tmp_path)
    for trading_date in SESSIONS:
        _touch(cycle.paths.feature_file(Timeframe.DAY_1, trading_date))
        _touch(cycle.paths.feature_manifest_file(Timeframe.DAY_1, trading_date))
    materializer = SimpleNamespace(stale_source_sessions=lambda **kwargs: (date(2026, 8, 19),))

    with pytest.raises(Phase23CurrentRunError, match="feature/source lineage is stale"):
        cycle._verify_feature_completion(
            _preparation(),
            materializer=materializer,
            timeframe=Timeframe.DAY_1,
            checkpoint_as_of=AS_OF,
        )
