from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from packages.control_plane.cleanup_policy import (
    PHASE16_CANCEL_PROVIDER_WRITES_ENABLED,
    PHASE16_FLATTEN_CLOSE_ORDER_METHOD_ACCEPTED,
    PHASE16_FLATTEN_PROVIDER_WRITES_ENABLED,
    cleanup_policy_fingerprint,
    validate_cleanup_policy,
)
from packages.control_plane.http_server import (
    CONTROL_PLANE_HTTP_CONTRACT_VERSION,
    MAX_STATIC_ASSET_BYTES,
)
from packages.control_plane.phase16_policy import (
    PHASE16_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED,
    PHASE16_BROWSER_CAN_CREATE_EXECUTION_AUTHORITY,
    PHASE16_CREDENTIAL_VALUES_EXPOSED_TO_BROWSER,
    PHASE16_DEFAULT_BIND_HOST,
    PHASE16_LIVE_EXECUTION_PROMOTION_ALLOWED,
    PHASE16_REMOTE_BIND_ENABLED_BY_DEFAULT,
    phase16_policy_fingerprint,
    validate_phase16_policy,
)
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings


PHASE16_INDEPENDENT_VALIDATION_CONTRACT_VERSION = (
    "phase16-validation-v1-independent-source-authority-route-recovery-zero-provider-write"
)
PHASE16_ACCEPTED_POLICY_FINGERPRINT = (
    "dbce22bdfd4ac6dfb1a476d3fd5d4717918ca2163f93c9245135892242020b55"
)
PHASE16_ACCEPTED_CLEANUP_POLICY_FINGERPRINT = (
    "ab0dd8a4fe0d89032a04cf4dd7e46ddb56b4086e75741b0f7ef9cc09365d36a1"
)
PHASE16_ACCEPTED_HTTP_CONTRACT_VERSION = (
    "control-plane-http-v7-loopback-browser-cleanup-review-abandon-no-provider-writes"
)


class Phase16IndependentValidationError(RuntimeError):
    pass


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return _sha256_bytes(raw)


