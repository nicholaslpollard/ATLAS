from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.reference_lake_adapter import (
    REFERENCE_LAKE_DEVELOPMENT_END,
    REFERENCE_LAKE_PROVIDER_SEAM_START,
    ReferenceDailyLakeAdapter,
)
from packages.backtesting.reference_strategy_runner import (
    ReferenceStrategyHistoricalRunner,
    reference_input_fingerprint,
)
from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.settings import AtlasSettings, load_settings
from packages.performance.ledger import StrategyTrialLedger
from packages.schemas.strategy_lab import (
    StrategyTrialDisposition,
    StrategyTrialDraft,
    StrategyTrialStage,
)
from packages.strategies.reference_library import (
    REFERENCE_STRATEGY_CATALOG,
    REFERENCE_STRATEGY_POLICY_FINGERPRINT,
)
from packages.features.reference_daily import REFERENCE_DAILY_FEATURE_FINGERPRINT


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _output_root(settings: AtlasSettings, start_date: date, end_date: date) -> Path:
    derived = settings.resolved_path(settings.data.paths.derived)
    return (
        derived
        / "strategy_lab"
        / "a33_b33_reference"
        / "development"
        / f"{start_date}_{end_date}"
    )


def _ledger_path(settings: AtlasSettings) -> Path:
    derived = settings.resolved_path(settings.data.paths.derived)
    return derived / "strategy_lab" / "trials" / "reference_strategy_trials.jsonl"


def _trial_draft(
    *,
    trial_id: str,
    disposition: StrategyTrialDisposition,
    input_fingerprint: str,
    run_fingerprint: str | None,
    performance_opened: bool,
    notes: tuple[str, ...],
) -> StrategyTrialDraft:
    specifications = REFERENCE_STRATEGY_CATALOG.all()
    return StrategyTrialDraft(
        trial_id=trial_id,
        registered_at_utc=datetime.now(UTC),
        stage=StrategyTrialStage.DEVELOPMENT_REPLAY,
        disposition=disposition,
        family_ids=REFERENCE_STRATEGY_CATALOG.family_ids(),
        strategy_ids=tuple(item.strategy_id for item in specifications),
        strategy_policy_fingerprint=REFERENCE_STRATEGY_POLICY_FINGERPRINT,
        feature_fingerprint=REFERENCE_DAILY_FEATURE_FINGERPRINT,
        hypotheses=tuple(
            f"{item.strategy_id}:primary_10bps_net_expectancy" for item in specifications
        ),
        input_fingerprint=input_fingerprint,
        run_fingerprint=run_fingerprint,
        performance_outcomes_opened=performance_opened,
        master_protected_return_rows_read=0,
        notes=notes,
    )


def _append_once(ledger: StrategyTrialLedger, draft: StrategyTrialDraft) -> None:
    existing = {record.trial_id: record for record in ledger.read()}.get(draft.trial_id)
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
        raise RuntimeError(f"existing strategy trial conflicts with rerun: {draft.trial_id}")


