from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Mapping

from packages.brokers.alpaca import AlpacaPaperBroker
from packages.brokers.base import BrokerAdapter, BrokerAdapterError
from packages.brokers.webull import WebullSandboxBroker
from packages.core.settings import AtlasSettings
from packages.execution.phase15_closeout import PHASE15_CLOSEOUT_CONTRACT_VERSION
from packages.execution.phase15_foundation import (
    PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT,
)
from packages.execution.phase15_policy import phase15_policy_fingerprint
from packages.schemas.control_plane_status import (
    BrokerReadStatus,
    ControlPlaneExecutionStatus,
    ControlPlaneHealthState,
    ControlPlaneReadState,
    ControlPlaneSystemStatus,
    CredentialPresence,
    Phase15AcceptanceStatus,
    PublicBrokerAccountStatus,
    PublicBrokerOrderStatus,
    PublicBrokerPositionStatus,
)
from packages.schemas.execution import BrokerName, ExecutionEnvironment

from .phase16_policy import (
    PHASE16_ACCEPTED_PHASE15_MERGE_SHA,
    PHASE16_ACCEPTED_PHASE15_POLICY_FINGERPRINT,
    PHASE16_ALLOWED_EXECUTION_ENVIRONMENTS,
    PHASE16_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED,
    PHASE16_BROWSER_CAN_CREATE_EXECUTION_AUTHORITY,
    PHASE16_CREDENTIAL_VALUES_EXPOSED_TO_BROWSER,
    PHASE16_DEFAULT_BIND_HOST,
    PHASE16_LIVE_EXECUTION_PROMOTION_ALLOWED,
    PHASE16_PRIMARY_BROKER,
    PHASE16_SECONDARY_BROKER,
    phase16_policy_fingerprint,
    validate_phase16_policy,
)


BrokerFactory = Callable[[BrokerName], BrokerAdapter]


class ControlPlaneStatusError(RuntimeError):
    pass


def _default_broker_factory(broker: BrokerName) -> BrokerAdapter:
    if broker == BrokerName.WEBULL:
        return WebullSandboxBroker()
    if broker == BrokerName.ALPACA:
        return AlpacaPaperBroker()
    raise ControlPlaneStatusError(f"unsupported provider broker: {broker}")


def _presence(env: Mapping[str, str], required: tuple[str, ...], optional: tuple[str, ...] = ()) -> CredentialPresence:
    required_present = {name: bool(str(env.get(name, "") or "").strip()) for name in required}
    optional_present = {name: bool(str(env.get(name, "") or "").strip()) for name in optional}
    return CredentialPresence(
        required_names=required,
        optional_names=optional,
        required_present=required_present,
        optional_present=optional_present,
        ready=all(required_present.values()),
    )


def _account_ref(account_id: str) -> str:
    return hashlib.sha256(account_id.encode("utf-8")).hexdigest()[:16]


