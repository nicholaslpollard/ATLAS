from __future__ import annotations

"""Static Windows launcher invariants; Python cannot fully parse PowerShell."""

from pathlib import Path
import re


ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts"/"run_spy_v95_preserve_2020_continue_2021_2023_20261101.ps1"


def test_numeric_prefix_original_json_property_cannot_use_dot_syntax():
    src=SCRIPT.read_text(encoding="utf8")
    # PowerShell '$($report.2020_missing_query_count)' fails to parse before
    # the campaign can even enter its try/finally safety boundary.
    assert not re.search(r"\$\([^)]+\.\d[0-9A-Za-z_]*",src)
    assert "PSObject.Properties['2020_missing_query_count'].Value" in src


def test_source_only_2020_and_explicit_regression_gate_present():
    src=SCRIPT.read_text(encoding="utf8")
    assert "--original-2020-v89-dir $source2020" in src
    assert "scripts.run_spy_v95_2020_read_only_source_reconciliation" in src
    assert "tests/test_spy_v95_2020_read_only_source_reconciliation.py" in src
    assert "tests/test_spy_v95_eight_complete_cohort_2020_censored_matrix.py" in src
    assert "foreach ($year in @(2021,2022,2023))" in src
    assert "tests/test_spy_v93_historical_spy_0dte_expiry_screen.py" in src
    assert "--acquire-options --output-dir $src" in src
    assert "PRESERVED_V95_EVIDENCE_ZIP" in src
    assert "2020_original_hypothetical_pnl_usd" not in src
