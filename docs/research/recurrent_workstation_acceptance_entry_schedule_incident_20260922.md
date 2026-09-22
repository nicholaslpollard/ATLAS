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

## Second attempt

After the first repair was accepted, a second isolated regular-session run was started:

- run id: `20260922T140229Z`
- ticker: `SPY`
- quote bundle fingerprint:
  `302ab9633eb58504f13f28d67bdc8f3f79c3971afb031b031bd43034bd7995bf`
- bundle capture timestamp: `2026-09-22T14:02:32.792512+00:00`

The quote capture again succeeded with one provider read and no provider/broker
mutation. The reserve evidence itself now satisfied
`built_at_utc >= scheduled_for_utc`, but applying RESERVE failed with:

```
RecurrentCycleOrchestrationError:
cycle updated timestamp cannot precede creation
```

The first repair correctly moved the deterministic cycle schedule to quote receipt.
However, the harness still created/began the recurrent cycle at the later bundle
capture timestamp and then applied RESERVE using the earlier quote receipt timestamp.
The durable recurrent-cycle receipt invariant correctly rejected an update before
cycle creation.

## Final repair

The production RESERVE and recurrent-cycle contracts remain unchanged.

The workstation acceptance harness now freezes the complete ENTRY chronology as:

```
provider_timestamp_utc
<= quote.received_at_utc
 = scheduled_for_utc
 = reserve built_at_utc
<= quote_bundle.captured_at_utc
 = cycle begin time
 = empty CLOSE application time
 = RESERVE application time
```

The schedule remains the first ATLAS-observable evidence time. The cycle mutation
timestamp is the later bundle-capture time, so no stage update can predate cycle
creation. The ENTRY acceptance artifact records the schedule, quote receipt, bundle
capture and cycle-action timestamps explicitly.

Regression coverage now proves both independent invariants:

1. RESERVE evidence cannot be built before its scheduled slot; and
2. cycle mutation cannot occur before the acceptance cycle-action timestamp.

## Authority boundary

This repair changes only the isolated workstation acceptance fixture chronology. It
does not change the recurrent RESERVE contract, strategy evidence, provider/broker
permissions, order authority, PAPER authority, LIVE authority, promotion authority or
confluence authority.

The failed run is not accepted workstation evidence. A new isolated run id must be
used for the next regular-market-hours attempt.
