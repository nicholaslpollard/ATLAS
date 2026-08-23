from __future__ import annotations

import hashlib
import os
from typing import Any

from packages.brokers.alpaca import AlpacaPaperBroker
from packages.brokers.base import BrokerAdapterError
from packages.core.settings import load_settings
from packages.execution.validator import ExecutionValidationError, reconcile_broker


WEBULL_SANDBOX_ENDPOINT = "api.sandbox.webull.com"


def _first_env(*names: str) -> str:
    for name in names:
        value = str(os.getenv(name, "") or "").strip()
        if value:
            return value
    return ""


def _ref(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _response_json(response: Any) -> Any:
    try:
        return response.json()
    except Exception:
        return None


def _provider_error_code(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "UNAVAILABLE"
    for key in ("error_code", "code", "error", "status"):
        value = payload.get(key)
        if value not in (None, "", [], {}):
            return str(value)[:120]
    return "UNAVAILABLE"


def _print_webull() -> None:
    print("Webull sandbox read diagnostic")
    key = _first_env("WEBULL_PAPER_APP_KEY", "WEBULL_APP_KEY")
    secret = _first_env("WEBULL_PAPER_APP_SECRET", "WEBULL_APP_SECRET")
    configured_account_id = _first_env("WEBULL_PAPER_ACCOUNT_ID", "WEBULL_ACCOUNT_ID")
    print(f"  app_key_present: {bool(key)}")
    print(f"  app_secret_present: {bool(secret)}")
    print(f"  account_id_configured: {bool(configured_account_id)}")
    if not key or not secret:
        print("  result: CREDENTIALS_UNAVAILABLE")
        return

    try:
        from webull.core.client import ApiClient
        from webull.trade.trade_client import TradeClient
    except ImportError:
        print("  result: WEBULL_SDK_UNAVAILABLE")
        return

    try:
        api_client = ApiClient(key, secret, "us")
        api_client.add_endpoint("us", WEBULL_SANDBOX_ENDPOINT)
        client = TradeClient(api_client)
        response = client.account_v2.get_account_list()
    except Exception as exc:
        print(f"  account_list_transport: ERROR_{type(exc).__name__.upper()}")
        return

    status = int(getattr(response, "status_code", 0))
    payload = _response_json(response)
    print(f"  account_list_http_status: {status}")
    if status != 200:
        print(f"  account_list_provider_code: {_provider_error_code(payload)}")
        print("  result: WEBULL_ACCOUNT_LIST_FAILED")
        return
    if not isinstance(payload, list):
        print(f"  account_list_shape: {type(payload).__name__}")
        print("  result: WEBULL_ACCOUNT_LIST_UNEXPECTED_SHAPE")
        return

    candidates: list[tuple[str, str]] = []
    print(f"  account_count: {len(payload)}")
    for item in payload:
        if not isinstance(item, dict):
            continue
        account_id = str(item.get("account_id") or "").strip()
        account_type = str(item.get("account_type") or "UNKNOWN").strip() or "UNKNOWN"
        if account_id:
            candidates.append((account_id, account_type))
            print(f"  account_candidate: type={account_type} ref={_ref(account_id)}")

    if configured_account_id:
        selected = configured_account_id
        if candidates and selected not in {account_id for account_id, _ in candidates}:
            print("  result: CONFIGURED_WEBULL_ACCOUNT_ID_NOT_IN_ACCOUNT_LIST")
            return
        print(f"  selected_account_ref: {_ref(selected)} (explicit configuration)")
    elif len(candidates) == 1:
        selected = candidates[0][0]
        print(f"  selected_account_ref: {_ref(selected)} (single unambiguous account)")
    elif not candidates:
        print("  result: WEBULL_ACCOUNT_ID_MISSING_FROM_ACCOUNT_LIST")
        return
    else:
        print("  selection: AMBIGUOUS")
        print("  result: WEBULL_PAPER_ACCOUNT_ID_REQUIRED")
        return

    probes = (
        ("balance", lambda: client.account_v2.get_account_balance(selected)),
        ("open_orders", lambda: client.order_v3.get_order_open(account_id=selected)),
        ("positions", lambda: client.account_v2.get_account_position(selected)),
    )
    for label, call in probes:
        try:
            response = call()
        except Exception as exc:
            print(f"  {label}_transport: ERROR_{type(exc).__name__.upper()}")
            print(f"  result: WEBULL_{label.upper()}_FAILED")
            return
        status = int(getattr(response, "status_code", 0))
        payload = _response_json(response)
        print(f"  {label}_http_status: {status}")
        if status != 200:
            print(f"  {label}_provider_code: {_provider_error_code(payload)}")
            print(f"  result: WEBULL_{label.upper()}_FAILED")
            return
        if label in {"open_orders", "positions"}:
            if isinstance(payload, list):
                print(f"  {label}_top_level_count: {len(payload)}")
            elif isinstance(payload, dict):
                rows = payload.get("orders") if label == "open_orders" else payload.get("positions")
                if isinstance(rows, list):
                    print(f"  {label}_top_level_count: {len(rows)}")
                else:
                    print(f"  {label}_shape: dict")
    print("  result: WEBULL_READ_PATH_REACHED_ALL_REQUIRED_ENDPOINTS")


def _print_alpaca() -> None:
    print("Alpaca paper read diagnostic")
    key = _first_env("ALPACA_PAPER_API_KEY")
    secret = _first_env("ALPACA_PAPER_API_SECRET")
    print(f"  api_key_present: {bool(key)}")
    print(f"  api_secret_present: {bool(secret)}")
    if not key or not secret:
        print("  result: CREDENTIALS_UNAVAILABLE")
        return
    try:
        adapter = AlpacaPaperBroker()
        reconciliation = reconcile_broker(adapter)
    except (BrokerAdapterError, ExecutionValidationError, OSError, ValueError, RuntimeError) as exc:
        print(f"  result: ALPACA_READ_FAILED_{type(exc).__name__.upper()}")
        return
    print(f"  account_ref: {_ref(reconciliation.account.account_id)}")
    print(f"  reconciled: {reconciliation.reconciled}")
    print(f"  open_order_count: {len(reconciliation.open_orders)}")
    print(f"  position_count: {len(reconciliation.positions)}")
    print(f"  safe_to_switch_broker: {reconciliation.safe_to_switch_broker}")
    print("  result: ALPACA_READ_PATH_RECONCILED")


def main() -> None:
    # load_settings() loads the repository's environment configuration without printing values.
    load_settings()
    print("ATLAS Phase 17 provider-readonly diagnostic")
    print("Provider mutations: DISABLED")
    print("Live execution: DISABLED")
    print()
    _print_webull()
    print()
    _print_alpaca()


if __name__ == "__main__":
    main()
