from __future__ import annotations

from packages.backtesting.phase27_closeout import (
    PHASE27_ARCHITECTURE_AUDIT_CONTRACT_VERSION,
    PHASE27_CLOSEOUT_REPORT_CONTRACT_VERSION,
    phase27_architecture_audit_checks,
    phase27_disposition,
)
from packages.core.settings import load_settings


def test_phase27_disposition_blocks_trade_construction_without_supported_alpha() -> None:
    disposition, entry = phase27_disposition(())
    assert disposition == "ACCEPTED_NEGATIVE"
    assert entry is False


def test_phase27_disposition_allows_next_entry_only_with_supported_alpha() -> None:
    disposition, entry = phase27_disposition(("supported-alpha",))
    assert disposition == "ACCEPTED_POSITIVE"
    assert entry is True


def test_phase27_closeout_contracts_and_architecture_audit_are_static_passing() -> None:
    settings = load_settings()
    checks = phase27_architecture_audit_checks(settings.project_root)
    assert PHASE27_ARCHITECTURE_AUDIT_CONTRACT_VERSION
    assert PHASE27_CLOSEOUT_REPORT_CONTRACT_VERSION
    assert all(checks.values()), [name for name, passed in checks.items() if not passed]
