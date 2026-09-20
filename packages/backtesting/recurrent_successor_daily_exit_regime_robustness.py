from __future__ import annotations

import math
import statistics
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Sequence

from packages.backtesting.recurrent_successor_daily_exit_confirmation_contract import (
    CANDIDATE_EXIT_POLICIES,
    RECURRENT_SUCCESSOR_DAILY_EXIT_CONFIRMATION_CONTRACT_FINGERPRINT,
)
from packages.backtesting.recurrent_successor_daily_exit_regime_robustness_contract import (
    ANNUAL_REGIME_WINDOWS,
    AUTHORITY,
    RECURRENT_SUCCESSOR_DAILY_EXIT_REGIME_ROBUSTNESS_CONTRACT,
    RECURRENT_SUCCESSOR_DAILY_EXIT_REGIME_ROBUSTNESS_CONTRACT_FINGERPRINT,
    SOURCE_2026_CONFIRMATION_RUN_FINGERPRINT,
)
from packages.backtesting.recurrent_successor_daily_exit_sweep import (
    _load_json,
    _simulate_policy_worker,
    _stable_hash,
    _write_json,
    load_daily_exit_cases,
    resolve_daily_exit_sweep_workers,
)


class RecurrentSuccessorDailyExitRegimeRobustnessError(RuntimeError):
    pass


def _source_2026_confirmation_summary(project_root: Path) -> dict[str, object]:
    root = (
        Path(project_root).resolve()
        / "data"
        / "research"
        / "recurrent_successor_daily_exit_confirmation"
        / RECURRENT_SUCCESSOR_DAILY_EXIT_CONFIRMATION_CONTRACT_FINGERPRINT[:16]
        / SOURCE_2026_CONFIRMATION_RUN_FINGERPRINT[:16]
    )
    summary_path = root / "confirmation_summary.json"
    if not summary_path.is_file():
        raise RecurrentSuccessorDailyExitRegimeRobustnessError(
            "accepted 2026 confirmation summary is missing"
        )
    summary = _load_json(summary_path)
    if (
        summary.get("status")
        != "COMPLETE_FORWARD_DAILY_EXIT_CONFIRMATION_DIAGNOSTIC"
    ):
        raise RecurrentSuccessorDailyExitRegimeRobustnessError(
            "2026 confirmation is not complete"
        )
    if summary.get("run_fingerprint") != SOURCE_2026_CONFIRMATION_RUN_FINGERPRINT:
        raise RecurrentSuccessorDailyExitRegimeRobustnessError(
            "2026 confirmation run fingerprint drifted"
        )
    if (
        summary.get("contract_fingerprint")
        != RECURRENT_SUCCESSOR_DAILY_EXIT_CONFIRMATION_CONTRACT_FINGERPRINT
    ):
        raise RecurrentSuccessorDailyExitRegimeRobustnessError(
            "2026 confirmation contract fingerprint drifted"
        )
    results = summary.get("candidate_results")
    if not isinstance(results, list):
        raise RecurrentSuccessorDailyExitRegimeRobustnessError(
            "2026 confirmation candidate results are missing"
        )
    observed = {
        (float(item["stop_fraction"]), float(item["target_fraction"]))
        for item in results
        if isinstance(item, dict)
    }
    missing = [pair for pair in CANDIDATE_EXIT_POLICIES if pair not in observed]
    if missing:
        raise RecurrentSuccessorDailyExitRegimeRobustnessError(
            f"2026 confirmation candidate rows are missing: {missing}"
        )
    return summary


