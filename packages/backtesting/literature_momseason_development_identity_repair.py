from __future__ import annotations

from datetime import date
from typing import Mapping

import duckdb

from .literature_momseason_adjusted_predictor_source import _clean_symbol
from .literature_momseason_development import MomSeasonDevelopmentResearch


LIT01_DEVELOPMENT_IDENTITY_REPAIR_VERSION = (
    "lit01-development-target-identity-v2-active-pit-then-authoritative-interval"
)
_SAFE_IDENTITY_QUALITIES = frozenset({"strong", "medium"})


def _safe_ticker_sets(
    rows: list[dict[str, object]],
) -> tuple[set[str], set[str]]:
    safe: set[str] = set()
    active: set[str] = set()
    for row in rows:
        quality = str(row.get("identity_quality") or "").strip().lower()
        ticker = _clean_symbol(row.get("ticker"))
        if quality not in _SAFE_IDENTITY_QUALITIES or ticker is None:
            continue
        safe.add(ticker)
        if bool(row.get("active", True)):
            active.add(ticker)
    return safe, active


def resolve_target_ticker_from_pit_rows(
    rows: list[dict[str, object]],
    *,
    endpoint_session: date,
    instrument_id: str,
    authoritative_ticker: str | None,
) -> tuple[str | None, str]:
    """Resolve one endpoint alias without using price/outcome information.

    A unique active PIT alias is strongest. If the snapshot still contains multiple
    safe aliases for the same stable instrument, only an authoritative provider
    ticker-validity interval may disambiguate them. No alphabetical or price-based
    choice is permitted.
    """

    safe, active = _safe_ticker_sets(rows)
    authoritative = _clean_symbol(authoritative_ticker)

    if len(active) == 1:
        return next(iter(active)), "UNIQUE_ACTIVE_PIT_ALIAS"

    if len(active) > 1:
        if authoritative is not None and authoritative in active:
            return authoritative, "AUTHORITATIVE_INTERVAL_ACTIVE_ALIAS"
        raise RuntimeError(
            "ambiguous active PIT ticker for development target endpoint without "
            "unique authoritative continuity evidence: "
            f"{endpoint_session} {instrument_id} aliases={sorted(active)}"
        )

    if len(safe) == 1:
        return next(iter(safe)), "UNIQUE_SAFE_PIT_ALIAS"

    if len(safe) > 1:
        if authoritative is not None and authoritative in safe:
            return authoritative, "AUTHORITATIVE_INTERVAL_SAFE_ALIAS"
        raise RuntimeError(
            "ambiguous PIT ticker for development target endpoint without unique "
            "authoritative continuity evidence: "
            f"{endpoint_session} {instrument_id} aliases={sorted(safe)}"
        )

    return None, "NO_SAFE_PIT_ALIAS"


class MomSeasonDevelopmentResearchIdentitySafe(MomSeasonDevelopmentResearch):
    """LIT-01 development runner with source-grounded target alias resolution.

    The scientific contract and accepted freeze are inherited unchanged. This class
    repairs only the pre-outcome source planner: duplicate historical aliases for one
    stable instrument are resolved by PIT active state and, when needed, the retained
    Massive authoritative ticker-event interval view.
    """

    def _authoritative_interval_ticker(
        self,
        *,
        endpoint_session: date,
        instrument_id: str,
    ) -> str | None:
        path = self.native.paths.authoritative_ticker_intervals_file()
        if not path.is_file():
            return None
        con = duckdb.connect(":memory:")
        try:
            rows = con.execute(
                """
                SELECT ticker
                FROM read_parquet(?)
                WHERE instrument_id = ?
                  AND continuity_authority = TRUE
                  AND valid_from_date <= ?
                  AND (valid_to_date_exclusive IS NULL OR ? < valid_to_date_exclusive)
                ORDER BY ticker
                """,
                [
                    str(path),
                    instrument_id,
                    endpoint_session,
                    endpoint_session,
                ],
            ).fetchall()
        finally:
            con.close()
        tickers = sorted(
            {
                ticker
                for row in rows
                if (ticker := _clean_symbol(row[0])) is not None
            }
        )
        if len(tickers) > 1:
            raise RuntimeError(
                "multiple authoritative ticker intervals cover one LIT-01 development "
                f"endpoint: {endpoint_session} {instrument_id} aliases={tickers}"
            )
        return tickers[0] if tickers else None

    def _historical_ticker_for_target(
        self,
        *,
        endpoint_session: date,
        instrument_id: str,
        formation_ticker: str,
        historical: Mapping[date, Mapping[str, list[dict[str, object]]]],
    ) -> str:
        authoritative = self._authoritative_interval_ticker(
            endpoint_session=endpoint_session,
            instrument_id=instrument_id,
        )

        if endpoint_session in historical:
            rows = list(historical[endpoint_session].get(instrument_id, []))
            resolved, _reason = resolve_target_ticker_from_pit_rows(
                rows,
                endpoint_session=endpoint_session,
                instrument_id=instrument_id,
                authoritative_ticker=authoritative,
            )
            if resolved is not None:
                return resolved

        if authoritative is not None:
            return authoritative

        ticker = _clean_symbol(formation_ticker)
        if ticker is None:
            raise RuntimeError(
                f"invalid formation ticker for development target endpoint: {instrument_id}"
            )
        return ticker
