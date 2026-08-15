# ATLAS Session and Bar Construction

ATLAS uses XNYS exchange-session boundaries and stores timestamps in UTC.
Session interpretation uses America/New_York local-market time.

## Segments

- Premarket: 04:00 local -> official regular open
- Regular: official open -> official close
- After-hours: official close -> 20:00 local
- Closed: outside the configured envelope

## Derived-bar anchors

Derived intraday bars are anchored to the start of their own segment, never to
midnight or generic wall-clock multiples.

For a normal 09:30–16:00 regular session:

- 15m: 09:30, 09:45, ...
- 1h: 09:30, 10:30, ... 15:30
- 4h: 09:30 and 13:30

The final bar in a segment may be shorter than the nominal timeframe. Its
`bar_end_utc` records the actual segment boundary.

OHLC is deterministic:

- open = first minute open ordered by timestamp
- high = maximum minute high
- low = minimum minute low
- close = last minute close ordered by timestamp
- volume = sum of minute volume
- transaction count = sum when supplied
- VWAP = volume-weighted aggregation only when source VWAP exists; otherwise null

Premarket, regular, and after-hours observations are never combined in a single
derived bar.
