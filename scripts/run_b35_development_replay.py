from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.b35_development_authorization import (
    ensure_development_authorization,
)
from packages.backtesting.b35_development_source import B35DevelopmentMinuteSource
from packages.backtesting.b35_parallel_replay import B35ParallelDevelopmentReplayEngine
from packages.backtesting.b35_split_evidence import (
    load_b35_split_evidence,
    split_evidence_report,
)
from packages.core.atomic_io import atomic_write_text
from packages.core.execution_profile import resolve_parallel_research_execution_profile
from packages.core.settings import AtlasSettings, load_settings
from packages.data.alpaca_v2_acquisition import V2_DEFAULT_START
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.performance.ledger import StrategyTrialLedger
from packages.schemas.strategy_lab import (
    StrategyTrialDisposition,
    StrategyTrialDraft,
    StrategyTrialStage,
)
from packages.strategies.b35_conditional_evidence_contract import (
    B34_PACK_FINGERPRINT,
    B34_STRATEGY_IDS,
    B35_PREOUTCOME_FINGERPRINT,
    DEVELOPMENT_LAST_SCORING_SESSION,
)


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(raw).hexdigest()


def _output_root(settings: AtlasSettings, start: date, end: date) -> Path:
    layout = V2Layout.beneath((settings.project_root / "data").resolve())
    return (
        layout.derived
        / "strategy_lab"
        / "b35_development"
        / B35_PREOUTCOME_FINGERPRINT[:16]
        / f"{start}_{end}"
    )


def _ledger_path(settings: AtlasSettings) -> Path:
    layout = V2Layout.beneath((settings.project_root / "data").resolve())
    return layout.derived / "strategy_lab" / "trials" / "reference_strategy_trials.jsonl"


def _trial(
    *,
    trial_id: str,
    disposition: StrategyTrialDisposition,
    input_fingerprint: str,
    run_fingerprint: str | None,
    outcomes_opened: bool,
    notes: tuple[str, ...],
) -> StrategyTrialDraft:
    return StrategyTrialDraft(
        trial_id=trial_id,
        registered_at_utc=datetime.now(UTC),
        stage=StrategyTrialStage.DEVELOPMENT_REPLAY,
        disposition=disposition,
        family_ids=("gap", "opening_range", "premarket"),
        strategy_ids=B34_STRATEGY_IDS,
        strategy_policy_fingerprint=B34_PACK_FINGERPRINT,
        feature_fingerprint=B35_PREOUTCOME_FINGERPRINT,
        hypotheses=(
            "b35_gap_continuation_50bps_conditioned_expectancy",
            "b35_opening_range_breakout_50bps_conditioned_expectancy",
            "b35_premarket_relvol_50bps_conditioned_expectancy",
            "b35_hvd_style_50bps_conditioned_expectancy",
        ),
        input_fingerprint=input_fingerprint,
        run_fingerprint=run_fingerprint,
        performance_outcomes_opened=outcomes_opened,
        master_protected_return_rows_read=0,
        notes=notes,
    )


def _append_once(ledger: StrategyTrialLedger, draft: StrategyTrialDraft) -> None:
    existing = {item.trial_id: item for item in ledger.read()}.get(draft.trial_id)
    if existing is None:
        ledger.append(draft)
        return
    fields = (
        "stage",
        "disposition",
        "family_ids",
        "strategy_ids",
        "strategy_policy_fingerprint",
        "feature_fingerprint",
        "hypotheses",
        "input_fingerprint",
        "run_fingerprint",
        "performance_outcomes_opened",
        "master_protected_return_rows_read",
        "notes",
    )
    if any(getattr(existing, field) != getattr(draft, field) for field in fields):
        raise RuntimeError(f"existing B35 trial conflicts with rerun: {draft.trial_id}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the frozen B35 DEVELOPMENT minute replay through 2026-04-30. "
            "The consumed master and future blind are structurally unavailable."
        )
    )
    # The governed B35 trial has one frozen scope and one canonical evidence/ledger
    # location. Operator-selectable slices or alternate ledgers would create an
    # avoidable data-snooping/audit bypass surface.
    parser.add_argument(
        "--source-only",
        action="store_true",
        help=(
            "Validate the exact frozen minute plan and split evidence, then stop "
            "before creating outcome authorization or opening any outcome."
        ),
    )
    parser.add_argument(
        "--authorize-development-outcomes",
        action="store_true",
        help=(
            "Create/verify the immutable hash-bound authorization and open only the "
            "frozen B35 DEVELOPMENT outcomes through 2026-04-30. This does not "
            "authorize master/future-blind reads, PAPER, LIVE, provider, or broker access."
        ),
    )
    return parser


