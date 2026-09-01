from __future__ import annotations

from packages.backtesting.alpha_gate_sec_13f_feasibility import SEC_13F_ANCHORS
from packages.backtesting.alpha_gate_sec_13f_feasibility_v2 import (
    SEC_13F_CAPACITY_EVIDENCE_COMPLETE,
    SEC_13F_COMPLETE_SOURCE_SCOPE_PROVEN,
    SEC_13F_FEASIBILITY_SCOPE,
    SEC_13F_FEASIBILITY_V2_FINGERPRINT,
    SEC_13F_RAW_RELATIVE_V2,
    SEC_13F_REPORT_RELATIVE_V2,
    SEC_13F_SCIENTIFIC_FREEZE_ALLOWED,
    sec_13f_feasibility_v2_fingerprint,
    sec_13f_probe_population_coverage,
)


def test_v2_fingerprint_is_frozen() -> None:
    assert sec_13f_feasibility_v2_fingerprint() == SEC_13F_FEASIBILITY_V2_FINGERPRINT
    assert SEC_13F_FEASIBILITY_V2_FINGERPRINT == "4f41f7b1ca93bb76d559134d8ef74505ffd6a598e96676011ef515026d491696"


def test_v2_is_explicitly_probe_only_not_complete_capacity() -> None:
    assert SEC_13F_FEASIBILITY_SCOPE == "PROBE_ONLY"
    assert SEC_13F_CAPACITY_EVIDENCE_COMPLETE is False
    assert SEC_13F_COMPLETE_SOURCE_SCOPE_PROVEN is False
    assert SEC_13F_SCIENTIFIC_FREEZE_ALLOWED is False


def test_probe_population_contract_cannot_prove_complete_scope() -> None:
    anchors = [{"initial_hr_infotable_rows": 100_000} for _label, _url in SEC_13F_ANCHORS]
    coverage = sec_13f_probe_population_coverage(anchors)
    assert coverage["valid_contract"] is True
    assert coverage["source_scope_proven"] is False
    assert coverage["stages"][0]["scope"] == "PROBE_ONLY"
    assert coverage["stages"][0]["complete_scope"] is False
    assert coverage["stages"][0]["rows"] == 400_000


def test_v2_evidence_paths_do_not_overwrite_v1() -> None:
    assert "feasibility_v2" in str(SEC_13F_RAW_RELATIVE_V2)
    assert "feasibility_v2" in str(SEC_13F_REPORT_RELATIVE_V2)


def test_v2_runner_imports_current_settings_api() -> None:
    from scripts.run_alpha_gate_sec_13f_feasibility_v2 import main

    assert callable(main)


def test_v2_static_contract_validator_runs_inside_full_pytest() -> None:
    from scripts.validate_alpha_gate_sec_13f_feasibility_v2 import main

    assert main() == 0
