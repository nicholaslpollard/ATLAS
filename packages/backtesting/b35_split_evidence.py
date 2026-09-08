from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from packages.data.alpaca_v2_acquisition import SOURCE_SNAPSHOT_CONTRACT
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.intraday_semantics_audit import (
    _SPLIT_ACTION_TYPES,
    _action_date,
    _action_symbols,
    _corporate_action_records,
)
from packages.strategies.b35_conditional_evidence_contract import (
    B35_PREOUTCOME_FINGERPRINT,
    DEVELOPMENT_LAST_SCORING_SESSION,
)


B35_SPLIT_EVIDENCE_CONTRACT = (
    "atlas-b35-split-evidence-v1-source-snapshot-hash-bound-preprotected"
)


class B35SplitEvidenceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class B35SplitEvidence:
    contract: str
    b35_preoutcome_fingerprint: str
    source_snapshot_path: Path
    source_snapshot_sha256: str
    corporate_actions_path: Path
    corporate_actions_sha256: str
    split_dates_by_symbol: dict[str, tuple[date, ...]]
    split_event_count: int
    fingerprint: str


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(raw).hexdigest()


def _assert_v2_path(path: Path, *, expected: Path, root: Path, label: str) -> Path:
    path = path.absolute()
    expected = expected.absolute()
    root = root.absolute()
    if path != expected:
        raise B35SplitEvidenceError(f"{label} is not the exact isolated V2 path")
    try:
        relative = expected.relative_to(root)
    except ValueError as exc:
        raise B35SplitEvidenceError(f"{label} escapes the isolated V2 root") from exc
    cursor = root
    if cursor.is_symlink():
        raise B35SplitEvidenceError(f"{label} V2 root is a symlink")
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise B35SplitEvidenceError(f"{label} path contains a symlink: {cursor}")
    resolved_root = root.resolve(strict=False)
    resolved = expected.resolve(strict=False)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise B35SplitEvidenceError(f"{label} resolves outside the isolated V2 root") from exc
    return expected


def _read_json(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(f"missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise B35SplitEvidenceError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise B35SplitEvidenceError(f"{label} is not a JSON object: {path}")
    return value


def load_b35_split_evidence(layout: V2Layout) -> B35SplitEvidence:
    """Load only hash-bound pre-protected split dates from the accepted V2 source."""

    expected_snapshot = (layout.manifests / "source_snapshot.json").absolute()
    source_snapshot_path = _assert_v2_path(
        expected_snapshot,
        expected=expected_snapshot,
        root=layout.root,
        label="V2 source snapshot",
    )
    source_snapshot = _read_json(source_snapshot_path, "V2 source snapshot")
    if source_snapshot.get("contract") != SOURCE_SNAPSHOT_CONTRACT:
        raise B35SplitEvidenceError("V2 source snapshot contract drifted")
    if source_snapshot.get("status") != "COMPLETE":
        raise B35SplitEvidenceError("V2 source snapshot is not COMPLETE")
    if source_snapshot.get("v1_ancestry") != "FORBIDDEN":
        raise B35SplitEvidenceError("V2 source snapshot permits legacy ancestry")

    native = source_snapshot.get("corporate_actions_native")
    if not isinstance(native, dict):
        raise B35SplitEvidenceError("V2 source snapshot has no corporate-actions binding")
    expected_path = (layout.corporate_actions / "native_actions.jsonl.gz").absolute()
    recorded_path = Path(str(native.get("path") or "")).absolute()
    _assert_v2_path(
        recorded_path,
        expected=expected_path,
        root=layout.root,
        label="V2 native corporate actions",
    )
    if not expected_path.is_file():
        raise FileNotFoundError(f"missing V2 native corporate actions: {expected_path}")
    actions_sha = _sha256_file(expected_path)
    if actions_sha != str(native.get("sha256") or ""):
        raise B35SplitEvidenceError("V2 native corporate-actions SHA-256 drifted")

    dates: dict[str, set[date]] = defaultdict(set)
    event_keys: set[tuple[str, date, str]] = set()
    for record in _corporate_action_records(layout):
        action_type = str(record.get("action_type") or "")
        if action_type not in _SPLIT_ACTION_TYPES:
            continue
        payload = record.get("payload")
        action_date = _action_date(payload)
        if action_date is None or action_date > DEVELOPMENT_LAST_SCORING_SESSION:
            continue
        for symbol in _action_symbols(payload):
            dates[symbol].add(action_date)
            event_keys.add((symbol, action_date, action_type))

    normalized = {key: tuple(sorted(values)) for key, values in sorted(dates.items())}
    source_snapshot_sha = _sha256_file(source_snapshot_path)
    fingerprint = _stable_hash(
        {
            "contract": B35_SPLIT_EVIDENCE_CONTRACT,
            "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
            "development_last_scoring_session": DEVELOPMENT_LAST_SCORING_SESSION.isoformat(),
            "source_snapshot_path": str(source_snapshot_path),
            "source_snapshot_sha256": source_snapshot_sha,
            "corporate_actions_path": str(expected_path),
            "corporate_actions_sha256": actions_sha,
            "split_dates_by_symbol": {
                symbol: [item.isoformat() for item in values]
                for symbol, values in normalized.items()
            },
            "split_event_count": len(event_keys),
            "provider_calls": 0,
            "broker_reads": 0,
            "broker_writes": 0,
        }
    )
    return B35SplitEvidence(
        contract=B35_SPLIT_EVIDENCE_CONTRACT,
        b35_preoutcome_fingerprint=B35_PREOUTCOME_FINGERPRINT,
        source_snapshot_path=source_snapshot_path,
        source_snapshot_sha256=source_snapshot_sha,
        corporate_actions_path=expected_path,
        corporate_actions_sha256=actions_sha,
        split_dates_by_symbol=normalized,
        split_event_count=len(event_keys),
        fingerprint=fingerprint,
    )


def split_evidence_report(evidence: B35SplitEvidence) -> dict[str, object]:
    return {
        "contract": evidence.contract,
        "status": "PASS",
        "b35_preoutcome_fingerprint": evidence.b35_preoutcome_fingerprint,
        "fingerprint": evidence.fingerprint,
        "source_snapshot_path": str(evidence.source_snapshot_path),
        "source_snapshot_sha256": evidence.source_snapshot_sha256,
        "corporate_actions_path": str(evidence.corporate_actions_path),
        "corporate_actions_sha256": evidence.corporate_actions_sha256,
        "split_symbol_count": len(evidence.split_dates_by_symbol),
        "split_event_count": evidence.split_event_count,
        "development_last_scoring_session": DEVELOPMENT_LAST_SCORING_SESSION.isoformat(),
        "provider_calls": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "paper_authority": False,
        "live_authority": False,
    }