class Phase16StatusService:
    """Read-only browser status service.

    Provider adapters are never initialized during construction or ordinary status reads.
    `broker_status(..., refresh=True)` is the only method that performs provider network
    reads, and it calls only account/positions/open_orders on the adapter.
    """

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        env: Mapping[str, str] | None = None,
        broker_factory: BrokerFactory | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self._env = env if env is not None else os.environ
        self._broker_factory = broker_factory or _default_broker_factory
        self._clock = clock or (lambda: datetime.now(UTC))
        derived = settings.resolved_path(settings.data.paths.derived)
        self.phase15_root = derived / "execution" / "phase15" / "v1"
        self.phase15_acceptance_path = self.phase15_root / "phase15_final_acceptance.json"

    def credentials(self, broker: BrokerName) -> CredentialPresence:
        if broker == BrokerName.WEBULL:
            return _presence(
                self._env,
                ("WEBULL_APP_KEY", "WEBULL_APP_SECRET"),
                ("WEBULL_ACCOUNT_ID",),
            )
        if broker == BrokerName.ALPACA:
            return _presence(
                self._env,
                ("ALPACA_PAPER_API_KEY", "ALPACA_PAPER_API_SECRET"),
            )
        raise ControlPlaneStatusError(f"unsupported provider broker: {broker}")

    def phase15_acceptance(self) -> Phase15AcceptanceStatus:
        path = self.phase15_acceptance_path
        if not path.is_file():
            return Phase15AcceptanceStatus(
                artifact_present=False,
                accepted=False,
                error_code="PHASE15_ACCEPTANCE_NOT_PRESENT",
            )
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("acceptance root is not an object")
        except (OSError, json.JSONDecodeError, ValueError):
            return Phase15AcceptanceStatus(
                artifact_present=True,
                accepted=False,
                error_code="PHASE15_ACCEPTANCE_INVALID",
            )

        final = raw.get("final_disposition") if isinstance(raw.get("final_disposition"), dict) else {}
        checks = (
            raw.get("contract_version") == PHASE15_CLOSEOUT_CONTRACT_VERSION,
            raw.get("pass") is True,
            raw.get("phase15_policy_fingerprint") == PHASE16_ACCEPTED_PHASE15_POLICY_FINGERPRINT,
            raw.get("phase15_policy_fingerprint") == phase15_policy_fingerprint(),
            raw.get("cumulative_foundation_fingerprint")
            == PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT,
            final.get("phase15_accepted") is True,
            final.get("live_execution_promoted") is False,
            final.get("automatic_cross_broker_failover_allowed") is False,
        )
        accepted = all(checks)
        return Phase15AcceptanceStatus(
            artifact_present=True,
            accepted=accepted,
            as_of_date=str(raw.get("as_of_date")) if raw.get("as_of_date") else None,
            policy_fingerprint=str(raw.get("phase15_policy_fingerprint"))
            if raw.get("phase15_policy_fingerprint")
            else None,
            cumulative_foundation_fingerprint=str(raw.get("cumulative_foundation_fingerprint"))
            if raw.get("cumulative_foundation_fingerprint")
            else None,
            execution_case_count=int(raw.get("execution_case_count"))
            if isinstance(raw.get("execution_case_count"), int)
            else None,
            actual_broker_execution_exercised=bool(
                final.get("actual_broker_execution_exercised_in_acceptance")
            )
            if "actual_broker_execution_exercised_in_acceptance" in final
            else None,
            live_execution_promoted=bool(final.get("live_execution_promoted"))
            if "live_execution_promoted" in final
            else None,
            error_code=None if accepted else "PHASE15_ACCEPTANCE_MISMATCH",
        )

    def system_status(self) -> ControlPlaneSystemStatus:
        validate_phase16_policy()
        phase15 = self.phase15_acceptance()
        health = ControlPlaneHealthState.HEALTHY if phase15.accepted else ControlPlaneHealthState.BLOCKED
        return ControlPlaneSystemStatus(
            generated_at_utc=self._clock(),
            health=health,
            phase16_policy_fingerprint=phase16_policy_fingerprint(),
            accepted_phase15_merge_sha=PHASE16_ACCEPTED_PHASE15_MERGE_SHA,
            accepted_phase15_policy_fingerprint=PHASE16_ACCEPTED_PHASE15_POLICY_FINGERPRINT,
            primary_broker=PHASE16_PRIMARY_BROKER,
            secondary_broker=PHASE16_SECONDARY_BROKER,
            selected_broker=None,
            allowed_execution_environments=PHASE16_ALLOWED_EXECUTION_ENVIRONMENTS,
            live_execution_promoted=PHASE16_LIVE_EXECUTION_PROMOTION_ALLOWED,
            automatic_cross_broker_failover_allowed=PHASE16_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED,
            browser_is_execution_authority=PHASE16_BROWSER_CAN_CREATE_EXECUTION_AUTHORITY,
            credentials_exposed=PHASE16_CREDENTIAL_VALUES_EXPOSED_TO_BROWSER,
            write_actions_enabled=False,
            bind_host_default=PHASE16_DEFAULT_BIND_HOST,
            phase15=phase15,
        )

    def execution_status(self) -> ControlPlaneExecutionStatus:
        phase15 = self.phase15_acceptance()
        return ControlPlaneExecutionStatus(
            phase15_accepted=phase15.accepted,
            phase15_as_of_date=phase15.as_of_date,
            phase15_execution_case_count=phase15.execution_case_count,
        )

    def broker_status(self, broker: BrokerName | str, *, refresh: bool = False) -> BrokerReadStatus:
        broker_name = BrokerName(broker)
        if broker_name not in {BrokerName.WEBULL, BrokerName.ALPACA}:
            raise ControlPlaneStatusError("provider status supports only Webull and Alpaca")
        credentials = self.credentials(broker_name)
        if not refresh:
            return BrokerReadStatus(
                broker=broker_name,
                environment=ExecutionEnvironment.PAPER,
                state=ControlPlaneReadState.UNPOLLED,
                credentials=credentials,
            )
        if not credentials.ready:
            return BrokerReadStatus(
                broker=broker_name,
                environment=ExecutionEnvironment.PAPER,
                state=ControlPlaneReadState.UNAVAILABLE,
                credentials=credentials,
                polled_at_utc=self._clock(),
                error_code="CREDENTIALS_UNAVAILABLE",
            )

        polled_at = self._clock()
        try:
            adapter = self._broker_factory(broker_name)
            if adapter.broker != broker_name or adapter.environment != ExecutionEnvironment.PAPER:
                raise ControlPlaneStatusError("broker adapter identity/environment mismatch")
            account = adapter.account()
            positions = adapter.positions()
            orders = adapter.open_orders()
        except (BrokerAdapterError, ControlPlaneStatusError, OSError, ValueError, RuntimeError) as exc:
            return BrokerReadStatus(
                broker=broker_name,
                environment=ExecutionEnvironment.PAPER,
                state=ControlPlaneReadState.ERROR,
                credentials=credentials,
                polled_at_utc=polled_at,
                error_code=f"BROKER_READ_FAILED_{type(exc).__name__.upper()}",
            )

        if account.broker != broker_name or account.environment != ExecutionEnvironment.PAPER:
            return BrokerReadStatus(
                broker=broker_name,
                environment=ExecutionEnvironment.PAPER,
                state=ControlPlaneReadState.ERROR,
                credentials=credentials,
                polled_at_utc=polled_at,
                error_code="BROKER_ACCOUNT_IDENTITY_MISMATCH",
            )
        account_id = account.account_id
        if any(row.broker != broker_name or row.account_id != account_id for row in positions):
            return BrokerReadStatus(
                broker=broker_name,
                environment=ExecutionEnvironment.PAPER,
                state=ControlPlaneReadState.ERROR,
                credentials=credentials,
                polled_at_utc=polled_at,
                error_code="BROKER_POSITION_IDENTITY_MISMATCH",
            )
        if any(row.broker != broker_name or row.account_id != account_id for row in orders):
            return BrokerReadStatus(
                broker=broker_name,
                environment=ExecutionEnvironment.PAPER,
                state=ControlPlaneReadState.ERROR,
                credentials=credentials,
                polled_at_utc=polled_at,
                error_code="BROKER_ORDER_IDENTITY_MISMATCH",
            )

        public_account = PublicBrokerAccountStatus(
            account_ref=_account_ref(account_id),
            as_of_utc=account.as_of_utc,
            equity=account.equity,
            cash=account.cash,
            buying_power=account.buying_power,
            gross_market_value=account.gross_market_value,
            trading_blocked=account.trading_blocked,
            shorting_enabled=account.shorting_enabled,
        )
        public_positions = tuple(
            PublicBrokerPositionStatus(
                ticker=row.ticker,
                quantity=row.quantity,
                market_value=row.market_value,
                average_entry_price=row.average_entry_price,
                as_of_utc=row.as_of_utc,
            )
            for row in positions
        )
        public_orders = tuple(
            PublicBrokerOrderStatus(
                client_order_id=row.client_order_id,
                ticker=row.ticker,
                side=row.side,
                status=row.status,
                requested_quantity=row.requested_quantity,
                filled_quantity=row.filled_quantity,
                average_fill_price=row.average_fill_price,
                submitted_at_utc=row.submitted_at_utc,
                updated_at_utc=row.updated_at_utc,
            )
            for row in orders
        )
        return BrokerReadStatus(
            broker=broker_name,
            environment=ExecutionEnvironment.PAPER,
            state=ControlPlaneReadState.AVAILABLE,
            credentials=credentials,
            polled_at_utc=polled_at,
            account=public_account,
            positions=public_positions,
            open_orders=public_orders,
        )

    def brokers_status(self, *, refresh: bool = False) -> tuple[BrokerReadStatus, BrokerReadStatus]:
        return (
            self.broker_status(BrokerName.WEBULL, refresh=refresh),
            self.broker_status(BrokerName.ALPACA, refresh=refresh),
        )

    def full_status(self, *, refresh_brokers: bool = False) -> dict[str, object]:
        system = self.system_status()
        execution = self.execution_status()
        brokers = self.brokers_status(refresh=refresh_brokers)
        return {
            "system": system.model_dump(mode="json"),
            "execution": execution.model_dump(mode="json"),
            "brokers": [row.model_dump(mode="json") for row in brokers],
        }
