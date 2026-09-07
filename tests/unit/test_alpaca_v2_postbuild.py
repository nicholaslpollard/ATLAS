from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pytest

from packages.core.settings import load_settings
from packages.data.alpaca_v2_acquisition import AlpacaV2NativeAcquirer
from packages.data.alpaca_v2_postbuild import (
    AlpacaV2NotCompleteError,
    AlpacaV2PostBuildCoordinator,
    AlpacaV2ValidationError,
    AlpacaV2SplitDailyAcquirer,
    _security_type_from_names,
)
from packages.providers.alpaca import AlpacaApiPage, AlpacaInvalidSymbolError


def _page(
    name: str,
    payload: object,
    *,
    token: str | None = None,
) -> AlpacaApiPage:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    next_token = payload.get("next_page_token") if isinstance(payload, dict) else None
    return AlpacaApiPage(
        request_name=name,
        url=f"https://example.test/{name}",
        http_status=200,
        raw_body=body,
        payload=payload,
        response_headers={},
        page_token_used=token,
        next_page_token=str(next_token) if next_token else None,
    )


class FakePostBuildAlpaca:
    def get_assets(self, *, status: str) -> AlpacaApiPage:
        if status == "inactive":
            return _page("assets_inactive", [])
        return _page(
            "assets_active",
            [
                {
                    "id": "asset-aapl",
                    "symbol": "AAPL",
                    "status": "active",
                    "class": "us_equity",
                    "exchange": "NASDAQ",
                    "name": "Apple Inc. Common Stock",
                    "tradable": True,
                },
                {
                    "id": "asset-etf",
                    "symbol": "ETFZ",
                    "status": "active",
                    "class": "us_equity",
                    "exchange": "NYSEARCA",
                    "name": "Example Index ETF",
                    "tradable": True,
                },
                {
                    "id": "asset-msft",
                    "symbol": "MSFT",
                    "status": "active",
                    "class": "us_equity",
                    "exchange": "NASDAQ",
                    "name": "Microsoft Corporation Common Stock",
                    "tradable": True,
                },
            ],
        )

    def corporate_action_page(
        self,
        *,
        start: str,
        end: str,
        page_token: str | None = None,
    ) -> AlpacaApiPage:
        return _page(
            "corporate_actions",
            {
                "corporate_actions": {
                    "forward_splits": [
                        {
                            "id": "split-aapl",
                            "symbol": "AAPL",
                            "ex_date": "2020-01-03",
                            "old_rate": 1,
                            "new_rate": 2,
                            "cusip": "037833100",
                        }
                    ],
                    "cash_mergers": [
                        {
                            "id": "merger-msft",
                            "acquiree_symbol": "MSFT",
                            "acquirer_symbol": "ACQR",
                            "effective_date": "2020-01-03",
                            "cash_rate": 1.0,
                        }
                    ],
                },
                "next_page_token": None,
            },
            token=page_token,
        )

    def historical_bar_page(self, **kwargs: object) -> AlpacaApiPage:
        symbols = tuple(str(value) for value in kwargs["symbols"])
        timeframe = str(kwargs["timeframe"])
        adjustment = str(kwargs["adjustment"])
        bars: dict[str, list[dict[str, object]]] = {}
        for symbol in symbols:
            if timeframe == "1Day":
                if symbol == "AAPL":
                    raw = [
                        ("2020-01-02T05:00:00Z", 100.0, 102.0, 99.0, 101.0, 1000),
                        ("2020-01-03T05:00:00Z", 50.5, 52.0, 50.0, 51.0, 2000),
                    ]
                    if adjustment == "split":
                        raw[0] = ("2020-01-02T05:00:00Z", 50.0, 51.0, 49.5, 50.5, 2000)
                else:
                    raw = [
                        ("2020-01-02T05:00:00Z", 20.0, 21.0, 19.0, 20.5, 500),
                        ("2020-01-03T05:00:00Z", 20.5, 22.0, 20.0, 21.5, 700),
                    ]
            else:
                raw = [
                    ("2020-01-02T14:30:00Z", 100.0, 101.0, 99.0, 100.5, 10),
                    ("2020-01-03T14:30:00Z", 50.5, 51.0, 50.0, 50.8, 20),
                ]
            bars[symbol] = [
                {
                    "t": timestamp,
                    "o": open_value,
                    "h": high,
                    "l": low,
                    "c": close,
                    "v": volume,
                    "vw": close,
                    "n": 5,
                }
                for timestamp, open_value, high, low, close, volume in raw
            ]
        return _page(
            "historical_bars",
            {"bars": bars, "next_page_token": None},
            token=(
                str(kwargs["page_token"])
                if kwargs.get("page_token") is not None
                else None
            ),
        )


