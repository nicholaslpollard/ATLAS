from __future__ import annotations

from scripts.diagnose_phase18_webull_order_state import _find_history_order


def test_find_history_order_flattens_combo_payload() -> None:
    payload = [
        {
            "combo_type": "MASTER",
            "orders": [
                {
                    "client_order_id": "p18v-target",
                    "order_id": "provider-order-redacted",
                    "symbol": "AAPL",
                    "side": "BUY",
                    "status": "CANCELLED",
                    "total_quantity": "1",
                    "filled_quantity": "0",
                },
                {
                    "client_order_id": "p18v-target-p",
                    "order_id": "provider-profit-redacted",
                    "symbol": "AAPL",
                    "side": "SELL",
                    "status": "CANCELLED",
                    "total_quantity": "1",
                    "filled_quantity": "0",
                },
            ],
        }
    ]

    order = _find_history_order(
        payload,
        "p18v-target",
        account_id="sanitized-test-account",
    )

    assert order is not None
    assert order.client_order_id == "p18v-target"
    assert order.ticker == "AAPL"
    assert order.status.value == "CANCELLED"
    assert order.filled_quantity == 0.0


def test_find_history_order_returns_none_for_absent_client_id() -> None:
    payload = {
        "orders": [
            {
                "client_order_id": "different-order",
                "order_id": "provider-order-redacted",
                "symbol": "AAPL",
                "side": "BUY",
                "status": "SUBMITTED",
                "total_quantity": "1",
                "filled_quantity": "0",
            }
        ]
    }

    assert (
        _find_history_order(
            payload,
            "p18v-target",
            account_id="sanitized-test-account",
        )
        is None
    )
