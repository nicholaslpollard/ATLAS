from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from packages.control_plane.phase16_closeout import PHASE16_CLOSEOUT_CONTRACT_VERSION
from packages.control_plane.phase16_smoke import (
    PHASE16_OPERATIONAL_SMOKE_CONTRACT_VERSION,
    Phase16OperationalSmoke,
)
from packages.control_plane.phase17_policy import (
    PHASE17_ACCEPTED_PHASE16_FROZEN_HEAD_SHA,
    PHASE17_ACCEPTED_PHASE16_IMPLEMENTATION_FINGERPRINT,
    PHASE17_ACCEPTED_PHASE16_POLICY_FINGERPRINT,
    PHASE17_ACCEPTED_PHASE16_SOURCE_FINGERPRINT,
    PHASE17_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED,
    PHASE17_LIVE_EXECUTION_PROMOTION_ALLOWED,
    PHASE17_PROVIDER_MUTATIONS_ALLOWED,
    PHASE17_REQUIRED_BROKERS,
    phase17_policy_fingerprint,
    validate_phase17_policy,
)
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings


PHASE17_READINESS_CONTRACT_VERSION = (
    "phase17-readiness-v1-phase16-artifact-preserving-dual-broker-readonly-reconciliation"
)


class Phase17ProviderReadinessError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(raw).hexdigest()


