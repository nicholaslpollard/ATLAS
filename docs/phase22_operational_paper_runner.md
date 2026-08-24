# Phase 22 — Operational Webull-primary PAPER Runner

**Status: ACCEPTED / MERGED**

Phase22 turns the accepted Phase15 execution stack and Phase21 unified PAPER-submit authority into one routine operator entrypoint. It does not add a new trading strategy, broker adapter, quote source, order-builder path, mutation seam, browser authority, scheduler authority, or LIVE capability.

Accepted implementation head: `68f16256c8f9976ae5b6283dde437e93fbe70155`.

Accepted merge: `15c0a997ec847764e41fbd525ff52aa8c58f96ac`.

## Purpose

Before Phase22, ATLAS had the safe primitives for broker-neutral SHADOW/PAPER execution, accepted real Webull sandbox lifecycle evidence, immutable execution outcomes, read-only outcome observability, and centralized run-scoped PAPER provider-submit authority. The remaining operational gap was that no routine operator command bound those primitives together. `run_phase15_closeout.py` is an acceptance/closeout command and Phase18's runner is intentionally certification-only.

Phase22 closes only that operator-binding gap.

## Policy

Contract:

`phase22-policy-v1-operational-paper-runner-webull-primary-explicit-run-authority`

Accepted deterministic fingerprint:

`1866f132831c5cab4436163ddae6f67a7cc4768fb6dfe444e826567a6946f577`

Locked rules:

- environment is PAPER/SANDBOX only;
- Webull is the default and primary broker;
- Alpaca is available only by explicit manual selection;
- LIVE remains disabled;
- automatic cross-broker failover remains disabled;
- browser execution authority remains disabled;
- scheduler execution authority remains disabled;
- Phase20 external mutation-stage registration remains disabled;
- arbitrary ticker, quantity, price, geometry, or case-file input is not accepted;
- accepted Phase13/14 evidence resolved through the existing Phase15 input boundary is the only trade-case source;
- every new PAPER provider submit still crosses the Phase21 centralized authority seam;
- exactly one raw `adapter.submit(plan)` remains under `packages/`, in `packages/execution/engine.py`;
- provider uncertainty stops without blind retry or automatic failover and requires deterministic-id reconciliation.

## Operator flow

Prepare command:

`python scripts/run_phase22_paper.py prepare [--broker webull|alpaca] [--as-of YYYY-MM-DD]`

The prepare operation:

1. loads normal ATLAS settings;
2. resolves accepted Phase15 input only;
3. defaults the selected PAPER broker to Webull;
4. if accepted execution-case count is zero, returns a no-authority/no-provider-operation preparation;
5. otherwise derives the exact Phase21 broker/PAPER/run-scoped challenge;
6. performs no provider mutation and does not execute a trade.

Execute command:

`python scripts/run_phase22_paper.py execute [--broker webull|alpaca] [--as-of YYYY-MM-DD]`

The execute operation repeats preparation, displays the deterministic Phase21 scope and required confirmation, and—only when accepted execution cases exist—requires the operator to type the exact confirmation interactively on standard input. There is deliberately no `--confirmation` command-line option so routine authorization evidence is not encouraged into shell history.

After exact authority validation, Phase22 delegates to `Phase15ExecutionRunEngine.run(...)` with a hard-bound PAPER environment and selected broker. Phase15 re-resolves accepted evidence and independently revalidates the Phase21 authority before live quote/provider initialization. If accepted input changes between preparation and execution, stale authority therefore fails closed before provider reads/submission.

## Zero-case behavior

Zero accepted execution cases are a valid operational state. In that state:

- no Phase21 mutation authority is requested;
- a supplied confirmation is rejected as unnecessary;
- Phase15 preserves its established zero-case behavior;
- quote source and broker initialization remain skipped;
- no provider submission occurs.

No strategy support threshold, promotion rule, deterministic case, or trade input may be weakened or fabricated to make the runner do work.

## Outcome and observability continuity

Phase22 does not create another outcome store. Phase15 continues to own immutable content-addressed execution outcome artifacts under its accepted execution evidence root. Phase19 already reads those outcome artifacts locally and read-only for the operations dashboard. This keeps execution evidence and observability on the accepted path rather than creating Phase22-specific parallel state.

## Security and authority boundary

`packages/execution/phase22_operator.py` owns coordination only. It does not instantiate Webull/Alpaca adapters, instantiate the live quote resolver, build arbitrary order plans, or call `adapter.submit`.

The command surface exposes only:

- `prepare` or `execute`;
- explicit broker selection, default Webull;
- optional accepted as-of date.

It does not expose:

- ticker;
- quantity;
- entry/limit price;
- stop/target geometry;
- LIVE environment;
- automatic failover;
- browser or scheduler execution authority;
- command-line mutation confirmation;
- broker credentials or raw broker account/order identifiers.

