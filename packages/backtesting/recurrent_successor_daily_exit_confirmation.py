from __future__ import annotations

import math
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Sequence

from packages.backtesting.recurrent_successor_daily_exit_confirmation_contract import (
    AUTHORITY,
    CANDIDATE_EXIT_POLICIES,
    FORWARD_CONFIRMATION_WINDOW,
    RECURRENT_SUCCESSOR_DAILY_EXIT_CONFIRMATION_CONTRACT,
    RECURRENT_SUCCESSOR_DAILY_EXIT_CONFIRMATION_CONTRACT_FINGERPRINT,
    SOURCE_2025_SWEEP_RUN_FINGERPRINT,
    TUNING_WINDOW,
)
from packages.backtesting.recurrent_successor_daily_exit_sweep import (
    _load_json,
    _simulate_policy,
    _simulate_policy_worker,
    _stable_hash,
    _write_json,
    load_daily_exit_cases,
    resolve_daily_exit_sweep_workers,
)
from packages.backtesting.recurrent_successor_daily_exit_sweep_contract import (
    RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT_FINGERPRINT,
)


class RecurrentSuccessorDailyExitConfirmationError(RuntimeError):
    pass


def _source_2025_sweep_summary(project_root: Path) -> dict[str, object]:
    root = (
        Path(project_root).resolve()
        / "data"
        / "research"
        / "recurrent_successor_daily_exit_sweep"
        / RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT_FINGERPRINT[:16]
        / SOURCE_2025_SWEEP_RUN_FINGERPRINT[:16]
    )
    summary_path = root / "sweep_summary.json"
    if not summary_path.is_file():
        raise RecurrentSuccessorDailyExitConfirmationError(
            "accepted 2025 exit-sweep summary is missing; run the frozen 2025 sweep first"
        )
    summary = _load_json(summary_path)
    if (
        summary.get("status")
        != "COMPLETE_DAILY_EXIT_POLICY_SWEEP_DIAGNOSTIC"
    ):
        raise RecurrentSuccessorDailyExitConfirmationError(
            "2025 exit sweep is not complete"
        )
    if summary.get("run_fingerprint") != SOURCE_2025_SWEEP_RUN_FINGERPRINT:
        raise RecurrentSuccessorDailyExitConfirmationError(
            "2025 exit-sweep run fingerprint drifted"
        )
    if (
        summary.get("contract_fingerprint")
        != RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT_FINGERPRINT
    ):
        raise RecurrentSuccessorDailyExitConfirmationError(
            "2025 exit-sweep contract fingerprint drifted"
        )
    scope = summary.get("scope")
    if not isinstance(scope, dict):
        raise RecurrentSuccessorDailyExitConfirmationError(
            "2025 exit-sweep scope is missing"
        )
    if (
        str(scope.get("start_session")) != TUNING_WINDOW[0].isoformat()
        or str(scope.get("end_session")) != TUNING_WINDOW[1].isoformat()
    ):
        raise RecurrentSuccessorDailyExitConfirmationError(
            "2025 exit-sweep tuning window drifted"
        )
    policy_results = summary.get("policy_results")
    if not isinstance(policy_results, list):
        raise RecurrentSuccessorDailyExitConfirmationError(
            "2025 exit-sweep policy results are missing"
        )
    observed = {
        (float(item["stop_fraction"]), float(item["target_fraction"]))
        for item in policy_results
        if isinstance(item, dict)
    }
    missing = [
        pair for pair in CANDIDATE_EXIT_POLICIES if pair not in observed
    ]
    if missing:
        raise RecurrentSuccessorDailyExitConfirmationError(
            f"2025 exit-sweep candidate rows are missing: {missing}"
        )
    return summary