def _write_opportunities(path: Path, opportunities: tuple[object, ...]) -> str:
    temp = unique_temp_path(path)
    try:
        with temp.open("w", encoding="utf-8", newline="") as handle:
            for item in opportunities:
                handle.write(item.model_dump_json())  # type: ignore[attr-defined]
                handle.write("\n")
        replace_with_retry(temp, path)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    return _sha256(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the frozen A33/B33 reference library on Massive-only DEVELOPMENT data."
        )
    )
    parser.add_argument("--start", type=date.fromisoformat, default=REFERENCE_LAKE_PROVIDER_SEAM_START)
    parser.add_argument("--end", type=date.fromisoformat, default=REFERENCE_LAKE_DEVELOPMENT_END)
    parser.add_argument("--split-report", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--trial-ledger", type=Path, default=None)
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="Validate and materialize no outcomes; stop after the read-only adapter report.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings(PROJECT_ROOT)
    target = Path(args.output_root) if args.output_root else _output_root(
        settings, args.start, args.end
    )
    target.mkdir(parents=True, exist_ok=True)

    print("ATLAS A33/B33 Reference DEVELOPMENT Replay")
    print(f"  scope: {args.start} -> {args.end}")
    print("  safety: DEVELOPMENT only; protected returns and provider/broker writes forbidden")
    adapter = ReferenceDailyLakeAdapter(settings)
    adapted = adapter.load(
        args.start,
        args.end,
        split_report=args.split_report,
    )
    adapter_report_path = target / "adapter_report.json"
    atomic_write_text(
        adapter_report_path,
        json.dumps(adapted.report, indent=2, sort_keys=True, default=str) + "\n",
    )
    print(
        f"  adapter: PASS rows={len(adapted.bars):,} "
        f"instruments={adapted.bars['instrument_id'].nunique():,}"
    )
    print(f"  adapter source fingerprint: {adapted.report['source_fingerprint']}")
    print(f"  adapter report: {adapter_report_path}")
    if args.source_only:
        print("  performance opened: false (--source-only)")
        return 0

    frame_fingerprint = reference_input_fingerprint(adapted.bars)
    run_token = f"{args.start:%Y%m%d}_{args.end:%Y%m%d}"
    ledger = StrategyTrialLedger(
        Path(args.trial_ledger) if args.trial_ledger else _ledger_path(settings)
    )
    registration_id = f"a33b33.dev.{run_token}.registration"
    _append_once(
        ledger,
        _trial_draft(
            trial_id=registration_id,
            disposition=StrategyTrialDisposition.REGISTERED,
            input_fingerprint=frame_fingerprint,
            run_fingerprint=None,
            performance_opened=False,
            notes=(
                "Frozen nine-policy DEVELOPMENT replay registered before outcome calculation.",
                f"Adapter source fingerprint: {adapted.report['source_fingerprint']}.",
                "No authority promotion is implied by this trial.",
            ),
        ),
    )
    print(f"  trial registered before performance: {registration_id}")

    run = ReferenceStrategyHistoricalRunner().run(adapted.bars)
    opportunities_path = target / "opportunities.jsonl"
    opportunity_sha = _write_opportunities(opportunities_path, run.opportunities)
    summary_payload = run.model_dump(mode="json", exclude={"opportunities"})
    summary_payload["opportunities_path"] = str(opportunities_path.resolve())
    summary_payload["opportunities_sha256"] = opportunity_sha
    summary_payload["adapter_report_path"] = str(adapter_report_path.resolve())
    summary_payload["adapter_source_fingerprint"] = adapted.report["source_fingerprint"]
    summary_path = target / "run_summary.json"
    atomic_write_text(
        summary_path,
        json.dumps(summary_payload, indent=2, sort_keys=True, default=str) + "\n",
    )

    completion_id = f"a33b33.dev.{run_token}.completion"
    _append_once(
        ledger,
        _trial_draft(
            trial_id=completion_id,
            disposition=StrategyTrialDisposition.COMPLETED,
            input_fingerprint=run.input_fingerprint,
            run_fingerprint=run.run_fingerprint,
            performance_opened=True,
            notes=(
                f"Registration record: {registration_id}.",
                f"Adapter source fingerprint: {adapted.report['source_fingerprint']}.",
                f"Opportunity evidence SHA-256: {opportunity_sha}.",
                "Independent-strategy replay only; not an account backtest or authority promotion.",
            ),
        ),
    )

    print(f"  run fingerprint: {run.run_fingerprint}")
    print(f"  opportunities: {len(run.opportunities):,} -> {opportunities_path}")
    print("  strategy summaries (10 bps primary cost):")
    for strategy_id, item in run.summary_by_strategy.items():
        mean_return = item["mean_primary_net_return"]
        rendered = "n/a" if mean_return is None else f"{float(mean_return):+.6%}"
        print(
            f"    {strategy_id}: signals={int(item['signals_fired']):,} "
            f"selected={int(item['selected_independent_replay']):,} "
            f"exited={int(item['exited']):,} mean_net={rendered}"
        )
    print(f"  run summary: {summary_path}")
    print(f"  trials ledger: {ledger.path}")
    print("  authority promotion: none")
    print("  protected return rows read: 0")
    print("  provider/broker/PAPER/LIVE writes: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
