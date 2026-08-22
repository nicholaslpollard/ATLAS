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


class BrokerOrderNotFound(BrokerAdapterError):
    """Definitive provider response that the requested client order id is absent."""


class BrokerSubmissionDisabled(BrokerAdapterError):
    pass


class BrokerSubmissionUncertain(BrokerAdapterError):
    """Submission may have reached the broker; callers must reconcile, never retry blindly."""


class BrokerMutationUncertain(BrokerAdapterError):
    """A non-submission broker mutation may have taken effect.

    This includes cancellation/close requests that encounter a transport exception or an
    acknowledgement followed by failed reconciliation. Callers must stop, mark provider
    state uncertain, and reconcile before considering any further mutation. Blind retry is
    forbidden because the original request may already have changed broker state.
    """


class BrokerAdapter(ABC):
    """Narrow execution adapter used by the Phase 15 orchestration layer.

    Implementations normalize provider-specific account/order semantics into immutable
    ATLAS schemas. They must never choose a different broker, alter an order plan, or
    silently retry a submission/mutation whose provider outcome may be uncertain.
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
        """Return exact order or raise BrokerOrderNotFound on a definitive miss."""
        raise NotImplementedError

    @abstractmethod
    def cancel(self, client_order_id: str) -> BrokerOrderSnapshot:
        """Cancel exact order or raise BrokerMutationUncertain when outcome is ambiguous."""
        raise NotImplementedError
