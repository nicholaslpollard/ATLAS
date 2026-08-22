from __future__ import annotations

import json
import threading
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from packages.brokers.base import BrokerAdapter
from packages.control_plane.http_server import create_status_server
from packages.control_plane.status import Phase16StatusService
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.schemas.execution import BrokerName


PHASE16_OPERATIONAL_SMOKE_CONTRACT_VERSION = (
    "phase16-smoke-v1-loopback-no-provider-default-explicit-readonly-broker-refresh"
)


class Phase16OperationalSmokeError(RuntimeError):
    pass


BrokerFactory = Callable[[BrokerName], BrokerAdapter]


class Phase16OperationalSmoke:
    """Exercise the localhost HTTP control plane without provider mutation.

    By default, a broker factory that raises on construction is installed so an accidental
    provider read causes the smoke to fail immediately. Read-only broker reconciliation is
    available only when the caller explicitly requests it.

    The accepted zero-provider smoke artifact and the optional provider-readonly artifact
    are deliberately stored at different paths. A later read-only reconciliation must never
    overwrite the evidence hash-bound into Phase 16 final acceptance.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "control_plane" / "phase16" / "v1"
        self.report_path = self.root / "phase16_operational_smoke.json"
        self.readonly_report_path = self.root / "phase16_provider_readonly_smoke.json"

    def output_path(self, *, refresh_brokers: bool) -> Path:
        return self.readonly_report_path if refresh_brokers else self.report_path

    @staticmethod
    def _get_json(base: str, path: str) -> dict[str, object]:
        request = urllib.request.Request(
            base + path,
            method="GET",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise Phase16OperationalSmokeError(f"smoke endpoint returned non-object JSON: {path}")
        return payload

    def run(
        self,
        *,
        refresh_brokers: bool = False,
        broker_factory: BrokerFactory | None = None,
        write_report: bool = True,
    ) -> dict[str, object]:
        provider_factory_calls = 0

        def forbidden_factory(broker: BrokerName) -> BrokerAdapter:
            nonlocal provider_factory_calls
            provider_factory_calls += 1
            raise Phase16OperationalSmokeError(
                f"provider adapter initialized during no-provider smoke: {broker.value}"
            )

        if refresh_brokers:
            service = Phase16StatusService(
                self.settings,
                broker_factory=broker_factory,
            )
        else:
            service = Phase16StatusService(
                self.settings,
                broker_factory=forbidden_factory,
            )

        acceptance = service.phase15_acceptance()
        if not acceptance.accepted:
            raise Phase16OperationalSmokeError(
                f"accepted Phase 15 artifact is required: {acceptance.error_code}"
            )

        server = create_status_server(
            service=service,
            host="127.0.0.1",
            port=0,
        )
        thread = threading.Thread(
            target=server.serve_forever,
            kwargs={"poll_interval": 0.01},
            daemon=True,
        )
        thread.start()
        host, port = server.server_address[:2]
        base = f"http://{host}:{port}"
        broker_payload: dict[str, object] | None = None
        try:
            health = self._get_json(base, "/healthz")
            system = self._get_json(base, "/api/v1/status/system")
            actions = self._get_json(base, "/api/v1/actions")
            session = self._get_json(base, "/api/v1/session")
            if refresh_brokers:
                broker_payload = self._get_json(base, "/api/v1/status/full?refresh=1")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=10)

        checks: dict[str, bool] = {
            "loopback_bind_exact": str(host) == "127.0.0.1",
            "ephemeral_port_allocated": int(port) > 0,
            "phase15_accepted": health.get("phase15_accepted") is True,
            "runtime_state_valid": health.get("runtime_state_valid") is True,
            "action_ledger_valid": health.get("action_ledger_valid") is True,
            "provider_write_uncertain_false": health.get("provider_write_uncertain") is False,
            "provider_write_endpoints_absent": health.get("provider_write_endpoints_present") is False,
            "live_execution_not_promoted": health.get("live_execution_promoted") is False,
            "system_payload_phase15_accepted": (
                isinstance(system.get("phase15"), dict)
                and system["phase15"].get("accepted") is True
            ),
            "actions_payload_list": isinstance(actions.get("actions"), list),
            "session_has_csrf_token": bool(session.get("csrf_token")),
            "session_has_header_name": bool(session.get("header_name")),
            "no_provider_factory_calls_by_default": refresh_brokers or provider_factory_calls == 0,
        }

        broker_summary: list[dict[str, object]] = []
        if refresh_brokers:
            rows = broker_payload.get("brokers") if isinstance(broker_payload, dict) else None
            if not isinstance(rows, list):
                checks["readonly_broker_rows_present"] = False
            else:
                checks["readonly_broker_rows_present"] = len(rows) == 2
                checks["readonly_brokers_reconciled"] = all(
                    isinstance(row, dict)
                    and row.get("state") == "AVAILABLE"
                    and row.get("reconciled") is True
                    for row in rows
                )
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    account = row.get("account") if isinstance(row.get("account"), dict) else {}
                    broker_summary.append(
                        {
                            "broker": row.get("broker"),
                            "state": row.get("state"),
                            "reconciled": row.get("reconciled"),
                            "safe_to_switch_broker": row.get("safe_to_switch_broker"),
                            "account_ref": account.get("account_ref"),
                            "open_order_count": len(row.get("open_orders") or []),
                            "position_count": len(row.get("positions") or []),
                            "error_code": row.get("error_code"),
                        }
                    )

        failed = tuple(sorted(name for name, value in checks.items() if not value))
        report: dict[str, object] = {
            "contract_version": PHASE16_OPERATIONAL_SMOKE_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "bind_host": str(host),
            "port_mode": "EPHEMERAL",
            "broker_refresh_requested": bool(refresh_brokers),
            "provider_factory_calls": provider_factory_calls,
            "provider_mutation_endpoint_invocations": 0,
            "provider_writes": 0,
            "live_writes": 0,
            "broker_summary": broker_summary,
            "checks": checks,
            "failed_checks": failed,
            "pass": not failed,
        }
        if failed:
            raise Phase16OperationalSmokeError(
                "Phase 16 operational smoke failed: " + ", ".join(failed)
            )
        if write_report:
            output_path = self.output_path(refresh_brokers=refresh_brokers)
            self.root.mkdir(parents=True, exist_ok=True)
            atomic_write_text(
                output_path,
                json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
            )
            report["report_path"] = str(output_path.resolve())
        return report