def _print(message: str) -> None:
    print(message, flush=True)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.source_only and args.authorize_development_outcomes:
        raise ValueError("--source-only cannot also authorize DEVELOPMENT outcomes")
    if not args.source_only and not args.authorize_development_outcomes:
        raise ValueError(
            "B35 DEVELOPMENT replay requires --authorize-development-outcomes; "
            "protected/future evidence remains forbidden"
        )

    process_started = datetime.now(UTC)
    start = V2_DEFAULT_START
    end = DEVELOPMENT_LAST_SCORING_SESSION
    settings = load_settings(PROJECT_ROOT)
    execution_profile = resolve_parallel_research_execution_profile()
    source = B35DevelopmentMinuteSource(
        settings,
        duckdb_threads=execution_profile.duckdb_threads_per_worker,
    )
    plan = source.plan(start, end)
    split_evidence = load_b35_split_evidence(source.layout)
    output_root = _output_root(settings, start, end)
    output_root.mkdir(parents=True, exist_ok=True)
    source_report = source.report(plan)
    atomic_write_text(
        output_root / "source_plan.json",
        json.dumps(source_report, indent=2, sort_keys=True, default=str) + "\n",
    )
    atomic_write_text(
        output_root / "split_evidence.json",
        json.dumps(
            split_evidence_report(split_evidence),
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
    )

    _print("ATLAS B35 Frozen DEVELOPMENT Conditional Replay")
    _print(f"  process started UTC: {process_started.isoformat()}")
    _print(f"  coordinator PID: {os.getpid()}")
    _print(f"  scope: {start} -> {end} (frozen; no operator override)")
    _print(f"  source units: {len(plan.units):,}")
    _print(f"  source fingerprint: {plan.source_fingerprint}")
    _print(f"  split evidence fingerprint: {split_evidence.fingerprint}")
    _print(f"  B35 contract fingerprint: {B35_PREOUTCOME_FINGERPRINT}")
    memory_gib = execution_profile.as_dict()["total_memory_gib"]
    _print(
        "  execution profile: "
        f"{execution_profile.logical_cpus} logical CPUs, "
        f"{memory_gib if memory_gib is not None else 'unknown'} GiB RAM, "
        f"workers={execution_profile.replay_workers}, "
        f"DuckDB threads/worker={execution_profile.duckdb_threads_per_worker}, "
        f"aggregate worker threads={execution_profile.aggregate_worker_threads}, "
        f"reserved logical CPUs={execution_profile.reserved_logical_cpus} "
        f"({execution_profile.profile_source})"
    )
    _print("  consumed master rows permitted/read: 0 / 0")
    _print("  future blind rows permitted/read: 0 / 0")
    _print("  provider calls / broker reads / broker writes: 0 / 0 / 0")
    _print("  PAPER / LIVE authority: false / false")
    if args.source_only:
        _print("  outcome authorization created: false")
        _print("  outcomes opened: false (--source-only)")
        _print(f"  source plan: {output_root / 'source_plan.json'}")
        _print(f"  split evidence: {output_root / 'split_evidence.json'}")
        return 0

    authorization_path = output_root / "development_outcome_authorization.json"
    authorization = ensure_development_authorization(
        authorization_path,
        plan=plan,
        split_evidence=split_evidence,
    )
    authorization_id = str(authorization["authorization_id"])
    input_fingerprint = _stable_hash(
        {
            "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
            "source_fingerprint": plan.source_fingerprint,
            "split_evidence_fingerprint": split_evidence.fingerprint,
            "authorization_id": authorization_id,
        }
    )

    ledger = StrategyTrialLedger(_ledger_path(settings))
    token = f"{start:%Y%m%d}_{end:%Y%m%d}.{input_fingerprint[:12]}"
    registration_id = f"b35.dev.{token}.registration"
    _append_once(
        ledger,
        _trial(
            trial_id=registration_id,
            disposition=StrategyTrialDisposition.REGISTERED,
            input_fingerprint=input_fingerprint,
            run_fingerprint=None,
            outcomes_opened=False,
            notes=(
                "Frozen B35 DEVELOPMENT outcome replay registered before first outcome calculation.",
                f"Immutable DEVELOPMENT authorization: {authorization_id}.",
                f"Split evidence fingerprint: {split_evidence.fingerprint}.",
                "Scored source ends 2026-04-30; consumed master and future blind are structurally forbidden.",
                "No provider/broker/PAPER/LIVE access or strategy promotion is authorized.",
            ),
        ),
    )
    _print(f"  immutable outcome authorization: {authorization_id}")
    _print(f"  trial registered before outcomes: {registration_id}")
    _print(f"  non-authoritative runtime status: {output_root / 'progress.json'}")

    summary = B35ParallelDevelopmentReplayEngine(
        source,
        execution_profile=execution_profile,
    ).run(
        plan,
        output_root=output_root,
        authorization=authorization,
    )
    run_fingerprint = str(summary["run_fingerprint"])
    completion_id = f"b35.dev.{token}.completion"
    _append_once(
        ledger,
        _trial(
            trial_id=completion_id,
            disposition=StrategyTrialDisposition.COMPLETED,
            input_fingerprint=input_fingerprint,
            run_fingerprint=run_fingerprint,
            outcomes_opened=True,
            notes=(
                "Frozen B35 DEVELOPMENT compact opportunity/outcome materialization completed.",
                f"Run fingerprint: {run_fingerprint}.",
                f"Immutable DEVELOPMENT authorization: {authorization_id}.",
                "Master-protected and future-blind rows read: 0.",
                "No authority promotion; selector/profile evidence remains RESEARCH.",
            ),
        ),
    )
    _print(f"  completed UTC: {datetime.now(UTC).isoformat()}")
    _print(f"  fired opportunities: {int(summary['fired_opportunity_records']):,}")
    _print(f"  run fingerprint: {run_fingerprint}")
    _print(f"  summary: {output_root / 'summary.json'}")
    _print(f"  completion trial: {completion_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