def run_recurrent_successor_daily_exit_confirmation(
    project_root: Path,
    *,
    initial_equity: float,
    policy_ids: Sequence[str] = (),
    output_root: Path | None = None,
    duckdb_threads: int | None = None,
    workers: int | None = None,
) -> dict[str, object]:
    if not math.isfinite(initial_equity) or initial_equity <= 0.0:
        raise RecurrentSuccessorDailyExitConfirmationError(
            "initial equity must be finite and positive"
        )

    project = Path(project_root).resolve()
    source_2025 = _source_2025_sweep_summary(project)
    start_session, end_session = FORWARD_CONFIRMATION_WINDOW

    print(
        "daily exit confirmation: loading chronologically post-tuning "
        f"DEVELOPMENT window {start_session} -> {end_session}",
        flush=True,
    )
    cases, source = load_daily_exit_cases(
        project,
        start_session=start_session,
        end_session=end_session,
        policy_ids=policy_ids,
        duckdb_threads=duckdb_threads,
    )

    run_identity = {
        "contract_fingerprint": (
            RECURRENT_SUCCESSOR_DAILY_EXIT_CONFIRMATION_CONTRACT_FINGERPRINT
        ),
        "source_2025_sweep_report_fingerprint": source_2025.get(
            "report_fingerprint"
        ),
        "source": source,
        "initial_equity": initial_equity,
        "policy_ids": sorted(set(str(value) for value in policy_ids)),
        "confirmation_window": [
            start_session.isoformat(),
            end_session.isoformat(),
        ],
        "candidate_exit_policies": CANDIDATE_EXIT_POLICIES,
    }
    run_fingerprint = _stable_hash(run_identity)

    root = (
        Path(output_root).resolve()
        if output_root is not None
        else (
            project
            / "data"
            / "research"
            / "recurrent_successor_daily_exit_confirmation"
            / RECURRENT_SUCCESSOR_DAILY_EXIT_CONFIRMATION_CONTRACT_FINGERPRINT[:16]
            / run_fingerprint[:16]
        )
    )
    root.mkdir(parents=True, exist_ok=True)

    _write_json(
        root / "contract.json",
        {
            "contract": RECURRENT_SUCCESSOR_DAILY_EXIT_CONFIRMATION_CONTRACT,
            "contract_fingerprint": (
                RECURRENT_SUCCESSOR_DAILY_EXIT_CONFIRMATION_CONTRACT_FINGERPRINT
            ),
            "source_2025_sweep_run_fingerprint": (
                SOURCE_2025_SWEEP_RUN_FINGERPRINT
            ),
            "candidate_exit_policies": CANDIDATE_EXIT_POLICIES,
            "confirmation_window": [
                start_session,
                end_session,
            ],
            "authority": AUTHORITY,
        },
    )

    worker_count, execution_profile = resolve_daily_exit_sweep_workers(workers)
    worker_count = min(worker_count, len(CANDIDATE_EXIT_POLICIES))
    execution_profile = {
        **execution_profile,
        "workers": worker_count,
        "candidate_jobs": len(CANDIDATE_EXIT_POLICIES),
    }

    print(
        "daily exit confirmation: "
        f"{len(CANDIDATE_EXIT_POLICIES)} frozen candidates / "
        f"{worker_count} policy workers / "
        f"{len(cases):,} usable daily LONG cases",
        flush=True,
    )

    results: list[dict[str, object]] = []
    if worker_count == 1:
        for index, (stop_fraction, target_fraction) in enumerate(
            CANDIDATE_EXIT_POLICIES,
            start=1,
        ):
            print(
                f"  candidate {index}/{len(CANDIDATE_EXIT_POLICIES)}: "
                f"stop={stop_fraction:.0%} target={target_fraction:.0%}",
                flush=True,
            )
            results.append(
                _simulate_policy(
                    cases,
                    initial_equity=initial_equity,
                    stop_fraction=stop_fraction,
                    target_fraction=target_fraction,
                    output_root=root,
                )
            )
    else:
        with ProcessPoolExecutor(max_workers=worker_count) as pool:
            futures = {
                pool.submit(
                    _simulate_policy_worker,
                    tuple(cases),
                    initial_equity,
                    stop_fraction,
                    target_fraction,
                    root,
                ): (index, stop_fraction, target_fraction)
                for index, (stop_fraction, target_fraction) in enumerate(
                    CANDIDATE_EXIT_POLICIES,
                    start=1,
                )
            }
            completed = 0
            for future in as_completed(futures):
                index, stop_fraction, target_fraction = futures[future]
                result = future.result()
                results.append(result)
                completed += 1
                print(
                    f"  confirmation complete {completed}/"
                    f"{len(CANDIDATE_EXIT_POLICIES)} "
                    f"(candidate {index}: stop={stop_fraction:.0%}, "
                    f"target={target_fraction:.0%}) "
                    f"return={float(result['total_return']):.2%}; "
                    f"marked DD="
                    f"{float(result['maximum_marked_equity_drawdown']):.2%}; "
                    f"trades={int(result['completed_positions']):,}",
                    flush=True,
                )

    results = sorted(
        results,
        key=lambda item: (
            float(item["stop_fraction"]),
            float(item["target_fraction"]),
        ),
    )
    report: dict[str, object] = {
        "status": "COMPLETE_FORWARD_DAILY_EXIT_CONFIRMATION_DIAGNOSTIC",
        "contract": RECURRENT_SUCCESSOR_DAILY_EXIT_CONFIRMATION_CONTRACT,
        "contract_fingerprint": (
            RECURRENT_SUCCESSOR_DAILY_EXIT_CONFIRMATION_CONTRACT_FINGERPRINT
        ),
        "run_fingerprint": run_fingerprint,
        "source_2025_sweep_run_fingerprint": SOURCE_2025_SWEEP_RUN_FINGERPRINT,
        "source_2025_sweep_report_fingerprint": source_2025.get(
            "report_fingerprint"
        ),
        "tuning_window": [
            TUNING_WINDOW[0],
            TUNING_WINDOW[1],
        ],
        "confirmation_window": [
            start_session,
            end_session,
        ],
        "initial_equity": initial_equity,
        "usable_daily_long_cases": len(cases),
        "execution_profile": execution_profile,
        "candidate_results": results,
        "interpretation": {
            "chronologically_after_tuning_window": True,
            "development_only": True,
            "automatic_winner_selected": False,
            "automatic_promotion": False,
            "backward_regime_robustness_still_required": True,
            "prospective_shadow_or_paper_still_required": True,
        },
        "authority": AUTHORITY,
    }
    report["report_fingerprint"] = _stable_hash(report)
    _write_json(root / "confirmation_summary.json", report)
    return report