## Validation contract

`scripts/validate_phase22.py` independently verifies:

- deterministic Phase22 policy fingerprint;
- Webull remains default/primary;
- PAPER-only operation;
- LIVE/failover/browser/scheduler/arbitrary-case authority remain false;
- Phase20 external mutation stages remain disabled;
- Phase22 delegates to Phase15 and composes Phase21 authority;
- Phase22 directly instantiates no broker adapter or quote provider;
- CLI exposes no ticker/quantity/price/confirmation argument;
- interactive confirmation exists for nonzero execute;
- exactly one raw `adapter.submit(plan)` remains in `packages/execution/engine.py`;
- control-plane modules do not import the Phase22 operator;
- validator itself performs zero provider calls/writes.

Focused tests cover provider-free preparation, zero-case operation, exact Webull/Alpaca authority delegation, wrong-confirmation fail-closed behavior, uncertainty stop behavior, and public metadata redaction.

## Cross-platform acceptance evidence

GitHub Actions run `32787337500` completed successfully on the Phase22 PR merge ref:

- Ubuntu: **974 passed in 13.80s**;
- Windows: **974 passed in 33.93s**;
- every validator through Phase22 PASS;
- dependency lock PASS;
- secret hygiene PASS;
- ATLAS Doctor PASS;
- provider-free feature self-test PASS with exact feature parity;
- compile and browser JavaScript syntax checks PASS;
- Phase22 policy fingerprint reproduced exactly as `1866f132831c5cab4436163ddae6f67a7cc4768fb6dfe444e826567a6946f577`;
- `default_broker=webull`;
- `environment=paper`;
- `confirmation_transport=interactive_stdin`;
- `arbitrary_case_input=false`;
- `live_execution=false`;
- `automatic_broker_failover=false`;
- `browser_execution=false`;
- `scheduler_execution=false`;
- `raw_adapter_submit_count=1`;
- provider calls/writes/broker writes `0 / 0 / 0`.

## Target-machine acceptance evidence

On 2026-08-24 the target Windows machine ran:

`python scripts/run_phase22_paper.py prepare --broker webull`

Observed result:

- Phase22 fingerprint: `1866f132831c5cab4436163ddae6f67a7cc4768fb6dfe444e826567a6946f577`;
- accepted as-of date: `2026-08-14`;
- selected broker: `webull`;
- environment: PAPER/SANDBOX ONLY;
- Webull primary: YES;
- Alpaca selection: MANUAL ONLY;
- LIVE: DISABLED;
- automatic cross-broker failover: DISABLED;
- browser execution authority: DISABLED;
- scheduler execution authority: DISABLED;
- accepted execution cases: **0**;
- explicit run authority required: **False**;
- disposition: `PREPARED_ZERO_PROVIDER_CALLS`.

This is the expected and accepted target-machine result for the current accepted lineage. Phase11 has zero `SUPPORTED` strategies, so accepted downstream Phase12/13/14/15 evidence contains no executable trade case. Phase22 correctly refuses to request mutation authority or initialize provider work simply to demonstrate activity.

A real routine Webull PAPER submit is deferred until a future accepted upstream analytical run naturally produces one or more executable cases. No `execute` call, fabricated case, arbitrary ticker, or repeated Phase18 certification mutation is required merely for Phase22 closeout.

## Acceptance meaning

The accepted current-population path is:

`accepted Phase13/14 -> Phase15 input resolver -> Phase22 prepare -> zero cases -> no Phase21 mutation authority -> zero provider calls`

Nonzero operator behavior is covered by focused tests/fake-provider semantics, the centralized accepted Phase21 authority contract, and the accepted Phase18 real Webull sandbox mutation/reconciliation lifecycle. Phase22 adds no provider-submit path of its own.

Phase22 is therefore **ACCEPTED / MERGED** at `15c0a997ec847764e41fbd525ff52aa8c58f96ac`.

The implementation merge occurred before this target-machine/living-document closeout was recorded. `maintenance/post-phase22-closeout` documents and repairs that procedural sequencing drift without changing code or authority.

## Non-goals

Phase22 does not:

- promote LIVE trading;
- prove profitability;
- authorize automatic broker failover;
- add automatic scheduling/daemon execution;
- promote PostgreSQL as a runtime prerequisite;
- place broker mutation stages inside Phase20;
- give the browser the ability to acquire execution authority;
- modify accepted ML/strategy/regime/risk/AI decisions;
- bypass Phase21 or Phase15;
- replace or repeat Phase18 certification evidence;
- manufacture nonzero execution cases.

## Next boundary

After the post-Phase22 documentation maintenance is CI-green and merged, audit the actual merged current-data/analysis path before defining Phase23. The next phase should close the smallest evidenced operational gap toward routine current end-to-end analysis feeding Phase22, not automatically jump to scheduler or PostgreSQL infrastructure.