from __future__ import annotations

import functools
import hashlib
import json
import os
import shutil
import time as monotonic_time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from packages.backtesting.b35_development_replay import _SymbolHistory, _canonical_bars
from packages.backtesting.b35_development_source import (
    B35DevelopmentMinuteSource,
    B35DevelopmentUnitBinding,
)
from packages.backtesting.b35_split_evidence import load_b35_split_evidence
from packages.backtesting.reference_v2_lake_adapter import ReferenceV2DailyLakeAdapter
from packages.backtesting.successor_development_engine import (
    SUCCESSOR_STANDALONE_ENGINE_CONTRACT,
    SuccessorMinuteHistory,
    evaluate_successor_daily_standalone,
    evaluate_successor_minute_session,
)
from packages.backtesting.successor_development_outcomes import (
    ACCEPTED_SUCCESSOR_RUNNER_CONTRACT_FINGERPRINT,
    ACCEPTED_SUCCESSOR_SOURCE_VERIFICATION_RUN_FINGERPRINT,
    DEVELOPMENT_END,
    DEVELOPMENT_START,
    SUCCESSOR_DEVELOPMENT_OUTCOME_FINGERPRINT,
    AcceptedSuccessorPreflight,
    outcome_contract_manifest,
    validate_accepted_successor_preflight,
)
from packages.backtesting.successor_parallel import (
    ResearchWorkUnit,
    SuccessorParallelCoordinator,
    validate_completed_group,
)
from packages.backtesting.successor_runner_contract import (
    canonical_sha256,
    daily_group_token,
    minute_symbol_groups,
    successor_policy_routes,
)
from packages.backtesting.successor_spy_benchmark_source import (
    SPY_BENCHMARK_SOURCE_AUDIT_CONTRACT,
    SPY_BENCHMARK_SOURCE_AUDIT_CONTRACT_FINGERPRINT,
    load_accepted_spy_benchmark_source,
)
from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.settings import AtlasSettings, load_settings
from packages.core.successor_execution_profile import (
    SuccessorResearchExecutionProfile,
    resolve_successor_research_execution_profile,
)
from packages.strategies.successor_implementation_bundle import (
    SUCCESSOR_IMPLEMENTATION_BUNDLE_FINGERPRINT,
)
from packages.strategies.successor_practitioner_lab import SUCCESSOR_LAB_FINGERPRINT


SUCCESSOR_DEVELOPMENT_RUNNER_CONTRACT = (
    "atlas-successor-development-runner-v1-standalone-first-restart-safe-no-promotion"
)
SUCCESSOR_DEVELOPMENT_INPUT_CONTRACT = (
    "atlas-successor-development-inputs-v1-scientific-source-bound-operational-materialization"
)
SUCCESSOR_DEVELOPMENT_BENCHMARK_CONTRACT = (
    "atlas-successor-development-benchmark-v1-fixed-groups-profile-equivalence"
)
BENCHMARK_DAILY_TOKENS = ("daily_00", "daily_32")
BENCHMARK_MINUTE_GROUP_INDEXES = (0, 60, 120, 180, 240, 300, 360, 420)
BENCHMARK_WORKER_SHAPES = (4, 6, 8)
SOURCE_HISTORY_POLICY = {
    "accepted_source_start": DEVELOPMENT_START.isoformat(),
    "evaluation_start": DEVELOPMENT_START.isoformat(),
    "predevelopment_warmup_available": False,
    "warmup_policy": "ACCUMULATE_INSIDE_DEVELOPMENT_NO_INVENTED_PREHISTORY",
    "unready_features": "REMAIN_UNAVAILABLE_UNTIL_REQUIRED_HISTORY_EXISTS",
}


class SuccessorDevelopmentRunnerError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PreparedSuccessorInputs:
    input_root: Path
    work_units: tuple[ResearchWorkUnit, ...]
    daily_groups: int
    minute_groups: int
    minute_source_units: int
    benchmark_locator: str
    benchmark_sha256: str
    input_manifest_fingerprint: str


@dataclass(frozen=True, slots=True)
class SuccessorDevelopmentRunIdentity:
    contract: dict[str, object]
    fingerprint: str
    preflight: AcceptedSuccessorPreflight
    split_evidence_fingerprint: str


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, payload: object) -> None:
    atomic_write_text(path, _canonical_json(payload) + "\n")


