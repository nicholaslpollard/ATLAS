# Sessions and Derived Bar Construction

The legacy Chart Monitor used wall-clock flooring that could mix premarket, regular-market, and after-hours data. ATLAS does not.

## Session classification

For U.S. equities ATLAS initially uses the XNYS calendar for official regular-session open/close times. Extended-hours conventions are tracked separately:

- premarket: 04:00 ET to official regular open
- regular: official exchange open through official close
- after-hours: official close to 20:00 ET

Holidays and early closes come from the exchange calendar.

## Regular-session derived bars

Regular-session 15m/1h/4h bars are anchored to the actual regular-session open.

Example normal session:

- 1h: 09:30–10:29:59, 10:30–11:29:59, ...
- 4h: 09:30–13:29:59, then a final partial regular-session bar from 13:30–16:00

The exact final-bar labeling convention will be implemented and unit-tested in the aggregation phase.

## Extended hours

Extended-hours 1-minute facts are preserved. They are not silently mixed into regular-session derived bars. Extended-hours features may be built separately where useful (gap behavior, premarket volume, overnight movement, etc.).

## No arbitrary row-chunk boundaries

Aggregation windows are determined from timestamps/session boundaries, never from arbitrary DataFrame chunk sizes. Chunking may be used internally for memory management only if aggregation correctness across boundaries is explicitly preserved.
