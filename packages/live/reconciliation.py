from __future__ import annotations

import json
from datetime import date

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.schemas.live_market import LiveReconciliationSummary


class LiveFinalizationReconciler:
    """Compare provisional WebSocket minute bars with finalized canonical 1m facts."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)

    @staticmethod
    def _create_empty_live_table(con) -> None:
        con.execute(
            """
            CREATE TEMP TABLE live_last (
                symbol VARCHAR,
                timestamp_utc TIMESTAMPTZ,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE,
                received_at_utc TIMESTAMPTZ
            )
            """
        )

    def _create_live_view(self, con, journal) -> None:
        if not journal.is_file() or journal.stat().st_size == 0:
            self._create_empty_live_table(con)
            return

        source = f"read_json_auto({sql_string(journal)}, format='newline_delimited')"
        described = con.execute(f"DESCRIBE SELECT * FROM {source}").fetchall()
        available = {str(row[0]) for row in described}
        required = {"ev", "sym", "s", "o", "h", "l", "c", "_atlas_received_at_utc"}
        if not required.issubset(available):
            # A journal containing only unsupported/focused event types may not have
            # any AM-shaped fields at all. That is a valid zero-live-bars session,
            # not a schema failure.
            self._create_empty_live_table(con)
            return

        if "dv" in available and "v" in available:
            volume_expr = "COALESCE(TRY_CAST(dv AS DOUBLE), TRY_CAST(v AS DOUBLE), 0.0)"
        elif "dv" in available:
            volume_expr = "COALESCE(TRY_CAST(dv AS DOUBLE), 0.0)"
        elif "v" in available:
            volume_expr = "COALESCE(TRY_CAST(v AS DOUBLE), 0.0)"
        else:
            volume_expr = "0.0"

        con.execute(
            f"""
            CREATE TEMP VIEW live_last AS
            WITH parsed AS (
                SELECT
                    trim(sym) AS symbol,
                    to_timestamp(CAST(s AS DOUBLE) / 1000.0) AS timestamp_utc,
                    CAST(o AS DOUBLE) AS open,
                    CAST(h AS DOUBLE) AS high,
                    CAST(l AS DOUBLE) AS low,
                    CAST(c AS DOUBLE) AS close,
                    {volume_expr} AS volume,
                    CAST(_atlas_received_at_utc AS TIMESTAMPTZ) AS received_at_utc,
                    row_number() OVER (
                        PARTITION BY trim(sym), CAST(s AS BIGINT)
                        ORDER BY CAST(_atlas_received_at_utc AS TIMESTAMPTZ) DESC
                    ) AS rn
                FROM {source}
                WHERE ev = 'AM'
            )
            SELECT symbol, timestamp_utc, open, high, low, close, volume, received_at_utc
            FROM parsed
            WHERE rn = 1
            """
        )

    def reconcile(
        self,
        session_date: date,
        *,
        price_tolerance: float = 1e-9,
        volume_tolerance: float = 1e-6,
        sample_limit: int = 20,
    ) -> LiveReconciliationSummary:
        canonical = self.paths.canonical_file(Timeframe.MINUTE_1, session_date)
        if not canonical.is_file():
            raise FileNotFoundError(
                f"Canonical 1m session is not available for {session_date}: {canonical}"
            )
        journal = self.paths.live_journal_file(session_date)
        report_path = self.paths.live_reconciliation_report(session_date)
        report_path.parent.mkdir(parents=True, exist_ok=True)

        con = connect_utc(":memory:")
        try:
            self._create_live_view(con, journal)
            con.execute(
                f"""
                CREATE TEMP VIEW canonical_final AS
                SELECT symbol, timestamp_utc, open, high, low, close, volume
                FROM read_parquet({sql_string(canonical)})
                """
            )
            con.execute(
                f"""
                CREATE TEMP VIEW comparison AS
                SELECT
                    COALESCE(l.symbol, c.symbol) AS symbol,
                    COALESCE(l.timestamp_utc, c.timestamp_utc) AS timestamp_utc,
                    l.symbol IS NOT NULL AS has_live,
                    c.symbol IS NOT NULL AS has_canonical,
                    l.open AS live_open,
                    c.open AS canonical_open,
                    l.high AS live_high,
                    c.high AS canonical_high,
                    l.low AS live_low,
                    c.low AS canonical_low,
                    l.close AS live_close,
                    c.close AS canonical_close,
                    l.volume AS live_volume,
                    c.volume AS canonical_volume,
                    CASE
                        WHEN l.symbol IS NULL OR c.symbol IS NULL THEN false
                        ELSE
                            abs(l.open - c.open) > {price_tolerance}
                            OR abs(l.high - c.high) > {price_tolerance}
                            OR abs(l.low - c.low) > {price_tolerance}
                            OR abs(l.close - c.close) > {price_tolerance}
                            OR abs(l.volume - c.volume) > {volume_tolerance}
                    END AS value_mismatch
                FROM live_last l
                FULL OUTER JOIN canonical_final c
                  ON l.symbol = c.symbol
                 AND l.timestamp_utc = c.timestamp_utc
                """
            )

            live_count = int(con.execute("SELECT count(*) FROM live_last").fetchone()[0])
            canonical_count = int(con.execute("SELECT count(*) FROM canonical_final").fetchone()[0])
            matched, live_only, canonical_only, mismatches = con.execute(
                """
                SELECT
                    count(*) FILTER (WHERE has_live AND has_canonical),
                    count(*) FILTER (WHERE has_live AND NOT has_canonical),
                    count(*) FILTER (WHERE NOT has_live AND has_canonical),
                    count(*) FILTER (WHERE has_live AND has_canonical AND value_mismatch)
                FROM comparison
                """
            ).fetchone()
            matched = int(matched)
            live_only = int(live_only)
            canonical_only = int(canonical_only)
            mismatches = int(mismatches)
            exact = matched - mismatches

            sample_rows = con.execute(
                """
                SELECT symbol, timestamp_utc, has_live, has_canonical,
                       live_open, canonical_open, live_high, canonical_high,
                       live_low, canonical_low, live_close, canonical_close,
                       live_volume, canonical_volume, value_mismatch
                FROM comparison
                WHERE NOT (has_live AND has_canonical) OR value_mismatch
                ORDER BY timestamp_utc, symbol
                LIMIT ?
                """,
                [sample_limit],
            ).fetchall()
            columns = (
                "symbol",
                "timestamp_utc",
                "has_live",
                "has_canonical",
                "live_open",
                "canonical_open",
                "live_high",
                "canonical_high",
                "live_low",
                "canonical_low",
                "live_close",
                "canonical_close",
                "live_volume",
                "canonical_volume",
                "value_mismatch",
            )
            samples = []
            for row in sample_rows:
                item = dict(zip(columns, row))
                if item["timestamp_utc"] is not None:
                    item["timestamp_utc"] = item["timestamp_utc"].isoformat()
                samples.append(item)
        finally:
            con.close()

        summary = LiveReconciliationSummary(
            session_date=session_date,
            live_bar_count=live_count,
            canonical_bar_count=canonical_count,
            matched_key_count=matched,
            live_only_key_count=live_only,
            canonical_only_key_count=canonical_only,
            value_mismatch_count=mismatches,
            exact_match_count=exact,
            report_path=str(report_path),
        )
        payload = {
            "summary": summary.model_dump(mode="json"),
            "policy": {
                "canonical_final_is_authoritative": True,
                "price_tolerance": price_tolerance,
                "volume_tolerance": volume_tolerance,
                "live_values_rewrite_canonical": False,
            },
            "anomaly_samples": samples,
        }
        atomic_write_text(report_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return summary
