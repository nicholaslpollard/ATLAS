from __future__ import annotations

from abc import ABC, abstractmethod

from packages.schemas.execution import (
    BrokerAccountSnapshot,
    BrokerName,
    BrokerOrderPlan,
    BrokerOrderSnapshot,
    BrokerPositionSnapshot,
    BrokerPreflightResult,
    ExecutionEnvironment,
)


class BrokerAdapterError(RuntimeError):
    pass


class BrokerSubmissionDisabled(BrokerAdapterError):
    pass


class BrokerAdapter(ABC):
    """Narrow execution adapter used by the Phase 15 orchestration layer.

    Implementations normalize provider-specific account/order semantics into immutable
    ATLAS schemas. They must never choose a different broker, alter an order plan, or
    silently retry a submission with a new client order id.
    """

    broker: BrokerName
    environment: ExecutionEnvironment

    @abstractmethod
    def account(self) -> BrokerAccountSnapshot:
        raise NotImplementedError

    @abstractmethod
    def positions(self) -> tuple[BrokerPositionSnapshot, ...]:
        raise NotImplementedError

    @abstractmethod
    def open_orders(self) -> tuple[BrokerOrderSnapshot, ...]:
        raise NotImplementedError

    @abstractmethod
    def preview(self, plan: BrokerOrderPlan) -> BrokerPreflightResult:
        raise NotImplementedError

    @abstractmethod
    def submit(self, plan: BrokerOrderPlan) -> BrokerOrderSnapshot:
        raise NotImplementedError

    @abstractmethod
    def order(self, client_order_id: str) -> BrokerOrderSnapshot:
        raise NotImplementedError

    @abstractmethod
    def cancel(self, client_order_id: str) -> BrokerOrderSnapshot:
        raise NotImplementedError
