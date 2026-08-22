from __future__ import annotations

from packages.brokers.webull.account_selection import (
    WebullSandboxAccountCandidate,
    select_webull_sandbox_candidate,
    update_dotenv_webull_account_id,
)


def _candidate(
    account_id: str,
    account_type: str,
    *,
    readable: bool = True,
    open_orders: int = 0,
    positions: int = 0,
) -> WebullSandboxAccountCandidate:
    return WebullSandboxAccountCandidate(
        account_id=account_id,
        account_type=account_type,
        balance_readable=readable,
        open_orders_readable=readable,
        positions_readable=readable,
        open_order_count=open_orders if readable else None,
        position_count=positions if readable else None,
    )


def test_selector_prefers_flat_margin_over_flat_cash() -> None:
    cash = _candidate("cash-account", "CASH")
    margin = _candidate("margin-account", "MARGIN")

    selected, reason = select_webull_sandbox_candidate((cash, margin))

    assert selected.account_id == "margin-account"
    assert reason == "AUTO_PREFER_FLAT_MARGIN"


def test_selector_prefers_flat_margin_over_exposed_margin() -> None:
    exposed = _candidate("margin-exposed", "MARGIN", positions=1)
    flat = _candidate("margin-flat", "MARGIN")

    selected, reason = select_webull_sandbox_candidate((exposed, flat))

    assert selected.account_id == "margin-flat"
    assert reason == "AUTO_PREFER_FLAT_MARGIN"


def test_selector_allows_explicit_sanitized_ref_override() -> None:
    default = _candidate("margin-account", "MARGIN")
    override = _candidate("cash-account", "CASH")

    selected, reason = select_webull_sandbox_candidate(
        (default, override), preferred_ref=override.account_ref
    )

    assert selected.account_id == "cash-account"
    assert reason == "EXPLICIT_SANITIZED_REF"


def test_selector_rejects_unreadable_explicit_candidate() -> None:
    unreadable = _candidate("bad-account", "MARGIN", readable=False)

    try:
        select_webull_sandbox_candidate((unreadable,), preferred_ref=unreadable.account_ref)
    except ValueError as exc:
        assert "did not pass all required read probes" in str(exc)
    else:
        raise AssertionError("expected unreadable explicit candidate to fail")


def test_update_dotenv_replaces_existing_account_without_duplicate(tmp_path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "WEBULL_PAPER_APP_KEY=key\nWEBULL_PAPER_ACCOUNT_ID=old\nOTHER=value\n",
        encoding="utf-8",
    )

    update_dotenv_webull_account_id(env_path, "new-account")

    text = env_path.read_text(encoding="utf-8")
    assert text.count("WEBULL_PAPER_ACCOUNT_ID=") == 1
    assert "WEBULL_PAPER_ACCOUNT_ID=new-account" in text
    assert "WEBULL_PAPER_ACCOUNT_ID=old" not in text
    assert "WEBULL_PAPER_APP_KEY=key" in text
    assert "OTHER=value" in text
