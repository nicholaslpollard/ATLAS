from __future__ import annotations

import pytest

from scripts.run_b35_development_replay import build_parser


@pytest.mark.parametrize(
    ("flag", "value"),
    (
        ("--start", "2026-01-01"),
        ("--end", "2026-04-01"),
        ("--output-root", "elsewhere"),
        ("--trial-ledger", "elsewhere.jsonl"),
    ),
)
def test_governed_b35_runner_rejects_operator_scope_and_path_overrides(
    flag: str,
    value: str,
) -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--source-only", flag, value])


def test_governed_b35_runner_exposes_only_separate_source_and_outcome_gates() -> None:
    source_only = build_parser().parse_args(["--source-only"])
    assert source_only.source_only is True
    assert source_only.authorize_development_outcomes is False
    assert not hasattr(source_only, "start")
    assert not hasattr(source_only, "end")
    assert not hasattr(source_only, "output_root")
    assert not hasattr(source_only, "trial_ledger")

    authorized = build_parser().parse_args(["--authorize-development-outcomes"])
    assert authorized.source_only is False
    assert authorized.authorize_development_outcomes is True
