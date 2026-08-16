# Phase 04 — Ticker-Event Continuity

Ticker text is a point-in-time market label, not an ATLAS instrument identity.
Phase 04B stores provider-reported ticker-change events as explicit continuity
evidence attached to the stable `instrument_id` created from the reference layer.

## Evidence hierarchy

For Massive ticker-event queries ATLAS uses:

1. Composite FIGI when present — `continuity_authority=true`
2. exact provider-native ticker only when Composite FIGI is unavailable —
   `continuity_authority=false`

Massive documents the ticker-events endpoint as experimental and accepts ticker,
CUSIP, or Composite FIGI identifiers. A ticker query describes the entity currently
represented by that ticker; stable identifiers are therefore preferred when ATLAS
needs historical continuity.

Ticker-only event evidence may be retained for research/audit, but it must never by
itself merge two ATLAS instrument identities.

## Provider-native ticker case

Ticker-change values preserve Massive/SIP case exactly apart from whitespace.
`TPC` and `TpC`, for example, remain distinct labels. Codes such as Composite FIGI
may be normalized independently because their case is not the ticker-identity
contract.

## Canonical storage

Per-instrument provider facts:

```text
data/canonical/corporate_actions/massive/ticker_events/
  instrument_id=<instrument_id>/part-000.parquet
```

Per-instrument sync manifests:

```text
data/manifests/reference/massive_ticker_events/<instrument_id>.json
```

Combined derived observation view:

```text
data/derived/reference/instruments/ticker_event_observations.parquet
```

Authoritative half-open ticker validity intervals:

```text
data/derived/reference/instruments/authoritative_ticker_intervals.parquet
```

The canonical event rows contain event date, provider-native ticker, event type,
query identifier/basis, whether the evidence is authoritative for continuity, and
fetch time. The derived views are rebuilt from canonical event files and do not
change their meaning.

An authoritative interval has the form `[valid_from_date, valid_to_date_exclusive)`.
For the real META acceptance case the resulting history is conceptually:

```text
FB    [2012-05-18, 2022-06-09)
META  [2022-06-09, open)
```

That map can later join a historical bar's provider ticker/date to the same stable
instrument without rewriting the original provider ticker fact.

Only Composite-FIGI-backed event rows can enter the authoritative interval view. If
one instrument has two different authoritative tickers on the same event date, ATLAS
suppresses that instrument's entire interval map rather than inventing an ordering.

## Targeted sync

Ticker events are intentionally not fetched for every instrument in the registry by
default. The endpoint is experimental and a broad universe would require tens of
thousands of REST requests, most of which are likely to return no changes.

Instead ATLAS initially syncs events when an instrument requires continuity evidence
(for example a reference-snapshot ticker mismatch, a corporate-action investigation,
a historical anomaly, or explicit research).

Given an existing reference snapshot:

```powershell
.\.venv\Scripts\python.exe scripts\sync_ticker_events.py `
  --ticker META `
  --date 2026-08-14
```

The CLI resolves the exact point-in-time ticker to one ATLAS instrument, selects the
strongest supported provider query identifier, persists the canonical event timeline,
and prints the normalized events. Repeating the same command is idempotent under the
ticker-event transformation contract unless `--force` is supplied. A skipped sync
still rebuilds the combined event/interval views, so derived contracts can evolve
without refetching unchanged provider events.

If a ticker resolves to more than one instrument in a snapshot, the sync refuses to
guess. A future explicit instrument-id workflow can resolve such cases with stronger
evidence.

## Deterministic reconciliation

After ticker events exist, reconcile them against all locally available reference
snapshots:

```powershell
.\.venv\Scripts\python.exe scripts\reconcile_identity_continuity.py `
  --ticker META `
  --date 2026-08-14
```

The reconciliation service is deliberately non-destructive. It does not rewrite
canonical bars/reference facts and never merges two `instrument_id` values. It
classifies the evidence into states such as:

- `confirmed_ticker_change` — multiple snapshot aliases are fully covered by
  authoritative provider events;
- `provider_history_confirmed` — the current snapshot alias is consistent with a
  broader authoritative provider timeline;
- `needs_authoritative_evidence` — snapshots show multiple aliases but no strong
  event timeline has been stored;
- `non_authoritative_support` — ticker-only event evidence is consistent but cannot
  establish identity continuity;
- `blocking_identity_anomaly` — contradictory authoritative events, a simultaneous
  exact-ticker collision, or an authoritative timeline that fails to cover an
  observed alias.

The report also records exact ticker text observed on other instrument identities.
Non-overlapping reuse is retained as reuse evidence, not merged. If the same exact
ticker resolves to multiple instrument IDs in the same point-in-time snapshot, the
condition is blocking.

Use `--json-out <path>` when a durable reconciliation artifact is needed.

## Merge policy

Ticker events enrich continuity; they do not replace ATLAS identity rules.

- Strong FIGI identity can connect snapshot observations across ticker labels.
- Composite-FIGI-backed provider ticker-change events can supply explicit
  dates/labels for that same stable instrument.
- Ticker-only events are non-authoritative and cannot merge identities.
- Ticker reuse across different instruments remains separate by design.
- Ambiguous or contradictory evidence is surfaced for reconciliation rather than
  silently coerced.
