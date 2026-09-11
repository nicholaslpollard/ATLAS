from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.b35_evidence_analysis import run_b35_evidence_analysis
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
    override = os.getenv("ATLAS_B35_ANALYSIS_DUCKDB_THREADS")
    logical = os.cpu_count() or 1
    usable = max(1, logical - 2)
    if override:
        value = int(override)
        if value < 1 or value > usable:
            raise ValueError(
                "ATLAS_B35_ANALYSIS_DUCKDB_THREADS must be between 1 and "
                f"{usable} on this host"
            )
        return value
    return min(usable, 10)


def main() -> int:
    output_root = _output_root()
    threads = _threads()
    print("ATLAS B35 DEVELOPMENT Strategy x Condition / Selector Analysis", flush=True)
    print(f"  frozen replay root: {output_root}", flush=True)
    print(
        "  authority: existing completed DEVELOPMENT outcomes only; "
        "master/future/provider/broker/PAPER/LIVE access forbidden",
        flush=True,
    )
    print(f"  DuckDB threads: {threads}", flush=True)
    report = run_b35_evidence_analysis(output_root, duckdb_threads=threads)
    print("\nB35 EVIDENCE ANALYSIS: COMPLETE", flush=True)
    print(f"  analysis fingerprint: {report['analysis_fingerprint']}", flush=True)
    print(
        f"  normalized opportunities: {int(report['normalized_opportunities']):,}",
        flush=True,
    )
    selector = report["selector_summary"]["overall"]
    print(
        "  selector test opportunities / selected / comparable: "
        f"{int(selector['test_opportunities']):,} / "
        f"{int(selector['selected_opportunities']):,} / "
        f"{int(selector['selected_comparable']):,}",
        flush=True,
    )
    print(
        f"  selector abstention rate: {float(selector['abstention_rate'] or 0.0):.2%}",
        flush=True,
    )
    mean_r = selector.get("mean_net_r_50")
    mean_return = selector.get("mean_net_return_50")
    mean_r_text = "n/a" if mean_r is None else f"{float(mean_r):.6f}"
    mean_return_text = "n/a" if mean_return is None else f"{float(mean_return):.6%}"
    print(
        "  selector mean net R / mean net return @50bps: "
        f"{mean_r_text} / {mean_return_text}",
        flush=True,
    )
    print(
        f"  summary: {output_root / 'analysis_v1' / 'analysis_summary.json'}",
        flush=True,
    )
    print("  promotion authority: false", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