def _write_parquet_atomic(path: Path, frame: pd.DataFrame) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = unique_temp_path(path)
    try:
        frame.to_parquet(temp, index=False)
        with temp.open("rb+") as handle:
            os.fsync(handle.fileno())
        replace_with_retry(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    return _sha256_file(path)


def _write_jsonl_atomic(path: Path, records: Iterable[dict[str, object]]) -> tuple[str, int, int, Counter[str]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = unique_temp_path(path)
    count = 0
    policies: Counter[str] = Counter()
    try:
        with temp.open("w", encoding="utf-8", newline="") as handle:
            for record in records:
                handle.write(_canonical_json(record) + "\n")
                count += 1
                route = record.get("route")
                if isinstance(route, dict):
                    policies[str(route.get("policy_id") or "UNKNOWN")] += 1
            handle.flush()
            os.fsync(handle.fileno())
        replace_with_retry(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    return _sha256_file(path), path.stat().st_size, count, policies


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _project_locator(project_root: Path, path: Path) -> str:
    root = project_root.resolve()
    resolved = path.resolve()
    if not _inside(resolved, root):
        raise SuccessorDevelopmentRunnerError(f"path escapes project root: {resolved}")
    return resolved.relative_to(root).as_posix()


def _resolve_project_locator(project_root: Path, locator: str) -> Path:
    relative = Path(locator)
    if not locator or relative.is_absolute():
        raise SuccessorDevelopmentRunnerError(f"locator must be project-relative: {locator!r}")
    resolved = (project_root.resolve() / relative).resolve()
    if not _inside(resolved, project_root):
        raise SuccessorDevelopmentRunnerError(f"locator escapes project root: {locator}")
    return resolved


def development_outcome_authority() -> dict[str, object]:
    return {
        "strategy_authority": "RESEARCH",
        "development_outcomes_permitted": True,
        "development_scope": [DEVELOPMENT_START.isoformat(), DEVELOPMENT_END.isoformat()],
        "consumed_master_rows_permitted": 0,
        "future_blind_rows_permitted": 0,
        "provider_calls_permitted": 0,
        "broker_reads_permitted": 0,
        "broker_writes_permitted": 0,
        "paper_authority": False,
        "live_authority": False,
        "promotion_authority": False,
        "conditioning_before_standalone_complete": False,
        "confluence_before_standalone_complete": False,
    }


def build_successor_development_run_identity(project_root: Path) -> SuccessorDevelopmentRunIdentity:
    preflight = validate_accepted_successor_preflight(project_root)
    settings = load_settings(Path(project_root).resolve())
    spy_source = load_accepted_spy_benchmark_source(settings, preflight=preflight)
    split_evidence = load_b35_split_evidence(B35DevelopmentMinuteSource(settings).layout)
    payload: dict[str, object] = {
        "contract": SUCCESSOR_DEVELOPMENT_RUNNER_CONTRACT,
        "accepted_preflight": preflight.scientific_payload(),
        "accepted_runner_contract_fingerprint": ACCEPTED_SUCCESSOR_RUNNER_CONTRACT_FINGERPRINT,
        "accepted_source_verification_run_fingerprint": ACCEPTED_SUCCESSOR_SOURCE_VERIFICATION_RUN_FINGERPRINT,
        "outcome_contract_fingerprint": SUCCESSOR_DEVELOPMENT_OUTCOME_FINGERPRINT,
        "outcome_contract": outcome_contract_manifest(),
        "standalone_engine_contract": SUCCESSOR_STANDALONE_ENGINE_CONTRACT,
        "successor_lab_fingerprint": SUCCESSOR_LAB_FINGERPRINT,
        "successor_implementation_bundle_fingerprint": SUCCESSOR_IMPLEMENTATION_BUNDLE_FINGERPRINT,
        "split_evidence_fingerprint": split_evidence.fingerprint,
        "routes": [route.as_dict() for route in successor_policy_routes()],
        "grouping": {
            "daily": "64_COMPLETE_INSTRUMENT_HISTORY_SHA256_BUCKETS",
            "minute": "ACCEPTED_B35_EXACT_SORTED_NATIVE_PLAN_SYMBOL_TUPLE_GROUPS",
            "execution_profile_changes_membership": False,
        },
        "source_history_policy": SOURCE_HISTORY_POLICY,
        "universe_policy": {
            "daily": "REFERENCE_COMMON_EXECUTABLE_UNIVERSE_ALL_18_ROUTES",
            "minute": "INHERIT_ACCEPTED_B35_NATIVE_PLAN_UNIVERSE_ALL_10_ROUTES",
            "minute_retained_baseline_universe_may_be_rewritten": False,
        },
        "spy_benchmark": {
            "contract": SPY_BENCHMARK_SOURCE_AUDIT_CONTRACT,
            "contract_fingerprint": SPY_BENCHMARK_SOURCE_AUDIT_CONTRACT_FINGERPRINT,
            "source": "ACCEPTED_SPY_SOURCE_AUDIT_MINUTE_PRIMARY_PRE2026_DAILY_REPAIR",
            "source_audit_scientific_fingerprint": spy_source.scientific_fingerprint,
            "benchmark_sha256": spy_source.benchmark_sha256,
        },
        "artifact_order": [
            "run_contract.json",
            "input_manifest.json",
            "groups/*/output.json",
            "groups/*/receipt.json",
            "standalone/*.jsonl",
            "standalone_summary.json",
            "conditioning_later",
            "confluence_later",
        ],
        "benchmark": {
            "daily_tokens": list(BENCHMARK_DAILY_TOKENS),
            "minute_group_indexes": list(BENCHMARK_MINUTE_GROUP_INDEXES),
            "worker_shapes": list(BENCHMARK_WORKER_SHAPES),
            "duckdb_threads_per_worker": 1,
            "identical_scientific_run_fingerprint_required": True,
            "performance_values_reported": False,
        },
        "authority": development_outcome_authority(),
    }
    fingerprint = canonical_sha256(payload)
    payload["fingerprint"] = fingerprint
    return SuccessorDevelopmentRunIdentity(
        contract=payload,
        fingerprint=fingerprint,
        preflight=preflight,
        split_evidence_fingerprint=split_evidence.fingerprint,
    )


def _input_manifest_path(input_root: Path, token: str) -> Path:
    return input_root / "groups" / f"{token}.json"


def _input_unit(
    *, token: str, kind: str, scientific: dict[str, object], operational: dict[str, object], input_root: Path
) -> ResearchWorkUnit:
    scientific_payload = {
        "contract": SUCCESSOR_DEVELOPMENT_INPUT_CONTRACT,
        "kind": kind,
        "token": token,
        **scientific,
    }
    fingerprint = canonical_sha256(scientific_payload)
    manifest = {
        "scientific": scientific_payload,
        "scientific_fingerprint": fingerprint,
        "operational": operational,
    }
    _write_json(_input_manifest_path(input_root, token), manifest)
    return ResearchWorkUnit(token=token, input_fingerprint=fingerprint)


def _serialize_unit(project_root: Path, unit: B35DevelopmentUnitBinding) -> dict[str, object]:
    return {
        "unit_id": unit.unit_id,
        "year": unit.year,
        "month": unit.month,
        "batch_index": unit.batch_index,
        "window_start": unit.window_start.isoformat(),
        "window_end_exclusive": unit.window_end_exclusive.isoformat(),
        "symbols": list(unit.symbols),
        "policy_sha256": unit.policy_sha256,
        "universe_sha256": unit.universe_sha256,
        "canonical_locator": _project_locator(project_root, unit.canonical_path),
        "canonical_sha256": unit.canonical_sha256,
        "checkpoint_locator": _project_locator(project_root, unit.checkpoint_path),
    }


def _deserialize_unit(project_root: Path, payload: dict[str, object]) -> B35DevelopmentUnitBinding:
    return B35DevelopmentUnitBinding(
        unit_id=str(payload["unit_id"]),
        year=int(payload["year"]),
        month=int(payload["month"]),
        batch_index=int(payload["batch_index"]),
        window_start=date.fromisoformat(str(payload["window_start"])),
        window_end_exclusive=date.fromisoformat(str(payload["window_end_exclusive"])),
        symbols=tuple(str(value) for value in payload["symbols"]),
        policy_sha256=str(payload["policy_sha256"]),
        universe_sha256=str(payload["universe_sha256"]),
        canonical_path=_resolve_project_locator(project_root, str(payload["canonical_locator"])),
        canonical_sha256=str(payload["canonical_sha256"]),
        checkpoint_path=_resolve_project_locator(project_root, str(payload["checkpoint_locator"])),
    )


def prepare_successor_development_inputs(
    settings: AtlasSettings,
    *,
    identity: SuccessorDevelopmentRunIdentity,
) -> PreparedSuccessorInputs:
    project_root = settings.project_root.resolve()
    input_root = (
        project_root
        / "data/v2_build/alpaca_sip_v2/derived/strategy_lab/successor_development_inputs"
        / identity.fingerprint[:16]
    ).resolve()
    input_root.mkdir(parents=True, exist_ok=True)

    spy_source = load_accepted_spy_benchmark_source(settings, preflight=identity.preflight)
    identity_spy = identity.contract.get("spy_benchmark")
    if not isinstance(identity_spy, dict):
        raise SuccessorDevelopmentRunnerError("run identity has no SPY benchmark binding")
    if (
        identity_spy.get("source_audit_scientific_fingerprint")
        != spy_source.scientific_fingerprint
        or identity_spy.get("benchmark_sha256") != spy_source.benchmark_sha256
    ):
        raise SuccessorDevelopmentRunnerError("SPY benchmark source audit changed after run identity construction")
    benchmark_path = spy_source.benchmark_path
    benchmark_sha = spy_source.benchmark_sha256
    spy_report = spy_source.scientific

    minute_source = B35DevelopmentMinuteSource(settings)
    minute_plan = minute_source.plan(DEVELOPMENT_START, DEVELOPMENT_END)

    daily_adapter = ReferenceV2DailyLakeAdapter(settings)
    daily_result = daily_adapter.load(DEVELOPMENT_START, DEVELOPMENT_END)
    frame = daily_result.bars.sort_values(
        ["instrument_id", "session_date", "timestamp_utc"], kind="stable"
    ).reset_index(drop=True)
    if int(daily_result.report.get("protected_master_return_rows_read", -1)) != 0:
        raise SuccessorDevelopmentRunnerError("daily DEVELOPMENT preparation read protected master rows")
    if frame.empty:
        raise SuccessorDevelopmentRunnerError("daily DEVELOPMENT source is empty")
    observed_start = min(pd.to_datetime(frame["session_date"], errors="raise").dt.date)
    if observed_start != DEVELOPMENT_START:
        raise SuccessorDevelopmentRunnerError(
            f"accepted daily source start drifted: {observed_start} != {DEVELOPMENT_START}"
        )

    instrument_ids = sorted(str(value) for value in frame["instrument_id"].unique())
    bucket_by_id = {instrument_id: daily_group_token(instrument_id) for instrument_id in instrument_ids}
    frame["_successor_group"] = frame["instrument_id"].astype(str).map(bucket_by_id)
    daily_units: list[ResearchWorkUnit] = []
    for token in sorted(set(bucket_by_id.values())):
        group = frame.loc[frame["_successor_group"] == token].drop(columns=["_successor_group"])
        group = group.sort_values(["instrument_id", "session_date", "timestamp_utc"], kind="stable")
        path = input_root / "daily" / f"{token}.parquet"
        parquet_sha = _write_parquet_atomic(path, group)
        ids = sorted(str(value) for value in group["instrument_id"].unique())
        daily_units.append(
            _input_unit(
                token=token,
                kind="daily",
                scientific={
                    "run_contract_fingerprint": identity.fingerprint,
                    "accepted_source_manifest_fingerprint": identity.preflight.source_manifest_fingerprint,
                    "scope": [DEVELOPMENT_START.isoformat(), DEVELOPMENT_END.isoformat()],
                    "instrument_ids": ids,
                    "row_count": len(group),
                    "materialized_parquet_sha256": parquet_sha,
                    "benchmark_sha256": benchmark_sha,
                    "benchmark_contract_fingerprint": SPY_BENCHMARK_SOURCE_AUDIT_CONTRACT_FINGERPRINT,
                },
                operational={
                    "parquet_locator": _project_locator(project_root, path),
                    "parquet_sha256": parquet_sha,
                    "benchmark_locator": _project_locator(project_root, benchmark_path),
                    "benchmark_sha256": benchmark_sha,
                },
                input_root=input_root,
            )
        )
    if len(daily_units) != 64:
        raise SuccessorDevelopmentRunnerError(f"expected all 64 daily groups, got {len(daily_units)}")

    minute_groups = minute_symbol_groups(minute_plan.units)
    minute_units: list[ResearchWorkUnit] = []
    for index, (symbols, units) in enumerate(minute_groups):
        token = f"minute_{index:04d}"
        minute_units.append(
            _input_unit(
                token=token,
                kind="minute",
                scientific={
                    "run_contract_fingerprint": identity.fingerprint,
                    "accepted_source_manifest_fingerprint": identity.preflight.source_manifest_fingerprint,
                    "split_evidence_fingerprint": identity.split_evidence_fingerprint,
                    "scope": [DEVELOPMENT_START.isoformat(), DEVELOPMENT_END.isoformat()],
                    "symbols": list(symbols),
                    "unit_ids": [unit.unit_id for unit in units],
                    "unit_bindings_sha256": canonical_sha256(
                        [
                            {"unit_id": unit.unit_id, "canonical_sha256": unit.canonical_sha256}
                            for unit in units
                        ]
                    ),
                    "source_fingerprint": minute_plan.source_fingerprint,
                },
                operational={
                    "units": [_serialize_unit(project_root, unit) for unit in units],
                },
                input_root=input_root,
            )
        )
    all_units = tuple(sorted((*daily_units, *minute_units), key=lambda item: item.token))
    summary = {
        "contract": SUCCESSOR_DEVELOPMENT_INPUT_CONTRACT,
        "run_contract_fingerprint": identity.fingerprint,
        "accepted_preflight": identity.preflight.scientific_payload(),
        "daily_source_report_fingerprint": canonical_sha256(
            {
                key: value
                for key, value in daily_result.report.items()
                if key not in {"generated_at_utc", "manifest_path"}
            }
        ),
        "daily_groups": len(daily_units),
        "minute_groups": len(minute_units),
        "minute_source_units": len(minute_plan.units),
        "source_history_policy": SOURCE_HISTORY_POLICY,
        "benchmark_locator": _project_locator(project_root, benchmark_path),
        "benchmark_sha256": benchmark_sha,
        "benchmark_report": spy_report,
        "work_units": [
            {"token": unit.token, "input_fingerprint": unit.input_fingerprint}
            for unit in all_units
        ],
        "authority": development_outcome_authority(),
    }
    summary_fingerprint = canonical_sha256(summary)
    summary["fingerprint"] = summary_fingerprint
    _write_json(input_root / "input_manifest.json", summary)
    return PreparedSuccessorInputs(
        input_root=input_root,
        work_units=all_units,
        daily_groups=len(daily_units),
        minute_groups=len(minute_units),
        minute_source_units=len(minute_plan.units),
        benchmark_locator=_project_locator(project_root, benchmark_path),
        benchmark_sha256=benchmark_sha,
        input_manifest_fingerprint=summary_fingerprint,
    )


def _load_input_manifest(input_root: Path, unit: ResearchWorkUnit) -> dict[str, object]:
    path = _input_manifest_path(input_root, unit.token)
    if not path.is_file():
        raise FileNotFoundError(f"missing successor DEVELOPMENT input manifest: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    scientific = payload.get("scientific")
    if not isinstance(scientific, dict) or canonical_sha256(scientific) != unit.input_fingerprint:
        raise SuccessorDevelopmentRunnerError(f"scientific input fingerprint drifted: {unit.token}")
    if payload.get("scientific_fingerprint") != unit.input_fingerprint:
        raise SuccessorDevelopmentRunnerError(f"input manifest self identity drifted: {unit.token}")
    if scientific.get("token") != unit.token:
        raise SuccessorDevelopmentRunnerError(f"input token drifted: {unit.token}")
    operational = payload.get("operational")
    if not isinstance(operational, dict):
        raise SuccessorDevelopmentRunnerError(f"operational input missing: {unit.token}")
    return payload


def _artifact_result(
    *,
    unit: ResearchWorkUnit,
    kind: str,
    output_root: Path,
    records: Iterable[dict[str, object]],
    source_units: int,
) -> dict[str, object]:
    locator = f"standalone/{unit.token}.jsonl"
    artifact_path = output_root / locator
    sha, bytes_written, count, policies = _write_jsonl_atomic(artifact_path, records)
    return {
        "contract": SUCCESSOR_DEVELOPMENT_RUNNER_CONTRACT,
        "token": unit.token,
        "kind": kind,
        "standalone_artifact_locator": locator,
        "standalone_artifact_sha256": sha,
        "standalone_artifact_bytes": bytes_written,
        "standalone_record_count": count,
        "policy_record_counts": dict(sorted(policies.items())),
        "source_units": source_units,
        "consumed_master_rows_read": 0,
        "future_blind_rows_read": 0,
        "provider_calls": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "paper_authority": False,
        "live_authority": False,
        "promotion_authority": False,
    }


def run_successor_development_group(
    unit: ResearchWorkUnit,
    *,
    project_root: str,
    input_root: str,
    output_root: str,
    duckdb_threads: int,
    scientific_contract_fingerprint: str,
) -> dict[str, object]:
    project = Path(project_root).resolve()
    inputs = Path(input_root).resolve()
    output = Path(output_root).resolve()
    manifest = _load_input_manifest(inputs, unit)
    scientific = manifest["scientific"]
    operational = manifest["operational"]
    if scientific.get("run_contract_fingerprint") != scientific_contract_fingerprint:
        raise SuccessorDevelopmentRunnerError(f"run contract drifted in {unit.token}")
    kind = str(scientific.get("kind") or "")
    if kind == "daily":
        parquet = _resolve_project_locator(project, str(operational["parquet_locator"]))
        benchmark = _resolve_project_locator(project, str(operational["benchmark_locator"]))
        if str(operational.get("parquet_sha256") or "") != str(
            scientific.get("materialized_parquet_sha256") or ""
        ):
            raise SuccessorDevelopmentRunnerError(
                f"daily scientific/operational parquet binding drifted: {unit.token}"
            )
        if str(operational.get("benchmark_sha256") or "") != str(
            scientific.get("benchmark_sha256") or ""
        ):
            raise SuccessorDevelopmentRunnerError(
                f"daily scientific/operational benchmark binding drifted: {unit.token}"
            )
        if scientific.get("benchmark_contract_fingerprint") != SPY_BENCHMARK_SOURCE_AUDIT_CONTRACT_FINGERPRINT:
            raise SuccessorDevelopmentRunnerError(
                f"daily benchmark contract drifted: {unit.token}"
            )
        if _sha256_file(parquet) != str(operational["parquet_sha256"]):
            raise SuccessorDevelopmentRunnerError(f"daily operational input hash drifted: {unit.token}")
        if _sha256_file(benchmark) != str(operational["benchmark_sha256"]):
            raise SuccessorDevelopmentRunnerError("SPY benchmark operational input hash drifted")
        frame = pd.read_parquet(parquet)
        benchmark_frame = pd.read_parquet(benchmark)
        ids = sorted(str(value) for value in frame["instrument_id"].unique())
        if ids != list(scientific["instrument_ids"]) or len(frame) != int(scientific["row_count"]):
            raise SuccessorDevelopmentRunnerError(f"daily operational input content drifted: {unit.token}")
        records = evaluate_successor_daily_standalone(frame, benchmark_frame=benchmark_frame)
        return _artifact_result(
            unit=unit,
            kind=kind,
            output_root=output,
            records=records,
            source_units=len(ids),
        )
    if kind != "minute":
        raise SuccessorDevelopmentRunnerError(f"unsupported successor input kind: {kind}")

    settings = load_settings(project)
    source = B35DevelopmentMinuteSource(settings, duckdb_threads=duckdb_threads)
    split_evidence = load_b35_split_evidence(source.layout)
    if split_evidence.fingerprint != scientific.get("split_evidence_fingerprint"):
        raise SuccessorDevelopmentRunnerError(f"minute split evidence drifted: {unit.token}")
    raw_units = operational.get("units")
    if not isinstance(raw_units, list) or not raw_units:
        raise SuccessorDevelopmentRunnerError(f"minute unit manifest missing: {unit.token}")
    units = tuple(_deserialize_unit(project, item) for item in raw_units)
    if [item.unit_id for item in units] != list(scientific["unit_ids"]):
        raise SuccessorDevelopmentRunnerError(f"minute unit ids drifted: {unit.token}")
    unit_bindings_sha256 = canonical_sha256(
        [
            {"unit_id": item.unit_id, "canonical_sha256": item.canonical_sha256}
            for item in units
        ]
    )
    if unit_bindings_sha256 != scientific.get("unit_bindings_sha256"):
        raise SuccessorDevelopmentRunnerError(f"minute source bindings drifted: {unit.token}")
    symbols = tuple(str(value) for value in scientific["symbols"])
    if any(item.symbols != symbols for item in units):
        raise SuccessorDevelopmentRunnerError(f"minute symbol group drifted: {unit.token}")

    retained_histories = {symbol: _SymbolHistory.empty() for symbol in symbols}
    successor_histories = {symbol: SuccessorMinuteHistory() for symbol in symbols}

    def minute_records():
        for binding in units:
            frame = source.load_unit(
                binding,
                start_session=DEVELOPMENT_START,
                end_session=DEVELOPMENT_END,
            )
            if frame.empty:
                continue
            frame["session_date"] = pd.to_datetime(frame["session_date"], errors="raise").dt.date
            for (symbol, session_date), session_frame in frame.groupby(
                ["symbol", "session_date"], sort=True, observed=True
            ):
                symbol = str(symbol)
                if symbol not in retained_histories or not isinstance(session_date, date):
                    raise SuccessorDevelopmentRunnerError(f"minute group emitted unexpected identity: {unit.token}")
                bars = _canonical_bars(session_frame)
                records = evaluate_successor_minute_session(
                    bars,
                    symbol=symbol,
                    session_date=session_date,
                    retained_history=retained_histories[symbol],
                    successor_history=successor_histories[symbol],
                    symbol_split_dates=split_evidence.split_dates_by_symbol.get(symbol, ()),
                )
                for record in records:
                    yield record

    return _artifact_result(
        unit=unit,
        kind=kind,
        output_root=output,
        records=minute_records(),
        source_units=len(units),
    )


def _group_output_path(output_root: Path, token: str) -> Path:
    return output_root / "groups" / token / "output.json"


def _group_receipt_path(output_root: Path, token: str) -> Path:
    return output_root / "groups" / token / "receipt.json"


def invalidate_corrupt_standalone_reuse(
    output_root: Path,
    units: Sequence[ResearchWorkUnit],
    *,
    scientific_contract_fingerprint: str,
) -> int:
    invalidated = 0
    for unit in units:
        completed = validate_completed_group(
            output_root,
            unit,
            scientific_contract_fingerprint=scientific_contract_fingerprint,
        )
        if completed is None:
            continue
        output_payload = json.loads(_group_output_path(output_root, unit.token).read_text(encoding="utf-8"))
        locator = str(output_payload.get("standalone_artifact_locator") or "")
        artifact = (output_root / locator).resolve()
        valid_locator = bool(locator) and _inside(artifact, output_root)
        expected_sha = str(output_payload.get("standalone_artifact_sha256") or "")
        if not valid_locator or not artifact.is_file() or _sha256_file(artifact) != expected_sha:
            _group_output_path(output_root, unit.token).unlink(missing_ok=True)
            _group_receipt_path(output_root, unit.token).unlink(missing_ok=True)
            if valid_locator:
                artifact.unlink(missing_ok=True)
            invalidated += 1
    return invalidated


def validate_standalone_artifacts(
    output_root: Path,
    units: Sequence[ResearchWorkUnit],
    *,
    scientific_contract_fingerprint: str,
) -> dict[str, object]:
    artifacts: list[dict[str, object]] = []
    aggregate_counts: Counter[str] = Counter()
    for unit in sorted(units, key=lambda item: item.token):
        completed = validate_completed_group(
            output_root,
            unit,
            scientific_contract_fingerprint=scientific_contract_fingerprint,
        )
        if completed is None:
            raise SuccessorDevelopmentRunnerError(f"missing completed group: {unit.token}")
        payload = json.loads(_group_output_path(output_root, unit.token).read_text(encoding="utf-8"))
        locator = str(payload.get("standalone_artifact_locator") or "")
        artifact = (output_root / locator).resolve()
        if not locator or not _inside(artifact, output_root) or not artifact.is_file():
            raise SuccessorDevelopmentRunnerError(f"standalone artifact missing/escaping: {unit.token}")
        actual = _sha256_file(artifact)
        if actual != payload.get("standalone_artifact_sha256"):
            raise SuccessorDevelopmentRunnerError(f"standalone artifact hash drifted: {unit.token}")
        counts = payload.get("policy_record_counts")
        if not isinstance(counts, dict):
            raise SuccessorDevelopmentRunnerError(f"policy record counts missing: {unit.token}")
        aggregate_counts.update({str(key): int(value) for key, value in counts.items()})
        artifacts.append(
            {
                "token": unit.token,
                "kind": payload["kind"],
                "sha256": actual,
                "record_count": int(payload["standalone_record_count"]),
            }
        )
    return {
        "status": "VALIDATED_STANDALONE_COMPLETE",
        "group_count": len(artifacts),
        "record_count": sum(int(item["record_count"]) for item in artifacts),
        "policy_record_counts": dict(sorted(aggregate_counts.items())),
        "artifact_set_fingerprint": canonical_sha256(artifacts),
        "artifacts": artifacts,
    }


def _worker(
    *,
    settings: AtlasSettings,
    inputs: PreparedSuccessorInputs,
    output_root: Path,
    profile: SuccessorResearchExecutionProfile,
    scientific_contract_fingerprint: str,
):
    return functools.partial(
        run_successor_development_group,
        project_root=str(settings.project_root.resolve()),
        input_root=str(inputs.input_root),
        output_root=str(output_root.resolve()),
        duckdb_threads=profile.duckdb_threads_per_worker,
        scientific_contract_fingerprint=scientific_contract_fingerprint,
    )


def run_successor_development_standalone(
    settings: AtlasSettings,
    *,
    identity: SuccessorDevelopmentRunIdentity,
    inputs: PreparedSuccessorInputs,
    execution_profile: SuccessorResearchExecutionProfile,
    units: Sequence[ResearchWorkUnit] | None = None,
    output_root: Path | None = None,
) -> dict[str, object]:
    selected = tuple(units or inputs.work_units)
    root = output_root or (
        settings.project_root.resolve()
        / "data/v2_build/alpaca_sip_v2/derived/strategy_lab/successor_development"
        / identity.fingerprint[:16]
    )
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    _write_json(root / "run_contract.json", identity.contract)
    source_input_manifest_path = inputs.input_root / "input_manifest.json"
    if not source_input_manifest_path.is_file():
        raise SuccessorDevelopmentRunnerError(
            f"prepared input manifest is missing: {source_input_manifest_path}"
        )
    input_manifest = json.loads(source_input_manifest_path.read_text(encoding="utf-8"))
    if not isinstance(input_manifest, dict):
        raise SuccessorDevelopmentRunnerError("prepared input manifest is not a JSON object")
    declared_input_fingerprint = str(input_manifest.get("fingerprint") or "")
    unsigned_input_manifest = dict(input_manifest)
    unsigned_input_manifest.pop("fingerprint", None)
    actual_input_fingerprint = canonical_sha256(unsigned_input_manifest)
    if (
        declared_input_fingerprint != inputs.input_manifest_fingerprint
        or actual_input_fingerprint != inputs.input_manifest_fingerprint
    ):
        raise SuccessorDevelopmentRunnerError("prepared input manifest fingerprint drifted")
    _write_json(root / "input_manifest.json", input_manifest)
    invalidated = invalidate_corrupt_standalone_reuse(
        root,
        selected,
        scientific_contract_fingerprint=identity.fingerprint,
    )
    coordinator = SuccessorParallelCoordinator(execution_profile=execution_profile)
    run_summary = coordinator.run(
        selected,
        worker=_worker(
            settings=settings,
            inputs=inputs,
            output_root=root,
            profile=execution_profile,
            scientific_contract_fingerprint=identity.fingerprint,
        ),
        output_root=root,
        scientific_contract_fingerprint=identity.fingerprint,
    )
    standalone = validate_standalone_artifacts(
        root,
        selected,
        scientific_contract_fingerprint=identity.fingerprint,
    )
    summary = {
        "status": "COMPLETE_STANDALONE_ONLY",
        "contract": SUCCESSOR_DEVELOPMENT_RUNNER_CONTRACT,
        "run_contract_fingerprint": identity.fingerprint,
        "source_preflight": identity.preflight.scientific_payload(),
        "input_manifest_fingerprint": inputs.input_manifest_fingerprint,
        "parallel_run": run_summary,
        "standalone": standalone,
        "corrupt_reuse_invalidated": invalidated,
        "conditioning_opened": False,
        "confluence_opened": False,
        "authority": development_outcome_authority(),
    }
    _write_json(root / "standalone_summary.json", summary)
    return summary


def _benchmark_units(inputs: PreparedSuccessorInputs) -> tuple[ResearchWorkUnit, ...]:
    by_token = {unit.token: unit for unit in inputs.work_units}
    tokens = list(BENCHMARK_DAILY_TOKENS)
    tokens.extend(f"minute_{index:04d}" for index in BENCHMARK_MINUTE_GROUP_INDEXES)
    missing = [token for token in tokens if token not in by_token]
    if missing:
        raise SuccessorDevelopmentRunnerError(
            "benchmark frozen group tokens unavailable: " + ", ".join(missing)
        )
    return tuple(by_token[token] for token in tokens)


def _profile_with_workers(
    base: SuccessorResearchExecutionProfile, workers: int
) -> SuccessorResearchExecutionProfile:
    usable = max(1, base.logical_cpus - base.reserved_logical_cpus)
    if workers > usable:
        raise SuccessorDevelopmentRunnerError(
            f"benchmark shape {workers}x1 exceeds reserved CPU envelope {usable}"
        )
    return SuccessorResearchExecutionProfile(
        logical_cpus=base.logical_cpus,
        total_memory_bytes=base.total_memory_bytes,
        reserved_logical_cpus=base.reserved_logical_cpus,
        workers=workers,
        duckdb_threads_per_worker=1,
        aggregate_worker_threads=workers,
        profile_source="frozen_successor_benchmark_shape",
        thermal_headroom_policy=base.thermal_headroom_policy,
    )


def run_successor_development_benchmark(
    settings: AtlasSettings,
    *,
    identity: SuccessorDevelopmentRunIdentity,
    inputs: PreparedSuccessorInputs,
) -> dict[str, object]:
    base = resolve_successor_research_execution_profile()
    selected = _benchmark_units(inputs)
    benchmark_root = (
        settings.project_root.resolve()
        / "data/v2_build/alpaca_sip_v2/derived/strategy_lab/successor_development_benchmark"
        / identity.fingerprint[:16]
    )
    shapes: list[dict[str, object]] = []
    for workers in BENCHMARK_WORKER_SHAPES:
        if workers > max(1, base.logical_cpus - base.reserved_logical_cpus):
            continue
        profile = _profile_with_workers(base, workers)
        shape_root = benchmark_root / f"{workers}x1"
        # Benchmark compares fresh execution shapes, never restart reuse timing.
        shutil.rmtree(shape_root, ignore_errors=True)
        started = monotonic_time.monotonic()
        summary = run_successor_development_standalone(
            settings,
            identity=identity,
            inputs=inputs,
            execution_profile=profile,
            units=selected,
            output_root=shape_root,
        )
        elapsed = monotonic_time.monotonic() - started
        shapes.append(
            {
                "workers": workers,
                "duckdb_threads_per_worker": 1,
                "elapsed_seconds": elapsed,
                "scientific_run_fingerprint": summary["parallel_run"]["run_fingerprint"],
                "artifact_set_fingerprint": summary["standalone"]["artifact_set_fingerprint"],
                "record_count": summary["standalone"]["record_count"],
            }
        )
    if len(shapes) < 2:
        raise SuccessorDevelopmentRunnerError("benchmark requires at least two valid worker shapes")
    run_fingerprints = {str(item["scientific_run_fingerprint"]) for item in shapes}
    artifact_fingerprints = {str(item["artifact_set_fingerprint"]) for item in shapes}
    record_counts = {int(item["record_count"]) for item in shapes}
    if len(run_fingerprints) != 1 or len(artifact_fingerprints) != 1 or len(record_counts) != 1:
        raise SuccessorDevelopmentRunnerError("benchmark execution shapes are not scientifically equivalent")
    fastest = min(shapes, key=lambda item: float(item["elapsed_seconds"]))
    report = {
        "status": "PASS_EXACT_EQUIVALENCE",
        "contract": SUCCESSOR_DEVELOPMENT_BENCHMARK_CONTRACT,
        "run_contract_fingerprint": identity.fingerprint,
        "frozen_group_tokens": [unit.token for unit in selected],
        "shapes": shapes,
        "equivalent_scientific_run_fingerprint": next(iter(run_fingerprints)),
        "equivalent_artifact_set_fingerprint": next(iter(artifact_fingerprints)),
        "record_count": next(iter(record_counts)),
        "fastest_shape_by_wall_clock": f"{fastest['workers']}x1",
        "thermal_acceptance": "OPERATOR_CONFIRMATION_REQUIRED_BEFORE_LONG_RUN",
        "performance_values_reported": False,
        "authority": development_outcome_authority(),
    }
    _write_json(benchmark_root / "benchmark_summary.json", report)
    return report
