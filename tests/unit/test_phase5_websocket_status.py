from __future__ import annotations

import pytest

from packages.providers.massive.websocket import (
    MassiveStocksWebSocketClient,
    MassiveWebSocketAuthenticationError,
    MassiveWebSocketSubscriptionError,
)


def test_runtime_subscription_rejection_is_fatal():
    with pytest.raises(MassiveWebSocketSubscriptionError):
        MassiveStocksWebSocketClient._raise_for_runtime_status(
            {
                "ev": "status",
                "status": "error",
                "message": "not authorized for requested subscription",
            }
        )


def test_runtime_authentication_rejection_is_fatal():
    with pytest.raises(MassiveWebSocketAuthenticationError):
        MassiveStocksWebSocketClient._raise_for_runtime_status(
            {
                "ev": "status",
                "status": "auth_failed",
                "message": "authentication failed",
            }
        )
