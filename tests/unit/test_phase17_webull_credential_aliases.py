from __future__ import annotations

from packages.brokers.webull.broker import WebullSandboxBroker, _first_env
from packages.control_plane.status import Phase16StatusService
from packages.schemas.execution import BrokerName


def _status_service(env: dict[str, str]) -> Phase16StatusService:
    service = object.__new__(Phase16StatusService)
    service._env = env
    return service


def test_webull_status_uses_canonical_paper_credential_names() -> None:
    secret_key = "paper-key-value"
    secret_value = "paper-secret-value"
    credentials = _status_service(
        {
            "WEBULL_PAPER_APP_KEY": secret_key,
            "WEBULL_PAPER_APP_SECRET": secret_value,
            "WEBULL_PAPER_ACCOUNT_ID": "paper-account",
        }
    ).credentials(BrokerName.WEBULL)

    assert credentials.ready is True
    assert credentials.required_names == (
        "WEBULL_PAPER_APP_KEY",
        "WEBULL_PAPER_APP_SECRET",
    )
    assert credentials.optional_names == ("WEBULL_PAPER_ACCOUNT_ID",)
    assert credentials.required_present == {
        "WEBULL_PAPER_APP_KEY": True,
        "WEBULL_PAPER_APP_SECRET": True,
    }
    assert credentials.optional_present == {"WEBULL_PAPER_ACCOUNT_ID": True}
    serialized = str(credentials.model_dump(mode="json"))
    assert secret_key not in serialized
    assert secret_value not in serialized
    assert "paper-account" not in serialized


def test_webull_status_accepts_legacy_aliases_without_exposing_them_as_canonical_names() -> None:
    credentials = _status_service(
        {
            "WEBULL_APP_KEY": "legacy-key",
            "WEBULL_APP_SECRET": "legacy-secret",
            "WEBULL_ACCOUNT_ID": "legacy-account",
        }
    ).credentials(BrokerName.WEBULL)

    assert credentials.ready is True
    assert credentials.required_names == (
        "WEBULL_PAPER_APP_KEY",
        "WEBULL_PAPER_APP_SECRET",
    )
    assert credentials.optional_names == ("WEBULL_PAPER_ACCOUNT_ID",)


def test_webull_status_fails_closed_when_one_required_credential_is_missing() -> None:
    credentials = _status_service(
        {"WEBULL_PAPER_APP_KEY": "paper-key"}
    ).credentials(BrokerName.WEBULL)

    assert credentials.ready is False
    assert credentials.required_present == {
        "WEBULL_PAPER_APP_KEY": True,
        "WEBULL_PAPER_APP_SECRET": False,
    }


def test_webull_environment_resolution_prefers_canonical_paper_namespace(monkeypatch) -> None:
    monkeypatch.setenv("WEBULL_PAPER_APP_KEY", "paper-key")
    monkeypatch.setenv("WEBULL_APP_KEY", "legacy-key")
    assert _first_env("WEBULL_PAPER_APP_KEY", "WEBULL_APP_KEY") == "paper-key"


def test_webull_environment_resolution_falls_back_to_legacy_alias(monkeypatch) -> None:
    monkeypatch.delenv("WEBULL_PAPER_APP_KEY", raising=False)
    monkeypatch.setenv("WEBULL_APP_KEY", "legacy-key")
    assert _first_env("WEBULL_PAPER_APP_KEY", "WEBULL_APP_KEY") == "legacy-key"


def test_webull_sandbox_account_id_prefers_canonical_paper_namespace(monkeypatch) -> None:
    monkeypatch.setenv("WEBULL_PAPER_ACCOUNT_ID", "paper-account")
    monkeypatch.setenv("WEBULL_ACCOUNT_ID", "legacy-account")

    broker = WebullSandboxBroker(trade_client=object())

    assert broker.account_id == "paper-account"
