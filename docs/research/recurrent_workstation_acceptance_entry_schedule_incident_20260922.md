# Recurrent workstation acceptance entry-schedule incident — 2026-09-22

## Status

The first target-workstation regular-session run of
`scripts/run_recurrent_workstation_acceptance.py` reached the current Webull sandbox
L1 quote capture successfully and then failed closed during the ENTRY child phase.

Run id:

`20260922T133439Z`

Ticker:

`SPY`

Observed current quote bundle fingerprint:

`fc352dbb933f67335f514f6b5a59ce42cc724162c67cf59e09f9dab339d84d30`

Bundle capture timestamp:

`2026-09-22T13:34:43.158543+00:00`

The capture reported one provider read and zero provider writes, broker reads,
broker writes, PAPER authority or LIVE authority.

## Failure

The ENTRY child raised:

```
RecurrentReserveEvidenceError:
reserve evidence cannot be built before its scheduled cycle slot
```

The workstation harness had built its deterministic ENTRY cycle identity with
`scheduled_for_utc = quote_bundle.captured_at_utc`.

It then built the RESERVE evidence bundle with
`built_at_utc = quote.received_at_utc`.

The quote contract intentionally requires
`provider_timestamp_utc <= received_at_utc <= captured_at_utc`. Therefore the local
quote receipt can legitimately precede bundle capture by milliseconds. The workstation
harness consequently scheduled the cycle slightly after the evidence build timestamp.

The durable RESERVE invariant was correct and rejected the chronology.

## Repair

The production RESERVE evidence contract is unchanged.

The workstation acceptance harness now derives the ENTRY cycle schedule from the
**local quote receipt timestamp**, which is the first ATLAS-observable time for the
accepted quote:

`scheduled_for_utc = quote.received_at_utc`

The recurrent cycle still begins at the later bundle capture timestamp. The persisted
ENTRY acceptance stage records all three relevant times/lineage:

- scheduled cycle timestamp;
- quote receipt timestamp; and
- bundle capture timestamp.

A regression test reproduces the observed millisecond ordering and proves that a
RESERVE bundle built exactly at quote receipt satisfies the existing
`built_at_utc >= scheduled_for_utc` invariant.

## Authority boundary

This repair changes only the isolated workstation acceptance fixture chronology. It
does not change the recurrent RESERVE contract, strategy evidence, provider/broker
permissions, order authority, PAPER authority, LIVE authority, promotion authority or
confluence authority.

The failed run is not accepted workstation evidence. A new isolated run id must be
used for the next regular-market-hours attempt.
