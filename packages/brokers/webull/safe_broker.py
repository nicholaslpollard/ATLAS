from __future__ import annotations

import logging
from typing import Any

from packages.brokers.base import BrokerAdapterError, BrokerOrderNotFound

from .broker import WebullSandboxBroker as _WebullSandboxBroker


_SENSITIVE_WEBULL_LOGGERS = (
    "webull.core.client",
    "webull.core.http.initializer.client_initializer",
)
_ORDER_ABSENT_MARKER = "order not present"


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
    the SDK's explicit order-not-present exception and preventing unsafe SDK log
    dumps. No mutation, retry, failover, or authority semantics are changed.
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
