from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from packages.core.atomic_io import atomic_write_text
from packages.schemas.strategy_lab import StrategyTrialDraft, StrategyTrialRecord


STRATEGY_TRIAL_LEDGER_CONTRACT_VERSION = (
    "strategy-trial-ledger-v1-append-only-hash-chain-protected-zero"
)
GENESIS_RECORD_HASH = "0" * 64


class StrategyTrialLedgerError(RuntimeError):
    pass


class StrategyTrialLedgerConflict(StrategyTrialLedgerError):
    pass


def _record_hash(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _hashable_record(record: StrategyTrialRecord) -> dict[str, object]:
    return record.model_dump(mode="json", exclude={"record_hash"})


class StrategyTrialLedger:
    """Small append-only JSONL research ledger with an auditable hash chain."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def _read_text(self) -> str:
        if not self.path.exists():
            return ""
        try:
            return self.path.read_text(encoding="utf-8")
        except OSError as exc:
            raise StrategyTrialLedgerError(f"cannot read strategy trial ledger: {self.path}") from exc

    def read(self) -> tuple[StrategyTrialRecord, ...]:
        text = self._read_text()
        records: list[StrategyTrialRecord] = []
        previous = GENESIS_RECORD_HASH
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                raise StrategyTrialLedgerError(f"blank trial ledger line: {line_number}")
            try:
                record = StrategyTrialRecord.model_validate_json(line)
            except (ValidationError, ValueError) as exc:
                raise StrategyTrialLedgerError(
                    f"invalid strategy trial ledger line: {line_number}"
                ) from exc
            if record.contract_version != STRATEGY_TRIAL_LEDGER_CONTRACT_VERSION:
                raise StrategyTrialLedgerError(f"trial ledger contract drift at line {line_number}")
            if record.sequence != line_number:
                raise StrategyTrialLedgerError(f"trial ledger sequence drift at line {line_number}")
            if record.previous_record_hash != previous:
                raise StrategyTrialLedgerError(f"trial ledger hash-chain break at line {line_number}")
            if _record_hash(_hashable_record(record)) != record.record_hash:
                raise StrategyTrialLedgerError(f"trial ledger record hash mismatch at line {line_number}")
            records.append(record)
            previous = record.record_hash
        if len({record.trial_id for record in records}) != len(records):
            raise StrategyTrialLedgerError("trial ledger contains duplicate trial_id values")
        return tuple(records)

    def append(self, draft: StrategyTrialDraft) -> StrategyTrialRecord:
        original_text = self._read_text()
        records = self.read()
        if any(record.trial_id == draft.trial_id for record in records):
            raise StrategyTrialLedgerConflict(f"trial_id already exists: {draft.trial_id}")
        payload = {
            **draft.model_dump(mode="json"),
            "contract_version": STRATEGY_TRIAL_LEDGER_CONTRACT_VERSION,
            "sequence": len(records) + 1,
            "previous_record_hash": records[-1].record_hash if records else GENESIS_RECORD_HASH,
        }
        record = StrategyTrialRecord(**payload, record_hash=_record_hash(payload))
        current_text = self._read_text()
        if current_text != original_text:
            raise StrategyTrialLedgerConflict("strategy trial ledger changed during append")
        new_line = json.dumps(
            record.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )
        updated = original_text + ("" if not original_text or original_text.endswith("\n") else "\n")
        atomic_write_text(self.path, updated + new_line + "\n")
        return record
