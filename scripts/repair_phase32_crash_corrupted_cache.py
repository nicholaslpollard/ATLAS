from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase32_predictor_acquisition import PHASE32_EVIDENCE_RELATIVE
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import load_settings


REPAIR_CONTRACT = "phase32-crash-corrupted-cache-targeted-quarantine-v1"
INCIDENT_ID = "phase32-cache-crash-20260829"

EXPECTED_CORRUPT = (
    {
        "relative_path": "massive_reference/2026-06-23/34243222535982df996fa4a7.json",
        "size": 601,
        "sha256": "1b94bb6a330c915941eaa7d5b7a1d84a7d7832e3a0e3f20a03cc23925242aa2b",
    },
    {
        "relative_path": "sec_submissions/0002131853/0001213900-26-068397.json",
        "size": 743,
        "sha256": "8d61db14747e1bfe393ddf9f98e7120b001e2dbc28b5d25b7db6a0603d22f176",
    },
)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _validate_corrupt_payload(path: Path, spec: dict[str, object]) -> bytes:
    raw = path.read_bytes()
    expected_size = int(spec["size"])
    expected_sha = str(spec["sha256"])
    if len(raw) != expected_size:
        raise RuntimeError(
            f"refusing repair: unexpected size for {path}: {len(raw)} != {expected_size}"
        )
    actual_sha = _sha256(raw)
    if actual_sha != expected_sha:
        raise RuntimeError(
            f"refusing repair: unexpected SHA-256 for {path}: {actual_sha} != {expected_sha}"
        )
    if not raw or any(byte != 0 for byte in raw):
        raise RuntimeError(f"refusing repair: payload is not the diagnosed all-null corruption: {path}")
    return raw


def main() -> int:
    settings = load_settings()
    provider_root = settings.resolved_path(settings.data.paths.provider)
    evidence_root = provider_root / PHASE32_EVIDENCE_RELATIVE
    quarantine_root = evidence_root / "quarantine" / INCIDENT_ID
    manifest_path = quarantine_root / "manifest.json"

    print("ATLAS Phase 32 — Targeted Crash-Cache Quarantine Repair")
    print(f"Contract: {REPAIR_CONTRACT}")
    print(f"Evidence root: {evidence_root}")
    print("Scope: exact diagnosed local cache files only")
    print("Network / market outcomes / broker / orders / PAPER / LIVE: DISABLED")
    print()

    if not evidence_root.is_dir():
        print("Result: REPAIR_NOT_APPLIED")
        print("Reason: Phase32 evidence root does not exist")
        return 2

    quarantine_root.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, object]] = []

    try:
        for spec in EXPECTED_CORRUPT:
            relative = Path(str(spec["relative_path"]))
            source = evidence_root / relative
            quarantined = quarantine_root / (relative.as_posix().replace("/", "__") + ".corrupt.bin")

            if source.exists():
                raw = _validate_corrupt_payload(source, spec)
                if quarantined.exists():
                    existing = quarantined.read_bytes()
                    if existing != raw:
                        raise RuntimeError(
                            f"refusing repair: quarantine target already exists with different bytes: {quarantined}"
                        )
                    source.unlink()
                    disposition = "source_removed_after_existing_exact_quarantine_verified"
                else:
                    quarantined.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(source, quarantined)
                    disposition = "atomically_moved_to_quarantine"
            elif quarantined.exists():
                raw = _validate_corrupt_payload(quarantined, spec)
                disposition = "already_quarantined_exact_payload"
            else:
                raise RuntimeError(
                    f"refusing repair: neither diagnosed source nor quarantine artifact exists: {source}"
                )

            manifest_rows.append(
                {
                    "original_relative_path": relative.as_posix(),
                    "quarantine_relative_path": quarantined.relative_to(evidence_root).as_posix(),
                    "size": len(raw),
                    "sha256": _sha256(raw),
                    "null_bytes": raw.count(0),
                    "disposition": disposition,
                }
            )
            print(f"Quarantined: {relative.as_posix()}")

        manifest = {
            "contract": REPAIR_CONTRACT,
            "incident_id": INCIDENT_ID,
            "classification": "abrupt-system-crash-compatible all-null reconstruction-cache corruption",
            "scientific_policy_changed": False,
            "market_outcomes_read": 0,
            "protected_returns_read": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "orders": 0,
            "paper": 0,
            "live": 0,
            "repair_action": (
                "Preserve exact diagnosed corrupt bytes under quarantine and remove only their original "
                "cache paths so the normal acquisition path must reacquire those source records."
            ),
            "files": manifest_rows,
            "written_utc": datetime.now(UTC).isoformat(),
        }
        atomic_write_text(
            manifest_path,
            _canonical_json(manifest) + "\n",
            encoding="utf-8",
            fsync=True,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print("Result: REPAIR_NOT_APPLIED")
        print(f"Reason: {exc}")
        print("Stop here. Do not resume Phase32 acquisition until the repair state is diagnosed.")
        return 2

    print()
    print("Result: TARGETED_QUARANTINE_REPAIR_APPLIED")
    print(f"Quarantine manifest: {manifest_path}")
    print(f"Files quarantined/verified: {len(manifest_rows)}")
    print("Original corrupt cache paths are absent and must be reacquired by the normal Phase32 source path.")
    print("No scientific policy, outcome evidence, or trading authority was changed or opened.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
