from __future__ import annotations

import hashlib
import json
import os
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable

from packages.core.atomic_io import atomic_write_text
from packages.core.successor_execution_profile import SuccessorResearchExecutionProfile


SUCCESSOR_PARALLEL_RUNTIME_CONTRACT = (
    "successor-parallel-runtime-v1-restart-safe-profile-independent-science"
)


@dataclass(frozen=True, slots=True)
class ResearchWorkUnit:
    token: str
    input_fingerprint: str

    def __post_init__(self) -> None:
        if not self.token or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in self.token):
            raise ValueError("work-unit token must be filesystem-safe")
        if len(self.input_fingerprint) != 64 or any(char not in "0123456789abcdef" for char in self.input_fingerprint):
            raise ValueError("work-unit input_fingerprint must be lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class CompletedGroup:
    token: str
    receipt_id: str
    output_sha256: str
    reused: bool


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _self_hash(payload: dict[str, object], field: str) -> str:
    copy = dict(payload)
    copy.pop(field, None)
    return _sha256_bytes(_canonical_json(copy).encode("utf-8"))


def _group_paths(output_root: Path, token: str) -> tuple[Path, Path]:
    root = output_root / "groups" / token
    return root / "output.json", root / "receipt.json"


def validate_completed_group(
    output_root: Path,
    unit: ResearchWorkUnit,
    *,
    scientific_contract_fingerprint: str,
) -> CompletedGroup | None:
    output_path, receipt_path = _group_paths(output_root, unit.token)
    if not receipt_path.exists():
        if output_path.exists():
            output_path.unlink()
        return None
    if not output_path.is_file():
        raise RuntimeError(f"receipt exists without output for {unit.token}")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("receipt_id") != _self_hash(receipt, "receipt_id"):
        raise RuntimeError(f"receipt self-hash failed for {unit.token}")
    required = {
        "contract": SUCCESSOR_PARALLEL_RUNTIME_CONTRACT,
        "token": unit.token,
        "input_fingerprint": unit.input_fingerprint,
        "scientific_contract_fingerprint": scientific_contract_fingerprint,
    }
    for key, expected in required.items():
        if receipt.get(key) != expected:
            raise RuntimeError(f"receipt {key} drifted for {unit.token}")
    output_sha = _sha256_path(output_path)
    if receipt.get("output_sha256") != output_sha:
        raise RuntimeError(f"output hash failed for {unit.token}")
    return CompletedGroup(
        token=unit.token,
        receipt_id=str(receipt["receipt_id"]),
        output_sha256=output_sha,
        reused=True,
    )


def publish_completed_group(
    output_root: Path,
    unit: ResearchWorkUnit,
    result: dict[str, object],
    *,
    scientific_contract_fingerprint: str,
) -> CompletedGroup:
    output_path, receipt_path = _group_paths(output_root, unit.token)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_text = _canonical_json(result) + "\n"
    atomic_write_text(output_path, output_text)
    output_sha = _sha256_bytes(output_text.encode("utf-8"))
    receipt: dict[str, object] = {
        "contract": SUCCESSOR_PARALLEL_RUNTIME_CONTRACT,
        "token": unit.token,
        "input_fingerprint": unit.input_fingerprint,
        "scientific_contract_fingerprint": scientific_contract_fingerprint,
        "output_sha256": output_sha,
    }
    receipt["receipt_id"] = _self_hash(receipt, "receipt_id")
    atomic_write_text(receipt_path, _canonical_json(receipt) + "\n")
    return CompletedGroup(
        token=unit.token,
        receipt_id=str(receipt["receipt_id"]),
        output_sha256=output_sha,
        reused=False,
    )


def scientific_run_fingerprint(
    *,
    scientific_contract_fingerprint: str,
    completed_groups: Iterable[CompletedGroup],
) -> str:
    """Hash scientific identity without worker/thread/runtime telemetry."""
    payload = {
        "scientific_contract_fingerprint": scientific_contract_fingerprint,
        "receipt_ids": sorted(group.receipt_id for group in completed_groups),
    }
    return _sha256_bytes(_canonical_json(payload).encode("utf-8"))


class SuccessorParallelCoordinator:
    """Run independent groups in parallel with validated checkpoint reuse.

    ``worker`` must be a top-level picklable callable accepting ``ResearchWorkUnit``
    and returning a JSON-serializable dict. Execution profile choices are telemetry
    only and never enter scientific hashes.
    """

    def __init__(
        self,
        *,
        execution_profile: SuccessorResearchExecutionProfile,
        heartbeat_seconds: float = 60.0,
    ) -> None:
        if heartbeat_seconds <= 0:
            raise ValueError("heartbeat_seconds must be positive")
        self.profile = execution_profile
        self.heartbeat_seconds = heartbeat_seconds

    def _write_progress(
        self,
        path: Path,
        *,
        state: str,
        total: int,
        completed: list[CompletedGroup],
        started_monotonic: float,
        active_tokens: list[str],
        last_error: str | None = None,
    ) -> None:
        new_count = sum(not group.reused for group in completed)
        reused_count = sum(group.reused for group in completed)
        payload = {
            "contract": SUCCESSOR_PARALLEL_RUNTIME_CONTRACT,
            "state": state,
            "coordinator_pid": os.getpid(),
            "groups_total": total,
            "groups_completed": len(completed),
            "groups_reused": reused_count,
            "groups_new": new_count,
            "active_group_tokens": sorted(active_tokens),
            "elapsed_seconds": max(0.0, time.monotonic() - started_monotonic),
            "execution_profile": self.profile.as_dict(),
            "last_error": last_error,
        }
        atomic_write_text(path, _canonical_json(payload) + "\n")

    def run(
        self,
        units: Iterable[ResearchWorkUnit],
        *,
        worker: Callable[[ResearchWorkUnit], dict[str, object]],
        output_root: Path,
        scientific_contract_fingerprint: str,
    ) -> dict[str, object]:
        ordered = tuple(sorted(units, key=lambda item: item.token))
        if not ordered:
            raise ValueError("successor parallel run requires at least one work unit")
        if len({unit.token for unit in ordered}) != len(ordered):
            raise ValueError("successor work-unit tokens must be unique")
        output_root.mkdir(parents=True, exist_ok=True)
        progress_path = output_root / "progress.json"
        started = time.monotonic()
        completed: list[CompletedGroup] = []
        pending: list[ResearchWorkUnit] = []
        for unit in ordered:
            prior = validate_completed_group(
                output_root,
                unit,
                scientific_contract_fingerprint=scientific_contract_fingerprint,
            )
            if prior is None:
                pending.append(unit)
            else:
                completed.append(prior)

        self._write_progress(
            progress_path,
            state="RUNNING",
            total=len(ordered),
            completed=completed,
            started_monotonic=started,
            active_tokens=[],
        )
        if pending:
            with ProcessPoolExecutor(max_workers=self.profile.workers) as executor:
                future_to_unit = {executor.submit(worker, unit): unit for unit in pending}
                last_heartbeat = 0.0
                try:
                    while future_to_unit:
                        done, _ = wait(
                            tuple(future_to_unit),
                            timeout=min(1.0, self.heartbeat_seconds),
                            return_when=FIRST_COMPLETED,
                        )
                        for future in done:
                            unit = future_to_unit.pop(future)
                            result = future.result()
                            if not isinstance(result, dict):
                                raise TypeError("successor worker must return a dict")
                            completed.append(
                                publish_completed_group(
                                    output_root,
                                    unit,
                                    result,
                                    scientific_contract_fingerprint=scientific_contract_fingerprint,
                                )
                            )
                        now = time.monotonic()
                        if done or now - last_heartbeat >= self.heartbeat_seconds:
                            self._write_progress(
                                progress_path,
                                state="RUNNING",
                                total=len(ordered),
                                completed=completed,
                                started_monotonic=started,
                                active_tokens=[unit.token for unit in future_to_unit.values()],
                            )
                            last_heartbeat = now
                except BaseException as exc:
                    self._write_progress(
                        progress_path,
                        state="FAILED",
                        total=len(ordered),
                        completed=completed,
                        started_monotonic=started,
                        active_tokens=[unit.token for unit in future_to_unit.values()],
                        last_error=f"{type(exc).__name__}: {exc}",
                    )
                    raise

        if len(completed) != len(ordered):
            raise RuntimeError("successor parallel run finished without all groups")
        fingerprint = scientific_run_fingerprint(
            scientific_contract_fingerprint=scientific_contract_fingerprint,
            completed_groups=completed,
        )
        self._write_progress(
            progress_path,
            state="COMPLETE",
            total=len(ordered),
            completed=completed,
            started_monotonic=started,
            active_tokens=[],
        )
        return {
            "status": "COMPLETE",
            "group_count": len(completed),
            "reused_group_count": sum(group.reused for group in completed),
            "new_group_count": sum(not group.reused for group in completed),
            "run_fingerprint": fingerprint,
            "scientific_contract_fingerprint": scientific_contract_fingerprint,
            "receipt_ids": sorted(group.receipt_id for group in completed),
            "execution_profile": self.profile.as_dict(),
            "execution_profile_in_scientific_fingerprint": False,
        }
