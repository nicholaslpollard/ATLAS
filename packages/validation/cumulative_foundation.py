from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import pandas as pd

from packages.core.enums import Timeframe
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.core.atomic_io import atomic_write_text
from packages.data.alpaca_backfill_canonical_promotion import gate8_acceptance_checks
from packages.data.alpaca_backfill_policy import (
    ALPACA_BACKFILL_END,
    ALPACA_BACKFILL_START,
    ALPACA_MASSIVE_SEAM_START,
)
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.features.partition_store import FeaturePartitionManifest, sha256_file
from packages.regimes.split_origin_policy import (
    INTRADAY_POLICY,
    MARKET_SECTOR_HISTORY_ORIGIN_DATE,
    MARKET_SECTOR_MANIFEST_VERSION,
    MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
    MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
    REGIME_HISTORY_DATASET_VERSION,
    SPLIT_ORIGIN_POLICY_VERSION,
    TICKER_HISTORY_ORIGIN_DATE,
)
from packages.schemas.canonical_market import CANONICAL_STOCK_DAILY_SCHEMA_VERSION

from .cumulative_policy import (
    CUMULATIVE_BAR_NUMERIC_ABS_TOLERANCE,
    CUMULATIVE_BAR_NUMERIC_REL_TOLERANCE,
    CUMULATIVE_FEATURE_NUMERIC_ABS_TOLERANCE,
    CUMULATIVE_FEATURE_NUMERIC_REL_TOLERANCE,
    CUMULATIVE_FEATURE_SAMPLE_OBSERVATIONS_PER_SYMBOL,
    CUMULATIVE_FEATURE_SAMPLE_SYMBOLS_PER_TIMEFRAME,
    CUMULATIVE_FOUNDATION_ACCEPTANCE_VERSION,
    CUMULATIVE_FOUNDATION_AUDIT_CONTRACT_VERSION,
    CUMULATIVE_INTRADAY_SAMPLE_SESSIONS_PER_YEAR,
    CUMULATIVE_INTRADAY_SAMPLE_SYMBOLS_PER_SESSION,
    cumulative_policy_fingerprint,
    cumulative_policy_payload,
    validate_cumulative_policy,
)
from .independent_features import replay_core_features


_DATE_RE = re.compile(r"date=(\d{4}-\d{2}-\d{2})")
_STABLE_SYMBOL_PREFERENCES = (
    "SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "AMZN", "NVDA",
    "XOM", "JPM", "WMT", "KO", "XLK", "XLF", "XLE", "XLV",
)


class CumulativeFoundationAuditError(RuntimeError):
    pass


def _sql(value: str | Path) -> str:
    return "'" + str(value).replace("\\", "/").replace("'", "''") + "'"


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _partition_date(path: Path) -> date:
    for part in reversed(path.parts):
        match = _DATE_RE.fullmatch(part)
        if match:
            return date.fromisoformat(match.group(1))
    match = _DATE_RE.search(path.as_posix())
    if match:
        return date.fromisoformat(match.group(1))
    raise ValueError(f"path has no date=YYYY-MM-DD partition: {path}")


