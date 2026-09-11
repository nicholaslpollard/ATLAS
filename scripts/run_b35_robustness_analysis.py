from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.b35_robustness_analysis import run_b35_robustness_analysis
from packages.core.settings import load_settings
from packages.data.alpaca_v2_acquisition import V2_DEFAULT_START
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.strategies.b35_conditional_evidence_contract import (
    B35_PREOUTCOME_FINGERPRINT,
    DEVELOPMENT_LAST_SCORING_SESSION,
)


def _output_root() -> Path:
    settings = load_settings(PROJECT_ROOT)
    layout = V2Layout.beneath((settings.project_root / "data").resolve())
    return (
        layout.derived
        / "strategy_lab"
        / "b35_development"
        / B35_PREOUTCOME_FINGERPRINT[:16]
        / f"{V2_DEFAULT_START}_{DEVELOPMENT_LAST_SCORING_SESSION}"
    )


def _threads() -> int:
    override = os.getenv("ATLAS_B35_ROBUSTNESS_DUCKDB_THREADS")
    logical = os.cpu_count() or 1
    usable = max(1, logical - 2)
    if override:
        value = int(override)
        if value < 1 or value > usable:
            raise ValueError(
                "ATLAS_B35_ROBUSTNESS_DUCKDB_THREADS must be between 1 and "
                f"{usable} on this host"
            )
        return value
    return min(usable, 10)


def main() -> int:
    output_root = _output_root()
    threads = _threads()
    print("ATLAS B35 DEVELOPMENT Robustness / Multiplicity Analysis", flush=True)
    print(f"  frozen replay root: {output_root}", flush=True)
    print(
        "  authority: accepted DEVELOPMENT analysis artifacts only; "
        "master/future/provider/broker/PAPER/LIVE access forbidden",
        flush=True,
    )
    print(f"  DuckDB threads: {threads}", flush=True)
    report = run_b35_robustness_analysis(output_root, duckdb_threads=threads)
    print("\nB35 ROBUSTNESS ANALYSIS: COMPLETE", flush=True)
    print(f"  robustness fingerprint: {report['robustness_fingerprint']}", flush=True)
    print(f"  complete test sessions: {int(report['complete_test_sessions']):,}", flush=True)
    fdr = report["selected_cell_fdr_summary"]
    print(
        "  selected-cell BH-FDR hypotheses / q=.05 rejections: "
        f"{int(fdr['hypotheses']):,} / {int(fdr['bh_rejections_q_0_05']):,}",
        flush=True,
    )
    print(
        f"  PBO/CSCV estimate: {float(report['pbo_cscv']['probability_of_backtest_overfitting']):.2%}",
        flush=True,
    )
    print(
        "  preregistered minute-path perturbations pending exact targeted replay: "
        f"{len(report['perturbation_audit']['requires_targeted_minute_replay'])}",
        flush=True,
    )
    print(
        f"  summary: {output_root / 'analysis_v1' / 'robustness_v1' / 'robustness_summary.json'}",
        flush=True,
    )
    print("  promotion authority: false", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
