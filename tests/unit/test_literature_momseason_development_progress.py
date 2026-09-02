from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from packages.backtesting.literature_momseason_development_identity_repair import (
    MomSeasonDevelopmentResearchIdentitySafe,
)
from packages.backtesting.literature_momseason_development_progress import (
    LIT01_DEVELOPMENT_PROGRESS_VERSION,
    MomSeasonDevelopmentResearchWithProgress,
    _ProgressFormationSequence,
    _format_duration,
)


def test_progress_wrapper_preserves_identity_safe_runner() -> None:
    assert issubclass(
        MomSeasonDevelopmentResearchWithProgress,
        MomSeasonDevelopmentResearchIdentitySafe,
    )
    assert LIT01_DEVELOPMENT_PROGRESS_VERSION == "lit01-development-live-progress-v1"


def test_format_duration_is_compact_and_readable() -> None:
    assert _format_duration(None) == "unknown"
    assert _format_duration(4.2) == "4s"
    assert _format_duration(65.0) == "1m 05s"
    assert _format_duration(3665.0) == "1h 01m 05s"


def test_progress_formation_sequence_preserves_indexing_and_emits_live_output(capsys) -> None:
    items = (
        SimpleNamespace(month_start=date(2024, 1, 1)),
        SimpleNamespace(month_start=date(2024, 2, 1)),
    )
    wrapped = _ProgressFormationSequence(items, stage="PLAN")
    assert len(wrapped) == 2
    assert wrapped[0] is items[0]
    assert list(wrapped) == list(items)
    output = capsys.readouterr().out
    assert "[LIT-01][PLAN] 0/2" in output
    assert "starting month 1/2: 2024-01" in output
    assert "starting month 2/2: 2024-02" in output
    assert "[LIT-01][PLAN] 2/2 (100.0%)" in output
    assert "ETA~" in output
