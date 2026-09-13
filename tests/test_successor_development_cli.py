from __future__ import annotations

import pytest

from scripts import run_successor_development as cli


def test_cli_refuses_outcomes_without_explicit_authorization() -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--mode", "benchmark"])
    assert exc.value.code == 2


def test_cli_refuses_full_standalone_without_second_explicit_gate() -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--mode", "standalone", "--authorize-development-outcomes"])
    assert exc.value.code == 2


def test_cli_refuses_worker_override_for_frozen_benchmark_shapes() -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(
            [
                "--mode",
                "benchmark",
                "--authorize-development-outcomes",
                "--workers",
                "8",
            ]
        )
    assert exc.value.code == 2


def test_parser_exposes_only_benchmark_and_standalone_modes() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(
        ["--mode", "benchmark", "--authorize-development-outcomes"]
    )
    assert args.mode == "benchmark"
    assert args.authorize_development_outcomes is True
    assert args.authorize_full_standalone is False
