from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pytest

from packages.core.settings import load_settings
from packages.data.alpaca_v2_acquisition import (
    V2TimeLimitReached,
    AlpacaV2NativeAcquirer,
    _exclusive_windows,
    build_native_plan,
)
from packages.providers.alpaca import AlpacaApiPage, AlpacaInvalidSymbolError


def _page(
    name: str,
    payload: object,
    *,
    token: str | None = None,
    next_token: str | None = None,
    status: int = 200,
) -> AlpacaApiPage:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return AlpacaApiPage(
        request_name=name,
        url=f"https://example.test/{name}",
        http_status=status,
        raw_body=body,
        payload=payload,
        response_headers={},
        page_token_used=token,
        next_page_token=next_token,
    )


class FakeAlpaca:
    def __init__(self, *, two_pages: bool = False, reject: str | None = None) -> None:
        self.two_pages = two_pages
        self.reject = reject
        self.bar_calls: list[tuple[tuple[str, ...], str, str | None]] = []

    def get_assets(self, *, status: str) -> AlpacaApiPage:
        symbols = ["AAPL"] + ([self.reject] if self.reject else [])
        payload = [
            {
                "id": f"{status}-{index}",
                "symbol": symbol,
                "status": status,
                "class": "us_equity",
                "exchange": "NASDAQ",
                "name": symbol,
                "tradable": status == "active",
            }
            for index, symbol in enumerate(symbols)
        ]
        return _page(f"assets_{status}", payload)

    def corporate_action_page(
        self,
        *,
        start: str,
        end: str,
        page_token: str | None = None,
    ) -> AlpacaApiPage:
        return _page(
            "corporate_actions",
            {"corporate_actions": {"name_changes": []}, "next_page_token": None},
            token=page_token,
        )

    def historical_bar_page(self, **kwargs: object) -> AlpacaApiPage:
        symbols = tuple(str(value) for value in kwargs["symbols"])
        timeframe = str(kwargs["timeframe"])
        token = kwargs.get("page_token")
        self.bar_calls.append((symbols, timeframe, str(token) if token is not None else None))
        if self.reject and self.reject in symbols:
            payload = {"message": f"invalid symbol: {self.reject}"}
            error_page = _page("historical_bars", payload, status=400)
            raise AlpacaInvalidSymbolError(
                self.reject,
                error_page,
                f"invalid symbol: {self.reject}",
            )
        timestamp = (
            "2020-01-02T05:00:00Z"
            if timeframe == "1Day"
            else "2020-01-02T14:30:00Z"
        )
        if self.two_pages and token is None:
            next_token = "page-two"
        else:
            next_token = None
            if self.two_pages:
                timestamp = (
                    "2020-01-03T05:00:00Z"
                    if timeframe == "1Day"
                    else "2020-01-02T14:31:00Z"
                )
        payload = {
            "bars": {
                "AAPL": [
                    {
                        "t": timestamp,
                        "o": 100.0,
                        "h": 102.0,
                        "l": 99.0,
                        "c": 101.0,
                        "v": 1000,
                        "vw": 100.5,
                        "n": 10,
                    }
                ]
            },
            "next_page_token": next_token,
        }
        return _page(
            "historical_bars",
            payload,
            token=str(token) if token is not None else None,
            next_token=next_token,
        )


def _acquirer(tmp_path: Path, client: FakeAlpaca) -> AlpacaV2NativeAcquirer:
    settings = load_settings().model_copy(update={"project_root": tmp_path})
    result = AlpacaV2NativeAcquirer(
        settings,
        start_date=date(2020, 1, 2),
        now_utc=datetime(2020, 1, 3, 22, tzinfo=UTC),
        client=client,
    )
    result._require_disk = lambda **_: None  # type: ignore[method-assign]
    return result


def test_native_windows_are_adjacent_exclusive_and_plan_runs_daily_first() -> None:
    assert _exclusive_windows(date(2019, 12, 31), date(2020, 2, 2), "1Min") == [
        (date(2019, 12, 31), date(2020, 1, 1)),
        (date(2020, 1, 1), date(2020, 2, 1)),
        (date(2020, 2, 1), date(2020, 2, 3)),
    ]
    units = build_native_plan(
        symbols=["AAPL", "MSFT"],
        start=date(2020, 1, 2),
        cutoff=date(2020, 2, 2),
        universe_sha256="u" * 64,
        policy_sha256="p" * 64,
    )
    assert [unit.canonical_timeframe for unit in units] == ["1d", "1m", "1m"]
    assert len({unit.unit_id for unit in units}) == len(units)


