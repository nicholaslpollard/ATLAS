from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

import scripts.run_phase18_operational_validation as runner
from packages.core.enums import DataProvider, LiveFeedMode, SessionSegment
from packages.schemas.live_market import LiveQuote


NOW = datetime(2026, 8, 24, 15, 0, tzinfo=UTC)


def _quote() -> LiveQuote:
    return LiveQuote(
        symbol="AAPL",
        provider_timestamp_utc=NOW,
        session_date=date(2026, 8, 24),
        session_segment=SessionSegment.REGULAR,
        bid_price=100.0,
        bid_size=100,
        ask_price=100.1,
        ask_size=100,
        sequence=1,
        provider=DataProvider.MASSIVE,
        feed_mode=LiveFeedMode.REALTIME,
        expected_delay_seconds=0,
        received_at_utc=NOW,
    )


class _Resolver:
    def __init__(self, settings) -> None:
        self.settings = settings

    def quote(self, ticker: str) -> LiveQuote:
        assert ticker == "AAPL"
        return _quote()


def _broker_init_must_not_run(_broker):
    raise AssertionError("broker adapter must not initialize before exact authorization")


def test_runner_plan_only_initializes_no_broker(monkeypatch, capsys) -> None:
    monkeypatch.setattr(runner, "load_settings", lambda: object())
    monkeypatch.setattr(runner, "Phase15LiveQuoteResolver", _Resolver)
    monkeypatch.setattr(runner, "_build_adapter", _broker_init_must_not_run)
    monkeypatch.setattr(
        runner.argparse.ArgumentParser,
        "parse_args",
        lambda self: runner.argparse.Namespace(
            broker="webull",
            ticker="AAPL",
            authorize_paper_provider_mutation=False,
            confirmation="",
        ),
    )

    runner.main()

    output = capsys.readouterr().out
    assert "Authorization gate: NOT REQUESTED" in output
    assert "Broker adapter initialized: NO" in output
    assert "Provider calls performed: 0" in output
    assert "Provider writes performed: 0" in output
    assert "Disposition: PLAN_ONLY_ZERO_PROVIDER_CALLS" in output


def test_runner_wrong_confirmation_initializes_no_broker(monkeypatch, capsys) -> None:
    monkeypatch.setattr(runner, "load_settings", lambda: object())
    monkeypatch.setattr(runner, "Phase15LiveQuoteResolver", _Resolver)
    monkeypatch.setattr(runner, "_build_adapter", _broker_init_must_not_run)
    monkeypatch.setattr(
        runner.argparse.ArgumentParser,
        "parse_args",
        lambda self: runner.argparse.Namespace(
            broker="webull",
            ticker="AAPL",
            authorize_paper_provider_mutation=True,
            confirmation="WRONG",
        ),
    )

    with pytest.raises(SystemExit) as exc_info:
        runner.main()

    assert exc_info.value.code == 2
    output = capsys.readouterr().out
    assert "Authorization gate: DENIED" in output
    assert "Broker adapter initialized: NO" in output
    assert "Provider writes performed: 0" in output


def test_runner_blocked_quote_initializes_no_broker(monkeypatch, capsys) -> None:
    class _BlockedResolver:
        def __init__(self, settings) -> None:
            pass

        def quote(self, ticker: str):
            from packages.execution.quote_source import ExecutionQuoteError

            raise ExecutionQuoteError("test stale quote")

    monkeypatch.setattr(runner, "load_settings", lambda: object())
    monkeypatch.setattr(runner, "Phase15LiveQuoteResolver", _BlockedResolver)
    monkeypatch.setattr(runner, "_build_adapter", _broker_init_must_not_run)
    monkeypatch.setattr(
        runner.argparse.ArgumentParser,
        "parse_args",
        lambda self: runner.argparse.Namespace(
            broker="webull",
            ticker="AAPL",
            authorize_paper_provider_mutation=True,
            confirmation="AUTHORIZE_PAPER_PROVIDER_MUTATION",
        ),
    )

    with pytest.raises(SystemExit) as exc_info:
        runner.main()

    assert exc_info.value.code == 2
    output = capsys.readouterr().out
    assert "Plan status: BLOCKED" in output
    assert "Broker adapter initialized: NO" in output
    assert "Provider calls performed: 0" in output
    assert "Provider writes performed: 0" in output
