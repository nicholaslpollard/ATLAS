from __future__ import annotations

import gzip
import hashlib
import json
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import replace_with_retry, unique_temp_path
from packages.core.enums import Timeframe
from packages.features.feature_registry import (
    CORE_FEATURE_CONTRACT_VERSION,
    CORE_FEATURE_REGISTRY,
)
from packages.features.incremental import (
    IncrementalFeatureEngine,
    IncrementalSymbolFeatureState,
    _EMAState,
    _WilderState,
)


FEATURE_STATE_SCHEMA_VERSION = 2


def _recursive_payload(state: _EMAState | _WilderState) -> dict[str, float | int | None]:
    return {
        "period": state.period,
        "count": state.count,
        "seed_sum": state.seed_sum,
        "value": state.value,
    }


def _ema(payload: dict[str, Any]) -> _EMAState:
    return _EMAState(
        period=int(payload["period"]),
        count=int(payload["count"]),
        seed_sum=float(payload["seed_sum"]),
        value=None if payload["value"] is None else float(payload["value"]),
    )


def _wilder(payload: dict[str, Any]) -> _WilderState:
    return _WilderState(
        period=int(payload["period"]),
        count=int(payload["count"]),
        seed_sum=float(payload["seed_sum"]),
        value=None if payload["value"] is None else float(payload["value"]),
    )


def _state_payload(state_key: str, state: IncrementalSymbolFeatureState) -> dict[str, Any]:
    return {
        "state_key": state_key,
        "symbol": state.symbol,
        "last_timestamp_utc": (
            state.last_timestamp_utc.isoformat() if state.last_timestamp_utc is not None else None
        ),
        "previous_close": state.previous_close,
        "ema20": _recursive_payload(state.ema20),
        "ema50": _recursive_payload(state.ema50),
        "ema200": _recursive_payload(state.ema200),
        "ema12_macd": _recursive_payload(state.ema12_macd),
        "ema26_macd": _recursive_payload(state.ema26_macd),
        "macd_signal": _recursive_payload(state.macd_signal),
        "rsi_gain": _recursive_payload(state.rsi_gain),
        "rsi_loss": _recursive_payload(state.rsi_loss),
        "atr": _recursive_payload(state.atr),
        "previous_ema20": state.previous_ema20,
        "obv": state.obv,
        "has_obv_seed": state.has_obv_seed,
        "closes": list(state.closes),
        "highs": list(state.highs),
        "lows": list(state.lows),
        "volumes": list(state.volumes),
        "dollar_volumes": list(state.dollar_volumes),
        "log_returns": list(state.log_returns),
    }


def _restore_symbol(payload: dict[str, Any]) -> IncrementalSymbolFeatureState:
    last_timestamp = payload.get("last_timestamp_utc")
    return IncrementalSymbolFeatureState(
        symbol=str(payload["symbol"]),
        last_timestamp_utc=datetime.fromisoformat(last_timestamp) if last_timestamp else None,
        previous_close=(
            None if payload.get("previous_close") is None else float(payload["previous_close"])
        ),
        ema20=_ema(payload["ema20"]),
        ema50=_ema(payload["ema50"]),
        ema200=_ema(payload["ema200"]),
        ema12_macd=_ema(payload["ema12_macd"]),
        ema26_macd=_ema(payload["ema26_macd"]),
        macd_signal=_ema(payload["macd_signal"]),
        rsi_gain=_wilder(payload["rsi_gain"]),
        rsi_loss=_wilder(payload["rsi_loss"]),
        atr=_wilder(payload["atr"]),
        previous_ema20=(
            None if payload.get("previous_ema20") is None else float(payload["previous_ema20"])
        ),
        obv=float(payload.get("obv", 0.0)),
        has_obv_seed=bool(payload.get("has_obv_seed", False)),
        closes=deque((float(value) for value in payload.get("closes", [])), maxlen=20),
        highs=deque((float(value) for value in payload.get("highs", [])), maxlen=20),
        lows=deque((float(value) for value in payload.get("lows", [])), maxlen=20),
        volumes=deque((float(value) for value in payload.get("volumes", [])), maxlen=20),
        dollar_volumes=deque(
            (float(value) for value in payload.get("dollar_volumes", [])), maxlen=20
        ),
        log_returns=deque(
            (float(value) for value in payload.get("log_returns", [])), maxlen=20
        ),
    )


