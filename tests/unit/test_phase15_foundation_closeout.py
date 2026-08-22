from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.execution.phase15_closeout import phase15_acceptance_checks
from packages.execution.phase15_foundation import (
    PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT,
    PHASE15_ACCEPTED_CUMULATIVE_HISTORY_END,
    PHASE15_ACCEPTED_CUMULATIVE_POLICY_FINGERPRINT,
    Phase15CumulativeFoundationBinding,
    Phase15CumulativeFoundationResolver,
    Phase15FoundationError,
)
from packages.execution.phase15_policy import (
    PHASE15_REQUIRE_ACCEPTED_CUMULATIVE_FOUNDATION,
    phase15_policy_payload,
)
from packages.features.partition_store import sha256_file
from packages.validation.cumulative_acceptance import CUMULATIVE_FOUNDATION_VALIDATION_VERSION
from packages.validation.cumulative_policy import CUMULATIVE_FOUNDATION_ACCEPTANCE_VERSION


class _Settings:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.data = SimpleNamespace(paths=SimpleNamespace(derived=Path("data/derived")))

    def resolved_path(self, relative: Path | str) -> Path:
        path = Path(relative)
        return path if path.is_absolute() else self.root / path


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _foundation_artifacts(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "data" / "derived" / "validation" / "cumulative_foundation" / "v1"
    acceptance_path = root / "cumulative_foundation_acceptance.json"
    validation_path = root / "cumulative_foundation_validation.json"
    acceptance = {
        "contract_version": CUMULATIVE_FOUNDATION_ACCEPTANCE_VERSION,
        "source_fingerprint": PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT,
        "policy_fingerprint": PHASE15_ACCEPTED_CUMULATIVE_POLICY_FINGERPRINT,
        "history_start": "2016-01-04",
        "history_end": PHASE15_ACCEPTED_CUMULATIVE_HISTORY_END.isoformat(),
        "new_posthoc_statistical_thresholds": False,
        "canonical_writes": 0,
        "feature_writes": 0,
        "regime_writes": 0,
        "model_writes": 0,
        "broker_writes": 0,
        "external_provider_calls": 0,
        "pass": True,
    }
    _write_json(acceptance_path, acceptance)
    validation = {
        "contract_version": CUMULATIVE_FOUNDATION_VALIDATION_VERSION,
        "acceptance_sha256": sha256_file(acceptance_path),
        "checks": {
            "acceptance_contract_exact": True,
            "all_component_hashes_exact": True,
            "all_component_artifacts_pass": True,
            "acceptance_pass": True,
        },
        "pass": True,
    }
    _write_json(validation_path, validation)
    return acceptance_path, validation_path


def test_phase15_policy_binds_exact_cumulative_foundation() -> None:
    payload = phase15_policy_payload()
    assert PHASE15_REQUIRE_ACCEPTED_CUMULATIVE_FOUNDATION is True
    assert payload["accepted_cumulative_foundation_fingerprint"] == PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT
    assert payload["accepted_cumulative_policy_fingerprint"] == PHASE15_ACCEPTED_CUMULATIVE_POLICY_FINGERPRINT


def test_cumulative_foundation_resolver_accepts_exact_hash_bound_artifacts(tmp_path: Path) -> None:
    acceptance_path, validation_path = _foundation_artifacts(tmp_path)
    binding = Phase15CumulativeFoundationResolver(_Settings(tmp_path)).resolve()
    assert binding.foundation_fingerprint == PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT
    assert binding.policy_fingerprint == PHASE15_ACCEPTED_CUMULATIVE_POLICY_FINGERPRINT
    assert binding.history_start == date(2016, 1, 4)
    assert binding.history_end == date(2026, 8, 14)
    assert binding.acceptance_sha256 == sha256_file(acceptance_path)
    assert binding.validation_sha256 == sha256_file(validation_path)


def test_cumulative_foundation_resolver_rejects_changed_foundation_fingerprint(tmp_path: Path) -> None:
    acceptance_path, _validation_path = _foundation_artifacts(tmp_path)
    payload = json.loads(acceptance_path.read_text(encoding="utf-8"))
    payload["source_fingerprint"] = "0" * 64
    _write_json(acceptance_path, payload)
    with pytest.raises(Phase15FoundationError, match="foundation fingerprint"):
        Phase15CumulativeFoundationResolver(_Settings(tmp_path)).resolve()


def test_cumulative_foundation_resolver_rejects_validation_bound_to_old_acceptance(tmp_path: Path) -> None:
    acceptance_path, _validation_path = _foundation_artifacts(tmp_path)
    payload = json.loads(acceptance_path.read_text(encoding="utf-8"))
    payload["generated_at_utc"] = "tampered-but-otherwise-valid"
    _write_json(acceptance_path, payload)
    with pytest.raises(Phase15FoundationError, match="no longer binds acceptance"):
        Phase15CumulativeFoundationResolver(_Settings(tmp_path)).resolve()


def test_closeout_checks_require_zero_execution_and_exact_foundation() -> None:
    foundation = Phase15CumulativeFoundationBinding(
        contract_version="test-binding",
        acceptance_path=Path("acceptance.json"),
        acceptance_sha256="a" * 64,
        validation_path=Path("validation.json"),
        validation_sha256="b" * 64,
        foundation_fingerprint=PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT,
        policy_fingerprint=PHASE15_ACCEPTED_CUMULATIVE_POLICY_FINGERPRINT,
        history_start=date(2016, 1, 4),
        history_end=date(2026, 8, 14),
    )
    execution_input = SimpleNamespace(cumulative_foundation=foundation, execution_case_count=0)
    manifest = {
        "policy_fingerprint": __import__("packages.execution.phase15_policy", fromlist=["phase15_policy_fingerprint"]).phase15_policy_fingerprint(),
        "pass": True,
        "execution_case_count": 0,
        "no_case_disposition": "NO_ACCEPTED_PHASE14_EXECUTION_CASES",
        "quote_source_initialized": False,
        "quote_reads": 0,
        "broker_initialized": False,
        "provider_submission_attempts": 0,
        "known_broker_writes": 0,
        "known_order_writes": 0,
        "unknown_write_record_count": 0,
        "production_ml_writes": 0,
        "live_writes": 0,
        "execution_present": False,
        "automatic_broker_failover_performed": False,
    }
    validation = {
        "pass": True,
        "known_broker_writes": 0,
        "known_order_writes": 0,
        "unknown_write_record_count": 0,
        "production_ml_writes": 0,
        "live_writes": 0,
        "checks": {
            "accepted_phase14_input_reverified": True,
            "preregistered_policy_exact": True,
            "zero_case_noop_is_valid": True,
        },
    }
    checks = phase15_acceptance_checks(
        execution_input=execution_input,
        manifest=manifest,
        validation=validation,
    )
    assert all(checks.values())
    manifest["broker_initialized"] = True
    assert phase15_acceptance_checks(
        execution_input=execution_input,
        manifest=manifest,
        validation=validation,
    )["broker_not_initialized"] is False
