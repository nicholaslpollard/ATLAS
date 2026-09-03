from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pandas as pd

from packages.backtesting.reference_lake_adapter import validate_reference_lake_scope
from packages.core.settings import AtlasSettings
from packages.regimes.split_origin_policy import (
    MARKET_SECTOR_HISTORY_ORIGIN_DATE,
    MARKET_SECTOR_MANIFEST_VERSION,
    MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
    MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
    SPLIT_ORIGIN_POLICY_VERSION,
)
from packages.regimes.split_origin_state_engine import SplitOriginRegimeStateEngine


REFERENCE_REGIME_CONTEXT_CONTRACT_VERSION = (
    "reference-regime-context-v1-exact-asof-hash-bound-same-close-market-only"
)
REFERENCE_REGIME_CONTEXT_PROTECTED_RETURN_READS = 0
REFERENCE_REGIME_CONTEXT_PROVIDER_WRITES = 0
REFERENCE_REGIME_CONTEXT_BROKER_WRITES = 0
REFERENCE_REGIME_CONTEXT_PAPER_SUBMITS = 0
REFERENCE_REGIME_CONTEXT_LIVE_WRITES = 0
UNAVAILABLE_REGIME_CONTEXT = "UNAVAILABLE"


class ReferenceRegimeContextError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ReferenceMarketRegimeSource:
    manifest_path: Path
    snapshot_path: Path
    market_effective_path: Path


@dataclass(frozen=True, slots=True)
class ReferenceRegimeContextResult:
    bars: pd.DataFrame
    report: dict[str, object]


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