class FakeSplitVolumeDivergenceAlpaca(FakePostBuildAlpaca):
    def historical_bar_page(self, **kwargs: object) -> AlpacaApiPage:
        page = super().historical_bar_page(**kwargs)
        if (
            str(kwargs["timeframe"]) == "1Day"
            and str(kwargs["adjustment"]) == "split"
        ):
            payload = json.loads(page.raw_body)
            aapl = payload.get("bars", {}).get("AAPL", [])
            if aapl:
                aapl[0]["v"] = 2300
            return _page("historical_bars", payload, token=page.page_token_used)
        return page


class FakeSplitPriceFactorMismatchAlpaca(FakePostBuildAlpaca):
    def historical_bar_page(self, **kwargs: object) -> AlpacaApiPage:
        page = super().historical_bar_page(**kwargs)
        if (
            str(kwargs["timeframe"]) == "1Day"
            and str(kwargs["adjustment"]) == "split"
        ):
            payload = json.loads(page.raw_body)
            aapl = payload.get("bars", {}).get("AAPL", [])
            if aapl:
                aapl[0]["o"] = 50.25
            return _page("historical_bars", payload, token=page.page_token_used)
        return page


class FakeSplitRejectAlpaca(FakePostBuildAlpaca):
    def historical_bar_page(self, **kwargs: object) -> AlpacaApiPage:
        symbols = tuple(str(value) for value in kwargs["symbols"])
        if str(kwargs["adjustment"]) == "split" and "MSFT" in symbols:
            error_page = _page(
                "historical_bars",
                {"message": "invalid symbol: MSFT"},
            )
            raise AlpacaInvalidSymbolError(
                "MSFT", error_page, "invalid symbol: MSFT"
            )
        return super().historical_bar_page(**kwargs)


def _settings(tmp_path: Path):
    return load_settings().model_copy(update={"project_root": tmp_path})


def _native(
    tmp_path: Path,
    *,
    max_units: int | None = None,
    client: FakePostBuildAlpaca | None = None,
):
    settings = _settings(tmp_path)
    client = client or FakePostBuildAlpaca()
    acquirer = AlpacaV2NativeAcquirer(
        settings,
        start_date=date(2020, 1, 2),
        now_utc=datetime(2020, 1, 3, 22, tzinfo=UTC),
        client=client,
    )
    acquirer._require_disk = lambda **_: None  # type: ignore[method-assign]
    acquirer.run(max_units=max_units)
    return settings, client


def test_security_type_classifier_is_conservative() -> None:
    assert _security_type_from_names(["Example Class A Common Stock"]) == (
        "COMMON_STOCK",
        (),
    )
    security_type, reasons = _security_type_from_names(["Example Index ETF"])
    assert security_type == "UNCONFIRMED"
    assert "NON_COMMON_SECURITY_NAME" in reasons
    assert _security_type_from_names(["Example Incorporated"])[0] == "UNCONFIRMED"


def test_postbuild_refuses_incomplete_native_acquisition(tmp_path: Path) -> None:
    settings, _client = _native(tmp_path, max_units=1)
    with pytest.raises(AlpacaV2NotCompleteError):
        AlpacaV2PostBuildCoordinator(settings).validate_native()


def test_postbuild_validates_identity_adjusted_source_and_research_view(
    tmp_path: Path,
) -> None:
    settings, client = _native(tmp_path)
    coordinator = AlpacaV2PostBuildCoordinator(settings)

    native = coordinator.validate_native()
    daily = coordinator.validate_daily(native)
    identity = coordinator.build_identity_lifecycle(native, daily)
    split_acquirer = AlpacaV2SplitDailyAcquirer(settings, client=client)
    split_acquirer.base._require_disk = lambda **_: None  # type: ignore[method-assign]
    split = split_acquirer.run(native)
    research = coordinator.build_research_daily(native, daily, identity, split)

    assert native.report["status"] == "PASS"
    assert daily.report["status"] == "PASS"
    assert identity.report["status"] == "PASS"
    assert identity.report["identity_clear_common_stock_symbols"] == 1
    msft_identity = identity.symbol_map.loc[
        identity.symbol_map["symbol"] == "MSFT"
    ].iloc[0]
    assert bool(msft_identity["identity_clear"]) is False
    assert (
        "CORPORATE_ACTION_REQUIRES_SEPARATE_SEGMENT_POLICY:cash_mergers"
        in str(msft_identity["reason_codes"])
    )
    assert split.report["status"] == "COMPLETE"
    assert split.report["clean_candidate"] is True
    assert research.report["status"] == "PASS"
    assert research.report["eligible_symbols"] == 1
    assert research.report["research_rows"] == 2
    assert research.report["historical_performance_opened"] is False
    assert research.report["v1_rows_read"] == 0

    partition = Path(str(research.report["partitions"][0]["path"]))
    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(
            "SELECT ticker, open, close, volume, unadjusted_close, security_type, "
            "price_adjustment_mode "
            "FROM read_parquet(?) ORDER BY session_date",
            [str(partition)],
        ).fetchall()
    finally:
        con.close()
    assert rows == [
        ("AAPL", 50.0, 50.5, 2000.0, 101.0, "CS", "SPLIT_ADJUSTED"),
        ("AAPL", 50.5, 51.0, 2000.0, 51.0, "CS", "SPLIT_ADJUSTED"),
    ]

    native_rerun = coordinator.validate_native()
    daily_rerun = coordinator.validate_daily(native_rerun)
    identity_rerun = coordinator.build_identity_lifecycle(native_rerun, daily_rerun)
    split_rerun = split_acquirer.run(native_rerun)
    research_rerun = coordinator.build_research_daily(
        native_rerun, daily_rerun, identity_rerun, split_rerun
    )
    assert research_rerun.report["source_fingerprint"] == research.report[
        "source_fingerprint"
    ]


