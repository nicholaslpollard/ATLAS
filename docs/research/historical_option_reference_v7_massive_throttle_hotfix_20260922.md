# Historical Option Reference V7 Massive throttle coordination hotfix — 2026-09-22

## Observed target-workstation failure

The first accepted V7 workstation run correctly classified 212 monthly partitions as:

- 0 verified V7 reusable;
- 63 verified V6 raw reusable;
- 149 provider pending;
- 5 partition workers.

All 63 verified V6 raw partitions were successfully re-normalized under V7 and emitted
durable V7 receipts before the provider-pending phase. The provider phase then entered
Massive historical exact-match resolution from multiple worker threads. V7's private
`urllib` request path did not consume the already-configured
`massive.reference.requests_per_minute=5` budget.

The result was an HTTP 429 from Massive:

`You've exceeded the maximum requests per minute`

The failing request was not a source-semantic rejection. It occurred while resolving a
historical target row during provider acquisition. After the first worker exception,
`_run_bounded()` cancelled pending futures but waited synchronously for already-running
workers. Those workers could still be inside independent request/retry sleeps, so the CLI
appeared frozen until manually interrupted during `ThreadPoolExecutor.shutdown(wait=True)`.

This incident changes no option-reference scientific interpretation and does not modify
the V7 contract/resolver policy.

## Root cause

ATLAS already freezes Massive reference traffic at five request starts per minute in
`config/massive.yaml`, equivalent to approximately 12 seconds between starts.

The shared production Massive REST client honors that budget. Historical Option
Reference V7 inherited a separate direct-`urllib` request implementation from the
earlier option-reference acquisition versions. That implementation retried 429/5xx
responses but had no cross-worker request pacer. Five partition workers could therefore
burst requests against one account and defeat the configured provider budget.

The defect is transport/concurrency coordination, not data quality.

## Hotfix

The V7 request path now creates one shared request coordinator for the entire acquisition
run. Every V7 request—boundary probes, known-conflict probes, historical exact-match
resolution, Contract Overview calls and provider partition pagination—uses the same
account-level request budget.

The coordinator:

- reads the existing `massive.reference.requests_per_minute` setting;
- serializes request starts across all worker threads;
- at five requests/minute enforces about 12 seconds between starts;
- applies provider-wide cooldown after HTTP 429;
- honors `Retry-After` when supplied;
- uses a complete 60-second cooldown when a 429 supplies no `Retry-After`;
- retains the existing bounded retry count;
- allows peer workers to wake from pacing/backoff immediately after a fatal worker
  failure.

No source-policy threshold or resolver branch is changed.

## Clean resumability

A fatal provider/acquisition error now triggers coordinated cancellation before executor
shutdown. Queued work is cancelled; workers waiting in pacing/backoff wake immediately;
a worker already inside `urlopen` remains bounded by the configured request timeout.

The CLI catches expected V7 acquisition errors and prints:

`HISTORICAL OPTION REFERENCE V7: STOPPED_RESUMABLE`

with the concise reason and a statement that completed partition receipts remain
reusable. A manual interrupt similarly prints
`INTERRUPTED_RESUMABLE`.

V7 continues to use receipt-first restart semantics. The 63 completed V7 local rebuilds
from the first run therefore do not need to be rebuilt. Any provider partition that
managed to atomically finish a V7 receipt before the peer failure is also reusable on
restart.

## Visibility

Provider acquisition now prints an explicit phase transition containing:

- provider-pending partition count;
- worker count;
- shared Massive requests/minute budget;
- approximate interval between request starts.

While no monthly partition completes, a one-minute heartbeat reports:

- completed provider partitions;
- active/in-flight partitions;
- total request starts;
- observed throttle events.

This prevents a healthy rate-limited acquisition from looking hung merely because one
monthly partition takes a long time to finish.

## Authority boundary

This is an operational reliability correction only. Historical Option Reference V7
scientific/source semantics remain frozen exactly as accepted in PR #205.

No historical candidate-availability, dynamic-deliverable, price, strategy, predictor,
PAPER or LIVE authority is created. The Strategy Evidence Register remains unchanged.