def _summarize_candidate(
    stop_fraction: float,
    target_fraction: float,
    regime_results: Sequence[dict[str, object]],
) -> dict[str, object]:
    rows = [
        item
        for item in regime_results
        if math.isclose(float(item["stop_fraction"]), stop_fraction)
        and math.isclose(float(item["target_fraction"]), target_fraction)
        and item.get("status") == "COMPLETE"
    ]
    returns = [float(item["total_return"]) for item in rows]
    marked_dds = [
        float(item["maximum_marked_equity_drawdown"])
        for item in rows
    ]
    return {
        "stop_fraction": stop_fraction,
        "target_fraction": target_fraction,
        "regimes_with_usable_cases": len(rows),
        "positive_regimes": sum(value > 0.0 for value in returns),
        "negative_regimes": sum(value < 0.0 for value in returns),
        "flat_regimes": sum(value == 0.0 for value in returns),
        "median_regime_return": (
            None if not returns else statistics.median(returns)
        ),
        "mean_regime_return": (
            None if not returns else statistics.fmean(returns)
        ),
        "best_regime_return": None if not returns else max(returns),
        "worst_regime_return": None if not returns else min(returns),
        "median_marked_drawdown": (
            None if not marked_dds else statistics.median(marked_dds)
        ),
        "worst_marked_drawdown": (
            None if not marked_dds else min(marked_dds)
        ),
        "completed_positions": sum(
            int(item["completed_positions"]) for item in rows
        ),
    }