def _json(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise CumulativeFoundationAuditError(f"missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CumulativeFoundationAuditError(f"invalid JSON for {label}: {path}") from exc
    if not isinstance(value, dict):
        raise CumulativeFoundationAuditError(f"{label} is not a JSON object: {path}")
    return value


def _close(a: float, b: float, *, abs_tol: float, rel_tol: float) -> bool:
    if math.isnan(a) and math.isnan(b):
        return True
    if not math.isfinite(a) or not math.isfinite(b):
        return a == b
    return math.isclose(a, b, abs_tol=abs_tol, rel_tol=rel_tol)


def _deterministic_take(values: Iterable[str], count: int, namespace: str) -> list[str]:
    unique = sorted(set(values))
    ranked = sorted(
        unique,
        key=lambda value: hashlib.sha256(f"{namespace}|{value}".encode("utf-8")).hexdigest(),
    )
    return ranked[:count]


class CumulativeFoundationAuditor:
    """Read-only cumulative acceptance over ATLAS market-data and derived-state lineage."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.canonical_root = settings.resolved_path(settings.data.paths.canonical)
        self.derived_root = settings.resolved_path(settings.data.paths.derived)
        self.manifest_root = settings.resolved_path(settings.data.paths.manifests)
        self.root = self.derived_root / "validation" / "cumulative_foundation" / "v1"
        self._sha_cache: dict[Path, str] = {}

    def _sha(self, path: Path) -> str:
        resolved = path.resolve()
        value = self._sha_cache.get(resolved)
        if value is None:
            value = sha256_file(resolved)
            self._sha_cache[resolved] = value
        return value

    def _daily_files(self) -> list[Path]:
        root = self.canonical_root / "stocks" / Timeframe.DAY_1.value
        return sorted(root.glob("year=*/date=*/part-000.parquet"), key=_partition_date)

    def _files_for(self, timeframe: Timeframe, *, feature: bool = False) -> list[Path]:
        if feature:
            root = self.derived_root / "features" / timeframe.value
        elif timeframe == Timeframe.MINUTE_1:
            root = self.canonical_root / "stocks" / timeframe.value
        else:
            root = self.derived_root / "bars" / timeframe.value
        return sorted(root.glob("year=*/month=*/date=*/part-000.parquet"), key=_partition_date)

    def resolve_end_date(self) -> date:
        files = self._daily_files()
        if not files:
            raise CumulativeFoundationAuditError("canonical 1d lake is empty")
        latest = _partition_date(files[-1])
        if latest < ALPACA_MASSIVE_SEAM_START:
            raise CumulativeFoundationAuditError("canonical 1d lake never reaches Massive authority period")
        return latest

    def _audit_daily(self, end_date: date) -> dict[str, object]:
        files = [p for p in self._daily_files() if ALPACA_BACKFILL_START <= _partition_date(p) <= end_date]
        actual_sessions = [_partition_date(path) for path in files]
        expected_sessions = get_market_calendar().sessions_in_range(ALPACA_BACKFILL_START, end_date)
        missing_sessions = sorted(set(expected_sessions).difference(actual_sessions))
        unexpected_sessions = sorted(set(actual_sessions).difference(expected_sessions))
        duplicate_partitions = len(actual_sessions) - len(set(actual_sessions))
        if not files:
            raise CumulativeFoundationAuditError("no canonical daily partitions in audit range")

        glob = (self.canonical_root / "stocks" / "1d" / "year=*" / "date=*" / "part-000.parquet").as_posix()
        con = connect_utc(":memory:")
        try:
            con.execute(
                f"""
                CREATE TEMP VIEW daily AS
                SELECT *, filename
                FROM read_parquet({_sql(glob)}, union_by_name=true, filename=true)
                WHERE CAST(timestamp_utc AS DATE) BETWEEN DATE '{ALPACA_BACKFILL_START}' AND DATE '{end_date}'
                """
            )
            columns = {str(row[0]): str(row[1]).upper() for row in con.execute("DESCRIBE daily").fetchall()}
            row = con.execute(
                """
                SELECT
                    count(*) AS rows,
                    count(DISTINCT symbol) AS symbols,
                    count(DISTINCT CAST(timestamp_utc AS DATE)) AS sessions,
                    count(*) FILTER (WHERE symbol IS NULL OR trim(symbol)='') AS blank_symbol,
                    count(*) FILTER (WHERE timestamp_utc IS NULL) AS null_timestamp,
                    count(*) FILTER (
                        WHERE NOT isfinite(open) OR NOT isfinite(high) OR NOT isfinite(low) OR NOT isfinite(close)
                           OR open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
                           OR high < low OR open < low OR open > high OR close < low OR close > high
                    ) AS invalid_ohlc,
                    count(*) FILTER (WHERE NOT isfinite(volume) OR volume < 0) AS invalid_volume,
                    count(*) FILTER (WHERE transactions IS NOT NULL AND transactions < 0) AS invalid_transactions,
                    count(*) FILTER (
                        WHERE CAST(timestamp_utc AS DATE)
                           <> TRY_CAST(regexp_extract(filename, 'date=([0-9]{4}-[0-9]{2}-[0-9]{2})', 1) AS DATE)
                    ) AS partition_date_mismatch
                FROM daily
                """
            ).fetchone()
            duplicates = int(
                con.execute(
                    """
                    SELECT count(*) FROM (
                        SELECT symbol, timestamp_utc, count(*) n
                        FROM daily GROUP BY 1,2 HAVING n > 1
                    )
                    """
                ).fetchone()[0]
            )
            yearly = con.execute(
                """
                SELECT year(CAST(timestamp_utc AS DATE)) y,
                       count(*) rows,
                       count(DISTINCT symbol) symbols,
                       count(DISTINCT CAST(timestamp_utc AS DATE)) sessions,
                       median(volume) median_volume,
                       quantile_cont(close, 0.5) median_close
                FROM daily GROUP BY 1 ORDER BY 1
                """
            ).fetchall()
        finally:
            con.close()

        stats = {
            "row_count": int(row[0]),
            "symbol_count": int(row[1]),
            "session_count": int(row[2]),
            "blank_symbol_rows": int(row[3]),
            "null_timestamp_rows": int(row[4]),
            "invalid_ohlc_rows": int(row[5]),
            "invalid_volume_rows": int(row[6]),
            "invalid_transaction_rows": int(row[7]),
            "partition_date_mismatch_rows": int(row[8]),
            "duplicate_market_keys": duplicates,
            "partition_count": len(files),
            "expected_session_count": len(expected_sessions),
            "missing_sessions": [d.isoformat() for d in missing_sessions],
            "unexpected_sessions": [d.isoformat() for d in unexpected_sessions],
            "duplicate_partition_dates": duplicate_partitions,
            "schema_columns": columns,
            "yearly_diagnostics": [
                {
                    "year": int(y), "rows": int(r), "symbols": int(s), "sessions": int(n),
                    "median_volume": None if mv is None else float(mv),
                    "median_close": None if mc is None else float(mc),
                }
                for y, r, s, n, mv, mc in yearly
            ],
        }
        stats["pass"] = all(
            (
                stats["blank_symbol_rows"] == 0,
                stats["null_timestamp_rows"] == 0,
                stats["invalid_ohlc_rows"] == 0,
                stats["invalid_volume_rows"] == 0,
                stats["invalid_transaction_rows"] == 0,
                stats["partition_date_mismatch_rows"] == 0,
                stats["duplicate_market_keys"] == 0,
                not missing_sessions,
                not unexpected_sessions,
                duplicate_partitions == 0,
            )
        )
        return stats

    def _audit_seam_and_authority(self, end_date: date) -> dict[str, object]:
        files = self._daily_files()
        sessions = sorted(_partition_date(p) for p in files if _partition_date(p) <= end_date)
        pre = [d for d in sessions if d <= ALPACA_BACKFILL_END]
        post = [d for d in sessions if d >= ALPACA_MASSIVE_SEAM_START]
        if not pre or not post:
            raise CumulativeFoundationAuditError("provider seam cannot be resolved from canonical partitions")
        expected = get_market_calendar().sessions_in_range(pre[-1], post[0])
        seam_calendar_contiguous = expected == [pre[-1], post[0]]

        promotion_manifest = self.manifest_root / "historical_backfill" / "alpaca" / "canonical_promotion_v1.json"
        promotion = _json(promotion_manifest, "Gate 8 canonical promotion manifest")
        gate8_checks = gate8_acceptance_checks(promotion)
        return {
            "alpaca_authority_start": ALPACA_BACKFILL_START.isoformat(),
            "alpaca_authority_end": ALPACA_BACKFILL_END.isoformat(),
            "last_pre_seam_session": pre[-1].isoformat(),
            "massive_authority_start": ALPACA_MASSIVE_SEAM_START.isoformat(),
            "first_massive_session": post[0].isoformat(),
            "exchange_calendar_contiguous": seam_calendar_contiguous,
            "promotion_manifest_path": str(promotion_manifest.resolve()),
            "promotion_manifest_sha256": self._sha(promotion_manifest),
            "gate8_checks": gate8_checks,
            "pass": seam_calendar_contiguous
            and post[0] == ALPACA_MASSIVE_SEAM_START
            and all(gate8_checks.values()),
        }

    def _audit_intraday_lineage(self, end_date: date) -> dict[str, object]:
        results: dict[str, object] = {}
        passed = True
        for timeframe in (Timeframe.MINUTE_1, Timeframe.HOUR_1, Timeframe.HOUR_4):
            files = [p for p in self._files_for(timeframe) if _partition_date(p) <= end_date]
            dates = [_partition_date(p) for p in files]
            forbidden = [d for d in dates if d < TICKER_HISTORY_ORIGIN_DATE]
            item = {
                "partition_count": len(files),
                "first_partition_date": min(dates).isoformat() if dates else None,
                "last_partition_date": max(dates).isoformat() if dates else None,
                "pre_ticker_origin_partition_count": len(forbidden),
                "pre_ticker_origin_dates": [d.isoformat() for d in forbidden[:20]],
            }
            item["pass"] = len(forbidden) == 0 and bool(files)
            results[timeframe.value] = item
            passed = passed and bool(item["pass"])
        results["policy"] = INTRADAY_POLICY
        results["ticker_intraday_origin"] = TICKER_HISTORY_ORIGIN_DATE.isoformat()
        results["pass"] = passed and INTRADAY_POLICY == "NO_SYNTHETIC_PRE2021_4H_OR_1H_FROM_DAILY_BACKFILL"
        return results

    def _audit_feature_manifests(self, end_date: date, progress: Callable[[str], None] | None) -> dict[str, object]:
        overall = True
        result: dict[str, object] = {}
        for timeframe in (Timeframe.DAY_1, Timeframe.HOUR_1, Timeframe.HOUR_4):
            origin = ALPACA_BACKFILL_START if timeframe == Timeframe.DAY_1 else TICKER_HISTORY_ORIGIN_DATE
            manifest_dir = self.manifest_root / "features" / timeframe.value
            manifests = sorted(manifest_dir.glob("*/*.json"))
            manifests = [p for p in manifests if origin <= date.fromisoformat(p.stem) <= end_date]
            forbidden = sorted(
                p for p in manifest_dir.glob("*/*.json") if date.fromisoformat(p.stem) < origin
            )
            failures: list[str] = []
            prior_output: str | None = None
            checked = 0
            for path in manifests:
                trading_date = date.fromisoformat(path.stem)
                try:
                    record = FeaturePartitionManifest.from_dict(_json(path, "feature manifest"))
                    record.validate_contract(timeframe, trading_date)
                    source = Path(record.source_path)
                    feature = Path(record.feature_path)
                    if not source.is_file() or not feature.is_file():
                        raise ValueError("bound source/feature file missing")
                    if record.source_sha256 != self._sha(source):
                        raise ValueError("source hash mismatch")
                    if record.feature_sha256 != self._sha(feature):
                        raise ValueError("feature hash mismatch")
                    if prior_output is not None and record.input_state_fingerprint != prior_output:
                        raise ValueError("recursive state fingerprint discontinuity")
                    prior_output = record.output_state_fingerprint
                    checked += 1
                except Exception as exc:  # audit records exact manifest failure and continues
                    failures.append(f"{trading_date}: {type(exc).__name__}: {exc}")
            if progress is not None:
                progress(f"feature manifests {timeframe.value}: checked {checked:,}; failures {len(failures):,}")
            item = {
                "origin": origin.isoformat(),
                "manifest_count": len(manifests),
                "checked_manifest_count": checked,
                "forbidden_pre_origin_manifest_count": len(forbidden),
                "failure_count": len(failures),
                "failure_samples": failures[:20],
                "state_chain_continuous": len(failures) == 0,
            }
            item["pass"] = bool(manifests) and not forbidden and not failures
            result[timeframe.value] = item
            overall = overall and bool(item["pass"])
        result["pass"] = overall
        return result

    def _sample_intraday_sessions(self, end_date: date) -> list[date]:
        sets = []
        for tf in (Timeframe.MINUTE_1, Timeframe.HOUR_1, Timeframe.HOUR_4):
            sets.append({_partition_date(p) for p in self._files_for(tf) if _partition_date(p) <= end_date})
        common = sorted(set.intersection(*sets)) if sets else []
        by_year: dict[int, list[date]] = defaultdict(list)
        for item in common:
            by_year[item.year].append(item)
        selected: set[date] = set()
        for year, dates in by_year.items():
            if dates:
                selected.add(dates[0])
                selected.add(dates[-1])
                remaining = [d.isoformat() for d in dates[1:-1]]
                for text in _deterministic_take(
                    remaining,
                    max(0, CUMULATIVE_INTRADAY_SAMPLE_SESSIONS_PER_YEAR - 2),
                    f"intraday-session-{year}",
                ):
                    selected.add(date.fromisoformat(text))
        if ALPACA_MASSIVE_SEAM_START in common:
            selected.add(ALPACA_MASSIVE_SEAM_START)
        return sorted(selected)

    def _audit_intraday_reconciliation(self, end_date: date, progress: Callable[[str], None] | None) -> dict[str, object]:
        sessions = self._sample_intraday_sessions(end_date)
        mismatch_samples: list[dict[str, object]] = []
        checked_bars = 0
        checked_symbols = 0
        for session_date in sessions:
            minute = self.paths.canonical_file(Timeframe.MINUTE_1, session_date)
            if not minute.is_file():
                continue
            con = connect_utc(":memory:")
            try:
                symbols = [str(r[0]) for r in con.execute(
                    f"SELECT DISTINCT symbol FROM read_parquet({_sql(minute)}) WHERE session_segment='regular' ORDER BY symbol"
                ).fetchall()]
                selected = _deterministic_take(symbols, CUMULATIVE_INTRADAY_SAMPLE_SYMBOLS_PER_SESSION, f"bar-symbol-{session_date}")
                checked_symbols += len(selected)
                if not selected:
                    continue
                symbol_sql = ",".join(_sql(s) for s in selected)
                for timeframe in (Timeframe.HOUR_1, Timeframe.HOUR_4):
                    derived = self.paths.derived_file(timeframe, session_date)
                    if not derived.is_file():
                        mismatch_samples.append({"date": session_date.isoformat(), "timeframe": timeframe.value, "error": "derived partition missing"})
                        continue
                    rows = con.execute(
                        f"""
                        SELECT symbol, timestamp_utc, bar_end_utc, open, high, low, close, volume,
                               transaction_count
                        FROM read_parquet({_sql(derived)})
                        WHERE session_segment='regular' AND symbol IN ({symbol_sql})
                        ORDER BY symbol, timestamp_utc
                        """
                    ).fetchall()
                    for symbol, start, stop, opn, high, low, close, volume, tx in rows:
                        source = con.execute(
                            f"""
                            SELECT first(open ORDER BY timestamp_utc), max(high), min(low),
                                   last(close ORDER BY timestamp_utc), sum(volume)::DOUBLE,
                                   CASE WHEN count(transaction_count)=0 THEN NULL ELSE sum(transaction_count)::BIGINT END,
                                   count(*)
                            FROM read_parquet({_sql(minute)})
                            WHERE symbol=? AND session_segment='regular'
                              AND timestamp_utc >= ? AND timestamp_utc < ?
                            """,
                            [symbol, start, stop],
                        ).fetchone()
                        checked_bars += 1
                        expected = source[:6]
                        actual = (opn, high, low, close, volume, tx)
                        numeric_ok = all(
                            (a is None and b is None)
                            or (a is not None and b is not None and _close(float(a), float(b), abs_tol=CUMULATIVE_BAR_NUMERIC_ABS_TOLERANCE, rel_tol=CUMULATIVE_BAR_NUMERIC_REL_TOLERANCE))
                            for a, b in zip(actual[:5], expected[:5], strict=True)
                        )
                        tx_ok = actual[5] == expected[5]
                        if source[6] == 0 or not numeric_ok or not tx_ok:
                            mismatch_samples.append(
                                {"date": session_date.isoformat(), "timeframe": timeframe.value, "symbol": symbol,
                                 "timestamp_utc": str(start), "source_minute_rows": int(source[6]),
                                 "actual": [None if v is None else str(v) for v in actual],
                                 "expected": [None if v is None else str(v) for v in expected]}
                            )
            finally:
                con.close()
            if progress is not None:
                progress(f"intraday replay {session_date}: cumulative bars {checked_bars:,}; mismatches {len(mismatch_samples):,}")
        return {
            "sample_sessions": [d.isoformat() for d in sessions],
            "sample_session_count": len(sessions),
            "sample_symbol_streams": checked_symbols,
            "checked_derived_bars": checked_bars,
            "mismatch_count": len(mismatch_samples),
            "mismatch_samples": mismatch_samples[:20],
            "pass": bool(sessions) and checked_bars > 0 and not mismatch_samples,
        }

    def _select_feature_symbols(self, source_glob: str, timeframe: Timeframe, end_date: date) -> list[str]:
        con = connect_utc(":memory:")
        try:
            extra = " AND session_segment='regular'" if timeframe != Timeframe.DAY_1 else ""
            bounds = con.execute(
                f"""
                SELECT symbol, min(CAST(timestamp_utc AS DATE)) first_date,
                       max(CAST(timestamp_utc AS DATE)) last_date, count(*) n
                FROM read_parquet({_sql(source_glob)}, union_by_name=true)
                WHERE CAST(timestamp_utc AS DATE) <= DATE '{end_date}' {extra}
                GROUP BY symbol
                HAVING count(*) >= 250
                """
            ).fetchall()
        finally:
            con.close()
        candidates = [str(symbol) for symbol, first, last, n in bounds if last == end_date or (end_date - last).days <= 7]
        selected: list[str] = []
        candidate_set = set(candidates)
        for symbol in _STABLE_SYMBOL_PREFERENCES:
            if symbol in candidate_set and symbol not in selected:
                selected.append(symbol)
                if len(selected) >= CUMULATIVE_FEATURE_SAMPLE_SYMBOLS_PER_TIMEFRAME:
                    return selected
        remaining = [s for s in candidates if s not in selected]
        selected.extend(
            _deterministic_take(
                remaining,
                CUMULATIVE_FEATURE_SAMPLE_SYMBOLS_PER_TIMEFRAME - len(selected),
                f"feature-symbol-{timeframe.value}",
            )
        )
        return selected

    def _audit_feature_replay(self, end_date: date, progress: Callable[[str], None] | None) -> dict[str, object]:
        feature_names = [d.name for d in CORE_FEATURE_REGISTRY.all()]
        overall = True
        result: dict[str, object] = {}
        for timeframe in (Timeframe.DAY_1, Timeframe.HOUR_1, Timeframe.HOUR_4):
            if timeframe == Timeframe.DAY_1:
                source_glob = (self.canonical_root / "stocks" / "1d" / "year=*" / "date=*" / "part-000.parquet").as_posix()
            else:
                source_glob = (self.derived_root / "bars" / timeframe.value / "year=*" / "month=*" / "date=*" / "part-000.parquet").as_posix()
            feature_glob = (self.derived_root / "features" / timeframe.value / "year=*" / "month=*" / "date=*" / "part-000.parquet").as_posix()
            if timeframe == Timeframe.DAY_1:
                feature_glob = (self.derived_root / "features" / timeframe.value / "year=*" / "month=*" / "date=*" / "part-000.parquet").as_posix()
            symbols = self._select_feature_symbols(source_glob, timeframe, end_date)
            mismatches: list[dict[str, object]] = []
            comparisons = 0
            con = connect_utc(":memory:")
            try:
                for symbol in symbols:
                    segment_clause = " AND session_segment='regular'" if timeframe != Timeframe.DAY_1 else ""
                    source = con.execute(
                        f"""
                        SELECT timestamp_utc, high, low, close, volume
                        FROM read_parquet({_sql(source_glob)}, union_by_name=true)
                        WHERE symbol=? AND CAST(timestamp_utc AS DATE) <= DATE '{end_date}' {segment_clause}
                        ORDER BY timestamp_utc
                        """,
                        [symbol],
                    ).df()
                    if source.empty:
                        mismatches.append({"symbol": symbol, "error": "source stream empty"})
                        continue
                    replay = replay_core_features(source)
                    stored = con.execute(
                        f"""
                        SELECT * FROM read_parquet({_sql(feature_glob)}, union_by_name=true)
                        WHERE symbol=? AND CAST(timestamp_utc AS DATE) <= DATE '{end_date}'
                        ORDER BY timestamp_utc
                        """,
                        [symbol],
                    ).df()
                    if "session_segment" in stored.columns and timeframe != Timeframe.DAY_1:
                        stored = stored[stored["session_segment"].astype(str) == "regular"].copy()
                    stored["timestamp_utc"] = pd.to_datetime(stored["timestamp_utc"], utc=True)
                    replay["timestamp_utc"] = pd.to_datetime(replay["timestamp_utc"], utc=True)
                    merged = replay.merge(
                        stored[["timestamp_utc", *feature_names]], on="timestamp_utc", how="inner", suffixes=("_replay", "_stored")
                    )
                    if merged.empty:
                        mismatches.append({"symbol": symbol, "error": "no exact replay/stored timestamps"})
                        continue
                    eligible = merged.iloc[199:] if len(merged) > 199 else merged
                    targets = _deterministic_take(
                        [str(i) for i in eligible.index],
                        CUMULATIVE_FEATURE_SAMPLE_OBSERVATIONS_PER_SYMBOL,
                        f"feature-observation-{timeframe.value}-{symbol}",
                    )
                    for text in targets:
                        row = merged.loc[int(text)]
                        for name in feature_names:
                            a = row[f"{name}_replay"]
                            b = row[f"{name}_stored"]
                            a_nan = pd.isna(a)
                            b_nan = pd.isna(b)
                            comparisons += 1
                            if a_nan and b_nan:
                                continue
                            if a_nan != b_nan or not _close(float(a), float(b), abs_tol=CUMULATIVE_FEATURE_NUMERIC_ABS_TOLERANCE, rel_tol=CUMULATIVE_FEATURE_NUMERIC_REL_TOLERANCE):
                                mismatches.append(
                                    {"timeframe": timeframe.value, "symbol": symbol, "timestamp_utc": str(row["timestamp_utc"]),
                                     "feature": name, "replay": None if a_nan else float(a), "stored": None if b_nan else float(b)}
                                )
                                if len(mismatches) >= 100:
                                    break
                        if len(mismatches) >= 100:
                            break
                    if len(mismatches) >= 100:
                        break
            finally:
                con.close()
            if progress is not None:
                progress(f"independent feature replay {timeframe.value}: {comparisons:,} comparisons; mismatches {len(mismatches):,}")
            item = {
                "sample_symbols": symbols,
                "sample_symbol_count": len(symbols),
                "feature_count": len(feature_names),
                "numeric_comparisons": comparisons,
                "mismatch_count": len(mismatches),
                "mismatch_samples": mismatches[:20],
            }
            item["pass"] = bool(symbols) and comparisons > 0 and not mismatches
            result[timeframe.value] = item
            overall = overall and bool(item["pass"])
        result["pass"] = overall
        return result

    def _audit_regimes(self, end_date: date) -> dict[str, object]:
        manifest_path = self.paths.regime_state_manifest(end_date)
        manifest = _json(manifest_path, "latest split-origin regime manifest")
        history_root = self.derived_root / "regimes" / "history" / REGIME_HISTORY_DATASET_VERSION / f"as_of={end_date}"
        history_files = {
            name: history_root / f"{name}.parquet"
            for name in ("market_raw", "market_effective", "sector_raw", "sector_effective")
        }
        missing_history = [name for name, path in history_files.items() if not path.is_file()]
        minmax: dict[str, object] = {}
        con = connect_utc(":memory:")
        try:
            for name, path in history_files.items():
                if not path.is_file():
                    continue
                desc = {str(r[0]) for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet({_sql(path)})").fetchall()}
                date_col = "session_date" if "session_date" in desc else "as_of_date" if "as_of_date" in desc else None
                if date_col is not None:
                    first, last, rows = con.execute(
                        f"SELECT min({date_col}), max({date_col}), count(*) FROM read_parquet({_sql(path)})"
                    ).fetchone()
                    minmax[name] = {"first": str(first), "last": str(last), "rows": int(rows)}
        finally:
            con.close()

        contract_ok = (
            manifest.get("contract_version") == MARKET_SECTOR_MANIFEST_VERSION
            or manifest.get("manifest_version") == MARKET_SECTOR_MANIFEST_VERSION
        )
        snapshot_ok = (
            manifest.get("snapshot_contract_version") == MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION
            or dict(manifest.get("policy") or {}).get("snapshot_contract_version") == MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION
        )
        policy_text = json.dumps(manifest, sort_keys=True)
        provenance_ok = all(
            token in policy_text
            for token in (
                SPLIT_ORIGIN_POLICY_VERSION,
                MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
                MARKET_SECTOR_HISTORY_ORIGIN_DATE.isoformat(),
                TICKER_HISTORY_ORIGIN_DATE.isoformat(),
                INTRADAY_POLICY,
            )
        )
        no_pre_origin = True
        for item in minmax.values():
            first = date.fromisoformat(str(item["first"])[:10])
            if first < MARKET_SECTOR_HISTORY_ORIGIN_DATE:
                no_pre_origin = False
        return {
            "manifest_path": str(manifest_path.resolve()),
            "manifest_sha256": self._sha(manifest_path),
            "market_sector_origin": MARKET_SECTOR_HISTORY_ORIGIN_DATE.isoformat(),
            "ticker_origin": TICKER_HISTORY_ORIGIN_DATE.isoformat(),
            "split_origin_policy": SPLIT_ORIGIN_POLICY_VERSION,
            "intraday_policy": INTRADAY_POLICY,
            "history_dataset_version": REGIME_HISTORY_DATASET_VERSION,
            "history_files": {name: str(path.resolve()) for name, path in history_files.items()},
            "missing_history_files": missing_history,
            "history_ranges": minmax,
            "manifest_contract_current": contract_ok,
            "snapshot_contract_current": snapshot_ok,
            "split_origin_provenance_present": provenance_ok,
            "no_market_sector_history_before_2016_origin": no_pre_origin,
            "pass": not missing_history and contract_ok and snapshot_ok and provenance_ok and no_pre_origin,
        }

    def _audit_accepted_historical_evidence(self) -> dict[str, object]:
        final_path = (
            self.derived_root
            / "historical_backfill" / "alpaca" / "ml_long_history" / "v1"
            / "evaluation" / "v1" / "benchmark" / "v1"
            / "historical_extension_final_acceptance.json"
        )
        final = _json(final_path, "historical extension final acceptance")
        pass_value = final.get("pass") is True or dict(final.get("final_disposition") or {}).get("pass") is True
        text = json.dumps(final, sort_keys=True)
        authority_preserved = (
            "d485e6c287bacce1" in text
            and ("production" in text.lower() or "phase10" in text.lower())
        )
        return {
            "path": str(final_path.resolve()),
            "sha256": self._sha(final_path),
            "accepted": pass_value,
            "phase10_authority_reference_present": authority_preserved,
            "pass": pass_value and authority_preserved,
        }

    def run(
        self,
        *,
        end_date: date | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> dict[str, object]:
        validate_cumulative_policy()
        resolved_end = end_date or self.resolve_end_date()
        if resolved_end < ALPACA_MASSIVE_SEAM_START:
            raise CumulativeFoundationAuditError("audit end date predates Massive authority")
        self.root.mkdir(parents=True, exist_ok=True)

        def step(name: str, fn):
            if progress is not None:
                progress(name)
            value = fn()
            atomic_write_text(
                self.root / f"{name}.json",
                json.dumps(value, indent=2, sort_keys=True, default=str) + "\n",
            )
            return value

        daily = step("01_daily_canonical", lambda: self._audit_daily(resolved_end))
        seam = step("02_provider_seam", lambda: self._audit_seam_and_authority(resolved_end))
        intraday = step("03_intraday_lineage", lambda: self._audit_intraday_lineage(resolved_end))
        manifests = step("04_feature_manifests", lambda: self._audit_feature_manifests(resolved_end, progress))
        bars = step("05_intraday_reconciliation", lambda: self._audit_intraday_reconciliation(resolved_end, progress))
        features = step("06_independent_feature_replay", lambda: self._audit_feature_replay(resolved_end, progress))
        regimes = step("07_regime_lineage", lambda: self._audit_regimes(resolved_end))
        historical = step("08_accepted_historical_evidence", self._audit_accepted_historical_evidence)

        components = {
            "daily_canonical": bool(daily.get("pass")),
            "provider_seam": bool(seam.get("pass")),
            "intraday_lineage": bool(intraday.get("pass")),
            "feature_manifests": bool(manifests.get("pass")),
            "intraday_reconciliation": bool(bars.get("pass")),
            "independent_feature_replay": bool(features.get("pass")),
            "regime_lineage": bool(regimes.get("pass")),
            "accepted_historical_evidence": bool(historical.get("pass")),
        }
        component_files = sorted(self.root.glob("0[1-8]_*.json"))
        source_payload = {
            "contract_version": CUMULATIVE_FOUNDATION_ACCEPTANCE_VERSION,
            "policy_fingerprint": cumulative_policy_fingerprint(),
            "history_start": ALPACA_BACKFILL_START.isoformat(),
            "end_date": resolved_end.isoformat(),
            "component_hashes": {path.name: self._sha(path) for path in component_files},
            "components": components,
        }
        acceptance: dict[str, object] = {
            "contract_version": CUMULATIVE_FOUNDATION_ACCEPTANCE_VERSION,
            "audit_contract_version": CUMULATIVE_FOUNDATION_AUDIT_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": _stable_hash(source_payload),
            "policy": cumulative_policy_payload(),
            "policy_fingerprint": cumulative_policy_fingerprint(),
            "history_start": ALPACA_BACKFILL_START.isoformat(),
            "history_end": resolved_end.isoformat(),
            "canonical_daily_schema_version": CANONICAL_STOCK_DAILY_SCHEMA_VERSION,
            "provider_authority": {
                "alpaca": f"{ALPACA_BACKFILL_START} through {ALPACA_BACKFILL_END}",
                "massive": f"{ALPACA_MASSIVE_SEAM_START} onward",
            },
            "components": components,
            "component_hashes": source_payload["component_hashes"],
            "exhaustive_checks": (
                "canonical_daily_structural_rows",
                "exchange_session_partition_coverage",
                "feature_manifest_contract_and_file_hashes",
                "forbidden_pre2021_intraday_partition_inventory",
                "accepted_historical_lineage_artifact_binding",
            ),
            "deterministic_sampled_recomputations": (
                "canonical_1m_to_derived_1h_4h_ohlcv",
                "independent_core33_feature_replay_1d_1h_4h",
            ),
            "new_posthoc_statistical_thresholds": False,
            "canonical_writes": 0,
            "feature_writes": 0,
            "regime_writes": 0,
            "model_writes": 0,
            "broker_writes": 0,
            "external_provider_calls": 0,
            "pass": all(components.values()),
        }
        acceptance_path = self.root / "cumulative_foundation_acceptance.json"
        atomic_write_text(
            acceptance_path,
            json.dumps(acceptance, indent=2, sort_keys=True, default=str) + "\n",
        )
        acceptance["acceptance_path"] = str(acceptance_path.resolve())
        if not acceptance["pass"]:
            failed = sorted(name for name, value in components.items() if not value)
            raise CumulativeFoundationAuditError(
                "cumulative foundation audit failed: " + ", ".join(failed)
            )
        return acceptance
