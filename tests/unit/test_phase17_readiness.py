from __future__ import annotations

import hashlib
import json

from packages.control_plane.phase16_closeout import PHASE16_CLOSEOUT_CONTRACT_VERSION
from packages.control_plane.phase16_smoke import Phase16OperationalSmoke
from packages.control_plane.phase17_policy import (
    PHASE17_ACCEPTED_PHASE16_FROZEN_HEAD_SHA,
    PHASE17_ACCEPTED_PHASE16_IMPLEMENTATION_FINGERPRINT,
    PHASE17_ACCEPTED_PHASE16_POLICY_FINGERPRINT,
    PHASE17_ACCEPTED_PHASE16_SOURCE_FINGERPRINT,
    PHASE17_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED,
    PHASE17_LIVE_EXECUTION_PROMOTION_ALLOWED,
    PHASE17_PROVIDER_MUTATIONS_ALLOWED,
    PHASE17_PROVIDER_READS_ALLOWED,
    PHASE17_REQUIRED_BROKERS,
    phase17_policy_fingerprint,
)
from packages.control_plane.phase17_readiness import Phase17ProviderReadiness
from packages.core.settings import load_settings


EXPECTED_POLICY_FINGERPRINT = (
    "693113bbb09458ed2939e486f9f6e0a0bda44e331c6419065760586047b93ff8"
)


def _settings(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(update={"derived": tmp_path})
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_phase16_evidence(tmp_path, *, frozen_head: str = PHASE17_ACCEPTED_PHASE16_FROZEN_HEAD_SHA):
    root = tmp_path / "control_plane" / "phase16" / "v1"
    root.mkdir(parents=True, exist_ok=True)
    smoke = root / "phase16_operational_smoke.json"
    independent = root / "phase16_independent_validation.json"
    smoke.write_text(json.dumps({"pass": True}, sort_keys=True) + "\n", encoding="utf-8")
    independent.write_text(
        json.dumps({"pass": True}, sort_keys=True) + "\n", encoding="utf-8"
    )
    acceptance = {
        "contract_version": PHASE16_CLOSEOUT_CONTRACT_VERSION,
        "pass": True,
        "git_head_sha": frozen_head,
        "phase16_policy_fingerprint": PHASE17_ACCEPTED_PHASE16_POLICY_FINGERPRINT,
        "implementation_fingerprint": PHASE17_ACCEPTED_PHASE16_IMPLEMENTATION_FINGERPRINT,
        "source_fingerprint": PHASE17_ACCEPTED_PHASE16_SOURCE_FINGERPRINT,
        "operational_smoke_sha256": _sha(smoke),
        "independent_validation_sha256": _sha(independent),
        "final_disposition": {
            "browser_control_plane_accepted": True,
            "actual_provider_mutation_exercised_in_acceptance": False,
            "cleanup_provider_writes_promoted": False,
            "live_execution_promoted": False,
            "automatic_cross_broker_failover_allowed": False,
        },
    }
    (root / "phase16_final_acceptance.json").write_text(
        json.dumps(acceptance, sort_keys=True) + "\n", encoding="utf-8"
    )


def test_phase17_policy_is_readonly_and_exact() -> None:
    assert phase17_policy_fingerprint() == EXPECTED_POLICY_FINGERPRINT
    assert PHASE17_REQUIRED_BROKERS == ("webull", "alpaca")
    assert PHASE17_PROVIDER_READS_ALLOWED is True
    assert PHASE17_PROVIDER_MUTATIONS_ALLOWED is False
    assert PHASE17_LIVE_EXECUTION_PROMOTION_ALLOWED is False
    assert PHASE17_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED is False


def test_phase17_keeps_provider_read_report_separate(tmp_path) -> None:
    smoke = Phase16OperationalSmoke(_settings(tmp_path))
    assert smoke.output_path(refresh_brokers=False).name == "phase16_operational_smoke.json"
    assert smoke.output_path(refresh_brokers=True).name == "phase16_provider_readonly_smoke.json"
    assert smoke.output_path(refresh_brokers=False) != smoke.output_path(refresh_brokers=True)


def test_phase17_accepts_exact_phase16_closeout_lineage(tmp_path) -> None:
    _write_phase16_evidence(tmp_path)
    readiness = Phase17ProviderReadiness(_settings(tmp_path))
    _, checks = readiness._phase16_acceptance()
    assert all(checks.values())


def test_phase17_detects_changed_phase16_frozen_head(tmp_path) -> None:
    _write_phase16_evidence(tmp_path, frozen_head="0" * 40)
    readiness = Phase17ProviderReadiness(_settings(tmp_path))
    _, checks = readiness._phase16_acceptance()
    assert checks["phase16_frozen_head_exact"] is False