def run_recurrent_successor_daily_exit_regime_robustness(
    project_root: Path,
    *,
    initial_equity: float,
    policy_ids: Sequence[str] = (),
    output_root: Path | None = None,
    duckdb_threads: int | None = None,
    workers: int | None = None,
) -> dict[str, object]:
    if not math.isfinite(initial_equity) or initial_equity <= 0.0:
        raise RecurrentSuccessorDailyExitRegimeRobustnessError(
            "initial equity must be finite and positive"
        )

    project = Path(project_root).resolve()
    source_2026 = _source_2026_confirmation_summary(project)

    full_start = min(item[1] for item in ANNUAL_REGIME_WINDOWS)
    full_end = max(item[2] for item in ANNUAL_REGIME_WINDOWS)
    print(
        "daily exit regime robustness: loading accepted daily cases once for "
        f"{full_start} -> {full_end}",
        flush=True,
    )
    cases, source = load_daily_exit_cases(
        project,
        start_session=full_start,
        end_session=full_end,
        policy_ids=policy_ids,
        duckdb_threads=duckdb_threads,
    )

    run_identity = {
        "contract_fingerprint": (
            RECURRENT_SUCCESSOR_DAILY_EXIT_REGIME_ROBUSTNESS_CONTRACT_FINGERPRINT
        ),
        "source_2026_confirmation_report_fingerprint": source_2026.get(
            "report_fingerprint"
        ),
        "source": source,
        "initial_equity": initial_equity,
        "policy_ids": sorted(set(str(value) for value in policy_ids)),
        "annual_regime_windows": ANNUAL_REGIME_WINDOWS,
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
            / "recurrent_successor_daily_exit_regime_robustness"
            / RECURRENT_SUCCESSOR_DAILY_EXIT_REGIME_ROBUSTNESS_CONTRACT_FINGERPRINT[:16]
            / run_fingerprint[:16]
        )
    )
    root.mkdir(parents=True, exist_ok=True)
    _write_json(
        root / "contract.json",
        {
            "contract": RECURRENT_SUCCESSOR_DAILY_EXIT_REGIME_ROBUSTNESS_CONTRACT,
            "contract_fingerprint": (
                RECURRENT_SUCCESSOR_DAILY_EXIT_REGIME_ROBUSTNESS_CONTRACT_FINGERPRINT
            ),
            "source_2026_confirmation_run_fingerprint": (
                SOURCE_2026_CONFIRMATION_RUN_FINGERPRINT
            ),
            "candidate_exit_policies": CANDIDATE_EXIT_POLICIES,
            "annual_regime_windows": ANNUAL_REGIME_WINDOWS,
            "authority": AUTHORITY,
        },
    )

    regimes: list[dict[str, object]] = []
    tasks: list[
        tuple[str, tuple[object, ...], float, float, Path]
    ] = []

    for regime_id, start_session, end_session in ANNUAL_REGIME_WINDOWS:
        regime_cases = tuple(
            case
            for case in cases
            if start_session <= case.opportunity.signal_session <= end_session
        )
        if not regime_cases:
            for stop_fraction, target_fraction in CANDIDATE_EXIT_POLICIES:
                regimes.append(
                    {
                        "regime_id": regime_id,
                        "start_session": start_session,
                        "end_session": end_session,
                        "status": "NO_USABLE_CASES",
                        "usable_cases": 0,
                        "stop_fraction": stop_fraction,
                        "target_fraction": target_fraction,
                    }
                )
            continue
        for stop_fraction, target_fraction in CANDIDATE_EXIT_POLICIES:
            tasks.append(
                (
                    regime_id,
                    regime_cases,
                    stop_fraction,
                    target_fraction,
                    root / regime_id,
                )
            )

    worker_count, execution_profile = resolve_daily_exit_sweep_workers(workers)
    worker_count = min(worker_count, max(1, len(tasks)))
    execution_profile = {
        **execution_profile,
        "workers": worker_count,
        "regime_policy_jobs": len(tasks),
        "case_load_reuse": "ONE_PARENT_LOAD_SUBSET_BY_SIGNAL_SESSION",
    }
    print(
        "daily exit regime robustness: "
        f"{len(tasks)} regime-policy jobs / {worker_count} workers / "
        f"{len(cases):,} total usable cases",
        flush=True,
    )

    if tasks:
        with ProcessPoolExecutor(max_workers=worker_count) as pool:
            futures = {
                pool.submit(
                    _simulate_policy_worker,
                    tuple(regime_cases),
                    initial_equity,
                    stop_fraction,
                    target_fraction,
                    regime_root,
                ): (
                    regime_id,
                    regime_cases,
                    stop_fraction,
                    target_fraction,
                )
                for (
                    regime_id,
                    regime_cases,
                    stop_fraction,
                    target_fraction,
                    regime_root,
                ) in tasks
            }
            completed = 0
            for future in as_completed(futures):
                (
                    regime_id,
                    regime_cases,
                    stop_fraction,
                    target_fraction,
                ) = futures[future]
                result = future.result()
                completed += 1
                regime_meta = next(
                    item for item in ANNUAL_REGIME_WINDOWS if item[0] == regime_id
                )
                row = {
                    "regime_id": regime_id,
                    "start_session": regime_meta[1],
                    "end_session": regime_meta[2],
                    "status": "COMPLETE",
                    "usable_cases": len(regime_cases),
                    **result,
                }
                regimes.append(row)
                print(
                    f"  completed {completed}/{len(tasks)}: {regime_id} "
                    f"STOP {stop_fraction:.0%} / TARGET {target_fraction:.0%} "
                    f"return={float(result['total_return']):.2%}; "
                    f"marked DD="
                    f"{float(result['maximum_marked_equity_drawdown']):.2%}; "
                    f"trades={int(result['completed_positions']):,}",
                    flush=True,
                )

    regimes = sorted(
        regimes,
        key=lambda item: (
            str(item["regime_id"]),
            float(item["stop_fraction"]),
            float(item["target_fraction"]),
        ),
    )
    candidate_summary = [
        _summarize_candidate(stop, target, regimes)
        for stop, target in CANDIDATE_EXIT_POLICIES
    ]

    report: dict[str, object] = {
        "status": "COMPLETE_RETROSPECTIVE_DAILY_EXIT_REGIME_ROBUSTNESS",
        "contract": RECURRENT_SUCCESSOR_DAILY_EXIT_REGIME_ROBUSTNESS_CONTRACT,
        "contract_fingerprint": (
            RECURRENT_SUCCESSOR_DAILY_EXIT_REGIME_ROBUSTNESS_CONTRACT_FINGERPRINT
        ),
        "run_fingerprint": run_fingerprint,
        "source_2026_confirmation_run_fingerprint": (
            SOURCE_2026_CONFIRMATION_RUN_FINGERPRINT
        ),
        "source_2026_confirmation_report_fingerprint": source_2026.get(
            "report_fingerprint"
        ),
        "initial_equity_per_regime": initial_equity,
        "execution_profile": execution_profile,
        "total_loaded_usable_cases": len(cases),
        "regime_results": regimes,
        "candidate_summary": candidate_summary,
        "interpretation": {
            "retrospective_only": True,
            "candidate_parameters_unchanged": True,
            "automatic_winner_selected": False,
            "automatic_promotion": False,
            "purpose": (
                "CHARACTERIZE_STATIC_EXIT_REGIME_DEPENDENCE_BEFORE_DYNAMIC_EXIT_V1"
            ),
        },
        "authority": AUTHORITY,
    }
    report["report_fingerprint"] = _stable_hash(report)
    _write_json(root / "regime_robustness_summary.json", report)
    return report