def test_research_daily_audits_provider_native_split_volume_divergence(
    tmp_path: Path,
) -> None:
    client = FakeSplitVolumeDivergenceAlpaca()
    settings, client = _native(tmp_path, client=client)
    coordinator = AlpacaV2PostBuildCoordinator(settings)
    native = coordinator.validate_native()
    daily = coordinator.validate_daily(native)
    identity = coordinator.build_identity_lifecycle(native, daily)
    split_acquirer = AlpacaV2SplitDailyAcquirer(settings, client=client)
    split_acquirer.base._require_disk = lambda **_: None  # type: ignore[method-assign]
    split = split_acquirer.run(native)

    research = coordinator.build_research_daily(native, daily, identity, split)

    assert research.report["status"] == "PASS"
    assert research.report["checks"][
        "split_factor_and_provenance_failures_zero"
    ] is True
    assert research.report["volume_reconciliation_audit"] == {
        "paired_rows": 2,
        "positive_raw_volume_rows": 2,
        "inverse_price_expectation_divergence_rows": 1,
        "relative_tolerance": 1e-5,
        "acceptance_effect": "AUDIT_ONLY",
        "policy": (
            "Provider-native split-adjusted volume is preserved as supplied; "
            "inverse-price-factor volume equivalence is diagnostic evidence, "
            "not a price-factor or provenance acceptance invariant."
        ),
    }


def test_research_daily_still_rejects_split_price_factor_corruption(
    tmp_path: Path,
) -> None:
    client = FakeSplitPriceFactorMismatchAlpaca()
    settings, client = _native(tmp_path, client=client)
    coordinator = AlpacaV2PostBuildCoordinator(settings)
    native = coordinator.validate_native()
    daily = coordinator.validate_daily(native)
    identity = coordinator.build_identity_lifecycle(native, daily)
    split_acquirer = AlpacaV2SplitDailyAcquirer(settings, client=client)
    split_acquirer.base._require_disk = lambda **_: None  # type: ignore[method-assign]
    split = split_acquirer.run(native)

    with pytest.raises(
        AlpacaV2ValidationError,
        match="split_factor_and_provenance_failures_zero",
    ):
        coordinator.build_research_daily(native, daily, identity, split)


def test_split_adjusted_daily_resume_reuses_completed_units(tmp_path: Path) -> None:
    settings, client = _native(tmp_path)
    coordinator = AlpacaV2PostBuildCoordinator(settings)
    native = coordinator.validate_native()
    split_acquirer = AlpacaV2SplitDailyAcquirer(settings, client=client)
    split_acquirer.base._require_disk = lambda **_: None  # type: ignore[method-assign]

    first = split_acquirer.run(native)
    second = split_acquirer.run(native)

    assert first.report["source_fingerprint"] == second.report["source_fingerprint"]
    assert second.report["completed_units"] == second.report["total_units"] == 1


def test_split_rejection_excludes_literal_without_blocking_clean_remainder(
    tmp_path: Path,
) -> None:
    client = FakeSplitRejectAlpaca()
    settings, client = _native(tmp_path, client=client)
    coordinator = AlpacaV2PostBuildCoordinator(settings)
    native = coordinator.validate_native()
    daily = coordinator.validate_daily(native)
    identity = coordinator.build_identity_lifecycle(native, daily)
    split_acquirer = AlpacaV2SplitDailyAcquirer(settings, client=client)
    split_acquirer.base._require_disk = lambda **_: None  # type: ignore[method-assign]

    split = split_acquirer.run(native)
    research = coordinator.build_research_daily(
        native, daily, identity, split
    )

    assert split.report["status"] == "COMPLETE"
    assert split.report["clean_candidate"] is True
    assert split.report["excluded_symbols"] == ["MSFT"]
    assert split.report["status_counts"] == {"COMPLETE_WITH_QUARANTINE": 1}
    assert research.report["eligible_symbols"] == 1
    assert research.report["excluded_split_source_symbols"] == ["MSFT"]
