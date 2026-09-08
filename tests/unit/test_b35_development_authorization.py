from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from threading import Barrier

import pytest

from packages.backtesting.b35_development_authorization import (
    B35DevelopmentAuthorizationError,
    ensure_development_authorization,
    validate_development_authorization,
)
from packages.backtesting.b35_development_source import (
    B35_DEVELOPMENT_SOURCE_CONTRACT,
    B35DevelopmentSourcePlan,
)
from packages.backtesting.b35_split_evidence import B35SplitEvidence
from packages.strategies.b35_conditional_evidence_contract import B35_PREOUTCOME_FINGERPRINT


def _plan(*, source_fingerprint: str = "a" * 64) -> B35DevelopmentSourcePlan:
    return B35DevelopmentSourcePlan(
        contract=B35_DEVELOPMENT_SOURCE_CONTRACT,
        b35_preoutcome_fingerprint=B35_PREOUTCOME_FINGERPRINT,
        start_session=date(2016, 1, 4),
        end_session=date(2026, 4, 30),
        units=(),
        native_plan_sha256="b" * 64,
        native_plan_file_sha256="c" * 64,
        source_fingerprint=source_fingerprint,
    )


def _split(tmp_path: Path, *, fingerprint: str = "d" * 64) -> B35SplitEvidence:
    return B35SplitEvidence(
        contract="atlas-b35-split-evidence-v1-source-snapshot-hash-bound-preprotected",
        b35_preoutcome_fingerprint=B35_PREOUTCOME_FINGERPRINT,
        source_snapshot_path=tmp_path / "source_snapshot.json",
        source_snapshot_sha256="e" * 64,
        corporate_actions_path=tmp_path / "native_actions.jsonl.gz",
        corporate_actions_sha256="f" * 64,
        split_dates_by_symbol={},
        split_event_count=0,
        fingerprint=fingerprint,
    )


def test_authorization_is_self_hash_bound_and_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "authorization.json"
    plan = _plan()
    split = _split(tmp_path)
    created = ensure_development_authorization(path, plan=plan, split_evidence=split)
    first_id = validate_development_authorization(created, plan=plan, split_evidence=split)
    reopened = ensure_development_authorization(path, plan=plan, split_evidence=split)
    assert reopened == created
    assert reopened["authorization_id"] == first_id
    assert reopened["consumed_master_rows_permitted"] == 0
    assert reopened["future_blind_rows_permitted"] == 0
    assert reopened["broker_writes_permitted"] == 0


def test_concurrent_exact_authorization_attempts_converge(tmp_path: Path) -> None:
    path = tmp_path / "authorization.json"
    plan = _plan()
    split = _split(tmp_path)
    barrier = Barrier(2)

    def worker() -> dict[str, object]:
        barrier.wait()
        return ensure_development_authorization(
            path, plan=plan, split_evidence=split, wait_seconds=2.0
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(lambda _value: worker(), range(2)))
    assert first["authorization_id"] == second["authorization_id"]
    assert validate_development_authorization(first, plan=plan, split_evidence=split) == first[
        "authorization_id"
    ]
    assert not path.with_name(path.name + ".claim").exists()


def test_authorization_rejects_source_binding_change(tmp_path: Path) -> None:
    path = tmp_path / "authorization.json"
    original = _plan()
    split = _split(tmp_path)
    ensure_development_authorization(path, plan=original, split_evidence=split)
    changed = _plan(source_fingerprint="1" * 64)
    with pytest.raises(B35DevelopmentAuthorizationError, match="source_fingerprint"):
        ensure_development_authorization(path, plan=changed, split_evidence=split)


def test_authorization_rejects_split_binding_change(tmp_path: Path) -> None:
    path = tmp_path / "authorization.json"
    plan = _plan()
    original = _split(tmp_path)
    ensure_development_authorization(path, plan=plan, split_evidence=original)
    changed = _split(tmp_path, fingerprint="2" * 64)
    with pytest.raises(B35DevelopmentAuthorizationError, match="split_evidence_fingerprint"):
        ensure_development_authorization(path, plan=plan, split_evidence=changed)


def test_partial_authorization_file_never_grants_authority(tmp_path: Path) -> None:
    path = tmp_path / "authorization.json"
    path.write_text('{"contract":"partial"', encoding="utf-8")
    with pytest.raises(B35DevelopmentAuthorizationError, match="invalid existing"):
        ensure_development_authorization(path, plan=_plan(), split_evidence=_split(tmp_path))


def test_stranded_claim_fails_closed_without_authority(tmp_path: Path) -> None:
    path = tmp_path / "authorization.json"
    claim = path.with_name(path.name + ".claim")
    claim.write_text(json.dumps({"status": "PUBLICATION_CLAIM_ONLY_NOT_AUTHORITY"}), encoding="utf-8")
    with pytest.raises(B35DevelopmentAuthorizationError, match="stranded"):
        ensure_development_authorization(
            path,
            plan=_plan(),
            split_evidence=_split(tmp_path),
            wait_seconds=0.1,
        )
    assert not path.exists()
