from datetime import date

import pytest

from packages.providers.massive.corporate_actions import (
    MASSIVE_SPLITS_ENDPOINT,
    MASSIVE_SPLITS_PAGE_LIMIT,
    MassiveCorporateActionsProvider,
)


class FakeClient:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def iter_pages(self, path, params=None):
        self.calls.append((path, params))
        yield from self.pages


def test_phase10_split_provider_uses_current_massive_endpoint_and_bounds() -> None:
    client = FakeClient([{"results": []}])
    provider = MassiveCorporateActionsProvider(client=client)
    assert list(provider.splits(start_date=date(2022, 1, 1), end_date=date(2026, 8, 14))) == []
    path, params = client.calls[0]
    assert path == MASSIVE_SPLITS_ENDPOINT
    assert params["execution_date.gte"] == "2022-01-01"
    assert params["execution_date.lte"] == "2026-08-14"
    assert params["limit"] == MASSIVE_SPLITS_PAGE_LIMIT


def test_phase10_split_provider_streams_result_objects_only() -> None:
    client = FakeClient([
        {"results": [{"ticker": "AAPL"}, None, "bad"]},
        {"results": [{"ticker": "XYZ"}]},
    ])
    provider = MassiveCorporateActionsProvider(client=client)
    assert [item["ticker"] for item in provider.splits(
        start_date=date(2022, 1, 1), end_date=date(2026, 8, 14)
    )] == ["AAPL", "XYZ"]


def test_phase10_split_provider_rejects_reversed_date_range() -> None:
    provider = MassiveCorporateActionsProvider(client=FakeClient([]))
    with pytest.raises(ValueError, match="precedes"):
        list(provider.splits(start_date=date(2026, 8, 14), end_date=date(2022, 1, 1)))
