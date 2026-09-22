# Recurrent workstation market-hours acceptance closeout — 2026-09-22

## Status

The isolated regular-session recurrent workstation acceptance completed successfully on
the target Windows workstation.

Acceptance contract:

`atlas-recurrent-workstation-acceptance-v1`

Accepted run id:

`20260922T142213Z`

Ticker:

`SPY`

Environment:

`WEBULL_SANDBOX_READ_ONLY_L1`

Final receipt fingerprint:

`d0f880a85d5f07c0ddc68c7d3017a0ae0e3bacc04d5e0bb6473da3f601340c4a`

Acceptance receipt:

`data/acceptance/recurrent_workstation/20260922T142213Z/live/acceptance/receipt.json`

## Observed acceptance sequence

### Current quote capture / ENTRY

The first read-only quote capture completed successfully:

- bundle fingerprint:
  `87ae60f2006fee20d98c774a571d70216a2cf16885b805e8c2155f1e0f2e1db4`
- captured at:
  `2026-09-22T14:22:16.458482+00:00`
- quote count: 1
- provider reads: 1
- provider writes: 0
- broker reads/writes: 0

The deterministic product acceptance fixture then completed ENTRY successfully.

Decision-record fingerprint:

`271061449ab5d1247013e627c31dc966685f09ace2d4c45ba57f1fb05a5e4325`

### Restart / MARK

The second read-only SPY quote capture completed successfully:

- bundle fingerprint:
  `fd9968f72687228f086aa4bb3f994071a0a719877b93231d8884b7284909f2fa`
- captured at:
  `2026-09-22T14:22:21.602747+00:00`

The process-boundary restart and MARK phase passed. The immutable one-minute reference
horizon deadline was:

`2026-09-22T14:23:16.115156+00:00`

The parent runner waited approximately 52.2 seconds for that deadline rather than
forcing an early close.

### TIME CLOSE

The third read-only SPY quote capture completed successfully after the immutable
deadline:

- bundle fingerprint:
  `ffd10d7d972ca40e0eea076e06384e2a730aee893b24b8f0792290bd9087ba53`
- captured at:
  `2026-09-22T14:23:19.829502+00:00`

The time-aware close path produced final disposition `TIME` and passed.

Close bundle fingerprint:

`5647256f158b6d7a36791d655e59328c920c4be49f529ee02ae0641097b7e870`

### Restart / exact CLOSE retry

A second process-boundary restart replayed the exact persisted close bundle.

The exact retry passed without double-applying the trade:

- closed-trade count before retry: 1
- closed-trade count after retry: 1
- final closed-trade count: 1
- cycle health after retry: `OPEN_CYCLE`
- invalid durable cycle/stage lineage: none reported by the acceptance runner

Final receipt fingerprint:

`d0f880a85d5f07c0ddc68c7d3017a0ae0e3bacc04d5e0bb6473da3f601340c4a`

## Acceptance interpretation

This run closes the PR #161 current-Webull regular-market-hours operational-runtime
acceptance gate for the frozen v1 acceptance contract.

The accepted proof demonstrates, on the target workstation with current read-only
market evidence, that ATLAS can:

1. ingest current sandbox L1 evidence during the XNYS regular session;
2. construct and admit the deterministic reference fixture;
3. persist the recurrent account and cycle state;
4. survive a process restart and mark the authoritative recurrent state;
5. respect the immutable time horizon;
6. close the position through the production TIME path;
7. survive another process restart;
8. replay the exact close idempotently without creating a second closed trade;
9. expose valid cycle health after retry; and
10. produce a self-fingerprinted acceptance receipt.

The two earlier 2026-09-22 failed runs remain useful fail-closed incident evidence but
are not accepted runs. Their chronology defects were repaired without weakening the
production RESERVE evidence or recurrent-cycle invariants.

## Authority boundary

This acceptance is an operational product/runtime proof only. It is not strategy
evidence and does not validate or promote any strategy, selector, signal, family,
portfolio rule or option construct.

Across the accepted run:

- provider reads: exactly 3 explicit quote captures;
- provider writes: 0;
- broker reads: 0;
- broker writes: 0;
- order creation authority: false;
- PAPER authority: false;
- LIVE authority: false;
- promotion authority: false; and
- confluence authority: false.

Closing this gate does not itself authorize PAPER or LIVE trading. Any later trading
authority must remain a separately frozen and explicitly accepted package.
