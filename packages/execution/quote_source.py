from __future__ import annotations

from packages.core.enums import LiveConnectionState, LiveFeedMode, QuoteFreshness, SessionSegment
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.schemas.live_market import LiveQuote, LiveStateSnapshot


class ExecutionQuoteError(RuntimeError):
    pass


class Phase15LiveQuoteResolver:
    """Read one exact provider-native quote from ATLAS live state.

    This class never starts a stream. Execution is allowed only when the existing live
    state is actively subscribed, undelayed, gap-free, regular-session, and the symbol's
    quote is already classified FRESH by the live-state layer.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.path = MarketDataPaths(settings).live_state_file()
        self.read_count = 0

    def quote(self, ticker: str) -> LiveQuote:
        if not self.path.is_file():
            raise ExecutionQuoteError(f"live state is unavailable: {self.path}")
        try:
            snapshot = LiveStateSnapshot.model_validate_json(self.path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise ExecutionQuoteError("live state snapshot is invalid") from exc
        self.read_count += 1
        if snapshot.connection_state != LiveConnectionState.SUBSCRIBED:
            raise ExecutionQuoteError("live market-data connection is not subscribed")
        if snapshot.feed_mode != LiveFeedMode.REALTIME or snapshot.expected_delay_seconds != 0:
            raise ExecutionQuoteError("live execution evidence is not realtime")
        if snapshot.open_transport_gap_started_at_utc is not None:
            raise ExecutionQuoteError("live market-data transport gap is currently open")
        if snapshot.session.session_segment != SessionSegment.REGULAR:
            raise ExecutionQuoteError("execution quote source is outside regular session")
        matches = [item for item in snapshot.symbols if item.symbol == ticker]
        if len(matches) != 1:
            raise ExecutionQuoteError("live state does not contain exactly one provider-native ticker")
        symbol = matches[0]
        if symbol.quote is None:
            raise ExecutionQuoteError("live state ticker has no quote")
        if symbol.quote_freshness != QuoteFreshness.FRESH:
            raise ExecutionQuoteError("live state ticker quote is not FRESH")
        quote = symbol.quote
        if quote.feed_mode != LiveFeedMode.REALTIME or quote.expected_delay_seconds != 0:
            raise ExecutionQuoteError("ticker quote is not undelayed realtime evidence")
        if quote.session_segment != SessionSegment.REGULAR:
            raise ExecutionQuoteError("ticker quote is not a regular-session quote")
        return quote
