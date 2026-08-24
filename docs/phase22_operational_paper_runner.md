# Phase 22 — Operational Webull-primary PAPER Runner

**Status: IMPLEMENTED / VALIDATION IN PROGRESS**

Phase 22 turns the already accepted Phase15 execution stack and Phase21 unified PAPER-submit authority into one routine operator entrypoint. It does not add a new trading strategy, broker adapter, quote source, order-builder path, mutation seam, browser authority, scheduler authority, or LIVE capability.

## Purpose

Before Phase22, ATLAS had all required safe primitives for broker-neutral SHADOW/PAPER execution, real Webull sandbox lifecycle evidence, immutable execution outcomes, read-only outcome observability, and centralized run-scoped PAPER provider-submit authority. The remaining operational gap was that no routine operator command bound those primitives together. `run_phase15_closeout.py` is an acceptance/closeout command and Phase18's runner is intentionally certification-only.

Phase22 closes only that operational binding gap.

## Policy

Contract:

`phase22-policy-v1-operational-paper-runner-webull-primary-explicit-run-authority`

The deterministic fingerprint is emitted by `scripts/validate_phase22.py` and is recorded as acceptance evidence only after exact-head CI is green.

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

Command:

`python scripts/run_phase22_paper.py prepare [--broker webull|alpaca] [--as-of YYYY-MM-DD]`

The prepare operation:

1. loads normal ATLAS settings;
2. resolves accepted Phase15 input only;
3. defaults the selected PAPER broker to Webull;
4. if accepted execution-case count is zero, returns a no-authority/no-provider-operation preparation;
5. otherwise derives the exact Phase21 broker/PAPER/run-scoped challenge;
6. performs no provider mutation and does not execute a trade.

Command:

`python scripts/run_phase22_paper.py execute [--broker webull|alpaca] [--as-of YYYY-MM-DD]`

The execute operation repeats preparation, displays the deterministic Phase21 scope and required confirmation, and—only when accepted execution cases exist—requires the operator to type the exact confirmation interactively on standard input. There is deliberately no `--confirmation` command-line option so routine authorization evidence is not encouraged into shell history.

After exact authority validation, Phase22 delegates to `Phase15ExecutionRunEngine.run(...)` with a hard-bound PAPER environment and selected broker. Phase15 re-resolves accepted evidence and independently revalidates the Phase21 authority before live quote/provider initialization. If accepted input changes between preparation and execution, stale authority therefore fails closed before provider reads/submission.

## Zero-case behavior

Zero accepted Phase14 execution cases are a valid operational state. In that state:

- no Phase21 mutation authority is requested;
- a supplied confirmation is rejected as unnecessary;
- Phase15 preserves its established zero-case behavior;
- quote source and broker initialization remain skipped;
- no provider submission occurs.

No thresholds are weakened and no trade is manufactured to make the runner do work.

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
- broker credentials or raw broker account/order identifiers.

## Validation contract

`scripts/validate_phase22.py` independently verifies at minimum:

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
- replace Phase18 certification evidence.

## Acceptance boundary

Repository implementation/CI validation must perform zero real provider writes. A routine real Webull PAPER run is a separate target-machine operational evidence step and is required only when accepted upstream evidence actually contains one or more executable cases. The absence of an accepted execution case is a valid no-op and must not be bypassed merely to demonstrate a mutation.
