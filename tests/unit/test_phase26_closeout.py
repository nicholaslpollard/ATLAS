from __future__ import annotations

from pathlib import Path

from packages.backtesting.phase26_closeout import (
    PHASE26_ARCHITECTURE_AUDIT_CONTRACT_VERSION,
    PHASE26_CLOSEOUT_REPORT_CONTRACT_VERSION,
    phase26_architecture_audit_checks,
    phase26_disposition,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_phase26_architecture_audit_is_machine_verifiable_and_passing() -> None:
    checks = phase26_architecture_audit_checks(PROJECT_ROOT)
    assert checks
    assert all(checks.values()), [name for name, passed in checks.items() if not passed]
    audit = (PROJECT_ROOT / "docs" / "phase26_end_to_end_anti_workaround_audit.md").read_text(
        encoding="utf-8"
    )
    assert PHASE26_ARCHITECTURE_AUDIT_CONTRACT_VERSION in audit
    assert "**Disposition:** PASS" in audit


def test_phase26_negative_disposition_blocks_phase27_without_supported_alpha() -> None:
    disposition, phase27_entry = phase26_disposition(())
    assert disposition == "ACCEPTED_NEGATIVE"
    assert phase27_entry is False


def test_phase26_positive_disposition_requires_real_supported_ids() -> None:
    disposition, phase27_entry = phase26_disposition(("candidate-a",))
    assert disposition == "ACCEPTED_POSITIVE"
    assert phase27_entry is True


def test_phase26_closeout_does_not_retrofit_observed_target_counts_as_thresholds() -> None:
    source = (PROJECT_ROOT / "packages" / "backtesting" / "phase26_closeout.py").read_text(
        encoding="utf-8"
    )
    assert "21483" not in source
    assert "1096" not in source
    assert "Phase26CumulativeRunner(settings).run()" not in source
    assert PHASE26_CLOSEOUT_REPORT_CONTRACT_VERSION in source
