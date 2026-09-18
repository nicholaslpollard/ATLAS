from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from packages.core.enums import LiveFreshness
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.schemas.live_market import LiveStateSnapshot
from packages.simulation.current_live_evidence_contract import (
    CURRENT_LIVE_EVIDENCE_CONTRACT,
    CURRENT_LIVE_EVIDENCE_CONTRACT_FINGERPRINT,
)


CURRENT_LIVE_EVIDENCE_CONTRACT_VERSION = str(
    CURRENT_LIVE_EVIDENCE_CONTRACT["contract_id"]
)
CURRENT_LIVE_EVIDENCE_SOURCE_ID = "atlas-live-market-state/current.json"
_MAX_SOURCE_BYTES = 64 * 1024 * 1024


class CurrentLiveEvidenceError(RuntimeError):
    pass


def _require_sha(value: str, *, label: str) -> None:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise CurrentLiveEvidenceError(
            f"{label} must be a SHA-256 fingerprint"
        )


def _require_aware(value: datetime, *, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CurrentLiveEvidenceError(f"{label} must be timezone-aware")


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, BaseModel):
        return _canonicalize(value.model_dump(mode="json"))
    if is_dataclass(value):
        return {
            field.name: _canonicalize(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, dict):
        return {
            str(key): _canonicalize(item)
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [_canonicalize(item) for item in value]
    return value


def _fingerprint_payload(value: Any) -> str:
    raw = json.dumps(
        _canonicalize(value),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class CurrentLiveEvidenceV1:
    contract_version: str
    contract_fingerprint: str
    source_id: str
    source_sha256: str
    source_byte_count: int
    captured_at_utc: datetime
    snapshot: LiveStateSnapshot

    descriptive_only: bool = True
    provider_read_authority: bool = False
    provider_write_authority: bool = False
    broker_read_authority: bool = False
    broker_write_authority: bool = False
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    confluence_authority: bool = False

    def __post_init__(self) -> None:
        if self.contract_version != CURRENT_LIVE_EVIDENCE_CONTRACT_VERSION:
            raise CurrentLiveEvidenceError(
                "current-live evidence contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != CURRENT_LIVE_EVIDENCE_CONTRACT_FINGERPRINT
        ):
            raise CurrentLiveEvidenceError(
                "current-live evidence contract fingerprint mismatch"
            )
        if self.source_id != CURRENT_LIVE_EVIDENCE_SOURCE_ID:
            raise CurrentLiveEvidenceError(
                "current-live evidence source id mismatch"
            )
        _require_sha(self.source_sha256, label="current-live source")
        if self.source_byte_count <= 0 or self.source_byte_count > _MAX_SOURCE_BYTES:
            raise CurrentLiveEvidenceError(
                "current-live source byte count is invalid"
            )
        _require_aware(self.captured_at_utc, label="capture timestamp")
        if self.snapshot.generated_at_utc > self.captured_at_utc:
            raise CurrentLiveEvidenceError(
                "live snapshot cannot be generated after capture time"
            )
        if (
            self.snapshot.last_received_at_utc is not None
            and self.snapshot.last_received_at_utc
            > self.snapshot.generated_at_utc
        ):
            raise CurrentLiveEvidenceError(
                "live snapshot last-received timestamp cannot exceed generation time"
            )

        symbols = [state.symbol for state in self.snapshot.symbols]
        if len(symbols) != len(set(symbols)):
            raise CurrentLiveEvidenceError(
                "live snapshot contains duplicate exact-case symbols"
            )
        for state in self.snapshot.symbols:
            if state.minute is not None:
                if state.minute.symbol != state.symbol:
                    raise CurrentLiveEvidenceError(
                        "live minute symbol does not match symbol-state identity"
                    )
                if state.minute.feed_mode != self.snapshot.feed_mode:
                    raise CurrentLiveEvidenceError(
                        "live minute feed mode does not match snapshot"
                    )
                if (
                    state.minute.expected_delay_seconds
                    != self.snapshot.expected_delay_seconds
                ):
                    raise CurrentLiveEvidenceError(
                        "live minute delay does not match snapshot"
                    )
            if state.quote is not None:
                if state.quote.symbol != state.symbol:
                    raise CurrentLiveEvidenceError(
                        "live quote symbol does not match symbol-state identity"
                    )
                if state.quote.feed_mode != self.snapshot.feed_mode:
                    raise CurrentLiveEvidenceError(
                        "live quote feed mode does not match snapshot"
                    )
                if (
                    state.quote.expected_delay_seconds
                    != self.snapshot.expected_delay_seconds
                ):
                    raise CurrentLiveEvidenceError(
                        "live quote delay does not match snapshot"
                    )

        if not self.descriptive_only:
            raise CurrentLiveEvidenceError(
                "current-live evidence must remain descriptive only"
            )
        forbidden = (
            self.provider_read_authority,
            self.provider_write_authority,
            self.broker_read_authority,
            self.broker_write_authority,
            self.order_creation_authority,
            self.paper_authority,
            self.live_authority,
            self.promotion_authority,
            self.confluence_authority,
        )
        if any(forbidden):
            raise CurrentLiveEvidenceError(
                "current-live evidence cannot grant external or trading authority"
            )

    @property
    def evidence_fingerprint(self) -> str:
        return _fingerprint_payload(
            {
                "contract_version": self.contract_version,
                "contract_fingerprint": self.contract_fingerprint,
                "source_id": self.source_id,
                "source_sha256": self.source_sha256,
                "source_byte_count": self.source_byte_count,
                "snapshot": self.snapshot,
            }
        )

    @property
    def snapshot_age_seconds(self) -> float:
        return (
            self.captured_at_utc - self.snapshot.generated_at_utc
        ).total_seconds()

    @property
    def minute_symbol_count(self) -> int:
        return sum(
            state.minute is not None for state in self.snapshot.symbols
        )

    @property
    def quote_symbol_count(self) -> int:
        return sum(
            state.quote is not None for state in self.snapshot.symbols
        )

    @property
    def fresh_minute_symbol_count(self) -> int:
        return sum(
            state.minute is not None
            and state.minute_freshness == LiveFreshness.FRESH
            for state in self.snapshot.symbols
        )

    @property
    def fresh_quote_symbol_count(self) -> int:
        return sum(
            state.quote is not None
            and state.quote_freshness == LiveFreshness.FRESH
            for state in self.snapshot.symbols
        )

    @property
    def minute_only_symbol_count(self) -> int:
        return sum(
            state.minute is not None and state.quote is None
            for state in self.snapshot.symbols
        )


def current_live_evidence_payload(
    evidence: CurrentLiveEvidenceV1,
) -> dict[str, object]:
    snapshot = evidence.snapshot
    return {
        "contract_version": evidence.contract_version,
        "contract_fingerprint": evidence.contract_fingerprint,
        "evidence_fingerprint": evidence.evidence_fingerprint,
        "source_id": evidence.source_id,
        "source_sha256": evidence.source_sha256,
        "source_byte_count": evidence.source_byte_count,
        "captured_at_utc": evidence.captured_at_utc.isoformat(),
        "snapshot_generated_at_utc": (
            snapshot.generated_at_utc.isoformat()
        ),
        "snapshot_age_seconds": evidence.snapshot_age_seconds,
        "feed_mode": snapshot.feed_mode.value,
        "expected_delay_seconds": snapshot.expected_delay_seconds,
        "connection_state": snapshot.connection_state.value,
        "session_segment": snapshot.session.session_segment.value,
        "is_exchange_session": snapshot.session.is_exchange_session,
        "subscription_count": len(snapshot.subscriptions),
        "symbol_count": snapshot.symbol_count,
        "minute_symbol_count": evidence.minute_symbol_count,
        "quote_symbol_count": evidence.quote_symbol_count,
        "fresh_minute_symbol_count": evidence.fresh_minute_symbol_count,
        "fresh_quote_symbol_count": evidence.fresh_quote_symbol_count,
        "minute_only_symbol_count": evidence.minute_only_symbol_count,
        "open_transport_gap": (
            snapshot.open_transport_gap_started_at_utc is not None
        ),
        "parse_error_count": snapshot.parse_errors,
        "reconnect_count": snapshot.reconnects,
        "last_received_at_utc": (
            None
            if snapshot.last_received_at_utc is None
            else snapshot.last_received_at_utc.isoformat()
        ),
        "minute_to_quote_fabrication": False,
        "network_provider_calls_performed": 0,
        "network_broker_calls_performed": 0,
        "descriptive_only": True,
        "authority": {
            "provider_read_authority": False,
            "provider_write_authority": False,
            "broker_read_authority": False,
            "broker_write_authority": False,
            "order_creation_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "promotion_authority": False,
            "confluence_authority": False,
        },
    }


def read_current_live_evidence_v1(
    path: Path,
    *,
    captured_at_utc: datetime | None = None,
) -> CurrentLiveEvidenceV1:
    path = Path(path)
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise CurrentLiveEvidenceError(
            "current live-state artifact is unavailable"
        ) from exc
    if size <= 0 or size > _MAX_SOURCE_BYTES:
        raise CurrentLiveEvidenceError(
            "current live-state artifact size is invalid"
        )
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CurrentLiveEvidenceError(
            "current live-state artifact could not be read"
        ) from exc
    if len(raw) != size:
        raise CurrentLiveEvidenceError(
            "current live-state artifact changed while reading"
        )
    try:
        snapshot = LiveStateSnapshot.model_validate_json(raw)
    except ValidationError as exc:
        raise CurrentLiveEvidenceError(
            "current live-state artifact failed schema validation"
        ) from exc

    captured = captured_at_utc or datetime.now(UTC)
    _require_aware(captured, label="capture timestamp")
    captured = captured.astimezone(UTC)
    return CurrentLiveEvidenceV1(
        contract_version=CURRENT_LIVE_EVIDENCE_CONTRACT_VERSION,
        contract_fingerprint=CURRENT_LIVE_EVIDENCE_CONTRACT_FINGERPRINT,
        source_id=CURRENT_LIVE_EVIDENCE_SOURCE_ID,
        source_sha256=hashlib.sha256(raw).hexdigest(),
        source_byte_count=len(raw),
        captured_at_utc=captured,
        snapshot=snapshot,
    )


def capture_current_live_evidence_v1(
    settings: AtlasSettings,
    *,
    captured_at_utc: datetime | None = None,
) -> CurrentLiveEvidenceV1:
    return read_current_live_evidence_v1(
        MarketDataPaths(settings).live_state_file(),
        captured_at_utc=captured_at_utc,
    )


__all__ = [
    "CURRENT_LIVE_EVIDENCE_CONTRACT_FINGERPRINT",
    "CURRENT_LIVE_EVIDENCE_SOURCE_ID",
    "CurrentLiveEvidenceError",
    "CurrentLiveEvidenceV1",
    "capture_current_live_evidence_v1",
    "current_live_evidence_payload",
    "read_current_live_evidence_v1",
]