def _read_json(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise ReferenceRegimeContextError(f"missing exact-as-of {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReferenceRegimeContextError(f"invalid exact-as-of {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise ReferenceRegimeContextError(f"exact-as-of {label} must be a JSON object")
    return payload


def _resolved_equal(left: object, right: Path) -> bool:
    try:
        return Path(str(left)).resolve() == right.resolve()
    except (OSError, ValueError):
        return False


class ReferenceRegimeContextAdapter:
    """Attach accepted PIT market state without inventing ticker or sector context.

    The exact split-origin history whose ``as_of_date`` equals the replay end is the
    only permitted source. Its manifest binds the snapshot and market-effective
    Parquet hashes. Same-session market state is available at the finalized regular
    close and is therefore usable by a strategy that cannot enter before the next
    regular-session open.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.engine = SplitOriginRegimeStateEngine(settings)

    def discover_source(self, end_date: date) -> ReferenceMarketRegimeSource:
        paths = self.engine.history_paths(end_date)
        return ReferenceMarketRegimeSource(
            manifest_path=self.engine.manifest_path(end_date),
            snapshot_path=self.engine.snapshot_path(end_date),
            market_effective_path=paths["market_effective"],
        )

    @staticmethod
    def _validate_contract(
        source: ReferenceMarketRegimeSource,
        end_date: date,
    ) -> tuple[dict[str, object], dict[str, object], str, str, str]:
        manifest = _read_json(source.manifest_path, "regime manifest")
        expected_manifest = {
            "manifest_version": MARKET_SECTOR_MANIFEST_VERSION,
            "snapshot_contract_version": MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
            "state_policy_contract_version": MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
            "split_origin_policy_version": SPLIT_ORIGIN_POLICY_VERSION,
            "as_of_date": end_date.isoformat(),
        }
        for field, expected in expected_manifest.items():
            if manifest.get(field) != expected:
                raise ReferenceRegimeContextError(
                    f"exact-as-of regime manifest {field} does not match {expected}"
                )
        if manifest.get("history_origin_date") != MARKET_SECTOR_HISTORY_ORIGIN_DATE.isoformat():
            raise ReferenceRegimeContextError("regime manifest history origin drifted")
        if not _resolved_equal(manifest.get("snapshot_path"), source.snapshot_path):
            raise ReferenceRegimeContextError("regime manifest snapshot path is not exact")

        history_files = manifest.get("history_files")
        if not isinstance(history_files, dict):
            raise ReferenceRegimeContextError("regime manifest has no history_files object")
        market_entry = history_files.get("market_effective")
        if not isinstance(market_entry, dict):
            raise ReferenceRegimeContextError("regime manifest has no market_effective binding")
        if not _resolved_equal(market_entry.get("path"), source.market_effective_path):
            raise ReferenceRegimeContextError("market-effective history path is not exact")

        snapshot = _read_json(source.snapshot_path, "regime snapshot")
        expected_snapshot = {
            "snapshot_contract_version": MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
            "state_policy_contract_version": MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
            "split_origin_policy_version": SPLIT_ORIGIN_POLICY_VERSION,
            "as_of_date": end_date.isoformat(),
        }
        for field, expected in expected_snapshot.items():
            if snapshot.get(field) != expected:
                raise ReferenceRegimeContextError(
                    f"exact-as-of regime snapshot {field} does not match {expected}"
                )

        snapshot_sha = _sha256_file(source.snapshot_path)
        if manifest.get("snapshot_sha256") != snapshot_sha:
            raise ReferenceRegimeContextError("regime snapshot SHA-256 drifted")
        if not source.market_effective_path.is_file():
            raise ReferenceRegimeContextError(
                f"missing exact-as-of market-effective history: {source.market_effective_path}"
            )
        market_sha = _sha256_file(source.market_effective_path)
        if market_entry.get("sha256") != market_sha:
            raise ReferenceRegimeContextError("market-effective history SHA-256 drifted")
        manifest_sha = _sha256_file(source.manifest_path)
        return manifest, snapshot, manifest_sha, snapshot_sha, market_sha

    def attach(
        self,
        bars: pd.DataFrame,
        start_date: date,
        end_date: date,
        *,
        source: ReferenceMarketRegimeSource | None = None,
    ) -> ReferenceRegimeContextResult:
        validate_reference_lake_scope(start_date, end_date)
        if bars.empty:
            raise ReferenceRegimeContextError("regime context requires input bars")
        required = {"session_date", "signal_available_at_utc"}
        missing = sorted(required.difference(bars.columns))
        if missing:
            raise ReferenceRegimeContextError(
                "regime context input is missing columns: " + ", ".join(missing)
            )
        context_columns = {
            "market_regime_composite",
            "market_regime_available_at_utc",
            "sector_regime_composite",
            "ticker_regime_composite",
        }
        collision = sorted(context_columns.intersection(bars.columns))
        if collision:
            raise ReferenceRegimeContextError(
                "regime context columns already exist: " + ", ".join(collision)
            )

        enriched = bars.copy()
        enriched["session_date"] = pd.to_datetime(
            enriched["session_date"], errors="raise"
        ).dt.date
        enriched["signal_available_at_utc"] = pd.to_datetime(
            enriched["signal_available_at_utc"], utc=True, errors="raise"
        )
        if enriched["signal_available_at_utc"].isna().any():
            raise ReferenceRegimeContextError("signal availability timestamps cannot be null")
        observed = set(enriched["session_date"])
        if any(item < start_date or item > end_date for item in observed):
            raise ReferenceRegimeContextError("input bar session falls outside requested scope")
        try:
            expected_close = enriched["session_date"].map(
                lambda item: self.engine.calendar.regular_open_close(item)[1]
            )
        except ValueError as exc:
            raise ReferenceRegimeContextError(
                "regime context input contains a non-XNYS session"
            ) from exc
        expected_close = pd.to_datetime(expected_close, utc=True, errors="raise")
        if (enriched["signal_available_at_utc"] != expected_close).any():
            raise ReferenceRegimeContextError(
                "signal availability must equal the exact XNYS regular close"
            )

        resolved_source = source or self.discover_source(end_date)
        manifest, _snapshot, manifest_sha, snapshot_sha, market_sha = self._validate_contract(
            resolved_source, end_date
        )

        con = duckdb.connect(":memory:")
        try:
            history = con.execute(
                """
                SELECT CAST(trading_date AS DATE) AS session_date,
                       trim(CAST(composite AS VARCHAR)) AS market_regime_composite
                FROM read_parquet(?)
                WHERE CAST(trading_date AS DATE) BETWEEN ? AND ?
                ORDER BY trading_date
                """,
                [str(resolved_source.market_effective_path), start_date, end_date],
            ).fetchdf()
            bounds = con.execute(
                """
                SELECT min(CAST(trading_date AS DATE)), max(CAST(trading_date AS DATE)),
                       count(*), count(DISTINCT CAST(trading_date AS DATE)),
                       count(*) FILTER (
                           WHERE composite IS NULL OR trim(CAST(composite AS VARCHAR)) = ''
                       )
                FROM read_parquet(?)
                """,
                [str(resolved_source.market_effective_path)],
            ).fetchone()
        except duckdb.Error as exc:
            raise ReferenceRegimeContextError(
                "market-effective history does not satisfy the accepted schema"
            ) from exc
        finally:
            con.close()
        assert bounds is not None
        if bounds[0] is None or bounds[1] is None:
            raise ReferenceRegimeContextError("market-effective history is empty")
        if bounds[0] < MARKET_SECTOR_HISTORY_ORIGIN_DATE or bounds[1] != end_date:
            raise ReferenceRegimeContextError(
                "market-effective history range is not exact for the accepted as-of date"
            )
        if int(bounds[2]) != int(bounds[3]):
            raise ReferenceRegimeContextError("market-effective history has duplicate sessions")
        if int(bounds[4]) != 0:
            raise ReferenceRegimeContextError("market-effective history has blank regime state")

        history["session_date"] = pd.to_datetime(history["session_date"]).dt.date
        available = set(history["session_date"])
        missing_sessions = sorted(observed.difference(available))
        if missing_sessions:
            preview = ", ".join(item.isoformat() for item in missing_sessions[:10])
            raise ReferenceRegimeContextError(
                "market-effective history is missing input sessions: " + preview
            )

        enriched = enriched.merge(
            history,
            on="session_date",
            how="left",
            validate="many_to_one",
            sort=False,
        )
        if enriched["market_regime_composite"].isna().any():
            raise ReferenceRegimeContextError("market regime join produced null state")
        enriched["market_regime_available_at_utc"] = enriched["signal_available_at_utc"]
        enriched["sector_regime_composite"] = UNAVAILABLE_REGIME_CONTEXT
        enriched["ticker_regime_composite"] = UNAVAILABLE_REGIME_CONTEXT

        state_counts = {
            str(key): int(value)
            for key, value in enriched.groupby(
                "market_regime_composite", observed=True
            ).size().sort_index().items()
        }
        source_fingerprint = _stable_hash(
            {
                "contract_version": REFERENCE_REGIME_CONTEXT_CONTRACT_VERSION,
                "as_of_date": end_date,
                "manifest_sha256": manifest_sha,
                "snapshot_sha256": snapshot_sha,
                "market_effective_sha256": market_sha,
                "dependency_fingerprint": manifest.get("dependency_fingerprint"),
                "join": "same-session-effective-market-state-available-at-regular-close",
                "ticker_regime": UNAVAILABLE_REGIME_CONTEXT,
                "sector_regime": UNAVAILABLE_REGIME_CONTEXT,
            }
        )
        report: dict[str, object] = {
            "contract_version": REFERENCE_REGIME_CONTEXT_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "status": "PASS",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "source_as_of_date": manifest["as_of_date"],
            "manifest_path": str(resolved_source.manifest_path.resolve()),
            "manifest_sha256": manifest_sha,
            "snapshot_path": str(resolved_source.snapshot_path.resolve()),
            "snapshot_sha256": snapshot_sha,
            "market_effective_path": str(resolved_source.market_effective_path.resolve()),
            "market_effective_sha256": market_sha,
            "source_fingerprint": source_fingerprint,
            "input_rows": int(len(bars)),
            "output_rows": int(len(enriched)),
            "observed_sessions": len(observed),
            "market_state_counts": state_counts,
            "market_regime_timing": "SAME_SESSION_FINALIZED_CLOSE_FOR_NEXT_OPEN_DECISION",
            "ticker_regime": UNAVAILABLE_REGIME_CONTEXT,
            "ticker_regime_reason": "NO_ACCEPTED_REFERENCE_REPLAY_PIT_TICKER_STATE_JOIN",
            "sector_regime": UNAVAILABLE_REGIME_CONTEXT,
            "sector_regime_reason": "NO_ACCEPTED_PIT_INSTRUMENT_TO_SECTOR_MAPPING",
            "future_regime_rows_read": 0,
            "protected_master_return_rows_read": REFERENCE_REGIME_CONTEXT_PROTECTED_RETURN_READS,
            "provider_writes": REFERENCE_REGIME_CONTEXT_PROVIDER_WRITES,
            "broker_writes": REFERENCE_REGIME_CONTEXT_BROKER_WRITES,
            "paper_submits": REFERENCE_REGIME_CONTEXT_PAPER_SUBMITS,
            "live_writes": REFERENCE_REGIME_CONTEXT_LIVE_WRITES,
            "checks": {
                "exact_asof_manifest": True,
                "snapshot_hash_bound": True,
                "market_effective_hash_bound": True,
                "no_future_regime_rows": True,
                "all_observed_sessions_joined": True,
                "same_close_availability_explicit": True,
                "ticker_and_sector_unavailable_not_guessed": True,
                "external_writes_zero": True,
            },
        }
        return ReferenceRegimeContextResult(bars=enriched, report=report)
