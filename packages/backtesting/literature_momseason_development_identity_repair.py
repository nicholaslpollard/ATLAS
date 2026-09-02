from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Mapping

import duckdb

from packages.core.atomic_io import atomic_write_text

from .literature_momseason_adjusted_predictor_source import _clean_symbol
from .literature_momseason_development import MomSeasonDevelopmentResearch
from .literature_momseason_source import canonical_json


LIT01_DEVELOPMENT_IDENTITY_REPAIR_VERSION = (
    "lit01-development-target-identity-v4-active-pit-authoritative-when-issued-figi-events"
)
LIT01_IDENTITY_EVIDENCE_CONTRACT = (
    "lit01-development-target-continuity-evidence-v1-massive-composite-figi-pre-outcome"
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


def _regular_alias_with_when_issued_variant(aliases: set[str]) -> str | None:
    """Return the regular alias for the exact ``BASE`` + ``BASEw`` pattern.

    NYSE/CTA symbol convention uses a lowercase trailing ``w`` as the compact
    representation of the ``WI`` (When Issued) suffix. The rule is deliberately
    narrow and case-sensitive: only an exact two-alias set ``{BASE, BASEw}`` is
    resolved here. Any other simultaneous-alias shape remains ambiguous.
    """

    if len(aliases) != 2:
        return None
    for candidate in aliases:
        if f"{candidate}w" in aliases:
            return candidate
    return None


def _unique_authoritative_composite_figi(
    rows: list[dict[str, object]],
    *,
    endpoint_session: date,
    instrument_id: str,
) -> str | None:
    """Return one Composite FIGI only when PIT evidence is internally consistent.

    This deliberately mirrors ATLAS Phase 4 authority semantics: Composite FIGI is
    accepted as the provider query identifier for ticker-event continuity. Share
    Class FIGI or ticker text is not promoted to continuity authority here.
    """

    figis: set[str] = set()
    for row in rows:
        quality = str(row.get("identity_quality") or "").strip().lower()
        if quality not in _SAFE_IDENTITY_QUALITIES:
            continue
        value = str(row.get("composite_figi") or "").strip().upper()
        if value:
            figis.add(value)
    if len(figis) > 1:
        raise RuntimeError(
            "multiple Composite FIGIs appear for one stable LIT-01 development "
            f"instrument: {endpoint_session} {instrument_id} figis={sorted(figis)}"
        )
    return next(iter(figis)) if figis else None


def authoritative_ticker_from_massive_events(
    raw_events: list[dict[str, object]],
    *,
    endpoint_session: date,
    instrument_id: str,
) -> str | None:
    """Resolve the ticker valid at ``endpoint_session`` from Massive ticker events.

    Massive ticker-change events state the ticker becoming valid on the event date.
    ATLAS Phase 4 therefore models them as half-open validity intervals. This helper
    applies the same rule in-memory for isolated LIT-01 evidence. A same-day provider
    contradiction is blocking rather than ordered arbitrarily.
    """

    by_date: dict[date, set[str]] = {}
    for raw in raw_events:
        if str(raw.get("type") or "").strip().lower() != "ticker_change":
            continue
        raw_date = raw.get("date")
        change = raw.get("ticker_change")
        if not raw_date or not isinstance(change, dict):
            continue
        ticker = _clean_symbol(change.get("ticker"))
        if ticker is None:
            continue
        try:
            event_date = date.fromisoformat(str(raw_date))
        except ValueError:
            continue
        by_date.setdefault(event_date, set()).add(ticker)

    for event_date, tickers in sorted(by_date.items()):
        if len(tickers) > 1:
            raise RuntimeError(
                "Massive Composite-FIGI ticker events report multiple tickers on one "
                "event date for LIT-01 development continuity: "
                f"{instrument_id} {event_date} aliases={sorted(tickers)}"
            )

    eligible = [event_date for event_date in by_date if event_date <= endpoint_session]
    if not eligible:
        return None
    latest = max(eligible)
    return next(iter(by_date[latest]))


def resolve_target_ticker_from_pit_rows(
    rows: list[dict[str, object]],
    *,
    endpoint_session: date,
    instrument_id: str,
    authoritative_ticker: str | None,
) -> tuple[str | None, str]:
    """Resolve one endpoint alias without using price/outcome information.

    A unique active PIT alias is strongest. If the snapshot still contains multiple
    safe aliases for the same stable instrument, an authoritative provider ticker
    validity interval is preferred. If no interval is available, the only
    provider-symbol semantic exception is the exact regular/When-Issued pair
    ``BASE`` and ``BASEw``; the regular line is retained. No alphabetical,
    availability, volume, price, or return-based choice is permitted.
    """

    safe, active = _safe_ticker_sets(rows)
    authoritative = _clean_symbol(authoritative_ticker)

    if len(active) == 1:
        return next(iter(active)), "UNIQUE_ACTIVE_PIT_ALIAS"

    if len(active) > 1:
        if authoritative is not None and authoritative in active:
            return authoritative, "AUTHORITATIVE_INTERVAL_ACTIVE_ALIAS"
        regular = _regular_alias_with_when_issued_variant(active)
        if regular is not None:
            return regular, "REGULAR_ALIAS_WITH_WHEN_ISSUED_VARIANT"
        raise RuntimeError(
            "ambiguous active PIT ticker for development target endpoint without "
            "unique authoritative continuity evidence or exact regular/When-Issued "
            "alias semantics: "
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
    repairs only the pre-outcome source planner. Existing ATLAS authoritative ticker
    intervals remain first-class evidence. If a frozen target holding is still
    ambiguous and ``--acquire`` was explicitly supplied, the runner may query Massive
    ticker events by one unique PIT Composite FIGI and retain that response only in an
    isolated LIT-01 cache. It never mutates the canonical Phase 4 ticker-event store.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._allow_identity_source_acquisition = False
        self._identity_provider_calls_this_run = 0
        self._identity_cache_hits_this_run = 0
        self._identity_resolutions_this_run = 0

    def identity_evidence_path(self, instrument_id: str) -> Path:
        return self.root / "identity_continuity" / f"instrument_id={instrument_id}.json"

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

    def _load_or_acquire_identity_events(
        self,
        *,
        endpoint_session: date,
        instrument_id: str,
        rows: list[dict[str, object]],
    ) -> list[dict[str, object]] | None:
        composite_figi = _unique_authoritative_composite_figi(
            rows,
            endpoint_session=endpoint_session,
            instrument_id=instrument_id,
        )
        if composite_figi is None:
            return None

        path = self.identity_evidence_path(instrument_id)
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("contract_version") != LIT01_IDENTITY_EVIDENCE_CONTRACT:
                raise RuntimeError(
                    f"LIT-01 identity evidence contract mismatch: {instrument_id}"
                )
            if payload.get("instrument_id") != instrument_id:
                raise RuntimeError(
                    f"LIT-01 identity evidence instrument mismatch: {instrument_id}"
                )
            if payload.get("query_identifier_type") != "composite_figi":
                raise RuntimeError(
                    f"LIT-01 identity evidence is not Composite-FIGI authoritative: {instrument_id}"
                )
            if str(payload.get("query_identifier") or "").upper() != composite_figi:
                raise RuntimeError(
                    "LIT-01 identity evidence Composite FIGI differs from PIT source: "
                    f"{instrument_id}"
                )
            if not bool(payload.get("continuity_authority")):
                raise RuntimeError(
                    f"LIT-01 identity evidence lacks continuity authority: {instrument_id}"
                )
            raw = payload.get("raw_events")
            if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
                raise RuntimeError(
                    f"LIT-01 identity evidence raw event payload is invalid: {instrument_id}"
                )
            expected_fingerprint = hashlib.sha256(
                canonical_json(raw).encode("utf-8")
            ).hexdigest()
            if payload.get("provider_response_fingerprint") != expected_fingerprint:
                raise RuntimeError(
                    f"LIT-01 identity evidence fingerprint mismatch: {instrument_id}"
                )
            self._identity_cache_hits_this_run += 1
            return [dict(item) for item in raw]

        if not self._allow_identity_source_acquisition:
            return None

        raw_events = self.native.source.reference_provider.ticker_events(composite_figi)
        if not isinstance(raw_events, list) or not all(
            isinstance(item, dict) for item in raw_events
        ):
            raise RuntimeError(
                f"Massive ticker-event response is invalid for {instrument_id}"
            )
        self._identity_provider_calls_this_run += 1
        normalized_raw = [dict(item) for item in raw_events]
        payload = {
            "contract_version": LIT01_IDENTITY_EVIDENCE_CONTRACT,
            "identity_repair_version": LIT01_DEVELOPMENT_IDENTITY_REPAIR_VERSION,
            "instrument_id": instrument_id,
            "query_identifier": composite_figi,
            "query_identifier_type": "composite_figi",
            "continuity_authority": True,
            "provider": "Massive",
            "source_endpoint": "ticker_events",
            "source_only_pre_outcome": True,
            "raw_events": normalized_raw,
            "provider_response_fingerprint": hashlib.sha256(
                canonical_json(normalized_raw).encode("utf-8")
            ).hexdigest(),
            "development_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, canonical_json(payload) + "\n")
        return normalized_raw

    def _isolated_authoritative_ticker(
        self,
        *,
        endpoint_session: date,
        instrument_id: str,
        rows: list[dict[str, object]],
    ) -> str | None:
        raw_events = self._load_or_acquire_identity_events(
            endpoint_session=endpoint_session,
            instrument_id=instrument_id,
            rows=rows,
        )
        if raw_events is None:
            return None
        ticker = authoritative_ticker_from_massive_events(
            raw_events,
            endpoint_session=endpoint_session,
            instrument_id=instrument_id,
        )
        if ticker is not None:
            self._identity_resolutions_this_run += 1
        return ticker

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
            try:
                resolved, _reason = resolve_target_ticker_from_pit_rows(
                    rows,
                    endpoint_session=endpoint_session,
                    instrument_id=instrument_id,
                    authoritative_ticker=authoritative,
                )
            except RuntimeError as initial_error:
                isolated = self._isolated_authoritative_ticker(
                    endpoint_session=endpoint_session,
                    instrument_id=instrument_id,
                    rows=rows,
                )
                if isolated is None:
                    if not self._allow_identity_source_acquisition:
                        raise RuntimeError(
                            f"{initial_error}; rerun with --acquire to permit source-only "
                            "Composite-FIGI ticker-event continuity acquisition"
                        ) from initial_error
                    raise RuntimeError(
                        f"{initial_error}; Massive Composite-FIGI ticker events did not "
                        "establish a ticker valid at this endpoint"
                    ) from initial_error
                resolved, _reason = resolve_target_ticker_from_pit_rows(
                    rows,
                    endpoint_session=endpoint_session,
                    instrument_id=instrument_id,
                    authoritative_ticker=isolated,
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

    def run(
        self,
        *,
        acquire: bool = False,
        force_plan: bool = False,
        force_acquire: bool = False,
    ) -> dict[str, object]:
        self._allow_identity_source_acquisition = bool(acquire)
        self._identity_provider_calls_this_run = 0
        self._identity_cache_hits_this_run = 0
        self._identity_resolutions_this_run = 0
        try:
            result = super().run(
                acquire=acquire,
                force_plan=force_plan,
                force_acquire=force_acquire,
            )
        finally:
            self._allow_identity_source_acquisition = False

        identity_source = {
            "contract_version": LIT01_IDENTITY_EVIDENCE_CONTRACT,
            "provider_calls_performed_this_run": self._identity_provider_calls_this_run,
            "cache_hits_this_run": self._identity_cache_hits_this_run,
            "authoritative_endpoint_resolutions_this_run": self._identity_resolutions_this_run,
            "canonical_ticker_event_store_mutated": False,
            "development_outcome_rows_used_for_identity": 0,
            "protected_return_rows_read": 0,
        }
        result["identity_continuity_source"] = identity_source
        result["provider_reads_performed_this_run"] = int(
            result.get("provider_reads_performed_this_run") or 0
        ) + self._identity_provider_calls_this_run
        atomic_write_text(self.report_path(), canonical_json(result) + "\n")
        return result