class Phase17ProviderReadiness:
    """Validate real broker read access without crossing any provider-mutation checkpoint."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        derived = settings.resolved_path(settings.data.paths.derived)
        self.phase16_root = derived / "control_plane" / "phase16" / "v1"
        self.phase16_acceptance_path = self.phase16_root / "phase16_final_acceptance.json"
        self.phase16_acceptance_smoke_path = self.phase16_root / "phase16_operational_smoke.json"
        self.phase16_independent_validation_path = (
            self.phase16_root / "phase16_independent_validation.json"
        )
        self.phase16_readonly_smoke_path = (
            self.phase16_root / "phase16_provider_readonly_smoke.json"
        )
        self.root = derived / "control_plane" / "phase17" / "v1"
        self.report_path = self.root / "phase17_provider_readiness.json"

    @staticmethod
    def _load_object(path: Path, label: str) -> dict[str, object]:
        if not path.is_file():
            raise Phase17ProviderReadinessError(f"required {label} artifact is missing: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise Phase17ProviderReadinessError(f"invalid {label} artifact: {path}") from exc
        if not isinstance(payload, dict):
            raise Phase17ProviderReadinessError(f"{label} artifact must be a JSON object")
        return payload

    def _phase16_acceptance(self) -> tuple[dict[str, object], dict[str, bool]]:
        acceptance = self._load_object(self.phase16_acceptance_path, "Phase 16 acceptance")
        final = (
            acceptance.get("final_disposition")
            if isinstance(acceptance.get("final_disposition"), dict)
            else {}
        )
        checks = {
            "phase16_closeout_contract_exact": acceptance.get("contract_version")
            == PHASE16_CLOSEOUT_CONTRACT_VERSION,
            "phase16_acceptance_pass": acceptance.get("pass") is True,
            "phase16_frozen_head_exact": acceptance.get("git_head_sha")
            == PHASE17_ACCEPTED_PHASE16_FROZEN_HEAD_SHA,
            "phase16_policy_exact": acceptance.get("phase16_policy_fingerprint")
            == PHASE17_ACCEPTED_PHASE16_POLICY_FINGERPRINT,
            "phase16_implementation_exact": acceptance.get("implementation_fingerprint")
            == PHASE17_ACCEPTED_PHASE16_IMPLEMENTATION_FINGERPRINT,
            "phase16_source_exact": acceptance.get("source_fingerprint")
            == PHASE17_ACCEPTED_PHASE16_SOURCE_FINGERPRINT,
            "phase16_browser_control_plane_accepted": final.get("browser_control_plane_accepted")
            is True,
            "phase16_provider_mutation_absent": final.get(
                "actual_provider_mutation_exercised_in_acceptance"
            )
            is False,
            "phase16_cleanup_writes_not_promoted": final.get(
                "cleanup_provider_writes_promoted"
            )
            is False,
            "phase16_live_not_promoted": final.get("live_execution_promoted") is False,
            "phase16_automatic_failover_disabled": final.get(
                "automatic_cross_broker_failover_allowed"
            )
            is False,
        }
        return acceptance, checks

    def run(self) -> dict[str, object]:
        validate_phase17_policy()
        acceptance, checks = self._phase16_acceptance()
        if not all(checks.values()):
            failed = sorted(name for name, value in checks.items() if not value)
            raise Phase17ProviderReadinessError(
                "accepted Phase 16 lineage check failed: " + ", ".join(failed)
            )

        acceptance_smoke_sha_before = _sha256_file(self.phase16_acceptance_smoke_path)
        acceptance_sha_before = _sha256_file(self.phase16_acceptance_path)
        independent_sha = _sha256_file(self.phase16_independent_validation_path)

        checks.update(
            {
                "phase16_acceptance_smoke_hash_bound": acceptance.get(
                    "operational_smoke_sha256"
                )
                == acceptance_smoke_sha_before,
                "phase16_independent_validation_hash_bound": acceptance.get(
                    "independent_validation_sha256"
                )
                == independent_sha,
                "readonly_report_path_separate": self.phase16_readonly_smoke_path
                != self.phase16_acceptance_smoke_path,
            }
        )
        if not all(checks.values()):
            failed = sorted(name for name, value in checks.items() if not value)
            raise Phase17ProviderReadinessError(
                "Phase 16 artifact binding failed before provider reads: " + ", ".join(failed)
            )

        smoke = Phase16OperationalSmoke(self.settings).run(
            refresh_brokers=True,
            write_report=True,
        )
        readonly_smoke_sha = _sha256_file(self.phase16_readonly_smoke_path)
        acceptance_smoke_sha_after = _sha256_file(self.phase16_acceptance_smoke_path)
        acceptance_sha_after = _sha256_file(self.phase16_acceptance_path)

        broker_rows = smoke.get("broker_summary") if isinstance(smoke.get("broker_summary"), list) else []
        broker_names = tuple(
            sorted(
                str(row.get("broker"))
                for row in broker_rows
                if isinstance(row, dict) and row.get("broker")
            )
        )
        reconciled = all(
            isinstance(row, dict)
            and row.get("state") == "AVAILABLE"
            and row.get("reconciled") is True
            for row in broker_rows
        )

        checks.update(
            {
                "readonly_smoke_contract_exact": smoke.get("contract_version")
                == PHASE16_OPERATIONAL_SMOKE_CONTRACT_VERSION,
                "readonly_smoke_pass": smoke.get("pass") is True,
                "readonly_refresh_explicit": smoke.get("broker_refresh_requested") is True,
                "provider_adapter_initializations_exact_two": smoke.get("provider_factory_calls")
                == 2,
                "required_broker_rows_exact": broker_names
                == tuple(sorted(PHASE17_REQUIRED_BROKERS)),
                "both_brokers_reconciled": len(broker_rows) == 2 and reconciled,
                "provider_mutation_endpoints_unused": smoke.get(
                    "provider_mutation_endpoint_invocations"
                )
                == 0,
                "provider_writes_zero": smoke.get("provider_writes") == 0,
                "live_writes_zero": smoke.get("live_writes") == 0,
                "phase16_acceptance_smoke_unchanged": acceptance_smoke_sha_after
                == acceptance_smoke_sha_before,
                "phase16_acceptance_file_unchanged": acceptance_sha_after
                == acceptance_sha_before,
                "phase16_acceptance_smoke_still_hash_bound": acceptance.get(
                    "operational_smoke_sha256"
                )
                == acceptance_smoke_sha_after,
                "provider_mutation_policy_disabled": PHASE17_PROVIDER_MUTATIONS_ALLOWED is False,
                "live_promotion_disabled": PHASE17_LIVE_EXECUTION_PROMOTION_ALLOWED is False,
                "automatic_failover_disabled": PHASE17_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED
                is False,
            }
        )
        failed = tuple(sorted(name for name, value in checks.items() if not value))
        if failed:
            raise Phase17ProviderReadinessError(
                "Phase 17 provider-readonly readiness failed: " + ", ".join(failed)
            )

        source_payload = {
            "contract_version": PHASE17_READINESS_CONTRACT_VERSION,
            "policy_fingerprint": phase17_policy_fingerprint(),
            "phase16_acceptance_sha256": acceptance_sha_after,
            "phase16_acceptance_smoke_sha256": acceptance_smoke_sha_after,
            "phase16_independent_validation_sha256": independent_sha,
            "phase16_provider_readonly_smoke_sha256": readonly_smoke_sha,
            "broker_summary": broker_rows,
            "checks": checks,
        }
        report: dict[str, object] = {
            "contract_version": PHASE17_READINESS_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "phase17_policy_fingerprint": phase17_policy_fingerprint(),
            "source_fingerprint": _stable_hash(source_payload),
            "phase16_acceptance_sha256": acceptance_sha_after,
            "phase16_acceptance_smoke_sha256": acceptance_smoke_sha_after,
            "phase16_independent_validation_sha256": independent_sha,
            "phase16_provider_readonly_smoke_sha256": readonly_smoke_sha,
            "provider_adapter_initializations": int(smoke.get("provider_factory_calls", 0)),
            "provider_mutation_endpoint_invocations": 0,
            "provider_writes": 0,
            "live_writes": 0,
            "broker_summary": broker_rows,
            "checks": checks,
            "failed_checks": failed,
            "final_disposition": {
                "phase17_provider_readonly_readiness_accepted": True,
                "webull_sandbox_read_access_verified": "webull" in broker_names,
                "alpaca_paper_read_access_verified": "alpaca" in broker_names,
                "both_brokers_reconciled": True,
                "flat_brokers_required_for_readiness": False,
                "provider_mutation_authorized": False,
                "live_execution_promoted": False,
                "automatic_cross_broker_failover_allowed": False,
                "next_checkpoint": "PAPER_PROVIDER_MUTATION_REQUIRES_EXPLICIT_USER_AUTHORIZATION",
            },
            "pass": True,
        }
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self.report_path,
            json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        )
        report["report_path"] = str(self.report_path.resolve())
        return report
