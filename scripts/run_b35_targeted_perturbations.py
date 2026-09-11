from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.b35_development_authorization import (
    validate_development_authorization,
)
from packages.backtesting.b35_development_source import B35DevelopmentMinuteSource
from packages.backtesting.b35_split_evidence import load_b35_split_evidence
from packages.backtesting.b35_targeted_perturbations import (
    B35_ACCEPTED_ROBUSTNESS_FINGERPRINT,
    B35TargetedPerturbationReplayEngine,
    TARGETED_PERTURBATION_FINGERPRINT,
    TARGETED_VARIANTS,
    ensure_targeted_authorization,
)
from packages.core.execution_profile import resolve_parallel_research_execution_profile
from packages.core.settings import load_settings
from packages.data.alpaca_v2_acquisition import V2_DEFAULT_START
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.strategies.b35_conditional_evidence_contract import (
    B35_PREOUTCOME_FINGERPRINT,
    DEVELOPMENT_LAST_SCORING_SESSION,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the frozen B35 exact targeted minute-path perturbation pass. "
            "This is diagnostic only and cannot rewrite canonical B35 v1."
        )
    )
    parser.add_argument(
        "--authorize-targeted-perturbations",
        action="store_true",
        help=(
            "Explicitly authorize the frozen DEVELOPMENT-only targeted perturbation "
            "read. Consumed master, future blind, provider, broker, PAPER and LIVE "
            "access remain forbidden."
        ),
    )
    return parser


def _canonical_root(settings) -> Path:
    layout = V2Layout.beneath((settings.project_root / "data").resolve())
    return (
        layout.derived
        / "strategy_lab"
        / "b35_development"
        / B35_PREOUTCOME_FINGERPRINT[:16]
        / f"{V2_DEFAULT_START}_{DEVELOPMENT_LAST_SCORING_SESSION}"
    )


def _validate_robustness_summary(canonical_root: Path) -> None:
    path = (
        canonical_root
        / "analysis_v1"
        / "robustness_v1"
        / "robustness_summary.json"
    )
    if not path.is_file():
        raise RuntimeError("accepted B35 robustness_summary.json is missing")
    value = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "robustness_fingerprint": B35_ACCEPTED_ROBUSTNESS_FINGERPRINT,
        "status": "COMPLETE_PROFILE_WITH_TARGETED_PERTURBATIONS_PENDING",
        "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
        "complete_test_sessions": 2079,
    }
    for key, expected in required.items():
        if value.get(key) != expected:
            raise RuntimeError(f"B35 robustness summary {key} drifted")
    authority = value.get("authority")
    if not isinstance(authority, dict):
        raise RuntimeError("B35 robustness authority block is missing")
    if any(
        authority.get(key) != 0
        for key in ("provider_calls", "broker_reads", "broker_writes")
    ):
        raise RuntimeError("B35 robustness external access state drifted")
    if any(
        authority.get(key) is not False
        for key in (
            "paper_authority",
            "live_authority",
            "strategy_promotion",
            "selector_promotion",
        )
    ):
        raise RuntimeError("B35 robustness authority unexpectedly promoted")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.authorize_targeted_perturbations:
        raise ValueError(
            "targeted perturbation replay requires --authorize-targeted-perturbations"
        )

    settings = load_settings(PROJECT_ROOT)
    profile = resolve_parallel_research_execution_profile()
    source = B35DevelopmentMinuteSource(
        settings,
        duckdb_threads=profile.duckdb_threads_per_worker,
    )
    start = V2_DEFAULT_START
    end = DEVELOPMENT_LAST_SCORING_SESSION
    plan = source.plan(start, end)
    split_evidence = load_b35_split_evidence(source.layout)
    canonical_root = _canonical_root(settings)
    _validate_robustness_summary(canonical_root)

    development_authorization_path = (
        canonical_root / "development_outcome_authorization.json"
    )
    if not development_authorization_path.is_file():
        raise RuntimeError("B35 DEVELOPMENT authorization is missing")
    development_authorization = json.loads(
        development_authorization_path.read_text(encoding="utf-8")
    )
    development_authorization_id = validate_development_authorization(
        development_authorization,
        plan=plan,
        split_evidence=split_evidence,
    )

    output_root = (
        canonical_root
        / "analysis_v1"
        / "robustness_v1"
        / "targeted_minute_perturbations_v1"
    )
    output_root.mkdir(parents=True, exist_ok=True)
    authorization = ensure_targeted_authorization(
        output_root / "targeted_perturbation_authorization.json",
        plan=plan,
        split_evidence_fingerprint=split_evidence.fingerprint,
        development_authorization_id=development_authorization_id,
    )

    print("ATLAS B35 Exact Targeted Minute Perturbation Replay", flush=True)
    print(f"  process started UTC: {datetime.now(UTC).isoformat()}", flush=True)
    print(f"  coordinator PID: {os.getpid()}", flush=True)
    print(f"  scope: {start} -> {end} (frozen DEVELOPMENT only)", flush=True)
    print(f"  source units: {len(plan.units):,}", flush=True)
    print(f"  perturbation variants: {len(TARGETED_VARIANTS)}", flush=True)
    print(
        f"  targeted perturbation fingerprint: {TARGETED_PERTURBATION_FINGERPRINT}",
        flush=True,
    )
    print(
        f"  accepted robustness fingerprint: {B35_ACCEPTED_ROBUSTNESS_FINGERPRINT}",
        flush=True,
    )
    print(
        "  execution profile: "
        f"workers={profile.replay_workers}, "
        f"DuckDB threads/worker={profile.duckdb_threads_per_worker}",
        flush=True,
    )
    print("  one-axis-at-a-time perturbations: true", flush=True)
    print("  selector refit: false", flush=True)
    print("  canonical B35 replay rewrite: false", flush=True)
    print("  consumed master / future blind rows permitted: 0 / 0", flush=True)
    print("  provider / broker reads / broker writes: 0 / 0 / 0", flush=True)
    print("  PAPER / LIVE / promotion authority: false / false / false", flush=True)
    print(
        f"  explicit targeted authorization: {authorization['authorization_id']}",
        flush=True,
    )
    print(f"  progress: {output_root / 'progress.json'}", flush=True)

    summary = B35TargetedPerturbationReplayEngine(
        source,
        execution_profile=profile,
    ).run(
        plan,
        output_root=output_root,
        authorization=authorization,
    )

    print("", flush=True)
    print("B35 TARGETED MINUTE PERTURBATIONS: COMPLETE", flush=True)
    print(
        f"  run fingerprint: {summary['run_fingerprint']}",
        flush=True,
    )
    print(
        f"  groups / units: {summary['group_count']:,} / "
        f"{summary['source_unit_count']:,}",
        flush=True,
    )
    print(
        f"  variants: {summary['variant_count']}",
        flush=True,
    )
    print(
        f"  baseline equivalence: {summary['baseline_equivalence']}",
        flush=True,
    )
    print(
        f"  summary: {output_root / 'summary.json'}",
        flush=True,
    )
    print("  promotion authority: false", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
