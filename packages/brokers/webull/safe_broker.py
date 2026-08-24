from __future__ import annotations

import logging
import time
from typing import Any

from packages.brokers.base import (
    BrokerAdapterError,
    BrokerMutationUncertain,
    BrokerOrderNotFound,
)
from packages.schemas.execution import BrokerOrderStatus

from .broker import (
    WebullSandboxBroker as _WebullSandboxBroker,
    _json_response,
    _normalize_order,
    _orders_from_payload,
)


_SENSITIVE_WEBULL_LOGGERS = (
    "webull.core.client",
    "webull.core.http.initializer.client_initializer",
)
_ORDER_ABSENT_MARKER = "order not present"
_CANCEL_RECONCILIATION_DELAYS_SECONDS = (0.0, 0.25, 0.5, 1.0, 1.5, 2.0)


def harden_webull_sdk_logging() -> None:
    """Disable SDK loggers that can emit signed request/account metadata.

    ATLAS emits its own sanitized provider errors. The upstream Webull SDK can log
    complete request objects on provider errors, including account identifiers,
    app-key metadata, nonces and request signatures. Those diagnostics are not
    appropriate for operator-facing ATLAS logs.
    """

    for name in _SENSITIVE_WEBULL_LOGGERS:
        logging.getLogger(name).disabled = True


def _exception_chain_contains_explicit_order_absence(exc: BaseException) -> bool:
    """Return True only for Webull's explicit order-absence business response.

    The Webull Python SDK raises before returning its HTTP 417 response object for
    `OPENAPI_PARAM_ERR: Parameter error, Order not present.`. ATLAS must normalize
    that one condition to BrokerOrderNotFound so deterministic client-order-id
    absence can be proven. Other HTTP 417 / OPENAPI_PARAM_ERR responses remain
    ordinary provider failures and continue to fail closed.
    """

    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if _ORDER_ABSENT_MARKER in str(current).casefold():
            return True
        current = current.__cause__ or current.__context__
    return False


class WebullSandboxBroker(_WebullSandboxBroker):
    """Hardened ATLAS Webull sandbox adapter.

    This wrapper preserves the accepted broker implementation while normalizing
    Webull's explicit order-not-present response, suppressing unsafe SDK log dumps,
    and handling the provider's short post-cancel read-consistency window with
    bounded read-only reconciliation. Mutation, retry, failover, and authority
    semantics remain unchanged: a cancellation request is sent at most once.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        harden_webull_sdk_logging()
        super().__init__(*args, **kwargs)

    def order(self, client_order_id: str):
        try:
            return super().order(client_order_id)
        except BrokerAdapterError as exc:
            if _exception_chain_contains_explicit_order_absence(exc):
                raise BrokerOrderNotFound(client_order_id) from None
            raise

    def _history_order(self, client_order_id: str):
        """Return an exact history order when available, otherwise None.

        Order History is used only as a read-only fallback after a successful cancel
        acknowledgement. Any history transport/shape error remains non-authoritative;
        the bounded reconciliation loop continues and ultimately fails closed if no
        exact CANCELLED state can be proven.
        """

        try:
            response = self._client.order_v3.get_order_history(self.account_id)
        except Exception:
            return None
        if int(getattr(response, "status_code", 0)) != 200:
            return None
        try:
            payload = response.json()
        except Exception:
            return None
        row = next(
            (
                item
                for item in _orders_from_payload(payload)
                if str(item.get("client_order_id") or "").strip() == client_order_id
            ),
            None,
        )
        if row is None:
            return None
        try:
            return _normalize_order(row, account_id=self.account_id)
        except BrokerAdapterError:
            return None

    def cancel(self, client_order_id: str):
        """Cancel exactly once, then prove terminal state with bounded read-only reads.

        Webull sandbox can briefly return `Order not present` from Order Detail after
        acknowledging a cancellation. That response must not trigger a second cancel.
        ATLAS instead checks exact Order Detail and exact Order History for a bounded
        window. Failure to prove CANCELLED remains BrokerMutationUncertain.
        """

        client_order_id = str(client_order_id).strip()
        if not client_order_id:
            raise BrokerAdapterError("Webull cancellation requires a client order id")

        current = self.order(client_order_id)
        if current.status == BrokerOrderStatus.CANCELLED:
            return current
        if current.status in {BrokerOrderStatus.FILLED, BrokerOrderStatus.REJECTED}:
            raise BrokerAdapterError(
                f"Webull order is already terminal and cannot be cancelled: {current.status.value}"
            )
        if current.status not in {
            BrokerOrderStatus.SUBMITTED,
            BrokerOrderStatus.PARTIAL_FILLED,
        }:
            raise BrokerAdapterError(
                f"Webull order state is not cancelable: {current.status.value}"
            )

        try:
            response = self._client.order_v3.cancel_order(self.account_id, client_order_id)
        except Exception as exc:
            raise BrokerMutationUncertain(
                "Webull cancel request outcome is uncertain; reconcile exact client order id before any retry"
            ) from exc
        try:
            _json_response(response, "cancel order")
        except BrokerAdapterError as exc:
            raise BrokerMutationUncertain(
                "Webull cancellation was attempted but acknowledgement failed; reconcile before any further mutation"
            ) from exc

        observed_terminal = None
        for delay_seconds in _CANCEL_RECONCILIATION_DELAYS_SECONDS:
            if delay_seconds > 0.0:
                time.sleep(delay_seconds)

            detail = None
            try:
                detail = self.order(client_order_id)
            except BrokerOrderNotFound:
                pass
            except BrokerAdapterError:
                pass
            if detail is not None:
                if detail.status == BrokerOrderStatus.CANCELLED:
                    return detail
                if detail.status in {BrokerOrderStatus.FILLED, BrokerOrderStatus.REJECTED}:
                    observed_terminal = detail

            history = self._history_order(client_order_id)
            if history is not None:
                if history.status == BrokerOrderStatus.CANCELLED:
                    return history
                if history.status in {BrokerOrderStatus.FILLED, BrokerOrderStatus.REJECTED}:
                    observed_terminal = history

        if observed_terminal is not None:
            raise BrokerMutationUncertain(
                "Webull cancellation was acknowledged but exact order reached a different terminal state; reconcile exposure before any further mutation"
            )
        raise BrokerMutationUncertain(
            "Webull cancellation was acknowledged but exact CANCELLED state was not proven within the bounded read-only reconciliation window; no retry is allowed"
        )
