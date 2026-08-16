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

The canonical event rows contain event date, provider-native ticker, event type,
query identifier/basis, whether the evidence is authoritative for continuity, and
fetch time. The derived view is rebuilt from canonical event files and does not
change their meaning.

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
ticker-event transformation contract unless `--force` is supplied.

If a ticker resolves to more than one instrument in a snapshot, the sync refuses to
guess. A future explicit instrument-id workflow can resolve such cases with stronger
evidence.

## Merge policy

Ticker events enrich continuity; they do not replace ATLAS identity rules.

- Strong FIGI identity can connect snapshot observations across ticker labels.
- Provider ticker-change events can supply explicit dates/labels for that same stable
  instrument.
- Ticker-only events are non-authoritative and cannot merge identities.
- Ambiguous or contradictory evidence is surfaced for reconciliation rather than
  silently coerced.
