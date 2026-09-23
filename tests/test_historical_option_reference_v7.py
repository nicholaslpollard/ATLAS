from __future__ import annotations

import io
import json
import urllib.error
from datetime import date
from pathlib import Path

import pytest

import packages.data.historical_option_reference_v7 as acquisition
from packages.core.settings import load_settings
from packages.data.historical_option_reference_v7_contract import (
    ARTC_DIAGNOSTIC_EVIDENCE_FINGERPRINT,
    HISTORICAL_OPTION_REFERENCE_V7_CONTRACT_FINGERPRINT,
    UNVERSIONED_DELIVERABLE_CFI_POLICY,
    ReferencePartition,
    acquisition_contract_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

JULY_PARTITION = ReferencePartition(
    key="expired-2014-07",
    state="EXPIRED",
    expiration_gte=date(2014, 7, 1),
    expiration_lt=date(2014, 8, 1),
    expired=True,
)


def _settings(tmp_path: Path):
    base = load_settings(PROJECT_ROOT)
    return base.model_copy(update={"project_root": tmp_path.resolve()})


def _artc_cash_row() -> dict[str, object]:
    return {
        "ticker": "O:ARTC140719C00025000",
        "underlying_ticker": "ARTC",
        "contract_type": "call",
        "expiration_date": "2014-07-19",
        "strike_price": 25,
        "exercise_style": "american",
        "shares_per_contract": 100,
        "primary_exchange": "BATO",
        "cfi": "OCASCN",
        "additional_underlyings": [
            {
                "amount": 4825,
                "type": "currency",
                "underlying": "USD",
            }
        ],
    }


def _artc_physical_row() -> dict[str, object]:
    return {
        "ticker": "O:ARTC140719C00025000",
        "underlying_ticker": "ARTC",
        "contract_type": "call",
        "expiration_date": "2014-07-19",
        "strike_price": 25,
        "exercise_style": "american",
        "shares_per_contract": 100,
        "primary_exchange": "BATO",
        "cfi": "OCASPS",
    }


def _install_artc_exact_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cash = _artc_cash_row()
    list_calls = 0
    overview_calls = 0

    def historical_once(
        _settings,
        *,
        api_key: str,
        ticker: str,
        contract_type: str,
        expiration: date,
        strike_price: str,
        as_of: date,
    ):
        nonlocal list_calls
        list_calls += 1
        assert api_key == "token"
        assert ticker == "O:ARTC140719C00025000"
        assert contract_type == "call"
        assert expiration == date(2014, 7, 19)
        assert strike_price == "25"
        assert as_of == date(2014, 7, 18)
        return dict(cash), [f"list-{list_calls}"]

    def request_json(_settings, *, url: str, api_key: str):
        nonlocal overview_calls
        overview_calls += 1
        assert api_key == "token"
        assert "O%3AARTC140719C00025000" in url
        assert "as_of=2014-07-18" in url
        return {
            "status": "OK",
            "request_id": f"overview-{overview_calls}",
            "results": dict(cash),
        }

    monkeypatch.setattr(acquisition, "_historical_target_row_once", historical_once)
    monkeypatch.setattr(acquisition, "_request_json", request_json)


def test_v7_contract_freezes_artc_cash_deliverable_branch() -> None:
    manifest = acquisition_contract_manifest()

    assert len(HISTORICAL_OPTION_REFERENCE_V7_CONTRACT_FINGERPRINT) == 64
    assert manifest["contract"] == "atlas-historical-option-reference-v7"
    assert manifest["parent_v6_contract_fingerprint"] == (
        "f40edc7bc0dd872dfa944297571545a8e4ab14c112af1ea35ddd806bf2c30342"
    )
    assert manifest["v6_observed_failure"] == {
        "partition": "expired-2014-07",
        "ticker": "O:ARTC140719C00025000",
        "failure_class": "UNVERSIONED_ADDITIONAL_UNDERLYINGS_PLUS_CFI_CONFLICT",
    }

    accepted = manifest["accepted_diagnostics"]["artc_cash_deliverable_classification"]
    assert accepted["evidence_fingerprint"] == ARTC_DIAGNOSTIC_EVIDENCE_FINGERPRINT
    assert accepted["current_cfi_values"] == ["OCASCN", "OCASPS"]
    assert accepted["differing_fields"] == ["additional_underlyings", "cfi"]
    assert accepted["historical_payload_matches_exactly_one_current_row"] is True
    assert accepted["selected_provider_record_sha256"] == (
        "6f1274868c60e6d23c42c96e4698a08724b3ff1014dd6ecf5b3a992f9794d3d8"
    )
    assert accepted["selected_cash_additional_underlying_usd"] == 4825

    fallback = manifest["normalization"][
        "unversioned_cash_deliverable_classification_fallback"
    ]
    assert fallback["required_differing_fields_exactly"] == [
        "additional_underlyings",
        "cfi",
    ]
    assert fallback["one_current_payload_must_have_cash_additional_underlying"] is True
    assert fallback["one_current_payload_must_lack_additional_underlying"] is True
    assert fallback["historical_payload_must_exactly_match_one_current_conflicting_payload"] is True
    assert fallback["dynamic_deliverable_authority_created"] is False
    assert fallback["policy"] == UNVERSIONED_DELIVERABLE_CFI_POLICY

    assert manifest["normalization"]["ambiguity_quarantine"][
        "preserve_all_raw_conflicting_rows"
    ] is True
    assert manifest["authority"]["strategy_outcome_access"] is False
    assert manifest["authority"]["paper_authority"] is False
    assert manifest["authority"]["live_authority"] is False


def test_v7_artc_exact_history_selects_cash_deliverable_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_artc_exact_history(monkeypatch)
    settings = _settings(tmp_path)

    normalized, discarded = acquisition._resolve_ticker_versions(
        [_artc_cash_row(), _artc_physical_row()],
        partition=JULY_PARTITION,
        settings=settings,
        api_key="token",
    )

    assert discarded == 1
    assert normalized["ticker"] == "O:ARTC140719C00025000"
    assert normalized["provider_record_sha256"] == (
        "6f1274868c60e6d23c42c96e4698a08724b3ff1014dd6ecf5b3a992f9794d3d8"
    )
    assert normalized["cfi"] == "OCASCN"
    assert json.loads(str(normalized["additional_underlyings_json"])) == [
        {
            "amount": 4825,
            "type": "currency",
            "underlying": "USD",
        }
    ]
    assert normalized["historically_resolved_conflict"] is True
    assert normalized["conflict_resolution_policy"] == UNVERSIONED_DELIVERABLE_CFI_POLICY
    assert normalized["conflict_resolution_as_of_date"] == "2014-07-18"
    assert json.loads(
        str(normalized["conflict_resolution_differing_fields_json"])
    ) == ["additional_underlyings", "cfi"]


def test_v7_rejects_unversioned_additional_underlying_only_conflict(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    cash = _artc_cash_row()
    other = _artc_cash_row()
    other.pop("additional_underlyings")

    with pytest.raises(acquisition.HistoricalOptionReferenceV7Error, match="outside frozen V7 branches"):
        acquisition._resolve_ticker_versions(
            [cash, other],
            partition=JULY_PARTITION,
            settings=settings,
            api_key="token",
        )


def test_v7_rejects_non_cash_deliverable_classification_branch(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    adjusted = _artc_cash_row()
    adjusted["additional_underlyings"] = [
        {
            "amount": 100,
            "type": "equity",
            "underlying": "SNN",
        }
    ]

    with pytest.raises(
        acquisition.HistoricalOptionReferenceV7Error,
        match="positive USD cash deliverable",
    ):
        acquisition._resolve_ticker_versions(
            [adjusted, _artc_physical_row()],
            partition=JULY_PARTITION,
            settings=settings,
            api_key="token",
        )


def test_v7_known_conflict_preflight_fully_paginates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    spec = {
        "id": "ARTC_UNVERSIONED_CASH_DELIVERABLE_CLASSIFICATION",
        "ticker": "O:ARTC140719C00025000",
        "contract_type": "call",
        "expiration_date": "2014-07-19",
        "strike_price": 25,
        "expected_current_target_rows": 2,
        "expected_historical_target_rows": 1,
        "expected_differing_fields": ["additional_underlyings", "cfi"],
        "expected_highest_correction_rank": -1,
        "expected_selected_provider_record_sha256": (
            "6f1274868c60e6d23c42c96e4698a08724b3ff1014dd6ecf5b3a992f9794d3d8"
        ),
        "expected_selected_cfi": "OCASCN",
        "expected_cash_additional_underlying_usd": 4825,
        "resolution_branch": "UNVERSIONED_CASH_DELIVERABLE_CLASSIFICATION",
        "diagnostic_evidence_fingerprint": ARTC_DIAGNOSTIC_EVIDENCE_FINGERPRINT,
    }
    monkeypatch.setattr(acquisition, "KNOWN_CONFLICTS", (spec,))

    calls: list[str] = []
    base = settings.massive.provider.rest_base_url.rstrip("/")

    def request_json(_settings, *, url: str, api_key: str):
        assert api_key == "token"
        calls.append(url)
        if len(calls) == 1:
            return {
                "status": "OK",
                "results": [{"ticker": "O:AAA140719C00025000"}],
                "next_url": base + "/page2",
            }
        if len(calls) == 2:
            return {
                "status": "OK",
                "results": [{"ticker": "O:BBB140719C00025000"}],
                "next_url": base + "/page3",
            }
        assert len(calls) == 3
        return {
            "status": "OK",
            "results": [_artc_cash_row(), _artc_physical_row()],
        }

    def resolve_versions(*args, **kwargs):
        return (
            {
                "historically_resolved_conflict": True,
                "provider_record_sha256": (
                    "6f1274868c60e6d23c42c96e4698a08724b3ff1014dd6ecf5b3a992f9794d3d8"
                ),
                "underlying_ticker": "ARTC",
                "primary_exchange": "BATO",
                "cfi": "OCASCN",
                "additional_underlyings_json": json.dumps(
                    [{"amount": 4825, "type": "currency", "underlying": "USD"}],
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "selected_correction_rank": -1,
                "conflict_resolution_policy": UNVERSIONED_DELIVERABLE_CFI_POLICY,
                "conflict_resolution_as_of_date": "2014-07-18",
                "conflict_resolution_historical_list_sha256": (
                    "6f1274868c60e6d23c42c96e4698a08724b3ff1014dd6ecf5b3a992f9794d3d8"
                ),
                "conflict_resolution_overview_sha256": (
                    "6f1274868c60e6d23c42c96e4698a08724b3ff1014dd6ecf5b3a992f9794d3d8"
                ),
            },
            1,
        )

    monkeypatch.setattr(acquisition, "_request_json", request_json)
    monkeypatch.setattr(acquisition, "_resolve_ticker_versions", resolve_versions)

    result = acquisition._known_conflict_resolution_probes(
        settings,
        api_key="token",
    )

    assert len(calls) == 3
    assert result[0]["current_list_page_count"] == 3
    assert result[0]["current_target_rows"] == 2
    assert result[0]["selected_cfi"] == "OCASCN"


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._body


class _RecordingCoordinator:
    def __init__(self) -> None:
        self.request_starts = 0
        self.throttle_events = 0
        self.cooldowns: list[float] = []
        self.cancelled = False

    def wait_for_request_slot(self) -> None:
        self.request_starts += 1

    def impose_throttle_cooldown(self, seconds: float) -> None:
        self.throttle_events += 1
        self.cooldowns.append(float(seconds))

    def wait_backoff(self, seconds: float) -> None:
        return None

    def cancel(self) -> None:
        self.cancelled = True


def test_v7_request_json_coordinates_429_then_recovers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    coordinator = _RecordingCoordinator()
    monkeypatch.setattr(acquisition, "_ACTIVE_REQUEST_COORDINATOR", coordinator)

    calls = 0

    def opener(request, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise urllib.error.HTTPError(
                request.full_url,
                429,
                "Too Many Requests",
                {"Retry-After": "2"},
                io.BytesIO(b'{"status":"ERROR","error":"rate limited"}'),
            )
        return _FakeResponse({"status": "OK", "results": []})

    monkeypatch.setattr(acquisition.urllib.request, "urlopen", opener)

    payload = acquisition._request_json(
        settings,
        url="https://api.massive.com/v3/reference/options/contracts",
        api_key="token",
    )

    assert payload["status"] == "OK"
    assert calls == 2
    assert coordinator.request_starts == 2
    assert coordinator.throttle_events == 1
    assert coordinator.cooldowns == [2.0]


def test_v7_request_json_persistent_429_stops_resumable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    coordinator = _RecordingCoordinator()
    monkeypatch.setattr(acquisition, "_ACTIVE_REQUEST_COORDINATOR", coordinator)

    def opener(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            429,
            "Too Many Requests",
            {},
            io.BytesIO(b'{"status":"ERROR","error":"rate limited"}'),
        )

    monkeypatch.setattr(acquisition.urllib.request, "urlopen", opener)

    with pytest.raises(
        acquisition.HistoricalOptionReferenceV7ProviderThrottleError,
        match="Completed V7 receipts remain reusable",
    ):
        acquisition._request_json(
            settings,
            url="https://api.massive.com/v3/reference/options/contracts",
            api_key="token",
        )

    assert coordinator.request_starts == settings.massive.reference.max_attempts
    assert coordinator.throttle_events == settings.massive.reference.max_attempts
    assert all(seconds >= 60.0 for seconds in coordinator.cooldowns)


def test_v7_bounded_worker_failure_cancels_peer_request_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator = _RecordingCoordinator()
    monkeypatch.setattr(acquisition, "_ACTIVE_REQUEST_COORDINATOR", coordinator)

    def task(item: int) -> dict[str, object]:
        if item == 1:
            raise acquisition.HistoricalOptionReferenceV7Error("synthetic provider failure")
        return {"item": item}

    with pytest.raises(
        acquisition.HistoricalOptionReferenceV7Error,
        match="synthetic provider failure",
    ):
        acquisition._run_bounded(
            [1, 2],
            workers=2,
            task=task,
            on_complete=lambda item, receipt, done: None,
        )

    assert coordinator.cancelled is True


def test_v7_request_coordinator_uses_one_shared_interval() -> None:
    coordinator = acquisition._V7RequestCoordinator(requests_per_minute=5)
    assert coordinator.requests_per_minute == 5
    assert coordinator.minimum_interval_seconds == pytest.approx(12.0)
