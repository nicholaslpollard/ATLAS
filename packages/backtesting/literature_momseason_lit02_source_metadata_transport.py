from __future__ import annotations

from datetime import date
from typing import Mapping

from packages.core.exceptions import ProviderError

from .literature_momseason_lit02_source_metadata import MomSeasonLIT02SourceMetadata


LIT02_SOURCE_METADATA_TRANSPORT_VERSION = (
    "lit02-source-metadata-transport-v2-massive-404-source-unavailable"
)
LIT02_MASSIVE_TICKER_EVENTS_NOT_FOUND = "MASSIVE_TICKER_EVENTS_NOT_FOUND"


class MomSeasonLIT02SourceMetadataTransportSafe(MomSeasonLIT02SourceMetadata):
    """LIT-02 source classifier with fail-closed Massive 404 semantics.

    Massive's ticker-events endpoint is an optional continuity authority inside the
    frozen LIT-02 source hierarchy. A provider HTTP 404 establishes that this
    particular source did not supply a ticker-event record for the queried Composite
    FIGI. It is therefore source-unavailable evidence, not a reason to abort the full
    199-case source-only run. The case must continue to the separately frozen SEC
    authority and remains unresolved if no admissible source ultimately resolves it.

    Other Massive provider failures are still fatal because transport/rate/auth/server
    failures do not establish source absence.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._massive_event_not_found: set[str] = set()

    def _massive_ticker_events(self, composite_figi: str) -> list[dict[str, object]]:
        cached = self._massive_event_cache.get(composite_figi)
        if cached is not None:
            return cached
        self._massive_reads += 1
        try:
            raw = self.massive.ticker_events(composite_figi)
        except ProviderError as exc:
            message = str(exc)
            if "HTTP 404" not in message and " 404" not in message:
                raise
            self._massive_event_not_found.add(composite_figi)
            self._massive_event_cache[composite_figi] = []
            return []
        rows = [dict(item) for item in raw if isinstance(item, Mapping)]
        self._massive_event_cache[composite_figi] = rows
        return rows

    def _resolve_instrument(
        self,
        *,
        instrument_id: str,
        identity_rows: list[dict[str, object]],
        endpoint_session: date,
        historical_ticker: str,
    ) -> dict[str, object]:
        result = super()._resolve_instrument(
            instrument_id=instrument_id,
            identity_rows=identity_rows,
            endpoint_session=endpoint_session,
            historical_ticker=historical_ticker,
        )
        identity = result.get("identity")
        composite_figi = (
            str(identity.get("composite_figi") or "").strip()
            if isinstance(identity, Mapping)
            else ""
        )
        if not composite_figi or composite_figi not in self._massive_event_not_found:
            return result

        normalized = dict(result)
        evidence = normalized.get("massive_evidence")
        if isinstance(evidence, Mapping):
            evidence_payload = dict(evidence)
            evidence_payload["provider_status"] = "HTTP_404_NOT_FOUND"
            evidence_payload["source_available"] = False
            evidence_payload["transport_version"] = LIT02_SOURCE_METADATA_TRANSPORT_VERSION
            normalized["massive_evidence"] = evidence_payload

        if normalized.get("resolution_status") != "RESOLVED":
            reasons = {
                str(value)
                for value in (normalized.get("unresolved_reasons") or [])
                if str(value)
            }
            reasons.add(LIT02_MASSIVE_TICKER_EVENTS_NOT_FOUND)
            normalized["unresolved_reasons"] = sorted(reasons)
        return normalized
