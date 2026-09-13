from __future__ import annotations

import argparse
import functools
import hashlib
import json
import os
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.b35_development_source import B35DevelopmentMinuteSource
from packages.backtesting.reference_v2_lake_adapter import ReferenceV2DailyLakeAdapter
from packages.backtesting.successor_parallel import ResearchWorkUnit, SuccessorParallelCoordinator
from packages.backtesting.successor_runner_contract import (
    DAILY_SOURCE_ID,
    MINUTE_SOURCE_ID,
    SUCCESSOR_RUNNER_CONTRACT,
    build_source_binding_payload,
    build_successor_runner_contract,
    canonical_sha256,
    frozen_authority_contract,
    minute_symbol_groups,
)
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import load_settings
from packages.core.successor_execution_profile import resolve_successor_research_execution_profile
from packages.strategies.successor_practitioner_lab import DEVELOPMENT_END, DEVELOPMENT_START


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


def _resolve_source_locator(project_root: Path, locator: str) -> Path:
    relative = Path(locator)
    if not locator or relative.is_absolute():
        raise RuntimeError(f"successor source locator must be project-relative: {locator!r}")
    root = project_root.resolve()
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"successor source locator escapes project root: {locator}") from exc
    return resolved


def verify_source_binding_unit(
    unit: ResearchWorkUnit,
    *,
    input_root: str,
    project_root: str,
) -> dict[str, object]:
    """Hash source files only; never parse bars, signals, returns, or outcomes."""
    path = Path(input_root) / f"{unit.token}.json"
    if not path.is_file():
        raise FileNotFoundError(f"missing successor source-binding input: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if canonical_sha256(payload) != unit.input_fingerprint:
        raise RuntimeError(f"successor source-binding input fingerprint drifted: {unit.token}")
    if payload.get("contract") != SUCCESSOR_RUNNER_CONTRACT or payload.get("token") != unit.token:
        raise RuntimeError(f"successor source-binding input identity drifted: {unit.token}")
    records = payload.get("files")
    if not isinstance(records, list) or not records:
        raise RuntimeError(f"successor source-binding input has no files: {unit.token}")
    source_root = Path(project_root).resolve()
    bytes_verified = 0
    hashes: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            raise RuntimeError("successor source-binding file record malformed")
        source_path = _resolve_source_locator(source_root, str(record.get("relative_path") or ""))
        expected = str(record.get("sha256") or "")
        if not source_path.is_file():
            raise FileNotFoundError(f"missing successor source file: {source_path}")
        actual = _sha256_file(source_path)
        if actual != expected:
            raise RuntimeError(f"successor source SHA-256 drifted: {source_path}")
        bytes_verified += source_path.stat().st_size
        hashes.append(actual)
    return {
        "status": "SOURCE_BINDING_VERIFIED",
        "token": unit.token,
        "source_id": payload["source_id"],
        "files_verified": len(records),
        "bytes_verified": bytes_verified,
        "verified_hashes_sha256": canonical_sha256(sorted(hashes)),
        "outcome_rows_opened": 0,
        "authority": frozen_authority_contract(),
    }


def _daily_bindings(adapter: ReferenceV2DailyLakeAdapter) -> tuple[str, list[tuple[str, Path, str]], dict[str, object]]:
    manifest_path, manifest = adapter._manifest(None)
    adapter._scope(date.fromisoformat(DEVELOPMENT_START), date.fromisoformat(DEVELOPMENT_END), manifest)
    fingerprint = str(manifest["source_fingerprint"])
    expected_root = (adapter.layout.derived / adapter._VIEW_DIRECTORY / fingerprint[:16]).resolve()
    records = manifest.get("partitions")
    if not isinstance(records, list) or not records:
        raise RuntimeError("successor daily manifest has no partitions")
    bindings: list[tuple[str, Path, str]] = []
    seen_years: set[int] = set()
    rows = 0
    for record in records:
        if not isinstance(record, dict):
            raise RuntimeError("successor daily partition record malformed")
        year = int(record["year"])
        source_path = Path(str(record["path"])).resolve()
        expected_hash = str(record["sha256"])
        if year in seen_years:
            raise RuntimeError("successor daily partition year duplicated")
        seen_years.add(year)
        try:
            source_path.relative_to(expected_root)
        except ValueError as exc:
            raise RuntimeError("successor daily partition escapes exact generation") from exc
        if source_path.parent.name != f"year={year:04d}" or not source_path.is_file():
            raise RuntimeError(f"successor daily exact partition path drifted: {source_path}")
        if len(expected_hash) != 64:
            raise RuntimeError("successor daily partition SHA-256 malformed")
        rows += int(record["rows"])
        bindings.append((f"daily_source_{year:04d}", source_path, expected_hash))
    if rows != int(manifest.get("research_rows", -1)):
        raise RuntimeError("successor daily partition row accounting drifted")
    report = {
        "manifest_path": str(manifest_path),
        "source_root": str(expected_root),
        "source_fingerprint": fingerprint,
        "partition_count": len(bindings),
        "reported_rows": rows,
        "bar_rows_opened_by_preflight": 0,
    }
    return fingerprint, bindings, report


def _prepare_inputs(
    output_root: Path,
    project_root: Path,
    daily_bindings,
    minute_plan,
) -> tuple[list[ResearchWorkUnit], dict[str, object]]:
    input_root = output_root / "source_binding_inputs"
    input_root.mkdir(parents=True, exist_ok=True)
    work: list[ResearchWorkUnit] = []
    for token, path, expected_hash in daily_bindings:
        payload = build_source_binding_payload(
            token=token,
            source_id=DAILY_SOURCE_ID,
            files=((path, expected_hash),),
            project_root=project_root,
        )
        _write_json(input_root / f"{token}.json", payload)
        work.append(ResearchWorkUnit(token=token, input_fingerprint=canonical_sha256(payload)))

    minute_groups = minute_symbol_groups(minute_plan.units)
    for index, (_symbols, units) in enumerate(minute_groups):
        token = f"minute_source_{index:04d}"
        payload = build_source_binding_payload(
            token=token,
            source_id=MINUTE_SOURCE_ID,
            files=((item.canonical_path, item.canonical_sha256) for item in units),
            project_root=project_root,
        )
        _write_json(input_root / f"{token}.json", payload)
        work.append(ResearchWorkUnit(token=token, input_fingerprint=canonical_sha256(payload)))
    return work, {
        "source_binding_group_count": len(work),
        "daily_source_binding_groups": len(daily_bindings),
        "minute_source_binding_groups": len(minute_groups),
        "minute_source_units": len(minute_plan.units),
        "source_binding_input_root": str(input_root),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify the frozen successor DEVELOPMENT source/science contract without opening historical outcomes.")
    parser.add_argument(
        "--authorize-source-verification",
        action="store_true",
        help="Authorize DEVELOPMENT-only source hashing. Does not authorize outcome, protected, future, provider, broker, PAPER, LIVE, or promotion access.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.authorize_source_verification:
        raise ValueError("successor preflight requires --authorize-source-verification")

    settings = load_settings(PROJECT_ROOT)
    profile = resolve_successor_research_execution_profile()
    daily_adapter = ReferenceV2DailyLakeAdapter(settings)
    minute_source = B35DevelopmentMinuteSource(settings, duckdb_threads=profile.duckdb_threads_per_worker)
    start = date.fromisoformat(DEVELOPMENT_START)
    end = date.fromisoformat(DEVELOPMENT_END)

    daily_fingerprint, daily_bindings, daily_report = _daily_bindings(daily_adapter)
    minute_plan = minute_source.plan(start, end)
    contract = build_successor_runner_contract(
        daily_source_fingerprint=daily_fingerprint,
        minute_source_fingerprint=minute_plan.source_fingerprint,
    )
    contract_fingerprint = str(contract["fingerprint"])
    project_root = settings.project_root.resolve()
    output_root = (
        project_root
        / "data"
        / "v2_build"
        / "alpaca_sip_v2"
        / "derived"
        / "strategy_lab"
        / "successor_preflight"
        / contract_fingerprint[:16]
    ).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    work, binding_report = _prepare_inputs(output_root, project_root, daily_bindings, minute_plan)
    source_manifest = {
        "contract": SUCCESSOR_RUNNER_CONTRACT,
        "runner_contract_fingerprint": contract_fingerprint,
        "daily": daily_report,
        "minute": {
            "source_root": str(minute_source.layout.canonical_minute),
            "native_plan_path": str(minute_source.layout.manifests / "native_acquisition_plan.jsonl.gz"),
            "source_fingerprint": minute_plan.source_fingerprint,
            "native_plan_sha256": minute_plan.native_plan_sha256,
            "native_plan_file_sha256": minute_plan.native_plan_file_sha256,
            "unit_count": len(minute_plan.units),
            "bar_rows_opened_by_preflight": 0,
        },
        "binding": binding_report,
        "authority": frozen_authority_contract(),
    }
    _write_json(output_root / "preoutcome_contract.json", contract)
    _write_json(output_root / "source_manifest.json", source_manifest)
    _write_json(output_root / "execution_profile.json", profile.as_dict())

    print(f"successor preflight PID={os.getpid()} scope={DEVELOPMENT_START}..{DEVELOPMENT_END}")
    print(f"contract fingerprint={contract_fingerprint}")
    print(f"source groups={len(work)} minute units={len(minute_plan.units)}")
    print(f"execution profile={profile.workers} workers x {profile.duckdb_threads_per_worker} DuckDB thread")
    print("authority: outcomes=0 protected=0 future=0 provider=0 broker=0 PAPER=false LIVE=false promotion=false")
    print(f"output={output_root}")

    coordinator = SuccessorParallelCoordinator(execution_profile=profile)
    worker = functools.partial(
        verify_source_binding_unit,
        input_root=str(output_root / "source_binding_inputs"),
        project_root=str(project_root),
    )
    run_summary = coordinator.run(
        work,
        worker=worker,
        output_root=output_root,
        scientific_contract_fingerprint=contract_fingerprint,
    )
    summary = {
        "status": "COMPLETE_PREOUTCOME_SOURCE_VERIFICATION",
        "contract": SUCCESSOR_RUNNER_CONTRACT,
        "runner_contract_fingerprint": contract_fingerprint,
        "source_verification": run_summary,
        "source_manifest_fingerprint": canonical_sha256(source_manifest),
        "historical_outcomes_opened": False,
        "authority": frozen_authority_contract(),
    }
    _write_json(output_root / "summary.json", summary)
    print(f"COMPLETE groups={run_summary['group_count']} reused={run_summary['reused_group_count']} new={run_summary['new_group_count']}")
    print(f"source verification run fingerprint={run_summary['run_fingerprint']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
