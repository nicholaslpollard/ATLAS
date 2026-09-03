from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable


CONTRACT = "atlas-alpaca-sip-v2-rebuild-v1"
DECOMMISSION_CONTRACT = "atlas-v1-historical-decommission-v1"
MIN_FREE_RESERVE_BYTES = 30 * 1024**3

# These are historical database generations, not the whole data root. In
# particular data/live, data/models, and non-historical research outputs are not
# deletion targets.
V1_HISTORICAL_TARGETS = (
    "provider/massive",
    "provider/alpaca/historical_backfill",
    "raw/minute_aggs_v1",
    "staging/market",
    "canonical",
    "derived/bars",
    "derived/features",
    "derived/historical_backfill",
    "duckdb/atlas.duckdb",
)


def _stable_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_inside(path: Path, root: Path) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"path escapes data root: {path}") from exc
    if path == root:
        raise RuntimeError("the data root itself may never be a decommission target")


@dataclass(frozen=True)
class DecommissionEntry:
    relative_path: str
    kind: str
    files: int
    bytes: int
    inventory_sha256: str


@dataclass(frozen=True)
class DecommissionPlan:
    contract: str
    data_root: str
    entries: tuple[DecommissionEntry, ...]
    total_files: int
    total_bytes: int
    plan_sha256: str

    @property
    def confirmation_token(self) -> str:
        return f"DELETE-V1-{self.plan_sha256[:16].upper()}"


def _inventory_target(path: Path, data_root: Path) -> DecommissionEntry | None:
    if not path.exists() and not path.is_symlink():
        return None
    _assert_inside(path, data_root)
    if path.is_symlink():
        raise RuntimeError(f"refusing symlink decommission target: {path}")

    if path.is_file():
        rel = path.relative_to(data_root).as_posix()
        size = path.stat().st_size
        fingerprint = hashlib.sha256(
            _stable_json([[rel, int(size), _sha256_file(path)]])
        ).hexdigest()
        return DecommissionEntry(rel, "file", 1, int(size), fingerprint)

    rows: list[tuple[str, int, str]] = []
    for current, dirnames, filenames in os.walk(path, followlinks=False):
        current_path = Path(current)
        for dirname in list(dirnames):
            candidate = current_path / dirname
            if candidate.is_symlink():
                raise RuntimeError(f"refusing symlink inside decommission target: {candidate}")
        for filename in filenames:
            candidate = current_path / filename
            if candidate.is_symlink():
                raise RuntimeError(f"refusing symlink inside decommission target: {candidate}")
            stat = candidate.stat()
            rows.append(
                (
                    candidate.relative_to(data_root).as_posix(),
                    int(stat.st_size),
                    _sha256_file(candidate),
                )
            )
    rows.sort()
    rel = path.relative_to(data_root).as_posix()
    return DecommissionEntry(
        relative_path=rel,
        kind="directory",
        files=len(rows),
        bytes=sum(row[1] for row in rows),
        inventory_sha256=hashlib.sha256(_stable_json(rows)).hexdigest(),
    )


def build_decommission_plan(
    data_root: Path,
    targets: Iterable[str] = V1_HISTORICAL_TARGETS,
) -> DecommissionPlan:
    root = data_root.resolve()
    if root.is_symlink():
        raise RuntimeError(f"data root may not be a symlink: {root}")
    entries: list[DecommissionEntry] = []
    for relative in targets:
        lexical = root / relative
        _assert_inside(lexical, root)
        if lexical.is_symlink():
            raise RuntimeError(f"refusing symlink decommission target: {lexical}")
        candidate = lexical.resolve(strict=False)
        _assert_inside(candidate, root)
        entry = _inventory_target(candidate, root)
        if entry is not None:
            entries.append(entry)
    entries.sort(key=lambda item: item.relative_path)
    payload = {
        "contract": DECOMMISSION_CONTRACT,
        "data_root": str(root),
        "entries": [asdict(item) for item in entries],
        "total_files": sum(item.files for item in entries),
        "total_bytes": sum(item.bytes for item in entries),
    }
    return DecommissionPlan(
        contract=DECOMMISSION_CONTRACT,
        data_root=str(root),
        entries=tuple(entries),
        total_files=payload["total_files"],
        total_bytes=payload["total_bytes"],
        plan_sha256=hashlib.sha256(_stable_json(payload)).hexdigest(),
    )