def build_checkpoint_payload(
    engine: IncrementalFeatureEngine,
    *,
    timeframe: Timeframe,
    as_of_date: str,
) -> dict[str, Any]:
    states = [
        _state_payload(state_key, engine._states[state_key])
        for state_key in sorted(engine._states)
    ]
    return {
        "schema_version": FEATURE_STATE_SCHEMA_VERSION,
        "feature_contract_version": CORE_FEATURE_CONTRACT_VERSION,
        "feature_registry_fingerprint": CORE_FEATURE_REGISTRY.fingerprint(),
        "timeframe": timeframe.value,
        "as_of_date": as_of_date,
        "state_count": len(states),
        "symbol_count": engine.symbol_count,
        "states": states,
    }


def checkpoint_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def feature_state_fingerprint(
    engine: IncrementalFeatureEngine,
    *,
    timeframe: Timeframe,
    as_of_date: str,
) -> str:
    """Fingerprint exact in-memory state without writing a checkpoint file."""

    return checkpoint_fingerprint(
        build_checkpoint_payload(engine, timeframe=timeframe, as_of_date=as_of_date)
    )


class FeatureStateCheckpointStore:
    """Portable, deterministic gzip-JSON snapshots of exact incremental feature state."""

    def write(
        self,
        path: Path,
        engine: IncrementalFeatureEngine,
        *,
        timeframe: Timeframe,
        as_of_date: str,
    ) -> str:
        payload = build_checkpoint_payload(engine, timeframe=timeframe, as_of_date=as_of_date)
        fingerprint = checkpoint_fingerprint(payload)
        payload["checkpoint_fingerprint"] = fingerprint
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        compressed = gzip.compress(raw, compresslevel=6, mtime=0)

        path = Path(path)
        temp = unique_temp_path(path)
        try:
            with temp.open("wb") as handle:
                handle.write(compressed)
                handle.flush()
            replace_with_retry(temp, path)
        except Exception:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        return fingerprint

    def read(
        self,
        path: Path,
        *,
        expected_timeframe: Timeframe | None = None,
    ) -> tuple[IncrementalFeatureEngine, dict[str, Any]]:
        path = Path(path)
        with gzip.open(path, "rb") as handle:
            payload = json.loads(handle.read().decode("utf-8"))

        if int(payload.get("schema_version", -1)) != FEATURE_STATE_SCHEMA_VERSION:
            raise ValueError("unsupported feature-state checkpoint schema")
        if payload.get("feature_contract_version") != CORE_FEATURE_CONTRACT_VERSION:
            raise ValueError("feature-state checkpoint contract version is stale")
        if payload.get("feature_registry_fingerprint") != CORE_FEATURE_REGISTRY.fingerprint():
            raise ValueError("feature-state checkpoint registry fingerprint is stale")
        if expected_timeframe is not None and payload.get("timeframe") != expected_timeframe.value:
            raise ValueError("feature-state checkpoint timeframe mismatch")

        claimed = payload.get("checkpoint_fingerprint")
        fingerprint_payload = dict(payload)
        fingerprint_payload.pop("checkpoint_fingerprint", None)
        actual = checkpoint_fingerprint(fingerprint_payload)
        if claimed != actual:
            raise ValueError("feature-state checkpoint fingerprint mismatch")

        engine = IncrementalFeatureEngine()
        for item in payload.get("states", []):
            state = _restore_symbol(item)
            state_key = str(item.get("state_key", ""))
            if not state_key:
                raise ValueError("feature-state checkpoint contains a blank state_key")
            if state_key in engine._states:
                raise ValueError(f"duplicate feature-state key: {state_key}")
            engine._states[state_key] = state
        if int(payload.get("state_count", -1)) != engine.state_count:
            raise ValueError("feature-state checkpoint state count mismatch")
        if int(payload.get("symbol_count", -1)) != engine.symbol_count:
            raise ValueError("feature-state checkpoint symbol count mismatch")
        return engine, payload
