from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.b35_development_replay import B35DevelopmentReplayEngine
from packages.backtesting.b35_development_source import B35DevelopmentMinuteSource
from packages.core.atomic_io import atomic_write_text
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
    source_fingerprint: str,
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
        input_fingerprint=source_fingerprint,
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
    parser.add_argument("--start", type=date.fromisoformat, default=V2_DEFAULT_START)
    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        default=DEVELOPMENT_LAST_SCORING_SESSION,
    )
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--trial-ledger", type=Path, default=None)
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="Plan the hash-bound pre-protected source and stop before any outcome is opened.",
    )
    parser.add_argument(
        "--authorize-development-outcomes",
        action="store_true",
        help=(
            "Explicitly open only the frozen B35 DEVELOPMENT outcomes through 2026-04-30. "
            "This does not authorize master/future-blind reads, PAPER, LIVE, provider, or broker access."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.source_only and args.authorize_development_outcomes:
        raise ValueError("--source-only cannot also authorize DEVELOPMENT outcomes")
    if not args.source_only and not args.authorize_development_outcomes:
        raise ValueError(
            "B35 DEVELOPMENT replay requires --authorize-development-outcomes; "
            "protected/future evidence remains forbidden"
        )

    settings = load_settings(PROJECT_ROOT)
    source = B35DevelopmentMinuteSource(settings)
    plan = source.plan(args.start, args.end)
    output_root = (
        Path(args.output_root).resolve()
        if args.output_root is not None
        else _output_root(settings, args.start, args.end)
    )
    output_root.mkdir(parents=True, exist_ok=True)
    source_report = source.report(plan)
    atomic_write_text(
        output_root / "source_plan.json",
        json.dumps(source_report, indent=2, sort_keys=True, default=str) + "\n",
    )

    print("ATLAS B35 Frozen DEVELOPMENT Conditional Replay")
    print(f"  scope: {args.start} -> {args.end}")
    print(f"  source units: {len(plan.units):,}")
    print(f"  source fingerprint: {plan.source_fingerprint}")
    print(f"  B35 contract fingerprint: {B35_PREOUTCOME_FINGERPRINT}")
    print("  consumed master rows permitted/read: 0 / 0")
    print("  future blind rows permitted/read: 0 / 0")
    print("  provider calls / broker reads / broker writes: 0 / 0 / 0")
    print("  PAPER / LIVE authority: false / false")
    if args.source_only:
        print("  outcomes opened: false (--source-only)")
        print(f"  source plan: {output_root / 'source_plan.json'}")
        return 0

    ledger = StrategyTrialLedger(
        Path(args.trial_ledger).resolve()
        if args.trial_ledger is not None
        else _ledger_path(settings)
    )
    token = f"{args.start:%Y%m%d}_{args.end:%Y%m%d}.{plan.source_fingerprint[:12]}"
    registration_id = f"b35.dev.{token}.registration"
    _append_once(
        ledger,
        _trial(
            trial_id=registration_id,
            disposition=StrategyTrialDisposition.REGISTERED,
            source_fingerprint=plan.source_fingerprint,
            run_fingerprint=None,
            outcomes_opened=False,
            notes=(
                "Frozen B35 DEVELOPMENT outcome replay registered before first outcome calculation.",
                "Scored source ends 2026-04-30; consumed master and future blind are structurally forbidden.",
                "No provider/broker/PAPER/LIVE access or strategy promotion is authorized.",
            ),
        ),
    )
    print(f"  trial registered before outcomes: {registration_id}")

    summary = B35DevelopmentReplayEngine(source).run(plan, output_root=output_root)
    run_fingerprint = str(summary["run_fingerprint"])
    completion_id = f"b35.dev.{token}.completion"
    _append_once(
        ledger,
        _trial(
            trial_id=completion_id,
            disposition=StrategyTrialDisposition.COMPLETED,
            source_fingerprint=plan.source_fingerprint,
            run_fingerprint=run_fingerprint,
            outcomes_opened=True,
            notes=(
                "Frozen B35 DEVELOPMENT compact opportunity/outcome materialization completed.",
                f"Run fingerprint: {run_fingerprint}.",
                "Master-protected and future-blind rows read: 0.",
                "No authority promotion; selector/profile evidence remains RESEARCH.",
            ),
        ),
    )
    print(f"  fired opportunities: {int(summary['fired_opportunity_records']):,}")
    print(f"  run fingerprint: {run_fingerprint}")
    print(f"  summary: {output_root / 'summary.json'}")
    print(f"  completion trial: {completion_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