def write_decommission_plan(plan: DecommissionPlan, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = asdict(plan) | {"confirmation_token": plan.confirmation_token}
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, indent=2), encoding="utf-8")
    temporary.replace(path)


def execute_decommission(plan: DecommissionPlan, *, confirmation_token: str) -> int:
    return execute_decommission_with_journal(
        plan,
        confirmation_token=confirmation_token,
        journal_path=None,
    )


def _write_decommission_journal(
    path: Path,
    *,
    plan: DecommissionPlan,
    status: str,
    completed_targets: list[str],
    error: str | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "contract": DECOMMISSION_CONTRACT,
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "plan": asdict(plan),
        "completed_targets": completed_targets,
        "error": error,
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, indent=2), encoding="utf-8")
    temporary.replace(path)


def execute_decommission_with_journal(
    plan: DecommissionPlan,
    *,
    confirmation_token: str,
    journal_path: Path | None,
    progress: Callable[[str], None] | None = None,
) -> int:
    if confirmation_token != plan.confirmation_token:
        raise RuntimeError("V1 decommission confirmation token does not match the frozen plan")
    root = Path(plan.data_root).resolve()
    current = build_decommission_plan(root, (item.relative_path for item in plan.entries))
    if current.plan_sha256 != plan.plan_sha256:
        raise RuntimeError("V1 inventory changed after planning; regenerate and review the plan")

    completed: list[str] = []
    if journal_path is not None:
        _write_decommission_journal(
            journal_path,
            plan=plan,
            status="IN_PROGRESS",
            completed_targets=completed,
        )
    try:
        for entry in plan.entries:
            lexical = root / entry.relative_path
            _assert_inside(lexical, root)
            if lexical.is_symlink():
                raise RuntimeError(f"refusing symlink decommission target: {lexical}")
            target = lexical.resolve(strict=False)
            _assert_inside(target, root)
            if target.is_symlink():
                raise RuntimeError(f"refusing symlink decommission target: {target}")
            if entry.kind == "file":
                target.unlink()
            else:
                shutil.rmtree(target)
            completed.append(entry.relative_path)
            if progress is not None:
                progress(entry.relative_path)
            if journal_path is not None:
                _write_decommission_journal(
                    journal_path,
                    plan=plan,
                    status="IN_PROGRESS",
                    completed_targets=completed,
                )
    except Exception as exc:
        if journal_path is not None:
            _write_decommission_journal(
                journal_path,
                plan=plan,
                status="FAILED_PARTIAL" if completed else "FAILED_NO_DELETION",
                completed_targets=completed,
                error=f"{type(exc).__name__}: {exc}",
            )
        raise

    if journal_path is not None:
        _write_decommission_journal(
            journal_path,
            plan=plan,
            status="COMPLETE",
            completed_targets=completed,
        )
    return len(completed)


@dataclass(frozen=True)
class V2Layout:
    root: Path
    source: Path
    canonical_daily: Path
    canonical_minute: Path
    corporate_actions: Path
    identity: Path
    derived: Path
    manifests: Path
    checkpoints: Path
    validation: Path

    @classmethod
    def beneath(cls, data_root: Path) -> "V2Layout":
        root = data_root.resolve() / "v2_build" / "alpaca_sip_v2"
        return cls(
            root=root,
            source=root / "source",
            canonical_daily=root / "canonical" / "stocks" / "1d",
            canonical_minute=root / "canonical" / "stocks" / "1m",
            corporate_actions=root / "canonical" / "corporate_actions",
            identity=root / "canonical" / "identity",
            derived=root / "derived",
            manifests=root / "manifests",
            checkpoints=root / "checkpoints",
            validation=root / "validation",
        )

    def create(self) -> None:
        for path in asdict(self).values():
            Path(path).mkdir(parents=True, exist_ok=True)


def write_run_state(layout: V2Layout, *, stage: str, status: str, details: dict) -> Path:
    state_path = layout.checkpoints / "run_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "contract": CONTRACT,
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "status": status,
        "details": details,
    }
    temporary = state_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(document, indent=2), encoding="utf-8")
    temporary.replace(state_path)
    return state_path


def disk_guard(path: Path, *, required_bytes: int, reserve_bytes: int = MIN_FREE_RESERVE_BYTES) -> dict:
    usage = shutil.disk_usage(path)
    accepted = usage.free >= required_bytes + reserve_bytes
    return {
        "free_bytes": int(usage.free),
        "required_bytes": int(required_bytes),
        "reserve_bytes": int(reserve_bytes),
        "accepted": accepted,
    }
