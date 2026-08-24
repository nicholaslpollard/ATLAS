from __future__ import annotations

import argparse
import hashlib

from packages.brokers.base import BrokerAdapterError, BrokerOrderNotFound
from packages.brokers.webull import WebullSandboxBroker
from packages.brokers.webull.broker import _normalize_order, _orders_from_payload


def _ref(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _find_history_order(payload: object, client_order_id: str, *, account_id: str):
    rows = _orders_from_payload(payload)
    row = next(
        (
            item
            for item in rows
            if str(item.get("client_order_id") or "").strip() == client_order_id
        ),
        None,
    )
    if row is None:
        return None
    return _normalize_order(row, account_id=account_id)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only Phase 18 Webull sandbox order-state postmortem. Queries Order "
            "Detail, Order History, open orders, and positions; performs zero mutations."
        )
    )
    parser.add_argument("--client-order-id", required=True)
    args = parser.parse_args()
    client_order_id = str(args.client_order_id).strip()
    if not client_order_id:
        raise SystemExit("client order id cannot be blank")

    print("ATLAS Phase 18 Webull order-state diagnostic")
    print("environment: SANDBOX")
    print("mode: READ_ONLY")
    print("provider_writes: 0")
    print("broker_writes: 0")
    print(f"client_order_id: {client_order_id}")

    try:
        broker = WebullSandboxBroker()
    except Exception:
        print("adapter_status: BLOCKED")
        print("reason: Webull sandbox adapter initialization failed")
        return 2

    print("adapter_status: READY")
    print(f"account_ref: {_ref(broker.account_id)}")

    try:
        detail = broker.order(client_order_id)
    except BrokerOrderNotFound:
        print("order_detail: ABSENT")
    except BrokerAdapterError:
        print("order_detail: ERROR")
    else:
        print("order_detail: FOUND")
        print(f"detail_status: {detail.status.value}")
        print(f"detail_ticker: {detail.ticker}")
        print(f"detail_requested_quantity: {detail.requested_quantity}")
        print(f"detail_filled_quantity: {detail.filled_quantity}")

    try:
        response = broker._client.order_v3.get_order_history(broker.account_id)
    except Exception:
        print("order_history: ERROR")
    else:
        status_code = int(getattr(response, "status_code", 0))
        print(f"order_history_http_status: {status_code}")
        if status_code != 200:
            print("order_history: ERROR")
        else:
            try:
                history = _find_history_order(
                    response.json(),
                    client_order_id,
                    account_id=broker.account_id,
                )
            except Exception:
                print("order_history: PARSE_ERROR")
            else:
                if history is None:
                    print("order_history: NOT_FOUND")
                else:
                    print("order_history: FOUND")
                    print(f"history_status: {history.status.value}")
                    print(f"history_ticker: {history.ticker}")
                    print(f"history_requested_quantity: {history.requested_quantity}")
                    print(f"history_filled_quantity: {history.filled_quantity}")

    try:
        open_orders = broker.open_orders()
        positions = broker.positions()
    except BrokerAdapterError:
        print("account_reconciliation: ERROR")
        return 2

    exact_open = [row for row in open_orders if row.client_order_id == client_order_id]
    print("account_reconciliation: COMPLETE")
    print(f"open_order_count: {len(open_orders)}")
    print(f"position_count: {len(positions)}")
    print(f"exact_client_id_open: {bool(exact_open)}")
    print(f"flat_and_zero_open: {not open_orders and not positions}")
    print("disposition: READ_ONLY_POSTMORTEM_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
