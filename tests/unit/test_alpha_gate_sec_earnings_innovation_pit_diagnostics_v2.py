from __future__ import annotations

import pytest

from packages.backtesting.alpha_gate_sec_earnings_innovation_pit_audit import (
    EARNINGS_INNOVATION_PIT_AUDIT_CONTRACT,
    EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT,
)
from packages.backtesting.alpha_gate_sec_earnings_innovation_pit_diagnostics_v2 import (
    EARNINGS_INNOVATION_FEASIBILITY_PARENT_REPORT_SHA256,
    EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_FINGERPRINT,
    EarningsInnovationPITDiagnosticV2Error,
    _FAILED_EXACT,
    _FAILED_GATES,
    _verify_failed_audit,
    earnings_innovation_pit_diagnostic_v2_fingerprint,
)


def _failed_report() -> dict[str, object]:
    report: dict[str, object] = {
        "contract_version": EARNINGS_INNOVATION_PIT_AUDIT_CONTRACT,
        "pit_audit_fingerprint": EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT,
        **_FAILED_EXACT,
        "gates": dict(_FAILED_GATES),
        "acceptance_proven_fraction": 5896 / 5902,
    }
    return report


def test_diagnostic_v2_fingerprint_is_frozen() -> None:
    assert (
        earnings_innovation_pit_diagnostic_v2_fingerprint()
        == EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_FINGERPRINT
    )


def test_v2_guard_accepts_exact_first_failed_audit_structure() -> None:
    _verify_failed_audit(_failed_report())


def test_v2_guard_uses_parent_report_sha_as_parent_lineage_not_pit_report_hash() -> None:
    report = _failed_report()
    assert report["parent_report_sha256"] == EARNINGS_INNOVATION_FEASIBILITY_PARENT_REPORT_SHA256
    _verify_failed_audit(report)


def test_v2_guard_rejects_changed_failure_counts() -> None:
    report = _failed_report()
    report["period_context_ambiguities"] = 2
    with pytest.raises(EarningsInnovationPITDiagnosticV2Error):
        _verify_failed_audit(report)


def test_v2_guard_rejects_gate_vector_drift() -> None:
    report = _failed_report()
    gates = dict(_FAILED_GATES)
    gates["period_context_ambiguities_max"] = True
    report["gates"] = gates
    with pytest.raises(EarningsInnovationPITDiagnosticV2Error):
        _verify_failed_audit(report)
