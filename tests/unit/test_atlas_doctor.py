from __future__ import annotations

import json

from scripts.atlas_doctor import CONTRACT_VERSION, build_report, credential_presence


def test_doctor_credential_presence_never_returns_secret_values() -> None:
    env = {
        "MASSIVE_API_KEY": "massive-private-value",
        "MASSIVE_S3_ACCESS_KEY_ID": "s3-access-private-value",
        "MASSIVE_S3_SECRET_ACCESS_KEY": "s3-secret-private-value",
        "WEBULL_PAPER_APP_KEY": "webull-paper-private-key",
        "WEBULL_PAPER_APP_SECRET": "webull-paper-private-secret",
        "WEBULL_LIVE_APP_KEY": "webull-live-private-key",
        "WEBULL_LIVE_APP_SECRET": "webull-live-private-secret",
        "ALPACA_PAPER_API_KEY": "alpaca-paper-private-key",
        "ALPACA_PAPER_API_SECRET": "alpaca-paper-private-secret",
        "ALPACA_LIVE_API_KEY": "alpaca-live-private-key",
        "ALPACA_LIVE_API_SECRET": "alpaca-live-private-secret",
    }

    presence = credential_presence(env)

    assert set(presence.values()) == {"CONFIGURED"}
    serialized = json.dumps(presence, sort_keys=True)
    for value in env.values():
        assert value not in serialized


def test_doctor_report_is_provider_inert_and_sanitized() -> None:
    env = {
        "MASSIVE_API_KEY": "doctor-massive-secret",
        "MASSIVE_S3_ACCESS_KEY_ID": "doctor-s3-access-secret",
        "MASSIVE_S3_SECRET_ACCESS_KEY": "doctor-s3-secret",
        "WEBULL_PAPER_APP_KEY": "doctor-webull-key",
        "WEBULL_PAPER_APP_SECRET": "doctor-webull-secret",
        "ALPACA_PAPER_API_KEY": "doctor-alpaca-key",
        "ALPACA_PAPER_API_SECRET": "doctor-alpaca-secret",
    }

    report = build_report(env=env)
    serialized = json.dumps(report, sort_keys=True)

    assert report["contract_version"] == CONTRACT_VERSION
    assert report["overall"] == "PASS"
    assert report["checks"]["dependency_lock"] == "PASS"
    assert report["checks"]["secret_hygiene"] == "PASS"
    assert report["safety"]["provider_calls_performed"] == 0
    assert report["safety"]["provider_writes_performed"] == 0
    assert report["safety"]["phase18_provider_mutation_default"] == "DENIED"
    assert report["safety"]["phase18_explicit_target_authorization_required"] is True
    assert report["safety"]["live_execution_promotion"] == "DISABLED"
    assert report["safety"]["automatic_cross_broker_failover"] == "DISABLED"
    for value in env.values():
        assert value not in serialized
