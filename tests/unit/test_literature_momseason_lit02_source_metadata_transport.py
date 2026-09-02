from __future__ import annotations

import pytest

from packages.backtesting.literature_momseason_lit02_source_metadata_transport import (
    LIT02_MASSIVE_TICKER_EVENTS_NOT_FOUND,
    LIT02_SOURCE_METADATA_TRANSPORT_VERSION,
    MomSeasonLIT02SourceMetadataTransportSafe,
)
from packages.core.exceptions import ProviderError


class _Massive404:
    def __init__(self) -> None:
        self.calls = 0

    def ticker_events(self, identifier: str):
        self.calls += 1
        raise ProviderError("Massive REST request failed with HTTP 404")


class _Massive500:
    def ticker_events(self, identifier: str):
        raise ProviderError("Massive REST request failed with HTTP 500")


def _bare_runner(massive: object) -> MomSeasonLIT02SourceMetadataTransportSafe:
    runner = object.__new__(MomSeasonLIT02SourceMetadataTransportSafe)
    runner.massive = massive
    runner._massive_event_cache = {}
    runner._massive_event_not_found = set()
    runner._massive_reads = 0
    return runner


def test_massive_ticker_event_404_becomes_cached_source_absence() -> None:
    massive = _Massive404()
    runner = _bare_runner(massive)

    assert runner._massive_ticker_events("BBG000TEST01") == []
    assert runner._massive_reads == 1
    assert massive.calls == 1
    assert "BBG000TEST01" in runner._massive_event_not_found

    # Reuse the source-absence checkpoint in memory; do not repeat the provider read.
    assert runner._massive_ticker_events("BBG000TEST01") == []
    assert runner._massive_reads == 1
    assert massive.calls == 1


def test_massive_ticker_event_non_404_remains_fatal() -> None:
    runner = _bare_runner(_Massive500())
    with pytest.raises(ProviderError, match="HTTP 500"):
        runner._massive_ticker_events("BBG000TEST02")
    assert runner._massive_reads == 1


def test_transport_contract_constants_are_explicit() -> None:
    assert LIT02_SOURCE_METADATA_TRANSPORT_VERSION.endswith("massive-404-source-unavailable")
    assert LIT02_MASSIVE_TICKER_EVENTS_NOT_FOUND == "MASSIVE_TICKER_EVENTS_NOT_FOUND"
