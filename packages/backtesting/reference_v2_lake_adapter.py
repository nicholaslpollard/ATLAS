from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from packages.backtesting.reference_portfolio_policy import (
    reference_portfolio_policy_fingerprint,
)
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings
from packages.data.alpaca_v2_postbuild import (
    MASTER_HOLDOUT_AUTHORIZATION_CONTRACT,
    MASTER_HOLDOUT_CONSUMPTION_CONTRACT,
    RESEARCH_DAILY_CONTRACT,
    V2_REFERENCE_DEVELOPMENT_END,
    V2_REFERENCE_MASTER_PROTECTED_END,
    V2_REFERENCE_MASTER_PROTECTED_START,
    WALK_FORWARD_DAILY_CONTRACT,
    master_holdout_authorization_id,
)
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.holdout_receipts import read_holdout_receipt
from packages.features.reference_daily import REFERENCE_DAILY_FEATURE_FINGERPRINT
from packages.strategies.reference_library import (
    REFERENCE_STRATEGY_POLICY_FINGERPRINT,
)


REFERENCE_V2_LAKE_ADAPTER_CONTRACT_VERSION = (
    "reference-v2-lake-adapter-v2-alpaca-sip-hash-bound-explicit-evaluation-scopes"
)
REFERENCE_V2_UNAVAILABLE_REGIME_CONTRACT_VERSION = (
    "reference-v2-regime-context-v1-explicitly-unavailable-no-v1-fallback"
)
REFERENCE_V2_DEVELOPMENT_END = V2_REFERENCE_DEVELOPMENT_END
REFERENCE_V2_MASTER_PROTECTED_START = V2_REFERENCE_MASTER_PROTECTED_START
REFERENCE_V2_MASTER_PROTECTED_END = V2_REFERENCE_MASTER_PROTECTED_END
UNAVAILABLE_REGIME_CONTEXT = "UNAVAILABLE"


class ReferenceV2LakeAdapterError(RuntimeError):
    pass


class ReferenceV2LakeScopeError(ReferenceV2LakeAdapterError):
    pass


@dataclass(frozen=True, slots=True)
class ReferenceV2LakeAdapterResult:
    bars: pd.DataFrame
    report: dict[str, object]


@dataclass(frozen=True, slots=True)
class ReferenceV2RegimeContextResult:
    bars: pd.DataFrame
    report: dict[str, object]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_hash(value: object) -> str:
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReferenceV2LakeAdapterError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise ReferenceV2LakeAdapterError(f"{label} must be a JSON object: {path}")
    return value


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _sql_paths(paths: tuple[Path, ...]) -> str:
    return "[" + ",".join(
        "'" + path.as_posix().replace("'", "''") + "'" for path in paths
    ) + "]"