class Phase16IndependentValidator:
    """Independently inspect the Phase 16 authority surface without provider calls.

    The validator intentionally reads source files instead of exercising provider adapters.
    It proves the accepted browser/server/cleanup boundary and records immutable hashes of
    the reviewed implementation. Persisting the validation report is the only write.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.project_root = Path(settings.project_root).resolve()
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "control_plane" / "phase16" / "v1"
        self.report_path = self.root / "phase16_independent_validation.json"

    def _source(self, relative: str) -> tuple[Path, str]:
        path = (self.project_root / relative).resolve()
        try:
            path.relative_to(self.project_root)
        except ValueError as exc:
            raise Phase16IndependentValidationError("validation source escaped project root") from exc
        if not path.is_file():
            raise Phase16IndependentValidationError(f"required Phase 16 source is missing: {relative}")
        return path, path.read_text(encoding="utf-8")

    def run(self, *, write_report: bool = True) -> dict[str, object]:
        validate_phase16_policy()
        validate_cleanup_policy()

        source_names = (
            "packages/control_plane/action_ledger.py",
            "packages/control_plane/http_server.py",
            "packages/control_plane/cleanup_policy.py",
            "packages/control_plane/cleanup_plan_ledger.py",
            "packages/control_plane/cleanup_planner.py",
            "packages/control_plane/cleanup_processor.py",
            "packages/brokers/base.py",
            "packages/brokers/webull/broker.py",
            "packages/brokers/alpaca/broker.py",
            "apps/web/index.html",
            "apps/web/app.js",
            "apps/web/app.css",
        )
        sources: dict[str, str] = {}
        source_hashes: dict[str, str] = {}
        source_sizes: dict[str, int] = {}
        for name in source_names:
            path, text = self._source(name)
            sources[name] = text
            source_hashes[name] = _sha256_file(path)
            source_sizes[name] = path.stat().st_size

        http = sources["packages/control_plane/http_server.py"]
        processor = sources["packages/control_plane/cleanup_processor.py"]
        ledger = sources["packages/control_plane/action_ledger.py"]
        base = sources["packages/brokers/base.py"]
        webull = sources["packages/brokers/webull/broker.py"]
        alpaca = sources["packages/brokers/alpaca/broker.py"]
        html = sources["apps/web/index.html"]
        js = sources["apps/web/app.js"]
        css = sources["apps/web/app.css"]
        browser = html + "\n" + js + "\n" + css

        checks = {
            "phase16_policy_fingerprint_exact": phase16_policy_fingerprint()
            == PHASE16_ACCEPTED_POLICY_FINGERPRINT,
            "cleanup_policy_fingerprint_exact": cleanup_policy_fingerprint()
            == PHASE16_ACCEPTED_CLEANUP_POLICY_FINGERPRINT,
            "http_contract_exact": CONTROL_PLANE_HTTP_CONTRACT_VERSION
            == PHASE16_ACCEPTED_HTTP_CONTRACT_VERSION,
            "loopback_default_exact": PHASE16_DEFAULT_BIND_HOST == "127.0.0.1",
            "remote_bind_disabled": PHASE16_REMOTE_BIND_ENABLED_BY_DEFAULT is False,
            "live_execution_not_promoted": PHASE16_LIVE_EXECUTION_PROMOTION_ALLOWED is False,
            "automatic_failover_disabled": PHASE16_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED is False,
            "browser_not_execution_authority": PHASE16_BROWSER_CAN_CREATE_EXECUTION_AUTHORITY is False,
            "credential_values_not_browser_authority": PHASE16_CREDENTIAL_VALUES_EXPOSED_TO_BROWSER is False,
            "cancel_provider_writes_disabled": PHASE16_CANCEL_PROVIDER_WRITES_ENABLED is False,
            "flatten_provider_writes_disabled": PHASE16_FLATTEN_PROVIDER_WRITES_ENABLED is False,
            "flatten_close_method_unaccepted": PHASE16_FLATTEN_CLOSE_ORDER_METHOD_ACCEPTED is False,
            "generic_process_broker_switch_only": (
                "PROCESSOR_NOT_AVAILABLE_FOR_ACTION" in http
                and "ControlPlaneActionKind.BROKER_SWITCH" in http
            ),
            "cleanup_process_route_absent_server": "/cleanup-plan/process" not in http,
            "cleanup_process_route_absent_browser": "/cleanup-plan/process" not in browser,
            "cleanup_review_routes_present": all(
                token in http
                for token in (
                    "/cleanup-plan",
                    "/cleanup-plan/confirm",
                    "/cleanup-plan/close-review",
                    "/abandon",
                )
            ),
            "browser_exact_plan_review_present": all(
                token in js
                for token in (
                    "cleanup_plan_fingerprint",
                    "Confirm exact resources — no broker changes",
                    "/cleanup-plan/confirm",
                    "/cleanup-plan/close-review",
                    "/abandon",
                )
            ),
            "browser_fail_closed_write_assertions_present": all(
                token in js
                for token in (
                    "provider_write_authorized !== false",
                    "provider_write_endpoints_present !== false",
                    "provider_write_attempted !== false",
                    "provider_write_endpoint_invoked !== false",
                )
            ),
            "cleanup_processor_has_no_cancel_call": ".cancel(" not in processor,
            "cleanup_processor_has_no_position_close_call": all(
                token not in processor
                for token in ("close_position(", "close_all_positions(", "liquidate(")
            ),
            "cleanup_processor_refuses_write_promotion": (
                "cancel writes cannot be enabled under cleanup processor v1" in processor
                and "flatten writes cannot be enabled under cleanup processor v1" in processor
            ),
            "prewrite_abandon_present": "def abandon(" in ledger
            and "ACTION_ABANDONED_BY_USER" in ledger,
            "prewrite_abandon_forbids_provider_activity": (
                "record.provider_write_attempted" in ledger
                and "record.provider_write_uncertain" in ledger
                and "cannot be abandoned after provider-write activity" in ledger
            ),
            "mutation_uncertainty_contract_present": "class BrokerMutationUncertain" in base,
            "webull_cancel_uncertainty_present": "BrokerMutationUncertain" in webull
            and "reconcile exact client order id before any retry" in webull,
            "alpaca_cancel_uncertainty_present": "BrokerMutationUncertain" in alpaca
            and "reconcile exact client order id before any retry" in alpaca,
            "browser_contains_no_credential_env_names": all(
                token not in browser
                for token in (
                    "WEBULL_APP_KEY",
                    "WEBULL_APP_SECRET",
                    "WEBULL_ACCOUNT_ID",
                    "ALPACA_PAPER_API_KEY",
                    "ALPACA_PAPER_API_SECRET",
                )
            ),
            "static_assets_bounded": all(
                0 < source_sizes[name] <= MAX_STATIC_ASSET_BYTES
                for name in ("apps/web/index.html", "apps/web/app.js", "apps/web/app.css")
            ),
        }
        failed = tuple(sorted(name for name, value in checks.items() if not value))
        implementation_payload = {
            "contract_version": PHASE16_INDEPENDENT_VALIDATION_CONTRACT_VERSION,
            "phase16_policy_fingerprint": phase16_policy_fingerprint(),
            "cleanup_policy_fingerprint": cleanup_policy_fingerprint(),
            "http_contract_version": CONTROL_PLANE_HTTP_CONTRACT_VERSION,
            "source_hashes": source_hashes,
        }
        report: dict[str, object] = {
            "contract_version": PHASE16_INDEPENDENT_VALIDATION_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "phase16_policy_fingerprint": phase16_policy_fingerprint(),
            "cleanup_policy_fingerprint": cleanup_policy_fingerprint(),
            "http_contract_version": CONTROL_PLANE_HTTP_CONTRACT_VERSION,
            "implementation_fingerprint": _stable_hash(implementation_payload),
            "source_hashes": source_hashes,
            "source_sizes": source_sizes,
            "provider_calls": 0,
            "provider_writes": 0,
            "live_writes": 0,
            "checks": checks,
            "failed_checks": failed,
            "pass": not failed,
        }
        if failed:
            raise Phase16IndependentValidationError(
                "Phase 16 independent authority validation failed: " + ", ".join(failed)
            )
        if write_report:
            self.root.mkdir(parents=True, exist_ok=True)
            atomic_write_text(
                self.report_path,
                json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
            )
            report["report_path"] = str(self.report_path.resolve())
        return report
