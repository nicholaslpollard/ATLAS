from __future__ import annotations

import argparse
import os
from typing import Any

from packages.brokers.webull.account_selection import (
    WebullSandboxAccountCandidate,
    select_webull_sandbox_candidate,
    update_dotenv_webull_account_id,
)
from packages.core.settings import load_settings


WEBULL_SANDBOX_ENDPOINT = "api.sandbox.webull.com"


def _first_env(*names: str) -> str:
    for name in names:
        value = str(os.getenv(name, "") or "").strip()
        if value:
            return value
    return ""


def _payload(response: Any) -> Any:
    try:
        return response.json()
    except Exception:
        return None


def _row_count(payload: Any, key: str) -> int | None:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict) and isinstance(payload.get(key), list):
        return len(payload[key])
    return None


def _probe_account(client: Any, account_id: str, account_type: str) -> WebullSandboxAccountCandidate:
    try:
        balance_response = client.account_v2.get_account_balance(account_id)
        balance_ok = int(getattr(balance_response, "status_code", 0)) == 200
    except Exception:
        balance_ok = False

    try:
        orders_response = client.order_v3.get_order_open(account_id=account_id)
        orders_ok = int(getattr(orders_response, "status_code", 0)) == 200
        order_count = _row_count(_payload(orders_response), "orders") if orders_ok else None
    except Exception:
        orders_ok = False
        order_count = None

    try:
        positions_response = client.account_v2.get_account_position(account_id)
        positions_ok = int(getattr(positions_response, "status_code", 0)) == 200
        position_count = _row_count(_payload(positions_response), "positions") if positions_ok else None
    except Exception:
        positions_ok = False
        position_count = None

    return WebullSandboxAccountCandidate(
        account_id=account_id,
        account_type=account_type,
        balance_readable=balance_ok,
        open_orders_readable=orders_ok,
        positions_readable=positions_ok,
        open_order_count=order_count,
        position_count=position_count,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Safely bind one Webull sandbox account to local ATLAS Phase 17 configuration."
    )
    parser.add_argument(
        "--account-ref",
        default=None,
        help=(
            "Sanitized 16-character account ref from this selector/Phase 17 diagnostic. "
            "Required when more than one readable sandbox account exists."
        ),
    )
    args = parser.parse_args()

    settings = load_settings()
    key = _first_env("WEBULL_PAPER_APP_KEY", "WEBULL_APP_KEY")
    secret = _first_env("WEBULL_PAPER_APP_SECRET", "WEBULL_APP_SECRET")
    if not key or not secret:
        raise SystemExit("Webull sandbox credentials are unavailable in the local environment.")

    try:
        from webull.core.client import ApiClient
        from webull.trade.trade_client import TradeClient
    except ImportError as exc:
        raise SystemExit("webull-openapi-python-sdk is unavailable.") from exc

    api_client = ApiClient(key, secret, "us")
    api_client.add_endpoint("us", WEBULL_SANDBOX_ENDPOINT)
    client = TradeClient(api_client)
    try:
        response = client.account_v2.get_account_list()
    except Exception as exc:
        raise SystemExit(f"Webull sandbox account-list read failed: {type(exc).__name__}") from exc
    if int(getattr(response, "status_code", 0)) != 200:
        raise SystemExit(f"Webull sandbox account-list read failed with HTTP {getattr(response, 'status_code', '?')}.")
    account_rows = _payload(response)
    if not isinstance(account_rows, list):
        raise SystemExit("Webull sandbox account-list response had an unexpected shape.")

    candidates: list[WebullSandboxAccountCandidate] = []
    for row in account_rows:
        if not isinstance(row, dict):
            continue
        account_id = str(row.get("account_id") or "").strip()
        if not account_id:
            continue
        account_type = str(row.get("account_type") or "UNKNOWN").strip() or "UNKNOWN"
        candidates.append(_probe_account(client, account_id, account_type))

    print("ATLAS Phase 17 Webull sandbox account selector")
    print("Provider mutations: DISABLED")
    print("Live execution: DISABLED")
    print("Raw account IDs exposed: NO")
    print(f"Candidate count: {len(candidates)}")
    for candidate in candidates:
        print(
            "  candidate: "
            f"type={candidate.account_type} "
            f"ref={candidate.account_ref} "
            f"readable={candidate.readable} "
            f"flat={candidate.flat} "
            f"open_orders={candidate.open_order_count if candidate.open_order_count is not None else 'UNKNOWN'} "
            f"positions={candidate.position_count if candidate.position_count is not None else 'UNKNOWN'}"
        )

    try:
        selected, reason = select_webull_sandbox_candidate(
            tuple(candidates), preferred_ref=args.account_ref
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    env_path = settings.resolved_path(".env")
    update_dotenv_webull_account_id(env_path, selected.account_id)
    print(f"Selected account: type={selected.account_type} ref={selected.account_ref}")
    print(f"Selection reason: {reason}")
    print("Local configuration updated: WEBULL_PAPER_ACCOUNT_ID")
    print("Provider writes performed: 0")


if __name__ == "__main__":
    main()
