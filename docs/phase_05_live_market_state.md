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

### Current Massive plan boundary

The target deployment currently uses Massive Stocks Starter. Massive's current plan
matrix includes stock minute-aggregate WebSockets on Starter at 15-minute delayed
recency, but stock quote WebSockets (`Q`) are not included on Basic, Starter, or
Developer; they are a real-time Advanced-plan feed.

Therefore the production Phase 05 contract for the current deployment is:

```text
Massive delayed WebSocket: AM.*
```

and **not**:

```text
Massive delayed WebSocket: Q.<ticker>
```

The Massive quote parser/client support remains in the codebase as a provider
capability for a future Advanced-plan deployment, but it is not an acceptance
requirement for the current Starter deployment.

Focused live bid/ask data remains part of the overall ATLAS architecture, but the
current design obtains it later through the broker/finalist path (Robinhood) rather
than requiring a $199/month Massive Stocks Advanced subscription before measured
opportunity loss justifies that upgrade.

## Backpressure contract

The socket reader does as little work as possible and transfers raw frames into a
bounded asyncio queue. Parsing, journaling, and state mutation happen downstream.

ATLAS will not silently discard market data when the consumer falls behind. A full
ingress queue raises a backpressure fault, marks the connection degraded, and causes
a reconnect. This makes insufficient throughput observable and measurable.

The client also records low-overhead telemetry from each run: frames received,
processed events, peak ingress queue depth, and configured queue capacity. The
market-hours benchmark uses this telemetry directly so measurement does not require
slowing the event path with allocation tracing or per-event logging.

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

Live benchmark reports:

```text
data/live/benchmarks/YYYY/YYYY-MM-DD/YYYY-MM-DDTHHMMSSZ.json
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

Run a focused temporary delayed minute stream on the current Stocks Starter plan:

```powershell
.\.venv\Scripts\python.exe scripts\run_live_market_state.py `
  --feed delayed `
  --minute-symbols AAPL,MSFT `
  --max-seconds 60
```

Run broad delayed minute state for discovery:

```powershell
.\.venv\Scripts\python.exe scripts\run_live_market_state.py `
  --feed delayed `
  --minute-symbols "*"
```

`--quote-symbols` is retained for a future Massive Stocks Advanced deployment or
provider-capability testing. It is not expected to authorize on the current Stocks
Starter plan.

### Market-hours benchmark

Run the broad benchmark during an exchange session after the delayed feed has had
time to begin delivering regular-session bars. A five-minute strict run is the Phase
05 target-machine acceptance check:

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_live_market.py `
  --feed delayed `
  --minute-symbols "*" `
  --seconds 300 `
  --require-events `
  --strict
```

The report includes:

- raw WebSocket frames and normalized event rates;
- current-state symbol coverage;
- peak ingress queue depth/utilization;
- process CPU time and one-core-equivalent utilization;
- peak process RSS/working set;
- fresh/aging/stale minute-state counts;
- p50/p95/max excess lag after subtracting the expected 900-second provider delay;
- journal byte growth;
- parse errors, reconnects, and out-of-order observations.

`--strict` returns nonzero if parsing fails, the connection reconnects, or peak ingress
queue utilization reaches 80%. `--require-events` returns nonzero when no accepted
market events are observed. These flags are intended for market-hours acceptance, not
weekend smoke tests.

After the corresponding Massive flat file is downloaded and materialized into
canonical 1m, reconcile the live journal with finalized data:

```powershell
.\.venv\Scripts\python.exe scripts\reconcile_live_session.py --date YYYY-MM-DD
```

## Real-provider acceptance log

### 2026-08-16

Target Windows machine:

- full suite: **85 passed in 8.88s**;
- Phase 05 validator: PASS;
- delayed endpoint connection: PASS;
- delayed endpoint authentication: PASS (`Connected Successfully`, `authenticated`);
- combined `AM.AAPL,Q.AAPL` subscription: rejected with provider status `error: not authorized`;
- rejection classified as expected current-plan entitlement behavior because Stocks
  Starter includes delayed `AM` but does not include stock WebSocket `Q`;
- focused delayed `AM.AAPL` subscription: PASS, clean 15-second Sunday run with zero
  reconnects and zero events as expected while the market was closed;
- broad delayed `AM.*` subscription: PASS, clean 15-second Sunday run with zero parse
  errors/reconnects and zero events as expected while the market was closed.

The next provider check is the five-minute `AM.*` benchmark during the 2026-08-17
market session. Because the feed is delayed 15 minutes, the benchmark should begin no
earlier than approximately 09:45 ET if regular-session event flow is the goal; a
slightly later start gives a cleaner throughput sample.

## Acceptance gates

Phase 05 is accepted only after all of the following are proven:

1. unit/integration tests and validators pass on Windows and Ubuntu;
2. real Massive delayed WebSocket authentication succeeds with the user's rotated
   credentials;
3. a real delayed minute subscription writes a valid current-state snapshot and
   provisional journal;
4. the current-plan entitlement boundary is explicit: Starter uses delayed `AM`, while
   Massive `Q` is not treated as a required or available Starter feed;
5. broad `AM.*` is observed during a market session on the target machine with no
   backpressure, parse errors, or pathological CPU/memory use;
6. delayed-feed freshness behaves as expected;
7. at least one collected live session is compared with the later finalized canonical
   1m session, with canonical data remaining authoritative.

Phase 05 does not yet compute technical features. The Feature Engine consumes this
live-state contract in Phase 06.