class ReferenceV2DailyLakeAdapter:
    """Load only the hash-bound Alpaca SIP V2 daily research generation.

    The adapter cannot discover or fall back to legacy canonical, Massive, feature,
    regime, or identity paths. It accepts only the independently materialized V2
    research-daily manifest and its exact partition hashes.
    """

    _EXPECTED_COLUMNS = (
        "instrument_id",
        "ticker",
        "session_date",
        "timestamp_utc",
        "signal_available_at_utc",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "unadjusted_close",
        "pit_active",
        "security_type",
        "identity_clear",
        "price_adjustment_mode",
        "raw_price_lineage_id",
        "source_provider",
        "source_dataset",
        "adjusted_source_id",
    )
    _MANIFEST_NAME = "research_daily.json"
    _VIEW_DIRECTORY = "research_daily"
    _EXPECTED_CONTRACT = RESEARCH_DAILY_CONTRACT
    _ALLOW_PROTECTED = False
    _REPORT_SCOPE = "ALPACA_SIP_V2_DEVELOPMENT_ONLY"

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.data_root = (settings.project_root / "data").resolve()
        self.layout = V2Layout.beneath(self.data_root)
        self.calendar = MarketCalendar(exchange=settings.data.calendar.exchange)

    def _manifest(self, manifest_path: Path | None) -> tuple[Path, dict[str, Any]]:
        expected = (self.layout.manifests / self._MANIFEST_NAME).resolve()
        resolved = expected if manifest_path is None else Path(manifest_path).resolve()
        if resolved != expected:
            raise ReferenceV2LakeAdapterError(
                f"V2 adapter accepts only the isolated V2 {self._MANIFEST_NAME} manifest"
            )
        manifest = _read_json(resolved, "V2 research-daily manifest")
        required = {
            "contract": self._EXPECTED_CONTRACT,
            "status": "PASS",
            "v1_ancestry": "FORBIDDEN",
            "v1_rows_read": 0,
            "historical_performance_opened": False,
            "production_promoted": False,
            "paper_authority": False,
            "live_authority": False,
            "cash_dividend_credits_materialized": False,
            "development_only": not self._ALLOW_PROTECTED,
        }
        for field, expected_value in required.items():
            if manifest.get(field) != expected_value:
                raise ReferenceV2LakeAdapterError(
                    f"V2 research-daily manifest {field} is not {expected_value!r}"
                )
        protected_materialized = int(
            manifest.get("protected_return_rows_materialized", -1)
        )
        if self._ALLOW_PROTECTED:
            walk_forward_manifest = {
                "evaluation_scope": "FROZEN_ONE_TIME_WALK_FORWARD",
                "evaluation_start_session": REFERENCE_V2_MASTER_PROTECTED_START.isoformat(),
                "evaluation_end_session": manifest.get("cutoff_session"),
            }
            for field, expected_value in walk_forward_manifest.items():
                if manifest.get(field) != expected_value:
                    raise ReferenceV2LakeAdapterError(
                        f"V2 walk-forward manifest {field} is not {expected_value!r}"
                    )
            if protected_materialized <= 0:
                raise ReferenceV2LakeAdapterError(
                    "V2 walk-forward manifest has no materialized protected rows"
                )
            if (
                manifest.get("master_protected_return_rows_read")
                != protected_materialized
                or manifest.get("master_protected_holdout_consumed") is not True
            ):
                raise ReferenceV2LakeAdapterError(
                    "V2 walk-forward manifest does not account for consumed protected rows"
                )
            authorization_path = (
                self.layout.manifests / "master_holdout_authorization.json"
            ).resolve()
            authorization = _read_json(
                authorization_path, "master holdout authorization"
            )
            required_authorization = {
                "contract": MASTER_HOLDOUT_AUTHORIZATION_CONTRACT,
                "status": "AUTHORIZED_PENDING_HOLDOUT_READ",
                "purpose": "A33_B33_FROZEN_REFERENCE_WALK_FORWARD",
                "authorization_mechanism": "EXPLICIT_OPERATOR_CLI_FLAG",
                "master_protected_start": REFERENCE_V2_MASTER_PROTECTED_START.isoformat(),
                "master_protected_end": REFERENCE_V2_MASTER_PROTECTED_END.isoformat(),
                "source_cutoff_session": manifest.get("source_cutoff_session"),
                "development_end": REFERENCE_V2_DEVELOPMENT_END.isoformat(),
                "native_acceptance_fingerprint": manifest.get(
                    "native_acceptance_fingerprint"
                ),
                "split_daily_fingerprint": manifest.get("split_daily_fingerprint"),
                "strategy_policy_fingerprint": REFERENCE_STRATEGY_POLICY_FINGERPRINT,
                "feature_fingerprint": REFERENCE_DAILY_FEATURE_FINGERPRINT,
                "portfolio_policy_fingerprint": reference_portfolio_policy_fingerprint(),
                "parameter_changes_during_forward_window_permitted": False,
                "historical_reclassification_as_paper_permitted": False,
                "strategy_authority_promoted": False,
                "paper_authority": False,
                "live_authority": False,
            }
            for field, expected_value in required_authorization.items():
                if authorization.get(field) != expected_value:
                    raise ReferenceV2LakeAdapterError(
                        f"master holdout authorization {field} is not {expected_value!r}"
                    )
            authorization_id = str(authorization.get("authorization_id") or "")
            if (
                authorization_id != manifest.get("holdout_authorization_id")
                or authorization_id != master_holdout_authorization_id(authorization)
            ):
                raise ReferenceV2LakeAdapterError(
                    "master holdout authorization is not self-hash bound to the manifest"
                )
            try:
                authorized_at = datetime.fromisoformat(
                    str(authorization["authorized_at_utc"])
                )
            except (KeyError, ValueError) as exc:
                raise ReferenceV2LakeAdapterError(
                    "master holdout authorization timestamp is invalid"
                ) from exc
            if authorized_at.tzinfo is None or authorized_at.utcoffset() is None:
                raise ReferenceV2LakeAdapterError(
                    "master holdout authorization timestamp must be timezone-aware"
                )
            receipt = read_holdout_receipt(
                self.layout.manifests / "master_holdout_consumption.json"
            )
            required_receipt = {
                "contract": MASTER_HOLDOUT_CONSUMPTION_CONTRACT,
                "authorization_id": authorization_id,
                "master_protected_start": REFERENCE_V2_MASTER_PROTECTED_START.isoformat(),
                "master_protected_end": REFERENCE_V2_MASTER_PROTECTED_END.isoformat(),
                "walk_forward_end": manifest.get("cutoff_session"),
                "protected_return_rows_read": protected_materialized,
                "protected_rows_accounting_pending": False,
                "historical_replay_not_prospective_paper": True,
                "strategy_authority_promoted": False,
                "paper_authority": False,
                "live_authority": False,
            }
            for field, expected_value in required_receipt.items():
                if receipt.get(field) != expected_value:
                    raise ReferenceV2LakeAdapterError(
                        f"master holdout consumption receipt {field} is not {expected_value!r}"
                    )
            if receipt.get("status") not in {
                "CONSUMED_REPLAY_STARTED",
                "CONSUMED_REPLAY_FAILED",
                "CONSUMED_WALK_FORWARD_COMPLETE",
            }:
                raise ReferenceV2LakeAdapterError(
                    "master holdout consumption receipt does not authorize replay access"
                )
        elif (
            protected_materialized != 0
            or manifest.get("master_protected_return_rows_read") != 0
            or manifest.get("master_protected_holdout_consumed") is not False
        ):
            raise ReferenceV2LakeAdapterError(
                "V2 DEVELOPMENT manifest materialized or consumed protected rows"
            )
        fingerprint = str(manifest.get("source_fingerprint") or "")
        if len(fingerprint) != 64:
            raise ReferenceV2LakeAdapterError(
                "V2 research-daily source fingerprint is missing or malformed"
            )
        return resolved, manifest

    def _scope(
        self,
        start_date: date,
        end_date: date,
        manifest: dict[str, Any],
    ) -> tuple[date, date, tuple[date, ...]]:
        if end_date < start_date:
            raise ReferenceV2LakeScopeError("V2 replay end_date precedes start_date")
        if not self._ALLOW_PROTECTED and end_date > REFERENCE_V2_DEVELOPMENT_END:
            raise ReferenceV2LakeScopeError(
                "V2 reference replay cannot read the retained master protected window"
            )
        try:
            source_start = date.fromisoformat(str(manifest["start_date"]))
            source_end = date.fromisoformat(str(manifest["cutoff_session"]))
            capture_end = date.fromisoformat(str(manifest["source_cutoff_session"]))
        except (KeyError, ValueError) as exc:
            raise ReferenceV2LakeAdapterError(
                "V2 research-daily manifest has an invalid date range"
            ) from exc
        if not self._ALLOW_PROTECTED and source_end > REFERENCE_V2_DEVELOPMENT_END:
            raise ReferenceV2LakeAdapterError(
                "V2 research-daily source crosses the protected DEVELOPMENT cutoff"
            )
        expected_end = (
            capture_end
            if self._ALLOW_PROTECTED
            else min(capture_end, REFERENCE_V2_DEVELOPMENT_END)
        )
        if source_end != expected_end:
            raise ReferenceV2LakeAdapterError(
                "V2 research-daily cutoff is not the exact scope-safe source cutoff"
            )
        if self._ALLOW_PROTECTED:
            authorization = _read_json(
                self.layout.manifests / "master_holdout_authorization.json",
                "master holdout authorization",
            )
            if authorization.get("development_start") != start_date.isoformat():
                raise ReferenceV2LakeScopeError(
                    "V2 walk-forward warm-up start differs from its frozen authorization"
                )
            if start_date > REFERENCE_V2_DEVELOPMENT_END:
                raise ReferenceV2LakeScopeError(
                    "V2 walk-forward load requires pre-holdout indicator warm-up history"
                )
            if end_date < REFERENCE_V2_MASTER_PROTECTED_END:
                raise ReferenceV2LakeScopeError(
                    "V2 walk-forward load must contain the complete master holdout"
                )
            if end_date != source_end:
                raise ReferenceV2LakeScopeError(
                    "V2 walk-forward load must end at the latest validated source session"
                )
        if start_date < source_start or end_date > source_end:
            raise ReferenceV2LakeScopeError(
                f"requested scope is outside V2 research data {source_start}..{source_end}"
            )
        sessions = tuple(self.calendar.sessions_in_range(start_date, end_date))
        if not sessions:
            raise ReferenceV2LakeScopeError("V2 replay scope contains no XNYS sessions")
        if sessions[0] != start_date or sessions[-1] != end_date:
            raise ReferenceV2LakeScopeError(
                "V2 replay start_date and end_date must both be XNYS sessions"
            )
        return source_start, source_end, sessions

    def _partitions(
        self, manifest: dict[str, Any]
    ) -> tuple[tuple[Path, ...], list[dict[str, object]]]:
        records = manifest.get("partitions")
        if not isinstance(records, list) or not records:
            raise ReferenceV2LakeAdapterError(
                "V2 research-daily manifest has no partitions"
            )
        fingerprint = str(manifest["source_fingerprint"])
        expected_root = (
            self.layout.derived / self._VIEW_DIRECTORY / fingerprint[:16]
        ).resolve()
        paths: list[Path] = []
        inventory: list[dict[str, object]] = []
        years: set[int] = set()
        reported_total = 0
        for record in records:
            if not isinstance(record, dict):
                raise ReferenceV2LakeAdapterError(
                    "V2 research-daily partition record is malformed"
                )
            try:
                year = int(record["year"])
                path = Path(str(record["path"])).resolve()
                expected_hash = str(record["sha256"])
                rows = int(record["rows"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ReferenceV2LakeAdapterError(
                    "V2 research-daily partition record is incomplete"
                ) from exc
            if year in years:
                raise ReferenceV2LakeAdapterError(
                    f"duplicate V2 research-daily year partition: {year}"
                )
            years.add(year)
            if not _inside(path, expected_root):
                raise ReferenceV2LakeAdapterError(
                    f"V2 research-daily partition escapes its generation: {path}"
                )
            if path.parent.name != f"year={year:04d}":
                raise ReferenceV2LakeAdapterError(
                    f"V2 research-daily partition year/path mismatch: {path}"
                )
            if not path.is_file():
                raise FileNotFoundError(f"missing V2 research-daily partition: {path}")
            actual_hash = _sha256_file(path)
            if actual_hash != expected_hash:
                raise ReferenceV2LakeAdapterError(
                    f"V2 research-daily partition SHA-256 drifted: {path}"
                )
            if rows < 1:
                raise ReferenceV2LakeAdapterError(
                    f"V2 research-daily partition row count is invalid: {path}"
                )
            reported_total += rows
            paths.append(path)
            inventory.append(
                {"year": year, "path": str(path), "sha256": actual_hash, "rows": rows}
            )
        if reported_total != int(manifest.get("research_rows", -1)):
            raise ReferenceV2LakeAdapterError(
                "V2 research-daily partition rows do not match the manifest total"
            )
        return tuple(paths), inventory

    def load(
        self,
        start_date: date,
        end_date: date,
        *,
        manifest_path: Path | None = None,
    ) -> ReferenceV2LakeAdapterResult:
        resolved_manifest, manifest = self._manifest(manifest_path)
        source_start, source_end, sessions = self._scope(
            start_date, end_date, manifest
        )
        paths, inventory = self._partitions(manifest)
        selected = tuple(
            path
            for path, record in zip(paths, inventory, strict=True)
            if start_date.year <= int(record["year"]) <= end_date.year
        )
        if not selected:
            raise ReferenceV2LakeAdapterError(
                "V2 research-daily scope selects no year partitions"
            )

        schedule = pd.DataFrame(
            [
                {
                    "session_date": session,
                    "regular_open_utc": self.calendar.regular_open_close(session)[0],
                    "regular_close_utc": self.calendar.regular_open_close(session)[1],
                }
                for session in sessions
            ]
        )
        con = duckdb.connect(":memory:")
        con.register("v2_expected_sessions", schedule)
        source_sql = f"read_parquet({_sql_paths(selected)}, hive_partitioning=false)"
        full_source_sql = f"read_parquet({_sql_paths(paths)}, hive_partitioning=false)"
        try:
            description = con.execute(
                f"DESCRIBE SELECT * FROM {full_source_sql}"
            ).fetchall()
            names = tuple(str(row[0]) for row in description)
            if names != self._EXPECTED_COLUMNS:
                raise ReferenceV2LakeAdapterError(
                    "V2 research-daily physical columns are not exact"
                )
            full_stats = con.execute(
                f"""
                SELECT count(*), min(session_date), max(session_date),
                       count(*) FILTER (
                           WHERE session_date < DATE '{source_start}'
                              OR session_date > DATE '{source_end}'
                       )
                FROM {full_source_sql}
                """
            ).fetchone()
            assert full_stats is not None
            if (
                int(full_stats[0]) != int(manifest["research_rows"])
                or int(full_stats[3]) != 0
                or full_stats[1] is None
                or full_stats[2] is None
            ):
                raise ReferenceV2LakeAdapterError(
                    "V2 research-daily physical row/date bounds disagree with its manifest"
                )
            stats = con.execute(
                f"""
                SELECT
                    count(*) AS rows,
                    count(DISTINCT instrument_id) AS instruments,
                    count(DISTINCT b.session_date) AS sessions,
                    count(*) - count(DISTINCT (instrument_id, b.session_date)) AS duplicates,
                    count(*) FILTER (
                        WHERE instrument_id IS NULL OR trim(instrument_id) = ''
                           OR ticker IS NULL OR trim(ticker) = ''
                           OR source_provider <> 'alpaca'
                           OR source_dataset <> 'stock_daily_aggregates_split_adjusted'
                           OR adjusted_source_id NOT LIKE
                               'alpaca:sip:1Day:split:asof=-:v2:unit=%'
                           OR price_adjustment_mode <> 'SPLIT_ADJUSTED'
                           OR raw_price_lineage_id <>
                               'alpaca-v2:{str(manifest['source_fingerprint'])}'
                           OR security_type <> 'CS'
                           OR pit_active <> TRUE OR identity_clear <> TRUE
                           OR NOT isfinite(open) OR NOT isfinite(high)
                           OR NOT isfinite(low) OR NOT isfinite(close)
                           OR NOT isfinite(volume)
                           OR NOT isfinite(unadjusted_close)
                           OR open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
                           OR unadjusted_close <= 0 OR volume < 0
                           OR high < greatest(open, close)
                           OR low > least(open, close) OR high < low
                           OR s.session_date IS NULL
                           OR b.timestamp_utc <> s.regular_open_utc
                           OR b.signal_available_at_utc <> s.regular_close_utc
                    ) AS invalid_rows,
                    count(*) FILTER (
                        WHERE b.session_date BETWEEN
                            DATE '{REFERENCE_V2_MASTER_PROTECTED_START}'
                            AND DATE '{REFERENCE_V2_MASTER_PROTECTED_END}'
                    ) AS protected_rows
                FROM {source_sql} b
                LEFT JOIN v2_expected_sessions s USING (session_date)
                WHERE b.session_date BETWEEN DATE '{start_date}' AND DATE '{end_date}'
                """
            ).fetchone()
            identity_conflicts = int(
                con.execute(
                    f"""
                    SELECT count(*) FROM (
                        SELECT instrument_id
                        FROM {source_sql}
                        WHERE session_date BETWEEN DATE '{start_date}' AND DATE '{end_date}'
                        GROUP BY instrument_id
                        HAVING count(DISTINCT ticker) <> 1
                    )
                    """
                ).fetchone()[0]
            )
            output = con.execute(
                f"""
                SELECT *
                FROM {source_sql}
                WHERE session_date BETWEEN DATE '{start_date}' AND DATE '{end_date}'
                ORDER BY instrument_id, session_date, timestamp_utc
                """
            ).fetchdf()
        except duckdb.Error as exc:
            raise ReferenceV2LakeAdapterError(
                "V2 research-daily source does not satisfy its physical contract"
            ) from exc
        finally:
            con.unregister("v2_expected_sessions")
            con.close()
        assert stats is not None
        if int(stats[0]) == 0 or output.empty:
            raise ReferenceV2LakeAdapterError(
                "V2 research-daily scope produced no eligible rows"
            )
        if int(stats[3]) != 0:
            raise ReferenceV2LakeAdapterError(
                "V2 research-daily scope contains duplicate instrument/session rows"
            )
        if int(stats[4]) != 0:
            raise ReferenceV2LakeAdapterError(
                "V2 research-daily scope contains invalid or out-of-session rows"
            )
        if identity_conflicts:
            raise ReferenceV2LakeAdapterError(
                "V2 research-daily scope contains an instrument/ticker identity conflict"
            )
        protected_rows_read = int(stats[5])
        if not self._ALLOW_PROTECTED and protected_rows_read != 0:
            raise ReferenceV2LakeAdapterError(
                "V2 DEVELOPMENT adapter read protected rows"
            )
        if self._ALLOW_PROTECTED and protected_rows_read != int(
            manifest["protected_return_rows_materialized"]
        ):
            raise ReferenceV2LakeAdapterError(
                "V2 walk-forward protected-row count disagrees with its manifest"
            )

        output["session_date"] = pd.to_datetime(
            output["session_date"], errors="raise"
        ).dt.date
        output["timestamp_utc"] = pd.to_datetime(
            output["timestamp_utc"], utc=True, errors="raise"
        )
        output["signal_available_at_utc"] = pd.to_datetime(
            output["signal_available_at_utc"], utc=True, errors="raise"
        )
        for column in ("pit_active", "identity_clear"):
            output[column] = output[column].map(bool).astype(bool)
        values = output[
            ["open", "high", "low", "close", "volume", "unadjusted_close"]
        ].to_numpy(dtype="float64")
        if not np.isfinite(values).all():
            raise ReferenceV2LakeAdapterError(
                "V2 research-daily output contains non-finite OHLCV"
            )

        manifest_sha = _sha256_file(resolved_manifest)
        source_fingerprint = _stable_hash(
            {
                "contract_version": REFERENCE_V2_LAKE_ADAPTER_CONTRACT_VERSION,
                "manifest_sha256": manifest_sha,
                "research_daily_fingerprint": manifest["source_fingerprint"],
                "start_date": start_date,
                "end_date": end_date,
                "selected_partition_sha256": [
                    item["sha256"]
                    for item in inventory
                    if start_date.year <= int(item["year"]) <= end_date.year
                ],
                "v1_fallback": "FORBIDDEN",
                "evaluation_scope": self._REPORT_SCOPE,
                "protected_master_return_rows_read": protected_rows_read,
            }
        )
        report: dict[str, object] = {
            "contract_version": REFERENCE_V2_LAKE_ADAPTER_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "status": "PASS",
            "scope": self._REPORT_SCOPE,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "source_start_date": source_start.isoformat(),
            "source_cutoff_session": source_end.isoformat(),
            "xnys_sessions": len(sessions),
            "manifest_path": str(resolved_manifest),
            "manifest_sha256": manifest_sha,
            "research_daily_fingerprint": manifest["source_fingerprint"],
            "holdout_authorization_id": manifest.get("holdout_authorization_id"),
            "source_fingerprint": source_fingerprint,
            "verified_partitions": len(paths),
            "selected_partitions": len(selected),
            "output_rows": int(stats[0]),
            "output_instruments": int(stats[1]),
            "observed_sessions": int(stats[2]),
            "identity_conflicts": identity_conflicts,
            "price_adjustment_policy": "PROVIDER_NATIVE_SPLIT_ADJUSTED_SEPARATE_FROM_RAW",
            "return_economics": (
                "SPLIT_ADJUSTED_PRICE_RETURN_WITHOUT_CASH_DISTRIBUTION_CREDIT"
            ),
            "cash_dividend_credits_materialized": False,
            "signal_available_at_semantics": "XNYS_REGULAR_CLOSE_AFTER_DAILY_BAR_FINALIZATION",
            "entry_timing_semantics": "NO_EARLIER_THAN_NEXT_REGULAR_SESSION_OPEN",
            "v1_rows_read": 0,
            "v1_ancestry": "FORBIDDEN",
            "legacy_fallback_used": False,
            "protected_master_return_rows_read": protected_rows_read,
            "provider_writes": 0,
            "broker_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "performance_opened": False,
            "checks": {
                "isolated_v2_manifest_exact": True,
                "all_manifest_partitions_hash_verified": True,
                "physical_columns_exact": True,
                "alpaca_sip_split_adjusted_provenance_exact": True,
                "daily_availability_clock_exact": True,
                "identity_and_common_stock_explicit": True,
                "protected_returns_unread": protected_rows_read == 0,
                "protected_access_explicitly_authorized": self._ALLOW_PROTECTED,
                "legacy_fallback_forbidden": True,
                "external_writes_zero": True,
            },
        }
        return ReferenceV2LakeAdapterResult(bars=output, report=report)


class ReferenceV2WalkForwardLakeAdapter(ReferenceV2DailyLakeAdapter):
    """Load the one-time authorized V2 walk-forward view with warm-up history."""

    _MANIFEST_NAME = "walk_forward_daily.json"
    _VIEW_DIRECTORY = "walk_forward_daily"
    _EXPECTED_CONTRACT = WALK_FORWARD_DAILY_CONTRACT
    _ALLOW_PROTECTED = True
    _REPORT_SCOPE = "ALPACA_SIP_V2_FROZEN_ONE_TIME_WALK_FORWARD"


class ReferenceV2UnavailableRegimeContextAdapter:
    """Declare V2 regime context unavailable without reading a legacy regime layer."""

    def attach(
        self,
        bars: pd.DataFrame,
        start_date: date,
        end_date: date,
    ) -> ReferenceV2RegimeContextResult:
        if bars.empty:
            raise ReferenceV2LakeAdapterError("V2 regime context requires input bars")
        required = {"session_date", "signal_available_at_utc"}
        missing = sorted(required.difference(bars.columns))
        if missing:
            raise ReferenceV2LakeAdapterError(
                "V2 regime input is missing columns: " + ", ".join(missing)
            )
        context = {
            "market_regime_composite",
            "market_regime_available_at_utc",
            "sector_regime_composite",
            "ticker_regime_composite",
        }
        collision = sorted(context.intersection(bars.columns))
        if collision:
            raise ReferenceV2LakeAdapterError(
                "V2 regime columns already exist: " + ", ".join(collision)
            )
        result = bars.copy()
        sessions = pd.to_datetime(result["session_date"], errors="raise").dt.date
        if any(value < start_date or value > end_date for value in sessions):
            raise ReferenceV2LakeAdapterError(
                "V2 regime input contains an out-of-scope session"
            )
        protected_rows_read = int(
            sessions.between(
                REFERENCE_V2_MASTER_PROTECTED_START,
                REFERENCE_V2_MASTER_PROTECTED_END,
            ).sum()
        )
        result["market_regime_composite"] = UNAVAILABLE_REGIME_CONTEXT
        result["market_regime_available_at_utc"] = pd.to_datetime(
            result["signal_available_at_utc"], utc=True, errors="raise"
        )
        result["sector_regime_composite"] = UNAVAILABLE_REGIME_CONTEXT
        result["ticker_regime_composite"] = UNAVAILABLE_REGIME_CONTEXT
        source_fingerprint = _stable_hash(
            {
                "contract_version": REFERENCE_V2_UNAVAILABLE_REGIME_CONTRACT_VERSION,
                "start_date": start_date,
                "end_date": end_date,
                "input_rows": len(result),
                "state": UNAVAILABLE_REGIME_CONTEXT,
                "reason": "NO_ACCEPTED_V2_PIT_REGIME_GENERATION",
                "v1_fallback": "FORBIDDEN",
                "protected_master_return_rows_read": protected_rows_read,
            }
        )
        report: dict[str, object] = {
            "contract_version": REFERENCE_V2_UNAVAILABLE_REGIME_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "status": "PASS_WITH_CONTEXT_UNAVAILABLE",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "source_fingerprint": source_fingerprint,
            "input_rows": len(bars),
            "output_rows": len(result),
            "market_state_counts": {UNAVAILABLE_REGIME_CONTEXT: len(result)},
            "market_regime": UNAVAILABLE_REGIME_CONTEXT,
            "market_regime_reason": "NO_ACCEPTED_V2_PIT_REGIME_GENERATION",
            "sector_regime": UNAVAILABLE_REGIME_CONTEXT,
            "sector_regime_reason": "NO_ACCEPTED_V2_PIT_INSTRUMENT_TO_SECTOR_MAPPING",
            "ticker_regime": UNAVAILABLE_REGIME_CONTEXT,
            "ticker_regime_reason": "NO_ACCEPTED_V2_PIT_TICKER_STATE_GENERATION",
            "v1_regime_rows_read": 0,
            "legacy_fallback_used": False,
            "protected_master_return_rows_read": protected_rows_read,
            "provider_writes": 0,
            "broker_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "checks": {
                "unavailable_not_guessed": True,
                "v1_regime_fallback_forbidden": True,
                "protected_returns_unread": protected_rows_read == 0,
                "external_writes_zero": True,
            },
        }
        return ReferenceV2RegimeContextResult(bars=result, report=report)
