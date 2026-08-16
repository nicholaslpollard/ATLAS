# Phase 05 — Live Market State

Phase 05 gives ATLAS a continuously updated view of the stock market without
weakening the canonical-history guarantees established in Phases 02–04.

## Core rule: live is provisional, canonical is final

WebSocket events are low-latency provider observations. They are useful for current
state, discovery, monitoring, and event triggers, but they are not permanent trusted
history.

```text
Massive WebSocket
    |
    +--> current live state (latest-value cache)
    |
    +--> append-only provisional live journal

Massive finalized flat file
    |
    +--> Phase 02 ingestion/validation
    +--> Phase 03 canonical 1m/1d
    +--> finalized derived bars
    |
    +--> live-vs-final reconciliation report
```

No WebSocket observation directly writes or mutates canonical Parquet. If the
provider later corrects a minute, the finalized canonical session wins and the
reconciliation report records the difference.

## Feed strategy

ATLAS initially uses the delayed Massive stock WebSocket unless configuration is
explicitly changed. Feed delay is part of the data contract rather than hidden.

Broad discovery input:

```text
AM.*
```

Minute aggregates are low enough frequency to maintain broad-market current state
and become the primary live input for the later 5K discovery funnel.

Focused NBBO input:

```text
Q.<ticker>
```

Quotes are intentionally opt-in for positions, watchlist names, finalists, or other
focused symbols. ATLAS does not default to `Q.*`; the quote stream has a much higher
message rate and is unnecessary for first-stage broad discovery.

Minute and focused-quote topics share one stock-cluster connection.

## Backpressure contract

The socket reader does as little work as possible and transfers raw frames into a
bounded asyncio queue. Parsing, journaling, and state mutation happen downstream.

ATLAS will not silently discard market data when the consumer falls behind. A full
ingress queue raises a backpressure fault, marks the connection degraded, and causes
a reconnect. This makes insufficient throughput observable and measurable.

## Delay-aware freshness

Freshness is measured relative to the expected arrival time:

```text
expected arrival = provider event time + configured feed delay
excess age       = now - expected arrival
```

For the initial delayed feed, the configured expected delay is 900 seconds. A
15-minute-old provider event can therefore still be `fresh` if it arrived on time for
the subscribed feed.

Current thresholds:

- fresh: excess age <= 90 seconds
- aging: excess age <= 300 seconds
- stale: excess age > 300 seconds

The realtime feed has expected delay zero.

## Provider-native ticker case

Phase 04 proved provider ticker case is identity-significant. The live parser, state
store, subscriptions, journal, and reconciliation preserve Massive ticker text exactly
apart from surrounding whitespace. `TPC` and `TpC` remain distinct.

## Current-state ordering

The latest-value cache is deterministic:

- minute bars reject an older minute than the current symbol minute;
- another update for the same minute must have a later ATLAS receive time;
- quotes are ordered by provider timestamp and then provider sequence;
- rejected older observations increment an explicit counter.

The cache stores only the latest supported values per symbol. Full provisional
history belongs in the live journal.

## Storage

Current state:

```text
data/live/market_state/current.json
```

Provisional raw event journal:

```text
data/live/journal/massive/stocks/YYYY/YYYY-MM-DD.jsonl
```

Finalization reconciliation:

```text
data/live/reconciliation/YYYY/YYYY-MM-DD.json
```

These runtime files are outside Git and are not part of the canonical historical
lake.

## Commands

Validate the local Phase 05 software contract without network access:

```powershell
.\.venv\Scripts\python.exe scripts\validate_phase5.py
```

Probe Massive delayed WebSocket connectivity and authentication without subscribing:

```powershell
.\.venv\Scripts\python.exe scripts\probe_massive_websocket.py --feed delayed
```

Run a focused temporary stream:

```powershell
.\.venv\Scripts\python.exe scripts\run_live_market_state.py `
  --feed delayed `
  --minute-symbols AAPL,MSFT `
  --quote-symbols AAPL `
  --max-seconds 60
```

Run broad minute state with focused quotes:

```powershell
.\.venv\Scripts\python.exe scripts\run_live_market_state.py `
  --feed delayed `
  --minute-symbols "*" `
  --quote-symbols AAPL,MSFT
```

After the corresponding Massive flat file is downloaded and materialized into
canonical 1m, reconcile the live journal with finalized data:

```powershell
.\.venv\Scripts\python.exe scripts\reconcile_live_session.py --date YYYY-MM-DD
```

## Acceptance gates

Phase 05 is accepted only after all of the following are proven:

1. unit/integration tests and validators pass on Windows and Ubuntu;
2. real Massive delayed WebSocket authentication succeeds with the user's rotated
   credentials;
3. a real subscription writes a valid current-state snapshot and provisional journal;
4. focused quote ingestion is proven;
5. broad `AM.*` is observed during a market session on the target machine with no
   backpressure, parse errors, or pathological CPU/memory use;
6. delayed-feed freshness behaves as expected;
7. at least one collected live session is compared with the later finalized canonical
   1m session, with canonical data remaining authoritative.

Phase 05 does not yet compute technical features. The Feature Engine consumes this
live-state contract in Phase 06.