def test_provider_bounds_use_local_midnight_and_inclusive_end_without_overlap(
    tmp_path: Path,
) -> None:
    acquirer = _acquirer(tmp_path, FakeAlpaca())
    bootstrap = acquirer.freeze_bootstrap()
    source, symbols = acquirer.ensure_source_snapshot(bootstrap)
    units, _manifest = acquirer.ensure_plan(bootstrap, source, symbols)

    start, end = acquirer._request_bounds(units[0])

    assert start == "2020-01-02T05:00:00.000000Z"
    assert end == "2020-01-04T04:59:59.999999Z"


def test_fresh_native_build_creates_daily_and_minute_and_resume_makes_no_calls(
    tmp_path: Path,
) -> None:
    client = FakeAlpaca()
    acquirer = _acquirer(tmp_path, client)

    first = acquirer.run()
    calls_after_first = len(client.bar_calls)
    second = acquirer.run()

    assert first["status"] == "COMPLETE"
    assert first["daily_completed"] == first["daily_units"] == 1
    assert first["minute_completed"] == first["minute_units"] == 1
    assert first["canonical_rows"] == 2
    assert second["skipped_units_this_run"] == 2
    assert len(client.bar_calls) == calls_after_first == 2
    assert first["v1_ancestry"] == "FORBIDDEN"
    assert first["production_promoted"] is False

    canonical = sorted(acquirer.layout.root.glob("canonical/stocks/**/*.parquet"))
    assert len(canonical) == 2
    con = duckdb.connect(":memory:")
    try:
        assert sum(
            con.execute(
                "SELECT count(*) FROM read_parquet(?, hive_partitioning=false)",
                [str(path)],
            ).fetchone()[0]
            for path in canonical
        ) == 2
    finally:
        con.close()


def test_page_level_resume_continues_from_opaque_token(tmp_path: Path) -> None:
    client = FakeAlpaca(two_pages=True)
    acquirer = _acquirer(tmp_path, client)
    bootstrap = acquirer.freeze_bootstrap()
    source, symbols = acquirer.ensure_source_snapshot(bootstrap)
    units, _manifest = acquirer.ensure_plan(bootstrap, source, symbols)
    unit = next(item for item in units if item.canonical_timeframe == "1d")
    registry: dict[str, dict[str, object]] = {}

    with pytest.raises(V2TimeLimitReached):
        acquirer._acquire_unit(unit, registry=registry, stop_requested=lambda: True)

    assert client.bar_calls[-1][2] is None
    completed = acquirer._acquire_unit(unit, registry=registry)

    assert client.bar_calls[-1][2] == "page-two"
    assert [call[2] for call in client.bar_calls].count(None) == 1
    assert completed["page_count"] == 2
    assert completed["canonical"]["canonical_rows"] == 2


def test_provider_rejected_literal_is_global_quarantine_without_substitution(
    tmp_path: Path,
) -> None:
    client = FakeAlpaca(reject="BAD$")
    acquirer = _acquirer(tmp_path, client)
    bootstrap = acquirer.freeze_bootstrap()
    source, symbols = acquirer.ensure_source_snapshot(bootstrap)
    units, _manifest = acquirer.ensure_plan(bootstrap, source, symbols)
    unit = next(item for item in units if item.canonical_timeframe == "1d")
    registry: dict[str, dict[str, object]] = {}

    completed = acquirer._acquire_unit(unit, registry=registry)

    assert client.bar_calls[0][0] == ("AAPL", "BAD$")
    assert client.bar_calls[1][0] == ("AAPL",)
    assert "BAD$" in registry
    assert completed["status"] == "COMPLETE_WITH_QUARANTINE"
    assert completed["provider_rejections"][0]["symbol"] == "BAD$"
    assert completed["canonical"]["canonical_rows"] == 1


def test_corrupt_completed_canonical_fails_closed_on_resume(tmp_path: Path) -> None:
    acquirer = _acquirer(tmp_path, FakeAlpaca())
    acquirer.run(max_units=1)
    report = json.loads(acquirer.report_path.read_text(encoding="utf-8"))
    assert report["completed_units"] == 1
    canonical_path = next(acquirer.layout.canonical_daily.rglob("*.parquet"))
    canonical_path.write_bytes(b"corrupt")

    with pytest.raises(RuntimeError, match="canonical hash mismatch"):
        acquirer.run(max_units=1)
